"""Delivery lifecycle for explicitly scheduled adaptation entries."""

import logging

from sqlalchemy import update

from .models import Employee, EmployeeAdaptationPlanItem, FlowLaunchRequest, ScenarioTemplate
from .scenario_engine import INTERACTIVE_RESPONSE_TYPES, get_scenario_steps, get_waiting_progress, matches_role_scope, resolve_scenario_recipient, start_scenario
from .time_utils import utc_now

logger = logging.getLogger(__name__)


def owns_scenario(db, employee_id, scenario_key):
    return db.query(EmployeeAdaptationPlanItem.id).filter_by(employee_id=employee_id, flow_key=scenario_key).first() is not None


async def deliver_plan_request(db, bot, request):
    if request.launch_type != "adaptation_plan":
        return False
    item = db.query(EmployeeAdaptationPlanItem).filter_by(launch_request_id=request.id).first()
    if item is None:
        db.execute(update(FlowLaunchRequest).where(FlowLaunchRequest.id == request.id, FlowLaunchRequest.processed_at.is_(None)).values(processed_at=utc_now()))
        db.commit()
        return True
    employee = db.get(Employee, item.employee_id)
    scenario = db.query(ScenarioTemplate).filter_by(scenario_key=item.flow_key).first()
    if item.status not in {"planned", "blocked"}:
        db.execute(update(FlowLaunchRequest).where(FlowLaunchRequest.id == request.id, FlowLaunchRequest.processed_at.is_(None)).values(processed_at=utc_now()))
        db.commit()
        return True
    error = None
    if not employee or employee.is_bot_blocked or not scenario or not matches_role_scope(employee, scenario):
        error = "Сотрудник или сценарий недоступен"
    else:
        requires_response = any(step.response_type in INTERACTIVE_RESPONSE_TYPES for step in get_scenario_steps(db, scenario.scenario_key))
        recipient = resolve_scenario_recipient(db, employee, scenario, requires_response=requires_response)
        error = recipient.error
        if not error and recipient.employee_id and get_waiting_progress(db, recipient.employee_id):
            item.status = "blocked"
            item.last_error = "Получатель ещё отвечает на другой сценарий. Запуск ожидает освобождения диалога."
            db.commit()
            return True
    if error:
        item.status = "failed"
        item.last_error = error
        request.processed_at = utc_now()
        db.commit()
        return True
    # Claim the exact due version before external I/O; a concurrent date edit wins or loses atomically.
    claimed = db.execute(update(FlowLaunchRequest).where(
        FlowLaunchRequest.id == request.id,
        FlowLaunchRequest.processed_at.is_(None),
        FlowLaunchRequest.requested_at == request.requested_at,
    ).values(processed_at=utc_now()))
    if claimed.rowcount != 1:
        db.rollback()
        return True
    item.status = "starting"
    item.started_at = utc_now()
    item.last_error = None
    db.commit()
    try:
        started = await start_scenario(bot, db, employee, scenario.scenario_key, adaptation_plan_item_id=item.id)
        db.refresh(item)
        if item.status != "completed":
            item.status = "in_progress" if started else "failed"
            if not started:
                item.last_error = "Сценарий не запущен. Проверьте получателя и шаги перед повтором."
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Adaptation plan delivery failed: item_id=%s", item.id)
        db.refresh(item)
        item.status = "failed"
        item.last_error = "Ошибка доставки. Перед повтором проверьте сообщения получателя."
        db.commit()
    return True
