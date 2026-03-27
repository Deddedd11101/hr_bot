from __future__ import annotations

from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Optional

from aiogram import Bot
from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message
from pytz import timezone as tz_get
from sqlalchemy.orm import Session

from .config import settings
from .flow_templates import EMPLOYEE_ROLE_VALUES
from .models import Employee, EmployeeFile, FlowStepTemplate, OnboardingEvent, ScenarioProgress, ScenarioTemplate, SurveyAnswer
from .notifications import notify_hr_stage


CALLBACK_PREFIX = "scenario:"
RECRUITMENT_SCENARIO_KEY = "recruitment_hiring"
FIRST_DAY_SCENARIO_KEY = "first_day"
PROBATION_SCENARIO_KEYS = {"mid_probation", "end_probation"}


def get_scenario_steps(db: Session, scenario_key: str) -> list[FlowStepTemplate]:
    return (
        db.query(FlowStepTemplate)
        .filter(
            FlowStepTemplate.flow_key == scenario_key,
            FlowStepTemplate.parent_step_id.is_(None),
        )
        .order_by(FlowStepTemplate.sort_order, FlowStepTemplate.id)
        .all()
    )


def get_first_step(db: Session, scenario_key: str) -> Optional[FlowStepTemplate]:
    return (
        db.query(FlowStepTemplate)
        .filter(
            FlowStepTemplate.flow_key == scenario_key,
            FlowStepTemplate.parent_step_id.is_(None),
        )
        .order_by(FlowStepTemplate.sort_order, FlowStepTemplate.id)
        .first()
    )


def get_step_by_key(db: Session, scenario_key: str, step_key: str) -> Optional[FlowStepTemplate]:
    return (
        db.query(FlowStepTemplate)
        .filter(
            FlowStepTemplate.flow_key == scenario_key,
            FlowStepTemplate.step_key == step_key,
        )
        .first()
    )


def get_branch_steps(db: Session, parent_step_id: int) -> list[FlowStepTemplate]:
    return (
        db.query(FlowStepTemplate)
        .filter(FlowStepTemplate.parent_step_id == parent_step_id)
        .order_by(FlowStepTemplate.branch_option_index, FlowStepTemplate.id)
        .all()
    )


def get_branch_step(db: Session, parent_step_id: int, option_index: int) -> Optional[FlowStepTemplate]:
    return (
        db.query(FlowStepTemplate)
        .filter(
            FlowStepTemplate.parent_step_id == parent_step_id,
            FlowStepTemplate.branch_option_index == option_index,
        )
        .first()
    )


def get_next_step(db: Session, scenario_key: str, current_step: FlowStepTemplate) -> Optional[FlowStepTemplate]:
    steps = get_scenario_steps(db, scenario_key)
    for idx, step in enumerate(steps):
        if step.step_key == current_step.step_key:
            if idx + 1 < len(steps):
                return steps[idx + 1]
            return None
    return None


def resolve_step_message_template(step: FlowStepTemplate) -> str:
    custom_text = getattr(step, "custom_text", None)
    if custom_text is not None:
        return custom_text.strip()
    return step.default_text


def is_survey(scenario: Optional[ScenarioTemplate]) -> bool:
    return getattr(scenario, "scenario_kind", "scenario") == "survey"


def store_survey_answer(
    db: Session,
    employee: Employee,
    scenario: ScenarioTemplate,
    step: FlowStepTemplate,
    answer_value: Optional[str],
    file_name: Optional[str] = None,
) -> None:
    if not is_survey(scenario):
        return
    answer = (
        db.query(SurveyAnswer)
        .filter(
            SurveyAnswer.employee_id == employee.id,
            SurveyAnswer.scenario_key == scenario.scenario_key,
            SurveyAnswer.step_key == step.step_key,
        )
        .order_by(SurveyAnswer.id.desc())
        .first()
    )
    if not answer:
        answer = SurveyAnswer(
            employee_id=employee.id,
            scenario_key=scenario.scenario_key,
            step_key=step.step_key,
            answered_at=datetime.utcnow(),
        )
        db.add(answer)
    answer.answer_value = (answer_value or "").strip() or None
    answer.file_name = (file_name or "").strip() or None
    answer.answered_at = datetime.utcnow()


def apply_status_from_recruitment_choice(
    db: Session,
    employee: Employee,
    scenario: ScenarioTemplate,
    step: FlowStepTemplate,
    selected_value: str,
) -> None:
    if scenario.scenario_key != RECRUITMENT_SCENARIO_KEY or step.response_type != "branching":
        return
    first_step = get_first_step(db, scenario.scenario_key)
    if not first_step or first_step.step_key != step.step_key:
        return
    normalized = selected_value.strip().lower()
    if "кандидат" in normalized:
        employee.employee_stage = "candidate"
    elif "сотрудник" in normalized:
        employee.employee_stage = "employee"


def get_or_create_progress(db: Session, employee_id: int, scenario_key: str) -> ScenarioProgress:
    progress = (
        db.query(ScenarioProgress)
        .filter(
            ScenarioProgress.employee_id == employee_id,
            ScenarioProgress.scenario_key == scenario_key,
        )
        .first()
    )
    if progress:
        return progress
    now = datetime.utcnow()
    progress = ScenarioProgress(
        employee_id=employee_id,
        scenario_key=scenario_key,
        current_step_key=None,
        waiting_for_response=False,
        is_completed=False,
        started_at=now,
        updated_at=now,
        completed_at=None,
    )
    db.add(progress)
    db.flush()
    return progress


def reset_progress(db: Session, employee_id: int, scenario_key: str) -> ScenarioProgress:
    now = datetime.utcnow()
    progress = get_or_create_progress(db, employee_id, scenario_key)
    progress.current_step_key = None
    progress.waiting_for_response = False
    progress.is_completed = False
    progress.started_at = now
    progress.updated_at = now
    progress.completed_at = None
    return progress


def get_waiting_progress(db: Session, employee_id: int) -> Optional[ScenarioProgress]:
    return (
        db.query(ScenarioProgress)
        .filter(
            ScenarioProgress.employee_id == employee_id,
            ScenarioProgress.waiting_for_response.is_(True),
            ScenarioProgress.is_completed.is_(False),
        )
        .order_by(ScenarioProgress.updated_at.desc())
        .first()
    )


def get_waiting_progress_for_step(
    db: Session,
    employee_id: int,
    scenario_key: str,
    step_key: str,
) -> Optional[ScenarioProgress]:
    return (
        db.query(ScenarioProgress)
        .filter(
            ScenarioProgress.employee_id == employee_id,
            ScenarioProgress.scenario_key == scenario_key,
            ScenarioProgress.current_step_key == step_key,
            ScenarioProgress.waiting_for_response.is_(True),
            ScenarioProgress.is_completed.is_(False),
        )
        .order_by(ScenarioProgress.updated_at.desc())
        .first()
    )


def _get_tz():
    return tz_get(settings.TIMEZONE)


def _combine_date_time(value: date, hour: int, minute: int) -> datetime:
    tz = _get_tz()
    naive = datetime.combine(value, time(hour=hour, minute=minute))
    return tz.localize(naive)


def _is_workday(value: date) -> bool:
    return value.weekday() < 5


def add_workdays(start: date, days: int) -> date:
    if days == 0:
        return start
    current = start
    step = 1 if days > 0 else -1
    remaining = abs(days)
    while remaining > 0:
        current = current + timedelta(days=step)
        if _is_workday(current):
            remaining -= 1
    return current


def next_friday(value: date) -> date:
    return value + timedelta(days=(4 - value.weekday()) % 7)


def scenario_anchor_date(employee: Employee, scenario: ScenarioTemplate) -> Optional[date]:
    if scenario.trigger_mode == "bot_registration":
        return employee.created_at.date()
    if scenario.trigger_mode == "scenario_transition":
        return employee.created_at.date()
    if not employee.first_workday:
        return None
    if scenario.trigger_mode == "first_workday":
        return employee.first_workday
    if scenario.trigger_mode == "first_week_friday":
        return next_friday(employee.first_workday)
    if scenario.trigger_mode == "mid_probation":
        return add_workdays(employee.first_workday, settings.PROBATION_WORKDAYS // 2)
    if scenario.trigger_mode == "end_probation":
        return add_workdays(employee.first_workday, settings.PROBATION_WORKDAYS)
    return employee.first_workday


def matches_role_scope(employee: Employee, scenario: ScenarioTemplate) -> bool:
    if scenario.role_scope == "all":
        return True
    role_map = {
        "designer": "Дизайнер",
        "project_manager": "Project manager",
        "analyst": "Аналитик",
    }
    return (employee.desired_position or "") == role_map.get(scenario.role_scope, "")


def format_message(template: str, employee: Employee, anchor_date: date, step_time: Optional[str]) -> str:
    full_name_parts = (employee.full_name or "").strip().split()
    if len(full_name_parts) >= 2:
        name = full_name_parts[1]
    elif full_name_parts:
        name = full_name_parts[0]
    else:
        name = "коллега"
    full_name = (employee.full_name or "").strip() or "коллега"
    time_text = step_time or "10:00"
    return template.format(
        name=name,
        full_name=full_name,
        date=anchor_date.strftime("%d.%m.%Y"),
        time=time_text,
        test_url=settings.TEST_URL,
        practice_url=settings.PRACTICE_URL,
        tasks_url=settings.TASKS_URL,
        feedback_url=settings.FEEDBACK_URL,
    )


def step_reply_markup(step: FlowStepTemplate) -> Optional[InlineKeyboardMarkup]:
    if step.response_type not in {"buttons", "branching"} or not step.button_options:
        return None
    buttons = []
    for index, option in enumerate([item.strip() for item in step.button_options.splitlines() if item.strip()]):
        buttons.append(
            [
                InlineKeyboardButton(
                    text=option,
                    callback_data=f"{CALLBACK_PREFIX}{step.id}:{index}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None


async def send_step_attachment(bot: Bot, chat_id: str, step: FlowStepTemplate) -> None:
    attachment_path = (getattr(step, "attachment_path", None) or "").strip()
    if not attachment_path:
        return
    path = Path(attachment_path)
    if not path.exists():
        return
    await bot.send_document(
        chat_id=chat_id,
        document=FSInputFile(
            str(path),
            filename=getattr(step, "attachment_filename", None) or path.name,
        ),
    )


def is_terminal_step(db: Session, scenario_key: str, step_key: str) -> bool:
    steps = get_scenario_steps(db, scenario_key)
    if not steps:
        return False
    return steps[-1].step_key == step_key


def apply_response_to_employee(
    db: Session,
    employee: Employee,
    step: FlowStepTemplate,
    value: Optional[str],
    uploaded_file: Optional[EmployeeFile] = None,
) -> bool:
    target_field = (step.target_field or "").strip()
    if not target_field:
        return True

    normalized = (value or "").strip()
    if target_field == "full_name":
        employee.full_name = normalized or None
        return bool(normalized)
    if target_field == "desired_position":
        # Custom button values for a role should not block the scenario flow.
        employee.desired_position = normalized or None
        return True
    if target_field == "salary_expectation":
        employee.salary_expectation = normalized or None
        return bool(normalized)
    if target_field == "candidate_status":
        employee.candidate_status = normalized or None
        return bool(normalized)
    if target_field in {"personal_data_consent", "employee_data_consent"}:
        answer = normalized.lower()
        consent = answer in {
            "да",
            "да, согласен",
            "согласен",
            "ознакомлен, согласен",
            "ознакомлен и согласен",
            "yes",
            "true",
            "1",
        }
        setattr(employee, target_field, consent)
        if not consent:
            employee.candidate_status = "declined"
        return True
    if target_field in {"resume", "candidate_file"}:
        return uploaded_file is not None
    return True


async def send_step(
    bot: Bot,
    db: Session,
    employee: Employee,
    scenario: ScenarioTemplate,
    step: FlowStepTemplate,
    scheduled_at: Optional[datetime] = None,
) -> None:
    if not employee.telegram_user_id:
        return

    anchor_date = scenario_anchor_date(employee, scenario) or datetime.now(_get_tz()).date()
    message_text = format_message(resolve_step_message_template(step), employee, anchor_date, step.send_time)
    if message_text.strip():
        await bot.send_message(
            chat_id=employee.telegram_user_id,
            text=message_text,
            reply_markup=step_reply_markup(step),
        )
    await send_step_attachment(bot, employee.telegram_user_id, step)

    progress = get_or_create_progress(db, employee.id, scenario.scenario_key)
    progress.current_step_key = step.step_key
    progress.waiting_for_response = step.response_type in {"text", "file", "buttons", "branching"}
    progress.updated_at = datetime.utcnow()
    if not progress.waiting_for_response and is_terminal_step(db, scenario.scenario_key, step.step_key):
        progress.is_completed = True
        progress.completed_at = datetime.utcnow()

    db.add(
        OnboardingEvent(
            employee_id=employee.id,
            scheduled_at=scheduled_at or datetime.utcnow(),
            sent_at=datetime.utcnow(),
            event_key=step.step_key,
            message=message_text,
        )
    )
    db.commit()

    if is_terminal_step(db, scenario.scenario_key, step.step_key):
        try:
            await notify_hr_stage(bot, employee, step.step_key)
        except Exception:
            pass
    elif not progress.waiting_for_response:
        next_step = get_next_step(db, scenario.scenario_key, step)
        if next_step and (next_step.send_mode == "immediate" or settings.DEMO_MODE):
            await send_step(bot, db, employee, scenario, next_step)


async def advance_after_response(
    bot: Bot,
    db: Session,
    employee: Employee,
    scenario: ScenarioTemplate,
    current_step: FlowStepTemplate,
) -> None:
    progress = get_or_create_progress(db, employee.id, scenario.scenario_key)
    progress.waiting_for_response = False
    progress.updated_at = datetime.utcnow()

    step_for_next = current_step
    if current_step.parent_step_id:
        parent_step = db.get(FlowStepTemplate, current_step.parent_step_id)
        if parent_step:
            step_for_next = parent_step

    next_step = get_next_step(db, scenario.scenario_key, step_for_next)
    if not next_step:
        progress.is_completed = True
        progress.completed_at = datetime.utcnow()
        db.commit()
        return

    if next_step.send_mode == "immediate" or settings.DEMO_MODE:
        db.commit()
        await send_step(bot, db, employee, scenario, next_step)
        return

    db.commit()


async def send_branch_step_message(
    bot: Bot,
    db: Session,
    employee: Employee,
    scenario: ScenarioTemplate,
    parent_step: FlowStepTemplate,
    branch_step: FlowStepTemplate,
) -> None:
    if not employee.telegram_user_id:
        return
    anchor_date = scenario_anchor_date(employee, scenario) or datetime.now(_get_tz()).date()
    message_text = format_message(resolve_step_message_template(branch_step), employee, anchor_date, branch_step.send_time)
    if message_text.strip():
        await bot.send_message(
            chat_id=employee.telegram_user_id,
            text=message_text,
            reply_markup=step_reply_markup(branch_step),
        )
    await send_step_attachment(bot, employee.telegram_user_id, branch_step)

    progress = get_or_create_progress(db, employee.id, scenario.scenario_key)
    progress.current_step_key = branch_step.step_key
    progress.waiting_for_response = branch_step.response_type in {"text", "file", "buttons"}
    progress.updated_at = datetime.utcnow()
    db.add(
        OnboardingEvent(
            employee_id=employee.id,
            scheduled_at=datetime.utcnow(),
            sent_at=datetime.utcnow(),
            event_key=branch_step.step_key,
            message=message_text,
        )
    )
    db.commit()
    if branch_step.response_type == "launch_scenario":
        progress.waiting_for_response = False
        progress.is_completed = True
        progress.completed_at = datetime.utcnow()
        progress.updated_at = datetime.utcnow()
        db.commit()
        if branch_step.launch_scenario_key:
            await start_scenario(bot, db, employee, branch_step.launch_scenario_key)
        return
    if not progress.waiting_for_response:
        await advance_after_response(bot, db, employee, scenario, parent_step)


async def handle_text_response(bot: Bot, db: Session, employee: Employee, message: Message) -> bool:
    progress = get_waiting_progress(db, employee.id)
    if not progress or not progress.current_step_key:
        return False
    scenario = db.query(ScenarioTemplate).filter(ScenarioTemplate.scenario_key == progress.scenario_key).first()
    if not scenario:
        return False
    step = get_step_by_key(db, scenario.scenario_key, progress.current_step_key)
    if not step or step.response_type != "text":
        return False
    store_survey_answer(db, employee, scenario, step, message.text)
    if not apply_response_to_employee(db, employee, step, message.text):
        return False
    employee.candidate_status = step.step_key
    db.commit()
    await advance_after_response(bot, db, employee, scenario, step)
    return True


async def handle_button_response(bot: Bot, db: Session, employee: Employee, scenario_key: str, step_key: str, option_index: int) -> bool:
    progress = get_waiting_progress_for_step(db, employee.id, scenario_key, step_key)
    if not progress:
        return False
    scenario = db.query(ScenarioTemplate).filter(ScenarioTemplate.scenario_key == scenario_key).first()
    step = get_step_by_key(db, scenario_key, step_key) if scenario else None
    if not scenario or not step or step.response_type not in {"buttons", "branching"}:
        return False
    options = [item.strip() for item in (step.button_options or "").splitlines() if item.strip()]
    if option_index < 0 or option_index >= len(options):
        return False
    selected_value = options[option_index]
    store_survey_answer(db, employee, scenario, step, selected_value)
    if not apply_response_to_employee(db, employee, step, selected_value):
        return False
    apply_status_from_recruitment_choice(db, employee, scenario, step, selected_value)
    employee.candidate_status = step.step_key
    db.commit()
    if step.target_field in {"personal_data_consent", "employee_data_consent"} and not getattr(employee, step.target_field):
        progress.waiting_for_response = False
        progress.is_completed = True
        progress.completed_at = datetime.utcnow()
        db.commit()
        try:
            await notify_hr_stage(bot, employee, "recruitment_consent_no")
        except Exception:
            pass
        return True
    if step.response_type == "branching":
        branch_step = get_branch_step(db, step.id, option_index)
        if branch_step:
            await send_branch_step_message(bot, db, employee, scenario, step, branch_step)
            return True
    await advance_after_response(bot, db, employee, scenario, step)
    return True


async def handle_button_response_by_step_id(
    bot: Bot,
    db: Session,
    employee: Employee,
    step_id: int,
    option_index: int,
) -> bool:
    step = db.get(FlowStepTemplate, step_id)
    if not step:
        return False
    return await handle_button_response(
        bot,
        db,
        employee,
        step.flow_key,
        step.step_key,
        option_index,
    )


async def handle_file_response(
    bot: Bot,
    db: Session,
    employee: Employee,
    uploaded_file: EmployeeFile,
) -> bool:
    progress = get_waiting_progress(db, employee.id)
    if not progress or not progress.current_step_key:
        return False
    scenario = db.query(ScenarioTemplate).filter(ScenarioTemplate.scenario_key == progress.scenario_key).first()
    if not scenario:
        return False
    step = get_step_by_key(db, scenario.scenario_key, progress.current_step_key)
    if not step or step.response_type != "file":
        return False
    store_survey_answer(db, employee, scenario, step, uploaded_file.original_filename, uploaded_file.original_filename)
    if step.target_field == "resume":
        uploaded_file.category = "resume"
    if not apply_response_to_employee(db, employee, step, uploaded_file.original_filename, uploaded_file):
        return False
    employee.candidate_status = step.step_key
    db.commit()
    await advance_after_response(bot, db, employee, scenario, step)
    return True


async def start_scenario(bot: Bot, db: Session, employee: Employee, scenario_key: str) -> bool:
    scenario = db.query(ScenarioTemplate).filter(ScenarioTemplate.scenario_key == scenario_key).first()
    if not scenario or not matches_role_scope(employee, scenario):
        return False
    first_step = get_first_step(db, scenario_key)
    if not first_step:
        return False
    if scenario_key == FIRST_DAY_SCENARIO_KEY:
        employee.employee_stage = "first_day"
    elif scenario_key in PROBATION_SCENARIO_KEYS:
        employee.employee_stage = "probation"
    reset_progress(db, employee.id, scenario_key)
    db.commit()
    await send_step(bot, db, employee, scenario, first_step)
    return True
