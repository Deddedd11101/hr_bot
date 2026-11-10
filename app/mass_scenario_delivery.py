"""Durable per-subject attempts for new scheduled mass scenario actions."""

import logging
from collections import Counter

from sqlalchemy import update

from .models import Employee, MassScenarioAction, MassScenarioRecipient, ScenarioTemplate
from .scenario_engine import (INTERACTIVE_RESPONSE_TYPES, ScenarioRecipientBusy, get_conflicting_progress_for_survey_launch,
    get_scenario_steps, matches_role_scope, resolve_scenario_recipient, start_scenario)
from .time_utils import utc_now

logger = logging.getLogger(__name__)


def delivery_counts(db, action_id):
    return dict(Counter(status for (status,) in db.query(MassScenarioRecipient.status).filter_by(action_id=action_id)))


def delete_unstarted_action(db, action_id):
    changed = db.execute(update(MassScenarioAction).where(MassScenarioAction.id == action_id,
        MassScenarioAction.processed_at.is_(None)).values(recipient_count=MassScenarioAction.recipient_count))
    if changed.rowcount != 1:
        raise ValueError("Запуск уже изменён. Обновите страницу")
    if db.query(MassScenarioRecipient.id).filter(MassScenarioRecipient.action_id == action_id,
            MassScenarioRecipient.status.in_(["starting", "started"])).first():
        raise ValueError("Часть рассылки уже запущена или находится в доставке. Удаление запрещено")
    db.query(MassScenarioRecipient).filter_by(action_id=action_id).delete(synchronize_session=False)
    db.delete(db.get(MassScenarioAction, action_id))


async def deliver_mass_action(db, bot, action_id, recipient_ids):
    # Serialize snapshot creation with cancel/other workers. Never hold this lock across I/O.
    claimed = db.execute(update(MassScenarioAction).where(MassScenarioAction.id == action_id,
        MassScenarioAction.processed_at.is_(None), MassScenarioAction.recipient_queue_enabled.is_(True))
        .values(recipient_count=MassScenarioAction.recipient_count))
    if claimed.rowcount != 1:
        db.rollback()
        return
    action = db.get(MassScenarioAction, action_id, populate_existing=True)
    flow_key, scenario_kind = action.flow_key, action.scenario_kind
    rows = db.query(MassScenarioRecipient).filter_by(action_id=action_id).order_by(MassScenarioRecipient.id).all()
    if not rows:
        for employee_id in dict.fromkeys(recipient_ids):
            db.add(MassScenarioRecipient(action_id=action_id, employee_id=employee_id))
        db.flush()
        rows = db.query(MassScenarioRecipient).filter_by(action_id=action_id).order_by(MassScenarioRecipient.id).all()
    if not rows:
        action.recipient_count, action.processed_at = 0, utc_now()
    row_ids = [row.id for row in rows]
    db.commit()
    for row_id in row_ids:
        row = db.get(MassScenarioRecipient, row_id, populate_existing=True)
        if row is None or row.status != "pending":
            continue
        # Refresh mutable identity/scope before every attempt, not only at snapshot time.
        employee = db.get(Employee, row.employee_id, populate_existing=True)
        scenario = db.query(ScenarioTemplate).filter_by(scenario_key=flow_key).first()
        error = None
        if not employee or employee.is_bot_blocked or not scenario or scenario.scenario_kind != scenario_kind or not matches_role_scope(employee, scenario):
            error = "Сотрудник или сценарий недоступен"
        else:
            steps = get_scenario_steps(db, scenario.scenario_key)
            recipient = resolve_scenario_recipient(db, employee, scenario,
                requires_response=any(s.response_type in INTERACTIVE_RESPONSE_TYPES for s in steps))
            error = recipient.error or ("В сценарии нет шагов" if not steps else None)
            if not error and ((recipient.employee_id and get_conflicting_progress_for_survey_launch(db, recipient.employee_id, scenario.scenario_key)) or
                    get_conflicting_progress_for_survey_launch(db, employee.id, scenario.scenario_key)):
                continue
        changed = db.execute(update(MassScenarioRecipient).where(MassScenarioRecipient.id == row.id,
            MassScenarioRecipient.status == "pending").values(status="failed" if error else "starting",
                last_error=error or "Результат доставки требует проверки при обрыве", updated_at=utc_now()))
        db.commit()
        if changed.rowcount != 1 or error:
            continue
        try:
            started = await start_scenario(bot, db, employee, scenario.scenario_key,
                survey_launch_id=action_id if scenario_kind == "survey" else None, defer_if_busy=True)
            row = db.get(MassScenarioRecipient, row_id, populate_existing=True)
            row.status = "started" if started else "failed"
            row.last_error = None if started else "Не удалось запустить сценарий. Проверьте получателя и шаги"
            row.updated_at = utc_now()
            db.commit()
        except ScenarioRecipientBusy:
            db.rollback()
            db.execute(update(MassScenarioRecipient).where(MassScenarioRecipient.id == row_id,
                MassScenarioRecipient.status == "starting").values(status="pending", last_error=None, updated_at=utc_now()))
            db.commit()
        except Exception:
            db.rollback()
            # Starting is an at-most-once attempt, not an expiring lease.
            logger.warning("Mass scenario delivery uncertain: recipient_row_id=%s", row_id)
    counts = delivery_counts(db, action_id)
    action = db.get(MassScenarioAction, action_id, populate_existing=True)
    if action is None:
        return
    action.recipient_count = counts.get("started", 0)
    if not counts.get("pending") and not counts.get("starting"):
        action.processed_at = utc_now()
    db.commit()
