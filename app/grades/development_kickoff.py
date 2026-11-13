"""One-time post-adaptation 360 and its follow-up."""
import logging
from datetime import datetime, time, timedelta
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select

from ..adaptation_planning import CalendarDates
from ..models import AdminAccount, Employee, FlowLaunchRequest, GradeDevelopmentKickoff as Kickoff, GradeReviewCollection, ScenarioTemplate
from ..scenario_engine import get_first_step, matches_role_scope
from ..time_utils import default_adaptation_end
from . import development as dev
from .collections import create, recipient_ids

logger = logging.getLogger(__name__)


def proposal(db, employee):
    end = employee.adaptation_end or (default_adaptation_end(employee.first_workday) if employee.first_workday else None)
    if not end:
        return None
    return datetime.combine(CalendarDates(db).shift(end + timedelta(days=1), 0, "calendar"), time(10))


def payload(db, employee):
    row = db.get(Kickoff, employee.id)
    if not row:
        try:
            suggested = proposal(db, employee)
        except ValueError as exc:
            return {"last_error": str(exc)}
        return {"suggested_at": suggested.isoformat() if suggested else None}
    collection = db.get(GradeReviewCollection, row.collection_id) if row.collection_id else None
    followup = db.get(FlowLaunchRequest, row.followup_request_id) if row.followup_request_id else None
    return dict(due_at=row.due_at.isoformat(), specialization_id=row.specialization_id, scenario_key=row.scenario_key,
                collection_id=row.collection_id, finalized=bool(collection and collection.status == "final"),
                last_error=row.last_error,
                followup_at=followup.requested_at.isoformat() if followup else None,
                followup_processed=bool(followup and followup.processed_at))


def configure(db, employee_id, actor_id, data):
    from ..web.grades import preview_review

    dev._lock(db, employee_id)
    employee = db.get(Employee, employee_id)
    if not dev._active_staff(employee):
        raise ValueError("Сотрудник недоступен")
    row = db.get(Kickoff, employee_id, populate_existing=True)
    if row and row.collection_id:
        raise ValueError("Разовая оценка 360 уже запущена")
    try:
        due = datetime.fromisoformat(data["due_at"])
        if due.tzinfo is not None or "T" not in data["due_at"]:
            raise ValueError
    except (KeyError, TypeError, ValueError):
        raise ValueError("Укажите дату и время по Москве") from None
    earliest = proposal(db, employee)
    if not earliest or due.date() < earliest.date() or due <= dev.local_now():
        raise ValueError("Выберите будущую дату после окончания адаптации")
    scenario = db.scalar(select(ScenarioTemplate).where(ScenarioTemplate.scenario_key == data.get("scenario_key")))
    if not scenario or scenario.scenario_kind != "scenario" or not matches_role_scope(employee, scenario) or not get_first_step(db, scenario.scenario_key):
        raise ValueError("Выберите доступный сценарий организации ИПР")
    spec = data.get("specialization_id")
    if not preview_review(db, employee_id, spec, None)["scores"]:
        raise ValueError("В шаблоне оценки нет навыков")
    if not row:
        row = Kickoff(employee_id=employee_id)
        db.add(row)
    row.due_at, row.specialization_id, row.scenario_key, row.actor_id = due, spec, scenario.scenario_key, actor_id
    row.last_error = None
    db.flush()
    return payload(db, employee)


def launch(db, employee_id):
    dev._lock(db, employee_id)
    row = db.get(Kickoff, employee_id, populate_existing=True)
    if not row or row.collection_id or row.last_error or row.due_at > dev.local_now():
        return
    employee = db.get(Employee, employee_id)
    actor = db.get(AdminAccount, row.actor_id)
    try:
        with db.begin_nested():
            if not dev._active_staff(employee) or not actor or not actor.is_active:
                raise ValueError("Сотрудник или автор настройки недоступен")
            earliest = proposal(db, employee)
            if not earliest or row.due_at.date() < earliest.date():
                raise ValueError("Дата окончания адаптации изменилась; пересохраните план")
            manager = employee.manager_employee_id
            if not manager or manager == employee_id:
                raise ValueError("Назначьте руководителя в карточке сотрудника")
            recipient_ids(db, [manager])
            collection = create(db, employee_id, actor.id, dict(
                request_id=str(uuid5(NAMESPACE_URL, f"grade-kickoff:{employee_id}")),
                specialization_id=row.specialization_id, recipient_ids=[employee_id, manager]),
                include_self=True, manager_id=manager)
            row.collection_id = collection.id
    except (ValueError, LookupError) as exc:
        row.last_error = str(exc)


def schedule_followup(db, collection, actor_id, finalized_at):
    row = db.get(Kickoff, collection.employee_id)
    if not row or row.collection_id != collection.id or row.followup_request_id:
        return
    day = finalized_at.replace(tzinfo=dev.ZoneInfo("UTC")).astimezone(dev.MSK).date() + timedelta(days=7)
    due = datetime.combine(CalendarDates(db).shift(day, 0, "calendar"), time(10))
    request = FlowLaunchRequest(employee_id=row.employee_id, flow_key=row.scenario_key, launch_type="scheduled",
                                requested_at=due,
                                requested_by_account_id=actor_id)
    db.add(request)
    db.flush()
    row.followup_request_id = request.id


def process_due(session_factory):
    with session_factory() as db:
        ids = list(db.scalars(select(Kickoff.employee_id).where(
            Kickoff.collection_id.is_(None), Kickoff.last_error.is_(None), Kickoff.due_at <= dev.local_now())))
    for employee_id in ids:
        try:
            with session_factory() as db:
                launch(db, employee_id)
                db.commit()
        except Exception:
            logger.exception("Development kickoff failed: employee_id=%s", employee_id)
