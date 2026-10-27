"""Explicit Grade cycles; durable claims deliberately never retry ambiguous I/O."""

import calendar
import json
import logging
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select, update

from ..database import SessionLocal
from ..hr_linking import is_numeric_telegram_id
from ..mass_targeting import deserialize_target_selection, deserialize_target_values, mass_target_employee_query
from ..messaging import as_messenger
from ..messaging.identity import get_primary_chat_id
from ..models import (Employee, FlowLaunchRequest, GradeAssessment, GradeDevelopmentCycle as Cycle,
                      GradeDevelopmentDelivery as Delivery, GradeDevelopmentMilestone as Milestone,
                      HrSettings, MassScenarioAction, ScenarioTemplate)
from ..notifications import _notification_recipients
from ..scenario_engine import (INTERACTIVE_RESPONSE_TYPES, get_conflicting_progress_for_survey_launch,
                               get_scenario_steps, get_waiting_progress, matches_role_scope,
                               resolve_scenario_recipient, start_scenario)
from ..staff_email_verification import chat_id_allowed
from ..time_utils import utc_now

MSK = ZoneInfo("Europe/Moscow")
KINDS = ("ipr6", "ipr12", "review12")
EDITABLE = {"planned", "blocked"}
logger = logging.getLogger(__name__)


def local_now():
    return datetime.now(MSK).replace(tzinfo=None)


def _active_staff(employee):
    return bool(employee and not employee.is_bot_blocked and
                (employee.employee_stage or "").strip() in {"staff", "ipr", "adaptation"})


def _pause_unavailable(db, employee, cycle, item):
    if _active_staff(employee):
        return False
    item.status, item.last_error = "failed", "Сотрудник недоступен или не находится в штате. Цикл приостановлен; требуется проверка HR"
    cycle.enabled = False
    cycle.revision += 1
    db.commit()
    return True


def add_months(anchor, months):
    year, month0 = divmod(anchor.year * 12 + anchor.month - 1 + months, 12)
    return date(year, month0 + 1, min(anchor.day, calendar.monthrange(year, month0 + 1)[1]))


def default_dates(anchor):
    six = datetime.combine(add_months(anchor, 6), time(10))
    twelve = datetime.combine(add_months(anchor, 12), time(10))
    return dict(ipr6=six, ipr12=twelve, review12=twelve + timedelta(minutes=10))


def _latest(db, employee_id):
    return db.scalar(select(GradeAssessment).where(GradeAssessment.employee_id == employee_id,
        GradeAssessment.status == "final", GradeAssessment.archived_at.is_(None))
        .order_by(GradeAssessment.created_at.desc(), GradeAssessment.id.desc()))


def _unknown_date(assessment):
    snapshot = json.loads(assessment.catalog_snapshot or "{}")
    source = snapshot.get("import_source")
    return isinstance(source, dict) and not source.get("original_review_date")


def _assessment_anchor(assessment):
    source = json.loads(assessment.catalog_snapshot or "{}").get("import_source")
    original = source.get("original_review_date") if isinstance(source, dict) else None
    return date.fromisoformat(original) if original else (assessment.finalized_at or assessment.created_at).replace(tzinfo=ZoneInfo("UTC")).astimezone(MSK).date()


def owns_scenario(db, employee_id, scenario_key):
    # Pausing a cycle must not expose its scenarios to the generic scheduler.
    return db.scalar(select(Milestone.id).join(Cycle, Cycle.employee_id == Milestone.employee_id).where(
        Cycle.employee_id == employee_id, Cycle.assessment_id == Milestone.assessment_id,
        Milestone.scenario_key == scenario_key, Milestone.status != "cancelled").limit(1)) is not None


def record_launch_conflict(db, employee_id, scenario_key):
    cycle = db.scalar(select(Cycle).where(Cycle.employee_id == employee_id))
    if cycle:
        for item in db.scalars(select(Milestone).where(Milestone.employee_id == employee_id,
                Milestone.assessment_id == cycle.assessment_id, Milestone.scenario_key == scenario_key,
                Milestone.status != "cancelled")):
            if item.status in EDITABLE:
                item.status = "blocked"
            item.last_error = "Конфликт с отдельным запросом запуска. Он сохранён в очереди; HR должен отменить конфликтующий запрос"
        db.flush()


def _pending_mass_conflict(db, employee_id, scenario_keys):
    for action in db.scalars(select(MassScenarioAction).where(MassScenarioAction.flow_key.in_(scenario_keys),
            MassScenarioAction.scenario_kind == "scenario", MassScenarioAction.processed_at.is_(None))):
        query = mass_target_employee_query(db,
            target_all=action.target_all,
            target_employee_stages=deserialize_target_values(action.target_employee_stages, kind="employee"),
            target_candidate_stages=deserialize_target_values(action.target_candidate_stages, kind="candidate"),
            target_employee_id=action.target_employee_id,
            target_role_scope=action.target_role_scope,
            legacy_target_statuses=deserialize_target_values(action.target_statuses, kind="legacy"),
            target_role_scopes=deserialize_target_selection(action.target_role_scopes, kind="role"),
            target_employee_ids=deserialize_target_selection(action.target_employee_ids, kind="employee"))
        if query.filter(Employee.id == employee_id).first() is not None:
            return True
    return False


def _milestone_payload(item):
    return dict(id=item.id, kind=item.kind, due_at=item.due_at.isoformat(), status=item.status,
                last_error=item.last_error, assessment_id=item.assessment_id)


def payload(db, employee_id):
    if not db.get(Employee, employee_id):
        raise LookupError("Сотрудник не найден")
    cycle = db.scalar(select(Cycle).where(Cycle.employee_id == employee_id))
    latest = _latest(db, employee_id)
    rows = list(db.scalars(select(Milestone).where(Milestone.employee_id == employee_id).order_by(Milestone.due_at, Milestone.id)))
    current = [item for item in rows if cycle and item.assessment_id == cycle.assessment_id]
    ids = [item.id for item in rows]
    deliveries = [dict(id=d.id, milestone_id=d.milestone_id, role=d.role, status=d.status, last_error=d.last_error)
                  for d in db.scalars(select(Delivery).where(Delivery.milestone_id.in_(ids)).order_by(Delivery.id))] if ids else []
    return dict(revision=cycle.revision if cycle else 0,
        assessment_id=cycle.assessment_id if cycle else (latest.id if latest else None),
        latest_final_assessment_id=latest.id if latest else None,
        anchor_date=cycle.anchor_date.isoformat() if cycle else (_assessment_anchor(latest).isoformat() if latest and not _unknown_date(latest) else None),
        enabled=cycle.enabled if cycle else False,
        **{kind + "_scenario_key": getattr(cycle, kind + "_scenario_key") if cycle else None for kind in KINDS},
        milestones=[_milestone_payload(item) for item in current],
        history=[_milestone_payload(item) for item in rows if item not in current], deliveries=deliveries,
        scenarios=[dict(key=s.scenario_key, title=s.title) for s in db.scalars(select(ScenarioTemplate)
                   .where(ScenarioTemplate.scenario_kind == "scenario").order_by(ScenarioTemplate.sort_order, ScenarioTemplate.id))],
        needs_anchor=bool(latest and not cycle and _unknown_date(latest)))


def _lock(db, employee_id):
    from ..web.grades import _lock_employee
    _lock_employee(db, employee_id)
    db.expire_all()


def configure(db, employee_id, data):
    from ..web.grades import GradeConflictError
    if not isinstance(data, dict) or set(data) - {"assessment_id", "expected_revision", "anchor_date", "enabled", "due_dates", *(k + "_scenario_key" for k in KINDS)}:
        raise ValueError("Неизвестные поля настроек цикла развития")
    _lock(db, employee_id)
    cycle = db.scalar(select(Cycle).where(Cycle.employee_id == employee_id))
    expected = data.get("expected_revision")
    if type(expected) is not int or expected != (cycle.revision if cycle else 0):
        raise GradeConflictError("Настройки цикла изменились. Обновите страницу")
    latest = _latest(db, employee_id)
    if not latest or type(data.get("assessment_id")) is not int or data["assessment_id"] != latest.id:
        raise ValueError("Выберите последнюю завершённую оценку")
    raw = data.get("anchor_date")
    if raw is None and not _unknown_date(latest):
        anchor = _assessment_anchor(latest)
    else:
        try:
            anchor = date.fromisoformat(raw)
        except (ValueError, TypeError):
            raise ValueError("Укажите дату исходного ревью в формате ГГГГ-ММ-ДД") from None
    if type(data.get("enabled")) is not bool:
        raise ValueError("enabled должен быть логическим значением")
    if (data["enabled"] or not cycle) and not _active_staff(db.get(Employee, employee_id)):
        raise ValueError("Цикл развития доступен только незаблокированному сотруднику в статусе «Адаптация», «ИПР» или «В штате»")
    keys = {}
    for kind in KINDS:
        key = data.get(kind + "_scenario_key")
        if key is not None:
            if not isinstance(key, str) or not key or len(key) > 64:
                raise ValueError("Некорректный ключ сценария")
            scenario = db.scalar(select(ScenarioTemplate).where(ScenarioTemplate.scenario_key == key, ScenarioTemplate.scenario_kind == "scenario"))
            if data["enabled"] and (not scenario or not get_scenario_steps(db, key) or not matches_role_scope(db.get(Employee, employee_id), scenario)):
                raise ValueError("Сценарий недоступен, пуст или не подходит сотруднику")
        if data["enabled"] and not key:
            raise ValueError("Для включения цикла выберите все три сценария")
        keys[kind] = key
    if data["enabled"]:
        from ..adaptation_delivery import owns_scenario as adaptation_owns_scenario
        selected = list(keys.values())
        pending = db.scalar(select(FlowLaunchRequest.id).where(FlowLaunchRequest.employee_id == employee_id,
            FlowLaunchRequest.flow_key.in_(selected), FlowLaunchRequest.skip_step_key.is_(None),
            FlowLaunchRequest.processed_at.is_(None)).limit(1))
        mass = _pending_mass_conflict(db, employee_id, selected)
        if pending or mass or any(adaptation_owns_scenario(db, employee_id, key) for key in selected):
            raise GradeConflictError("Есть отдельный запуск или план адаптации для выбранного сценария. Разрешите конфликт перед включением цикла")
    dates = default_dates(anchor)
    overrides = data.get("due_dates", {})
    if not isinstance(overrides, dict) or set(overrides) - set(KINDS):
        raise ValueError("Некорректные даты этапов")
    old = list(db.scalars(select(Milestone).where(Milestone.employee_id == employee_id)))
    current = {item.kind: item for item in old if item.assessment_id == latest.id}
    same_anchor = bool(cycle and cycle.assessment_id == latest.id and cycle.anchor_date == anchor)
    for kind in KINDS:
        item = current.get(kind)
        if item and same_anchor:
            dates[kind] = item.due_at
        if kind in overrides:
            try:
                value = datetime.fromisoformat(overrides[kind])
            except (ValueError, TypeError):
                raise ValueError("Укажите даты этапов в локальном формате ISO") from None
            if value.tzinfo is not None:
                raise ValueError("Даты этапов задаются по Москве без часового смещения")
            if item and item.status not in EDITABLE and value != item.due_at:
                raise ValueError("Нельзя переносить уже запущенный этап")
            if (not item or item.status in EDITABLE) and value <= local_now():
                raise ValueError("Новая дата этапа должна быть в будущем")
            dates[kind] = value
        if data["enabled"] and (not item or item.status in EDITABLE) and dates[kind] <= local_now():
            raise ValueError("Нельзя включить просроченный этап. Укажите будущие даты")
    if dates["review12"] < dates["ipr12"] + timedelta(minutes=10):
        raise ValueError("Годовое ревью должно идти после ИПР с интервалом не менее 10 минут")
    if not cycle:
        cycle = Cycle(employee_id=employee_id, assessment_id=latest.id, anchor_date=anchor)
        db.add(cycle)
    for item in old:
        if item.assessment_id != latest.id and item.status in EDITABLE:
            item.status = "cancelled"
    cycle.assessment_id, cycle.anchor_date, cycle.enabled = latest.id, anchor, data["enabled"]
    cycle.revision = expected + 1
    for kind, key in keys.items():
        setattr(cycle, kind + "_scenario_key", key)
        item = current.get(kind)
        if not item:
            db.add(Milestone(employee_id=employee_id, assessment_id=latest.id, kind=kind, scenario_key=key, due_at=dates[kind]))
        elif item.status in EDITABLE:
            item.due_at, item.scenario_key = dates[kind], key
    db.flush()
    return payload(db, employee_id)


def renew_after_finalization(db, assessment):
    """Only existing explicit configurations renew; correction/replay never calls this."""
    cycle = db.scalar(select(Cycle).where(Cycle.employee_id == assessment.employee_id))
    if not cycle or cycle.assessment_id == assessment.id:
        return
    anchor = assessment.finalized_at.replace(tzinfo=ZoneInfo("UTC")).astimezone(MSK).date()
    old = list(db.scalars(select(Milestone).where(Milestone.employee_id == assessment.employee_id)))
    for item in old:
        if item.status in EDITABLE:
            item.status = "cancelled"
    cycle.assessment_id, cycle.anchor_date = assessment.id, anchor
    cycle.revision += 1
    for kind, due in default_dates(anchor).items():
        db.add(Milestone(employee_id=assessment.employee_id, assessment_id=assessment.id, kind=kind,
                         scenario_key=getattr(cycle, kind + "_scenario_key"), due_at=due))
    db.flush()


def _reminder_recipients(db, employee):
    settings = db.get(HrSettings, 1)
    hr = [chat for chat in _notification_recipients(settings) if is_numeric_telegram_id(chat) and chat_id_allowed(db, chat)]
    manager = db.get(Employee, employee.manager_employee_id) if employee.manager_employee_id else None
    manager_chat = get_primary_chat_id(manager, db=db) if _active_staff(manager) else None
    return {"hr": hr, "manager": [manager_chat] if manager_chat and is_numeric_telegram_id(manager_chat) else []}


def _seed_reminders(db, employee, item):
    if db.scalar(select(Delivery.id).where(Delivery.milestone_id == item.id)):
        return
    for role, recipients in _reminder_recipients(db, employee).items():
        for chat in recipients or [""]:
            db.add(Delivery(milestone_id=item.id, role=role, chat_id=chat,
                status="pending" if chat else "failed", last_error=None if chat else "Нет подтверждённого числового Telegram ID адресата. Требуется проверка HR"))
    db.flush()


async def _deliver_reminders(db, bot, item):
    for delivery_id in list(db.scalars(select(Delivery.id).where(Delivery.milestone_id == item.id, Delivery.status == "pending"))):
        _lock(db, item.employee_id)
        cycle = db.scalar(select(Cycle).where(Cycle.employee_id == item.employee_id))
        if not cycle or not cycle.enabled or cycle.assessment_id != item.assessment_id or item.status not in EDITABLE or item.due_at > local_now():
            db.rollback()
            return
        delivery = db.get(Delivery, delivery_id)
        if delivery.status != "pending":
            db.rollback()
            continue
        employee = db.get(Employee, item.employee_id)
        if _pause_unavailable(db, employee, cycle, item):
            return
        if delivery.chat_id not in _reminder_recipients(db, employee).get(delivery.role, []):
            delivery.status, delivery.last_error = "cancelled", "Адресат или подтверждение Telegram изменились. Отправка отменена, требуется проверка HR"
            db.commit()
            continue
        claimed = db.execute(update(Delivery).where(Delivery.id == delivery_id, Delivery.status == "pending")
            .values(status="starting", last_error="Отправка начата. При обрыве HR должен проверить доставку перед повтором"))
        db.commit()
        if claimed.rowcount != 1:
            continue
        delivery = db.get(Delivery, delivery_id)
        try:
            if not is_numeric_telegram_id(delivery.chat_id) or not chat_id_allowed(db, delivery.chat_id):
                raise ValueError("Подтверждение адресата изменилось")
            employee = db.get(Employee, item.employee_id)
            label = {"ipr6": "ИПР через 6 месяцев", "ipr12": "ИПР через 12 месяцев", "review12": "Годовое ревью"}[item.kind]
            text = f"Развитие сотрудника: {employee.full_name or 'ФИО не указано'} (№{employee.id}). {label}: {item.due_at:%d.%m.%Y %H:%M} МСК."
            db.commit()
            await as_messenger(bot).send_text(chat_id=delivery.chat_id, text=text)
            delivery.status, delivery.last_error = "sent", None
        except Exception:
            db.rollback()
            delivery = db.get(Delivery, delivery_id)
            delivery.status, delivery.last_error = "failed", "Ошибка или неопределённый результат отправки. HR должен проверить доставку перед повтором"
            logger.warning("Grade reminder failed: delivery_id=%s", delivery_id)
        db.commit()


async def process_due(bot):
    """Called inside scheduler serialization. DB claims additionally guard other workers."""
    with SessionLocal() as db:
        ids = list(db.scalars(select(Milestone.id).join(Cycle, Cycle.employee_id == Milestone.employee_id).where(
            Cycle.enabled.is_(True), Cycle.assessment_id == Milestone.assessment_id,
            Milestone.status.in_(EDITABLE), Milestone.due_at <= local_now()).order_by(Milestone.due_at, Milestone.id)))
    for item_id in ids:
        try:
            await _process_one(bot, item_id)
        except Exception:
            logger.exception("Grade development scan failed: milestone_id=%s", item_id)


async def _process_one(bot, item_id):
    with SessionLocal() as db:
        item = db.get(Milestone, item_id)
        if item is None:
            return
        _lock(db, item.employee_id)
        item = db.get(Milestone, item_id)
        cycle = db.scalar(select(Cycle).where(Cycle.employee_id == item.employee_id))
        if not cycle or not cycle.enabled or cycle.assessment_id != item.assessment_id or item.status not in EDITABLE or item.due_at > local_now():
            db.rollback()
            return
        employee = db.get(Employee, item.employee_id)
        if _pause_unavailable(db, employee, cycle, item):
            return
        assessment = db.get(GradeAssessment, item.assessment_id)
        if not assessment or assessment.status != "final" or assessment.archived_at is not None or assessment.employee_id != item.employee_id:
            item.status, item.last_error = "failed", "Исходная завершённая оценка недоступна. Цикл приостановлен"
            cycle.enabled = False
            cycle.revision += 1
            db.commit()
            return
        _seed_reminders(db, employee, item)
        db.commit()
        await _deliver_reminders(db, bot, item)
        _lock(db, employee.id)
        item, cycle = db.get(Milestone, item_id), db.get(Cycle, cycle.id)
        if not cycle.enabled or cycle.assessment_id != item.assessment_id or item.status not in EDITABLE or item.due_at > local_now():
            db.rollback()
            return
        if _pause_unavailable(db, employee, cycle, item):
            return
        assessment = db.get(GradeAssessment, item.assessment_id)
        if not assessment or assessment.status != "final" or assessment.archived_at is not None:
            item.status, item.last_error = "failed", "Исходная завершённая оценка недоступна. Требуется проверка HR"
            db.commit()
            return
        scenario = db.scalar(select(ScenarioTemplate).where(ScenarioTemplate.scenario_key == item.scenario_key))
        if not scenario or scenario.scenario_kind != "scenario" or employee.is_bot_blocked or not matches_role_scope(employee, scenario):
            item.status, item.last_error = "failed", "Сотрудник или сценарий недоступен. Требуется проверка HR"
            db.commit()
            return
        steps = get_scenario_steps(db, scenario.scenario_key)
        recipient = resolve_scenario_recipient(db, employee, scenario, requires_response=any(s.response_type in INTERACTIVE_RESPONSE_TYPES for s in steps))
        if not steps or recipient.error:
            item.status, item.last_error = "failed", recipient.error or "В сценарии нет шагов"
            db.commit()
            return
        predecessor = db.scalar(select(Milestone).where(Milestone.employee_id == employee.id,
            Milestone.assessment_id == item.assessment_id, Milestone.kind == "ipr12")) if item.kind == "review12" else None
        busy = ((recipient.employee_id and get_waiting_progress(db, recipient.employee_id))
                or get_conflicting_progress_for_survey_launch(db, employee.id, scenario.scenario_key))
        pending = db.scalar(select(FlowLaunchRequest.id).where(FlowLaunchRequest.employee_id == employee.id,
            FlowLaunchRequest.flow_key == scenario.scenario_key, FlowLaunchRequest.skip_step_key.is_(None),
            FlowLaunchRequest.processed_at.is_(None)).limit(1))
        mass = _pending_mass_conflict(db, employee.id, [scenario.scenario_key])
        from ..adaptation_delivery import owns_scenario as adaptation_owns_scenario
        if pending or mass or adaptation_owns_scenario(db, employee.id, scenario.scenario_key):
            item.status, item.last_error = "blocked", "Есть другой запрос запуска этого сценария. HR должен отменить конфликтующий запрос"
            db.commit()
            return
        if busy or (predecessor and predecessor.status != "started"):
            item.status, item.last_error = "blocked", "Ожидается завершение диалога адресата или запуск предыдущего ИПР. Этап сохранён"
            db.commit()
            return
        changed = db.execute(update(Milestone).where(Milestone.id == item_id, Milestone.status.in_(EDITABLE))
            .values(status="starting", claimed_at=utc_now(), last_error="Запуск начат. При обрыве HR должен проверить доставку перед повтором"))
        db.commit()
        if changed.rowcount != 1:
            return
        try:
            started = await start_scenario(bot, db, employee, scenario.scenario_key)
            item = db.get(Milestone, item_id)
            item.status = "started" if started else "failed"
            item.last_error = None if started else "Сценарий не запущен. Требуется проверка HR перед повтором"
            db.commit()
        except Exception:
            db.rollback()
            # A send may already have succeeded: never automatically reclaim this row.
            item = db.get(Milestone, item_id)
            item.status, item.last_error = "starting", "Результат запуска неизвестен. HR должен проверить доставку перед повтором"
            db.commit()
            logger.warning("Grade launch outcome uncertain: milestone_id=%s", item_id)
