"""Persistent, at-most-once attempts for legacy scheduler step jobs."""

import hashlib
import json
import logging
from datetime import UTC
from zoneinfo import ZoneInfo

from sqlalchemy import or_, update

from .config import settings
from .models import Employee, FlowStepTemplate, OnboardingEvent, ScenarioProgress, ScenarioStepDelivery as Delivery, ScenarioTemplate
from .scenario_engine import (ScenarioRecipientBusy, _admit_scenario_start, _store_progress_recipient,
    _deserialize_step_history, _serialize_step_history, get_first_step, get_step_by_key, get_or_create_progress,
    matches_role_scope, resolve_scenario_recipient, scenario_anchor_date, step_requires_response, send_step, start_scenario)
from .time_utils import utc_now

logger = logging.getLogger(__name__)


def utc_due(value):
    aware = value if value.tzinfo else value.replace(tzinfo=ZoneInfo(settings.TIMEZONE))
    return aware.astimezone(UTC).replace(tzinfo=None)


def enqueue_step(db, employee_id, scenario_key, step_key, run_at, explicit, batch_key, created_at, *, entry_root=None, scheduled_at=None):
    due = utc_due(run_at)
    scheduled = utc_due(scheduled_at) if scheduled_at is not None else due
    key = hashlib.sha256(json.dumps([employee_id, scenario_key, step_key, scheduled.isoformat(), explicit, batch_key]).encode()).hexdigest()
    db.execute(update(Employee).where(Employee.id == employee_id).values(id=Employee.id))
    existing = db.query(Delivery).filter_by(dedupe_key=key).first()
    if existing:
        return existing
    first = get_first_step(db, scenario_key)
    progress = db.query(ScenarioProgress).filter_by(employee_id=employee_id, scenario_key=scenario_key, is_completed=False).first()
    employee = db.get(Employee, employee_id)
    scenario = db.query(ScenarioTemplate).filter_by(scenario_key=scenario_key).first()
    resolution = resolve_scenario_recipient(db, employee, scenario, requires_response=False) if employee and scenario else None
    row = Delivery(dedupe_key=key, employee_id=employee_id, scenario_key=scenario_key, step_key=step_key,
        due_at=due, explicit=explicit, batch_key=batch_key, created_at=created_at,
        is_root=bool(first and first.step_key == step_key) if entry_root is None else entry_root,
        recipient_employee_id=resolution.employee_id if resolution else None,
        progress_id=progress.id if progress and not explicit else None,
        progress_started_at=progress.started_at if progress and not explicit else None)
    db.add(row)
    db.flush()
    return row


def _finish(db, row, state, reason=None):
    row.status, row.last_error = state, reason
    db.commit()


async def deliver_step(db, bot, delivery_id):
    locked = db.execute(update(Delivery).where(Delivery.id == delivery_id, Delivery.status == "pending",
        Delivery.due_at <= utc_now()).values(status="pending"))
    if locked.rowcount != 1:
        db.rollback()
        return
    row = db.get(Delivery, delivery_id, populate_existing=True)
    employee = db.get(Employee, row.employee_id, populate_existing=True)
    scenario = db.query(ScenarioTemplate).filter_by(scenario_key=row.scenario_key).first()
    step = db.query(FlowStepTemplate).filter_by(flow_key=row.scenario_key, step_key=row.step_key).first()
    if not employee or employee.is_bot_blocked or not scenario or not step or not matches_role_scope(employee, scenario):
        _finish(db, row, "failed", "Сотрудник или шаг недоступен")
        return
    if not row.explicit:
        from .scheduler import IMMEDIATE_TRIGGER_MODES
        from .adaptation_delivery import owns_scenario
        from .grades.development import owns_scenario as grade_owns
        if scenario.trigger_mode in IMMEDIATE_TRIGGER_MODES or owns_scenario(db, employee.id, row.scenario_key) or grade_owns(db, employee.id, row.scenario_key):
            _finish(db, row, "cancelled", "Автоматический запуск больше не принадлежит этому расписанию")
            return
        anchor = scenario_anchor_date(employee, scenario)
        if not anchor or (row.batch_key.startswith("auto:") and row.batch_key != f"auto:{anchor.isoformat()}"):
            _finish(db, row, "cancelled", "Исходная дата расписания изменилась")
            return
    sent = db.query(OnboardingEvent.id).filter_by(employee_id=row.employee_id, event_key=row.step_key)
    if row.explicit:
        sent = sent.filter(OnboardingEvent.scenario_key == row.scenario_key, OnboardingEvent.delivery_batch_key == row.batch_key)
    else:
        sent = sent.filter(or_(OnboardingEvent.scenario_key == row.scenario_key,
            (OnboardingEvent.scenario_key.is_(None)) & (OnboardingEvent.scenario_title == scenario.title)))
    if sent.first():
        _finish(db, row, "sent")
        return
    progress = db.query(ScenarioProgress).filter_by(employee_id=row.employee_id, scenario_key=row.scenario_key).first()
    if row.progress_id and (not progress or progress.id != row.progress_id or progress.started_at != row.progress_started_at):
        _finish(db, row, "cancelled", "Контекст диалога заменён; старый шаг не отправляется")
        return
    if progress and (progress.waiting_for_response or progress.last_delivery_error):
        _finish(db, row, "pending", "Ожидается ответ человека или проверка предыдущей доставки")
        return
    if row.is_root and progress and not progress.is_completed and not progress.interrupted_at:
        continuation = db.query(Delivery.id).filter_by(
            progress_id=progress.id, progress_started_at=progress.started_at,
            is_root=False, status="pending",
        ).first()
        if continuation:
            _finish(db, row, "pending", "Ожидается запланированный шаг предыдущего запуска")
            return
    if not row.is_root:
        root = db.query(Delivery).filter_by(employee_id=row.employee_id, scenario_key=row.scenario_key,
            batch_key=row.batch_key, is_root=True).first()
        if root and root.status in {"pending", "starting"}:
            _finish(db, row, "pending", "Ожидает первый шаг своего запуска")
            return
        if not progress or (root and root.status in {"failed", "cancelled"}) or progress.interrupted_at:
            _finish(db, row, "cancelled", "Исходный диалог недоступен или прерван")
            return
        if progress.is_completed:
            _finish(db, row, "cancelled", "Диалог уже завершён; старое продолжение не запускается")
            return
    try:
        resolution = _admit_scenario_start(db, employee, scenario, defer_if_busy=True,
            continuation_id=progress.id if progress and not row.is_root else None)
    except ScenarioRecipientBusy:
        db.rollback()
        db.execute(update(Delivery).where(Delivery.id == delivery_id, Delivery.status == "pending").values(
            last_error="Получатель занят другим диалогом; шаг сохранён в очереди"))
        db.commit()
        return
    if resolution.error or not resolution.chat_id:
        _finish(db, row, "failed", resolution.error or "Получатель недоступен")
        return
    other_send = db.query(Delivery.id).filter(Delivery.id != row.id, Delivery.status == "starting", or_(
        Delivery.recipient_employee_id == resolution.employee_id,
        (Delivery.employee_id == employee.id) & (Delivery.scenario_key == scenario.scenario_key))).first()
    if other_send:
        _finish(db, row, "pending", "Предыдущая доставка требует проверки")
        return
    if not row.is_root:
        progress = get_or_create_progress(db, employee.id, row.scenario_key)
        previous = get_step_by_key(db, row.scenario_key, progress.current_step_key) if progress.current_step_key else None
        if previous and previous.step_key != step.step_key and step_requires_response(previous):
            history = _deserialize_step_history(progress)
            if not history or history[-1] != previous.step_key:
                _serialize_step_history(progress, [*history, previous.step_key])
        _store_progress_recipient(progress, resolution)
        progress.delivery_batch_key = progress.delivery_batch_key or row.batch_key
        progress.current_step_key, progress.waiting_for_response = step.step_key, False
        progress.updated_at = utc_now()
        progress.last_delivery_error = "Результат начатой доставки неизвестен. Перед повтором проверьте сообщения получателя."
    row.status, row.last_error, row.recipient_employee_id = "starting", "Результат доставки требует проверки при обрыве", resolution.employee_id
    db.commit()
    try:
        if row.is_root:
            started = await start_scenario(bot, db, employee, scenario.scenario_key, defer_if_busy=True,
                scheduled_at=row.due_at, entry_step_key=row.step_key, delivery_batch_key=row.batch_key)
        else:
            started = await send_step(bot, db, employee, scenario, step, scheduled_at=row.due_at, _admitted_recipient=resolution)
        progress = db.query(ScenarioProgress).filter_by(employee_id=employee.id, scenario_key=scenario.scenario_key).first()
        if started and progress:
            row.progress_id, row.progress_started_at = progress.id, progress.started_at
            db.query(Delivery).filter_by(employee_id=employee.id, scenario_key=scenario.scenario_key, batch_key=row.batch_key,
                status="pending").update({Delivery.progress_id: progress.id, Delivery.progress_started_at: progress.started_at}, synchronize_session=False)
        _finish(db, row, "sent" if started else "failed", None if started else "Не удалось отправить шаг")
    except ScenarioRecipientBusy:
        db.rollback()
        db.execute(update(Delivery).where(Delivery.id == delivery_id, Delivery.status == "starting").values(status="pending",
            last_error="Получатель занят другим диалогом; шаг сохранён в очереди"))
        db.commit()
    except Exception:
        db.rollback()
        logger.warning("Scheduled step delivery uncertain: delivery_id=%s", delivery_id)


async def deliver_due_steps(db, bot):
    ids = [row[0] for row in db.query(Delivery.id).filter(Delivery.status == "pending", Delivery.due_at <= utc_now()).order_by(Delivery.due_at, Delivery.id)]
    for delivery_id in ids:
        await deliver_step(db, bot, delivery_id)
