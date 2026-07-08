from __future__ import annotations

from datetime import date
from datetime import datetime, time, timedelta
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pytz import timezone as tz_get
from sqlalchemy.orm import Session

from .config import settings
from .database import SessionLocal
from .mass_targeting import (
    deserialize_target_values,
    mass_target_employee_query,
)
from .messaging import as_messenger
from .messaging.identity import get_primary_chat_id
from .models import Employee, FlowLaunchRequest, FlowStepTemplate, MassMessageAction, MassScenarioAction, OnboardingEvent, ScenarioTemplate
from .scenario_engine import SINGLE_STEP_REQUEST_PREFIX, add_workdays, format_message, get_scenario_steps, get_step_by_key, matches_role_scope, scenario_anchor_date, send_step, start_scenario
from .time_utils import utc_now


def _get_tz():
    return tz_get(settings.TIMEZONE)


def _load_all_employees(db: Session) -> list[Employee]:
    return list(db.query(Employee).all())


def _load_pending_flow_requests(db: Session) -> list[FlowLaunchRequest]:
    now = datetime.now()
    return list(
        db.query(FlowLaunchRequest)
        .filter(
            FlowLaunchRequest.processed_at.is_(None),
            FlowLaunchRequest.requested_at <= now,
        )
        .all()
    )


def _load_pending_mass_scenario_actions(db: Session) -> list[MassScenarioAction]:
    now = datetime.now()
    return list(
        db.query(MassScenarioAction)
        .filter(
            MassScenarioAction.processed_at.is_(None),
            MassScenarioAction.launch_type == "scheduled",
            MassScenarioAction.requested_at <= now,
        )
        .all()
    )


def _load_pending_mass_message_actions(db: Session) -> list[MassMessageAction]:
    now = datetime.now()
    return list(
        db.query(MassMessageAction)
        .filter(
            MassMessageAction.processed_at.is_(None),
            MassMessageAction.launch_type == "scheduled",
            MassMessageAction.requested_at <= now,
        )
        .all()
    )


def _load_scenarios(db: Session) -> list[ScenarioTemplate]:
    return list(db.query(ScenarioTemplate).all())


def _mass_target_employees(
    db: Session,
    target_all: bool,
    target_employee_stages: list[str],
    target_candidate_stages: list[str],
    target_employee_id: Optional[int] = None,
    target_role_scope: Optional[str] = None,
    legacy_target_statuses: Optional[list[str]] = None,
) -> list[Employee]:
    return (
        mass_target_employee_query(
            db,
            target_all=target_all,
            target_employee_stages=target_employee_stages,
            target_candidate_stages=target_candidate_stages,
            target_employee_id=target_employee_id,
            target_role_scope=target_role_scope,
            legacy_target_statuses=legacy_target_statuses,
        )
        .order_by(Employee.id.asc())
        .all()
    )


async def _send_mass_message(db: Session, bot, employee: Employee, message_text: str, requested_at: datetime) -> bool:
    if employee.is_bot_blocked:
        return False
    messenger = as_messenger(bot)
    chat_id = get_primary_chat_id(employee, db=db)
    if not chat_id:
        return False
    rendered_text = format_message(db, message_text, employee, requested_at.date(), requested_at.strftime("%H:%M")).strip()
    if not rendered_text:
        return False
    await messenger.send_text(chat_id=chat_id, text=rendered_text)
    return True


def _load_sent_event_keys(db: Session, employee_id: int) -> set[str]:
    events = db.query(OnboardingEvent.event_key).filter(OnboardingEvent.employee_id == employee_id).all()
    return {row[0] for row in events}


def _scenario_has_sent_steps(steps: list[FlowStepTemplate], sent_keys: set[str]) -> bool:
    scenario_step_keys = {step.step_key for step in steps}
    return any(step_key in sent_keys for step_key in scenario_step_keys)


def _compute_step_run_at(anchor_date, step: FlowStepTemplate, manual: bool) -> Optional[datetime]:
    tz = _get_tz()
    if settings.DEMO_MODE or manual:
        return None

    event_date = add_workdays(anchor_date, step.day_offset_workdays)
    if step.send_time:
        try:
            hour, minute = [int(part) for part in step.send_time.split(":", 1)]
        except ValueError:
            hour, minute = 10, 0
    else:
        hour, minute = 10, 0

    return tz.localize(datetime.combine(event_date, time(hour=hour, minute=minute)))


async def run_scheduled_step(bot, employee_id: int, scenario_key: str, step_key: str, scheduled_at: datetime) -> None:
    with SessionLocal() as db:
        employee = db.get(Employee, employee_id)
        scenario = db.query(ScenarioTemplate).filter(ScenarioTemplate.scenario_key == scenario_key).first()
        step = (
            db.query(FlowStepTemplate)
            .filter(
                FlowStepTemplate.flow_key == scenario_key,
                FlowStepTemplate.step_key == step_key,
            )
            .first()
        )
        if not employee or not scenario or not step:
            return
        if employee.is_bot_blocked:
            return
        if not matches_role_scope(employee, scenario):
            return
        if (
            scenario.trigger_mode not in {"manual_only", "bot_registration", "scenario_transition"}
            and not scenario_anchor_date(employee, scenario)
        ):
            return
        if not get_primary_chat_id(employee, db=db):
            return
        await send_step(bot, db, employee, scenario, step, scheduled_at=scheduled_at)


def schedule_employee_scenario(
    db: Session,
    scheduler: AsyncIOScheduler,
    bot,
    employee: Employee,
    scenario: ScenarioTemplate,
    sent_keys: set[str],
    manual: bool,
    skip_step_key: Optional[str] = None,
    now: Optional[datetime] = None,
) -> None:
    if employee.is_bot_blocked:
        return
    if not matches_role_scope(employee, scenario):
        return

    anchor_date = scenario_anchor_date(employee, scenario)
    if not anchor_date:
        return

    steps = get_scenario_steps(db, scenario.scenario_key)
    if not steps:
        return

    now = now or datetime.now(_get_tz())
    if settings.DEMO_MODE or manual:
        step_interval = timedelta(minutes=settings.DEMO_STEP_MINUTES if settings.DEMO_MODE else settings.MANUAL_STEP_MINUTES)
        run_at = now if manual else now + step_interval
        planned_steps = steps
        if any(step.response_type in {"text", "file", "buttons"} for step in steps):
            planned_steps = steps[:1]
        for step in planned_steps:
            if manual and skip_step_key and step.step_key == skip_step_key:
                run_at = run_at + step_interval
                continue
            if not manual and step.step_key in sent_keys:
                continue
            job_id = f"employee-{employee.id}-{scenario.scenario_key}-{step.step_key}"
            if not manual and scheduler.get_job(job_id):
                continue
            scheduler.add_job(
                run_scheduled_step,
                "date",
                run_date=run_at,
                args=[bot, employee.id, scenario.scenario_key, step.step_key, run_at],
                id=job_id,
                replace_existing=manual,
            )
            run_at = run_at + step_interval
        return

    scenario_has_sent_steps = _scenario_has_sent_steps(steps, sent_keys)
    scheduled_same_day_catchup = False
    for step in steps:
        if step.step_key in sent_keys:
            continue
        run_at = _compute_step_run_at(anchor_date, step, manual=False)
        if not run_at:
            continue
        if run_at < now - timedelta(minutes=1):
            should_send_first_unsent_now = (
                not scenario_has_sent_steps
                and not scheduled_same_day_catchup
                and anchor_date == now.date()
            )
            if not should_send_first_unsent_now:
                continue
            run_at = now
            scheduled_same_day_catchup = True
        job_id = f"employee-{employee.id}-{scenario.scenario_key}-{step.step_key}"
        if scheduler.get_job(job_id):
            continue
        scheduler.add_job(
            run_scheduled_step,
            "date",
            run_date=run_at,
            args=[bot, employee.id, scenario.scenario_key, step.step_key, run_at],
            id=job_id,
            replace_existing=False,
        )


async def schedule_all_employees(scheduler: AsyncIOScheduler, bot) -> None:
    with SessionLocal() as db:
        employees = _load_all_employees(db)
        scenarios = _load_scenarios(db)
        scheduled_scenarios = [
            scenario for scenario in scenarios if scenario.trigger_mode not in {"manual_only", "bot_registration", "scenario_transition"}
        ]

        for employee in employees:
            if employee.is_bot_blocked:
                continue
            sent_keys = _load_sent_event_keys(db, employee.id)
            for scenario in scheduled_scenarios:
                schedule_employee_scenario(db, scheduler, bot, employee, scenario, sent_keys, manual=False)
            if scheduled_scenarios:
                employee.is_flow_scheduled = True

        pending_mass_scenario_actions = _load_pending_mass_scenario_actions(db)
        for action in pending_mass_scenario_actions:
            scenario = db.query(ScenarioTemplate).filter(ScenarioTemplate.scenario_key == action.flow_key).first()
            if not scenario or getattr(scenario, "scenario_kind", "scenario") != getattr(action, "scenario_kind", "scenario"):
                action.processed_at = utc_now()
                continue
            recipients = _mass_target_employees(
                db,
                action.target_all,
                deserialize_target_values(getattr(action, "target_employee_stages", None), kind="employee"),
                deserialize_target_values(getattr(action, "target_candidate_stages", None), kind="candidate"),
                getattr(action, "target_employee_id", None),
                getattr(action, "target_role_scope", None),
                deserialize_target_values(action.target_statuses, kind="legacy"),
            )
            started_count = 0
            for employee in recipients:
                if not get_primary_chat_id(employee, db=db):
                    continue
                if not matches_role_scope(employee, scenario):
                    continue
                started = await start_scenario(bot, db, employee, scenario.scenario_key)
                if started:
                    started_count += 1
            action.recipient_count = started_count
            action.processed_at = utc_now()

        pending_mass_message_actions = _load_pending_mass_message_actions(db)
        for action in pending_mass_message_actions:
            recipients = _mass_target_employees(
                db,
                action.target_all,
                deserialize_target_values(getattr(action, "target_employee_stages", None), kind="employee"),
                deserialize_target_values(getattr(action, "target_candidate_stages", None), kind="candidate"),
                getattr(action, "target_employee_id", None),
                getattr(action, "target_role_scope", None),
                deserialize_target_values(action.target_statuses, kind="legacy"),
            )
            sent_count = 0
            for employee in recipients:
                if await _send_mass_message(db, bot, employee, action.message_text, action.requested_at):
                    sent_count += 1
            action.recipient_count = sent_count
            action.processed_at = utc_now()

        pending_requests = _load_pending_flow_requests(db)
        for request in pending_requests:
            employee = db.get(Employee, request.employee_id)
            scenario = db.query(ScenarioTemplate).filter(ScenarioTemplate.scenario_key == request.flow_key).first()
            if not employee or not scenario:
                request.processed_at = utc_now()
                continue
            if employee.is_bot_blocked:
                request.processed_at = utc_now()
                continue
            if not matches_role_scope(employee, scenario):
                request.processed_at = utc_now()
                continue
            if (
                scenario.trigger_mode not in {"manual_only", "bot_registration", "scenario_transition"}
                and not scenario_anchor_date(employee, scenario)
            ):
                request.processed_at = utc_now()
                continue
            if not get_primary_chat_id(employee, db=db):
                continue
            if request.skip_step_key and request.skip_step_key.startswith(SINGLE_STEP_REQUEST_PREFIX):
                step_key = request.skip_step_key[len(SINGLE_STEP_REQUEST_PREFIX):]
                step = get_step_by_key(db, scenario.scenario_key, step_key)
                if step:
                    await send_step(bot, db, employee, scenario, step, scheduled_at=request.requested_at)
                request.processed_at = utc_now()
                continue
            sent_keys = _load_sent_event_keys(db, employee.id)
            schedule_employee_scenario(
                db,
                scheduler,
                bot,
                employee,
                scenario,
                sent_keys,
                manual=True,
                skip_step_key=request.skip_step_key,
            )
            request.processed_at = utc_now()

        if employees or pending_requests:
            db.commit()


