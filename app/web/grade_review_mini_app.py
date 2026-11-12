import hashlib
import json
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

from ..config import settings
from ..database import get_session
from ..messaging.identity import find_employees_by_channel_user_id, get_primary_chat_id
from ..models import Employee, EmployeeFeedbackRecipient, GradeReviewCollection, SurveyAnswer
from ..staff_email_verification import is_verified, verification_required
from ..time_utils import utc_now
from .employee_cabinet import PRIVATE_HEADERS, signed_telegram_id
from .grades import _lock_employee

router = APIRouter(prefix="/grade-review", include_in_schema=False)


def denied():
    return HTTPException(403, "Этот опрос недоступен.", headers=PRIVATE_HEADERS)


def context(db, request, collection_id, *, write=False):
    chat_id = signed_telegram_id(request.headers.get("X-Telegram-Init-Data"), settings.TELEGRAM_BOT_TOKEN, time.time(), max_age=7200)
    if not chat_id:
        raise denied()
    matches = find_employees_by_channel_user_id(db, channel="telegram", external_user_id=chat_id)
    if len(matches) != 1:
        raise denied()
    reviewer = matches[0]
    if (reviewer.employee_stage not in {"staff", "adaptation", "ipr"} or reviewer.is_bot_blocked
            or get_primary_chat_id(reviewer, db=db) != chat_id
            or (verification_required(reviewer) and not is_verified(db, reviewer, chat_id))):
        raise denied()
    collection = db.get(GradeReviewCollection, collection_id)
    if not collection:
        raise denied()
    snapshot = json.loads(collection.snapshot_json)
    if snapshot.get("delivery") != "mini_app":
        raise denied()
    recipient = db.query(EmployeeFeedbackRecipient).filter_by(
        run_id=collection.feedback_run_id, respondent_employee_id=reviewer.id,
    ).one_or_none()
    if not recipient or recipient.delivery_status not in {"sent", "completed"}:
        raise denied()
    if write:
        # Serialize respondent edits with HR finalization.
        _lock_employee(db, collection.employee_id)
        db.refresh(collection)
        db.refresh(recipient)
        if collection.status != "open" or recipient.delivery_status not in {"sent", "completed"}:
            raise HTTPException(409, "Редактирование закрыто.", headers=PRIVATE_HEADERS)
    subject = db.get(Employee, collection.employee_id)
    if not subject:
        raise denied()
    return reviewer, collection, recipient, snapshot, subject


def questions(snapshot):
    for item in snapshot["scores"]:
        rubric = item.get("rubric")
        levels = rubric["levels"] if rubric else {
            "0": "Нет", "1": "Понимание", "2": "Умение", "3": "Экспертиза", "4": "Лидерство",
        }
        yield {"key": f"skill_{item['skillId']}", "title": item["skillName"], "group": item["categoryName"],
               "options": dict(sorted(levels.items())), "skip": rubric["na"] if rubric else "Не могу оценить"}
    for i, title in enumerate(snapshot.get("open_questions", [])):
        yield {"key": f"open_{i}", "title": title}


def answer_rows(db, reviewer, collection):
    return db.query(SurveyAnswer).filter_by(
        employee_id=reviewer.id, scenario_key=collection.scenario_key, feedback_run_id=collection.feedback_run_id,
    )


def revision(values):
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()


@router.get("/{collection_id}")
def page(collection_id: int):
    return FileResponse(Path(__file__).resolve().parents[1] / "static" / "grade-review.html", headers=PRIVATE_HEADERS)


@router.get("/{collection_id}/answers")
def get_answers(collection_id: int, request: Request):
    with get_session() as db:
        reviewer, collection, recipient, snapshot, subject = context(db, request, collection_id)
        values = {row.step_key: row.answer_value for row in answer_rows(db, reviewer, collection).order_by(SurveyAnswer.id)}
        return JSONResponse(dict(subject=subject.full_name, questions=list(questions(snapshot)), answers=values,
                                 revision=revision(values), completed=recipient.delivery_status == "completed",
                                 editable=collection.status == "open"), headers=PRIVATE_HEADERS)


@router.put("/{collection_id}/answers")
def save_answers(collection_id: int, request: Request, payload: dict):
    with get_session() as db:
        reviewer, collection, recipient, snapshot, _ = context(db, request, collection_id, write=True)
        items = {item["key"]: item for item in questions(snapshot)}
        values = payload.get("answers")
        if not isinstance(values, dict) or values.keys() != items.keys():
            raise HTTPException(422, "Ответь на каждый вопрос или пропусти его явно.", headers=PRIVATE_HEADERS)
        for key, value in values.items():
            item = items[key]
            if value is not None and (not isinstance(value, str) or len(value) > 4096
                                      or ("options" in item and value not in item["options"])):
                raise HTTPException(422, "Недопустимый ответ.", headers=PRIVATE_HEADERS)
        rows = answer_rows(db, reviewer, collection)
        existing = {row.step_key: row for row in rows.order_by(SurveyAnswer.id)}
        previous = {key: row.answer_value for key, row in existing.items()}
        if revision(previous) != payload.get("revision") and values != previous:
            raise HTTPException(409, "Ответы изменились. Открой опрос заново.", headers=PRIVATE_HEADERS)
        for key, value in values.items():
            row = existing.get(key)
            if row is None:
                row = SurveyAnswer(employee_id=reviewer.id, scenario_key=collection.scenario_key, step_key=key,
                                   feedback_run_id=collection.feedback_run_id, respondent_name=reviewer.full_name,
                                   question_text=items[key]["title"])
                db.add(row)
            elif row.answer_value == value:
                continue
            row.answer_value = value
            row.answered_at = utc_now()
        recipient.delivery_status = "completed"
        db.commit()
        return JSONResponse({"revision": revision(values)}, headers=PRIVATE_HEADERS)
