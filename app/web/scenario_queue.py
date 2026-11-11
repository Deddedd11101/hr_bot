"""Employee-scoped visibility and guarded interruption of scenario runtime."""

from datetime import datetime, timedelta
import json

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from sqlalchemy import or_, update
from sqlalchemy.orm import Session

from ..database import get_session
from ..models import (Employee, EmployeeAdaptationPlanItem, EmployeeFeedbackRecipient,
                      FlowLaunchRequest, FlowStepTemplate, OnboardingEvent, ScenarioAnswerRun,
                      ScenarioProgress, ScenarioStepDelivery, ScenarioTemplate)
from ..scenario_engine import (get_conflicting_progress_for_survey_launch,
                               resolve_scenario_recipient, get_scenario_steps,
                               INTERACTIVE_RESPONSE_TYPES)
from ..time_utils import utc_now
from ..scenario_watchdog import progress_health
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


def _delivery_receipt(db, row):
    return db.query(OnboardingEvent.sent_at).filter(
        OnboardingEvent.employee_id == row.employee_id,
        OnboardingEvent.scenario_key == row.scenario_key,
        OnboardingEvent.event_key == row.step_key,
        OnboardingEvent.delivery_batch_key == row.batch_key,
        OnboardingEvent.sent_at >= row.created_at,
    ).order_by(OnboardingEvent.sent_at.desc()).first()


def _can_reconcile_delivery(db, row, receipt):
    if row.status != "starting" or not receipt or receipt.sent_at > utc_now() - timedelta(hours=3):
        return False
    return not db.query(ScenarioStepDelivery.id).filter(
        ScenarioStepDelivery.id != row.id,
        ScenarioStepDelivery.employee_id == row.employee_id,
        ScenarioStepDelivery.scenario_key == row.scenario_key,
        ScenarioStepDelivery.batch_key == row.batch_key,
        ScenarioStepDelivery.status.in_(["pending", "starting"]),
    ).first()


def _progress_row(db, progress):
    recipient_id = progress.recipient_employee_id or progress.employee_id
    recipient = db.get(Employee, recipient_id)
    return {"id": progress.id, "title": _title(db, progress.scenario_key),
            "employee_id": progress.employee_id, "recipient_id": recipient_id,
            "recipient_name": recipient.full_name if recipient else "Адресат недоступен",
            "updated_at": progress.updated_at.isoformat(),
            "started_at": progress.started_at.isoformat(),
            "waiting": progress.waiting_for_response,
            "long_wait": progress.updated_at < utc_now() - timedelta(days=1),
            "health": progress_health(db, progress)}


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
        recipient = resolve_scenario_recipient(db, person, scenario, requires_response=any(
            step.response_type in INTERACTIVE_RESPONSE_TYPES for step in get_scenario_steps(db, row.flow_key)
        )) if scenario else None
        busy = get_conflicting_progress_for_survey_launch(db, recipient.employee_id, row.flow_key) if recipient and recipient.employee_id else None
        pending.append({"id": row.id, "title": _title(db, row.flow_key),
                        "source": row.launch_type, "requested_at": row.requested_at.isoformat(),
                        "blocker": _progress_row(db, busy) if busy else None,
                        "recipient_error": recipient.error if recipient else "Сценарий не найден",
                        "can_cancel": row.skip_step_key is None})
    step_deliveries = []
    for row in db.query(ScenarioStepDelivery).filter(or_(ScenarioStepDelivery.employee_id == employee_id,
            ScenarioStepDelivery.recipient_employee_id == employee_id), ScenarioStepDelivery.status.in_(["pending", "starting", "failed"])).order_by(ScenarioStepDelivery.due_at, ScenarioStepDelivery.id):
        step = db.query(FlowStepTemplate).filter_by(flow_key=row.scenario_key, step_key=row.step_key).first()
        recipient = db.get(Employee, row.recipient_employee_id) if row.recipient_employee_id else None
        receipt = _delivery_receipt(db, row) if row.status == "starting" else None
        scenario_title = _title(db, row.scenario_key)
        step_title = step.step_title if step else "Шаг удалён"
        step_deliveries.append({"id": row.id, "title": f"{scenario_title} · {step_title}",
            "launch_key": json.dumps([row.employee_id, row.scenario_key, row.batch_key]),
            "scenario_title": scenario_title, "step_title": step_title,
            "due_at": row.due_at.isoformat(), "status": row.status, "reason": row.last_error,
            "recipient_name": recipient.full_name if recipient else None,
            "receipt_at": receipt.sent_at.isoformat() if receipt else None,
            "can_reconcile": _can_reconcile_delivery(db, row, receipt),
            "can_cancel": row.status == "pending" and row.is_root})
    return {"active": [_progress_row(db, row) for row in active], "pending": pending, "step_deliveries": step_deliveries,
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


@router.post("/api/employees/{employee_id}/scenario-queue/step-deliveries/{delivery_id}/cancel")
def cancel_step_delivery(request: Request, employee_id: int, delivery_id: int,
                         payload: dict = Body(...), db: Session = Depends(get_db)):
    user = require_api_admin(request)
    _employee(db, employee_id)
    expected = _expected(payload)
    changed = db.execute(update(ScenarioStepDelivery).where(ScenarioStepDelivery.id == delivery_id,
        or_(ScenarioStepDelivery.employee_id == employee_id, ScenarioStepDelivery.recipient_employee_id == employee_id),
        ScenarioStepDelivery.status == "pending", ScenarioStepDelivery.is_root.is_(True), ScenarioStepDelivery.due_at == expected)
        .values(status="cancelled", last_error="Запуск отменён администратором"))
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Запуск изменён, уже отправляется или является продолжением диалога. Обновите очередь.")
    row = db.get(ScenarioStepDelivery, delivery_id, populate_existing=True)
    db.query(ScenarioStepDelivery).filter_by(employee_id=row.employee_id, scenario_key=row.scenario_key,
        batch_key=row.batch_key, status="pending").update(
        {ScenarioStepDelivery.status: "cancelled", ScenarioStepDelivery.last_error: "Корневой запуск отменён"}, synchronize_session=False)
    _event(db, row.employee_id, f"Администратор {user.id}: отменён корневой плановый запуск #{row.id} без отправки.")
    db.commit()
    return queue_api(request, employee_id, db)


@router.post("/api/employees/{employee_id}/scenario-queue/step-deliveries/{delivery_id}/reconcile")
def reconcile_step_delivery(request: Request, employee_id: int, delivery_id: int,
                            payload: dict = Body(...), db: Session = Depends(get_db)):
    user = require_api_admin(request)
    expected = _expected(payload)
    locked = db.execute(update(ScenarioStepDelivery).where(
        ScenarioStepDelivery.id == delivery_id, ScenarioStepDelivery.status == "starting",
        ScenarioStepDelivery.due_at == expected,
        or_(ScenarioStepDelivery.employee_id == employee_id, ScenarioStepDelivery.recipient_employee_id == employee_id),
    ).values(status="starting"))
    row = db.get(ScenarioStepDelivery, delivery_id, populate_existing=True) if locked.rowcount == 1 else None
    if row is None or not _can_reconcile_delivery(db, row, _delivery_receipt(db, row)):
        db.rollback()
        raise HTTPException(409, "Нет подтверждения отправки, есть связанные шаги или запись уже изменилась. Обновите очередь.")
    row.status, row.last_error = "sent", None
    _event(db, row.employee_id, f"Администратор {user.id}: подтверждена отправка шага #{row.id} по журналу, без повторной отправки.")
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
    from ..models import ScenarioStepDelivery
    db.query(ScenarioStepDelivery).filter_by(progress_id=progress.id, progress_started_at=progress.started_at, status="pending").update(
        {ScenarioStepDelivery.status: "cancelled", ScenarioStepDelivery.last_error: "Диалог прерван администратором"}, synchronize_session=False)
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
