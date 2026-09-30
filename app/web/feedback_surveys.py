"""Employee-scoped colleague feedback surveys."""

import logging
from io import BytesIO

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_session
from ..messaging import create_telegram_messenger
from ..messaging.identity import get_primary_chat_id
from ..models import (
    Employee,
    EmployeeFeedbackRecipient,
    EmployeeFeedbackRun,
    FlowStepTemplate,
    ScenarioProgress,
    ScenarioTemplate,
    SurveyAnswer,
)
from ..scenario_engine import get_first_step, get_waiting_progress, matches_role_scope, start_scenario
from ..time_utils import utc_now
from .support import require_api_auth

router = APIRouter()
logger = logging.getLogger(__name__)


def _excel_text(value: str | None) -> str:
    text_value = value or ""
    return f"'{text_value}" if text_value.lstrip().startswith(("=", "+", "-", "@")) else text_value


def get_db():
    with get_session() as db:
        yield db


def _subject(db: Session, employee_id: int) -> Employee:
    employee = db.get(Employee, employee_id)
    if employee is None or employee.employee_stage == "candidate":
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    return employee


def _finish_failed_start(db: Session, employee_id: int, scenario_key: str, run_id: int) -> None:
    progress = db.query(ScenarioProgress).filter_by(employee_id=employee_id, scenario_key=scenario_key).first()
    if progress and progress.feedback_run_id == run_id:
        progress.waiting_for_response = False
        progress.is_completed = True
        progress.completed_at = utc_now()
        progress.last_delivery_error = progress.last_delivery_error or "Не удалось отправить опрос."


def _feedback_payload(db: Session, subject: Employee) -> dict:
    surveys = (
        db.query(ScenarioTemplate)
        .filter(ScenarioTemplate.scenario_kind == "survey", ScenarioTemplate.recipient_mode == "self")
        .order_by(ScenarioTemplate.title, ScenarioTemplate.id)
        .all()
    )
    recipients = (
        db.query(Employee)
        .filter(Employee.id != subject.id, Employee.employee_stage != "candidate")
        .order_by(Employee.full_name, Employee.id)
        .all()
    )
    runs = (
        db.query(EmployeeFeedbackRun)
        .filter_by(subject_employee_id=subject.id)
        .order_by(EmployeeFeedbackRun.created_at.desc(), EmployeeFeedbackRun.id.desc())
        .all()
    )
    run_ids = [run.id for run in runs]
    recipient_rows = (
        db.query(EmployeeFeedbackRecipient).filter(EmployeeFeedbackRecipient.run_id.in_(run_ids)).all()
        if run_ids else []
    )
    answer_count = (
        db.query(SurveyAnswer).filter(SurveyAnswer.feedback_run_id.in_(run_ids)).count()
        if run_ids else 0
    )
    scenario_titles = {survey.scenario_key: survey.title for survey in surveys}
    return {
        "surveys": [
            {
                "key": item.scenario_key,
                "title": item.title,
                "eligible_recipient_ids": [employee.id for employee in recipients if matches_role_scope(employee, item)],
            }
            for item in surveys if get_first_step(db, item.scenario_key)
        ],
        "recipients": [
            {
                "id": item.id,
                "full_name": item.full_name or f"Сотрудник #{item.id}",
                "position": item.desired_position or "",
                "available": bool(get_primary_chat_id(item, db=db)) and not item.is_bot_blocked,
            }
            for item in recipients
        ],
        "runs": [
            {
                "id": run.id,
                "title": run.scenario_title or scenario_titles.get(run.scenario_key, run.scenario_key),
                "created_at": run.created_at.isoformat(),
                "recipient_count": sum(row.run_id == run.id for row in recipient_rows),
                "completed_count": sum(row.run_id == run.id and row.delivery_status == "completed" for row in recipient_rows),
                "failed_count": sum(row.run_id == run.id and row.delivery_status == "failed" for row in recipient_rows),
            }
            for run in runs
        ],
        "answer_count": answer_count,
        "download_url": f"/api/employees/{subject.id}/feedback-surveys/export" if answer_count else None,
    }


@router.get("/api/employees/{employee_id}/feedback-surveys")
def feedback_surveys_api(request: Request, employee_id: int, db: Session = Depends(get_db)):
    require_api_auth(request)
    return _feedback_payload(db, _subject(db, employee_id))


@router.post("/api/employees/{employee_id}/feedback-surveys")
async def launch_feedback_survey_api(
    request: Request,
    employee_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    require_api_auth(request)
    subject = _subject(db, employee_id)
    scenario_key = str(payload.get("scenario_key") or "").strip()
    survey = db.query(ScenarioTemplate).filter_by(scenario_key=scenario_key, scenario_kind="survey").first()
    if not survey or not get_first_step(db, scenario_key) or survey.recipient_mode != "self":
        raise HTTPException(status_code=400, detail="Выберите опрос, который отправляется самому отвечающему.")
    raw_ids = payload.get("recipient_employee_ids")
    if not isinstance(raw_ids, list) or not raw_ids or len(raw_ids) > 100:
        raise HTTPException(status_code=400, detail="Выберите от 1 до 100 сотрудников для опроса.")
    try:
        recipient_ids = list(dict.fromkeys(int(value) for value in raw_ids))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Некорректный список сотрудников.") from None
    if any(value <= 0 or value == subject.id for value in recipient_ids):
        raise HTTPException(status_code=400, detail="Нельзя отправить опрос сотруднику о самом себе.")
    recipients = db.query(Employee).filter(Employee.id.in_(recipient_ids)).all()
    if len(recipients) != len(recipient_ids) or any(
        item.employee_stage == "candidate"
        or item.is_bot_blocked
        or not get_primary_chat_id(item, db=db)
        or not matches_role_scope(item, survey)
        for item in recipients
    ):
        raise HTTPException(status_code=400, detail="Некоторые сотрудники недоступны для этого опроса или не привязаны к боту.")
    active_progress = db.query(ScenarioProgress).filter(
        ScenarioProgress.employee_id.in_(recipient_ids),
        ScenarioProgress.is_completed.is_(False),
    ).first()
    if active_progress or any(get_waiting_progress(db, item.id) is not None for item in recipients):
        raise HTTPException(status_code=409, detail="У одного из выбранных сотрудников уже есть незавершённый сценарий.")
    if not settings.TELEGRAM_BOT_TOKEN:
        raise HTTPException(status_code=400, detail="Не задан токен Telegram-бота.")

    run = EmployeeFeedbackRun(subject_employee_id=subject.id, scenario_key=scenario_key, scenario_title=survey.title, created_at=utc_now())
    db.add(run)
    db.flush()
    for recipient_id in recipient_ids:
        db.add(EmployeeFeedbackRecipient(run_id=run.id, respondent_employee_id=recipient_id, delivery_status="pending"))
    db.commit()

    messenger = create_telegram_messenger(settings.TELEGRAM_BOT_TOKEN)
    try:
        for recipient in recipients:
            row = db.query(EmployeeFeedbackRecipient).filter_by(run_id=run.id, respondent_employee_id=recipient.id).one()
            try:
                started = await start_scenario(
                    messenger, db, recipient, scenario_key, feedback_run_id=run.id,
                )
                if row.delivery_status != "completed":
                    row.delivery_status = "sent" if started else "failed"
                if not started:
                    _finish_failed_start(db, recipient.id, scenario_key, run.id)
            except Exception:
                logger.exception("Feedback survey delivery failed for run=%s recipient=%s", run.id, recipient.id)
                db.rollback()
                row = db.query(EmployeeFeedbackRecipient).filter_by(run_id=run.id, respondent_employee_id=recipient.id).one()
                row.delivery_status = "failed"
                _finish_failed_start(db, recipient.id, scenario_key, run.id)
            db.commit()
    finally:
        await messenger.close()
    return _feedback_payload(db, subject)


@router.get("/api/employees/{employee_id}/feedback-surveys/export")
def export_feedback_survey_api(request: Request, employee_id: int, db: Session = Depends(get_db)):
    require_api_auth(request)
    subject = _subject(db, employee_id)
    runs = db.query(EmployeeFeedbackRun).filter_by(subject_employee_id=subject.id).all()
    run_ids = [run.id for run in runs]
    if not run_ids:
        raise HTTPException(status_code=404, detail="Ответов обратной связи пока нет.")
    answers = (
        db.query(SurveyAnswer)
        .filter(SurveyAnswer.feedback_run_id.in_(run_ids))
        .order_by(SurveyAnswer.answered_at, SurveyAnswer.id)
        .all()
    )
    if not answers:
        raise HTTPException(status_code=404, detail="Ответов обратной связи пока нет.")
    runs_by_id = {run.id: run for run in runs}
    scenarios = {row.scenario_key: row.title for row in db.query(ScenarioTemplate).filter(ScenarioTemplate.scenario_kind == "survey").all()}
    steps = {(row.flow_key, row.step_key): (row.custom_text if row.custom_text is not None else row.default_text or row.step_title) for row in db.query(FlowStepTemplate).all()}
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Обратная связь"
    sheet.append(["Дата запуска", "Опрос", "ФИО отвечавшего", "Вопрос", "Ответ", "Дата ответа"])
    for answer in answers:
        run = runs_by_id[answer.feedback_run_id]
        respondent = db.get(Employee, answer.employee_id)
        sheet.append([
            run.created_at.strftime("%d.%m.%Y %H:%M"),
            _excel_text(run.scenario_title or scenarios.get(run.scenario_key, run.scenario_key)),
            _excel_text(answer.respondent_name or (respondent.full_name if respondent else f"Сотрудник #{answer.employee_id}")),
            _excel_text(answer.question_text or steps.get((run.scenario_key, answer.step_key), answer.step_key)),
            _excel_text(answer.file_name or answer.answer_value),
            answer.answered_at.strftime("%d.%m.%Y %H:%M"),
        ])
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="feedback_employee_{subject.id}.xlsx"'},
    )
