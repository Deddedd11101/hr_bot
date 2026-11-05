"""Employee-scoped visibility and guarded interruption of scenario runtime."""

from datetime import datetime, timedelta

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from sqlalchemy import or_, update
from sqlalchemy.orm import Session

from ..database import get_session
from ..models import (Employee, EmployeeAdaptationPlanItem, EmployeeFeedbackRecipient,
                      FlowLaunchRequest, OnboardingEvent, ScenarioAnswerRun,
                      ScenarioProgress, ScenarioTemplate)
from ..scenario_engine import (get_conflicting_progress_for_survey_launch,
                               resolve_scenario_recipient)
from ..time_utils import utc_now
from .support import require_api_admin, require_api_auth

router = APIRouter()


def get_db():
    with get_session() as db:
        yield db


def _employee(db, employee_id):
    person = db.get(Employee, employee_id)
    if person is None:
        raise HTTPException(404, "Карточка не найдена")
    return person


def _title(db, key):
    scenario = db.query(ScenarioTemplate).filter_by(scenario_key=key).first()
    return scenario.title if scenario else "Удалённый сценарий"


def _progress_row(db, progress):
    recipient_id = progress.recipient_employee_id or progress.employee_id
    recipient = db.get(Employee, recipient_id)
    return {"id": progress.id, "title": _title(db, progress.scenario_key),
            "employee_id": progress.employee_id, "recipient_id": recipient_id,
            "recipient_name": recipient.full_name if recipient else "Адресат недоступен",
            "updated_at": progress.updated_at.isoformat(),
            "started_at": progress.started_at.isoformat(),
            "waiting": progress.waiting_for_response,
            "long_wait": progress.updated_at < utc_now() - timedelta(days=1)}


def snapshot(db, employee_id):
    _employee(db, employee_id)
    active = db.query(ScenarioProgress).filter(
        or_(ScenarioProgress.employee_id == employee_id, ScenarioProgress.recipient_employee_id == employee_id),
        ScenarioProgress.is_completed.is_(False), ScenarioProgress.interrupted_at.is_(None),
    ).order_by(ScenarioProgress.started_at, ScenarioProgress.id).all()
    requests = db.query(FlowLaunchRequest).filter_by(employee_id=employee_id, processed_at=None).order_by(
        FlowLaunchRequest.requested_at, FlowLaunchRequest.id).all()
    pending = []
    person = db.get(Employee, employee_id)
    for row in requests:
        scenario = db.query(ScenarioTemplate).filter_by(scenario_key=row.flow_key).first()
        recipient = resolve_scenario_recipient(db, person, scenario, requires_response=True) if scenario else None
        busy = get_conflicting_progress_for_survey_launch(db, recipient.employee_id, row.flow_key) if recipient and recipient.employee_id else None
        pending.append({"id": row.id, "title": _title(db, row.flow_key),
                        "source": row.launch_type, "requested_at": row.requested_at.isoformat(),
                        "blocker": _progress_row(db, busy) if busy else None,
                        "can_cancel": row.skip_step_key is None})
    return {"active": [_progress_row(db, row) for row in active], "pending": pending,
            "timezone_note": "Время диалогов — UTC; время плановых запусков — часовой пояс приложения"}


@router.get("/api/employees/{employee_id}/scenario-queue")
def queue_api(request: Request, employee_id: int, db: Session = Depends(get_db)):
    user = require_api_auth(request)
    return {**snapshot(db, employee_id), "can_manage": user.role == "admin"}


def _expected(payload):
    try:
        value = datetime.fromisoformat(payload["expected_at"])
        if value.tzinfo is not None:
            raise ValueError()
        return value
    except (KeyError, ValueError, TypeError):
        raise HTTPException(422, "Обновите состояние очереди")


def _event(db, employee_id, message):
    now = utc_now()
    db.add(OnboardingEvent(employee_id=employee_id, event_key="scenario_queue_action",
                           scheduled_at=now, sent_at=now, message=message))


@router.post("/api/employees/{employee_id}/scenario-queue/requests/{request_id}/cancel")
def cancel_request(request: Request, employee_id: int, request_id: int,
                   payload: dict = Body(...), db: Session = Depends(get_db)):
    user = require_api_admin(request)
    _employee(db, employee_id)
    expected = _expected(payload)
    changed = db.execute(update(FlowLaunchRequest).where(
        FlowLaunchRequest.id == request_id, FlowLaunchRequest.employee_id == employee_id,
        FlowLaunchRequest.processed_at.is_(None), FlowLaunchRequest.requested_at == expected,
        FlowLaunchRequest.skip_step_key.is_(None),
    ).values(processed_at=utc_now()))
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Запуск уже изменён или обрабатывается. Обновите очередь.")
    db.query(EmployeeAdaptationPlanItem).filter_by(launch_request_id=request_id).filter(
        EmployeeAdaptationPlanItem.status.in_(["planned", "blocked"])).update(
            {EmployeeAdaptationPlanItem.status: "cancelled"}, synchronize_session=False)
    _event(db, employee_id, f"Администратор {user.id}: отменён запрос сценария #{request_id}. Отправка не выполнялась.")
    db.commit()
    return queue_api(request, employee_id, db)


@router.post("/api/employees/{employee_id}/scenario-queue/progress/{progress_id}/interrupt")
def interrupt_progress(request: Request, employee_id: int, progress_id: int,
                       payload: dict = Body(...), db: Session = Depends(get_db)):
    user = require_api_admin(request)
    _employee(db, employee_id)
    expected = _expected(payload)
    now = utc_now()
    # A waiting dialog is not in a send/claim state. Never interrupt uncertain delivery.
    changed = db.execute(update(ScenarioProgress).where(
        ScenarioProgress.id == progress_id,
        or_(ScenarioProgress.employee_id == employee_id, ScenarioProgress.recipient_employee_id == employee_id),
        ScenarioProgress.updated_at == expected, ScenarioProgress.is_completed.is_(False),
        ScenarioProgress.waiting_for_response.is_(True), ScenarioProgress.interrupted_at.is_(None),
    ).values(interrupted_at=now, waiting_for_response=False, is_completed=True,
             completed_at=now, updated_at=now, pending_confirmation_value=None,
             pending_confirmation_option_index=None, pending_confirmation_message_id=None))
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Диалог изменился или находится в доставке. Обновите очередь.")
    progress = db.get(ScenarioProgress, progress_id, populate_existing=True)
    if progress.answer_run_id:
        db.query(ScenarioAnswerRun).filter_by(id=progress.answer_run_id, status="in_progress").update(
            {ScenarioAnswerRun.status: "interrupted"}, synchronize_session=False)
    if progress.adaptation_plan_item_id:
        db.query(EmployeeAdaptationPlanItem).filter_by(id=progress.adaptation_plan_item_id).update(
            {EmployeeAdaptationPlanItem.status: "interrupted"}, synchronize_session=False)
    if progress.feedback_run_id:
        db.query(EmployeeFeedbackRecipient).filter_by(run_id=progress.feedback_run_id,
            respondent_employee_id=progress.employee_id, delivery_status="sent").update(
                {EmployeeFeedbackRecipient.delivery_status: "unavailable"}, synchronize_session=False)
    # Drop continuations only; independent future reruns remain scheduled.
    db.query(FlowLaunchRequest).filter_by(employee_id=progress.employee_id, flow_key=progress.scenario_key,
        processed_at=None).filter(FlowLaunchRequest.skip_step_key.isnot(None)).update(
            {FlowLaunchRequest.processed_at: now}, synchronize_session=False)
    _event(db, progress.employee_id, f"Администратор {user.id}: прерван диалог сценария #{progress.id}. Ответы сохранены.")
    db.commit()
    return queue_api(request, employee_id, db)
