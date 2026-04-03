from __future__ import annotations

import html
import re
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Optional

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from pytz import timezone as tz_get
from sqlalchemy.orm import Session

from .config import settings
from .employee_card import render_employee_card_png
from .flow_templates import EMPLOYEE_ROLE_VALUES
from .messaging.identity import get_primary_chat_id
from .messaging import as_messenger
from .models import Employee, EmployeeDocumentLink, EmployeeFile, FlowLaunchRequest, FlowStepTemplate, OnboardingEvent, ScenarioProgress, ScenarioTemplate, StepButtonNotification, SurveyAnswer
from .notifications import notify_hr_stage


CALLBACK_PREFIX = "scenario:"
RECRUITMENT_SCENARIO_KEY = "recruitment_hiring"
FIRST_DAY_SCENARIO_KEY = "first_day"
PROBATION_SCENARIO_KEYS = {"mid_probation", "end_probation"}
DOCUMENT_TAG_RE = re.compile(r"\{doc:([^}]+)\}")
SINGLE_STEP_REQUEST_PREFIX = "__single_step__:"
NOTIFICATION_SCOPE_TO_EMPLOYEE_FIELD = {
    "manager": "manager_telegram_id",
    "mentor_adaptation": "mentor_adaptation_telegram_id",
    "mentor_ipr": "mentor_ipr_telegram_id",
}


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


def get_chain_steps(db: Session, parent_step_id: int) -> list[FlowStepTemplate]:
    return (
        db.query(FlowStepTemplate)
        .filter(
            FlowStepTemplate.parent_step_id == parent_step_id,
            FlowStepTemplate.branch_option_index.is_(None),
        )
        .order_by(FlowStepTemplate.sort_order, FlowStepTemplate.id)
        .all()
    )


def get_first_chain_step(db: Session, parent_step_id: int) -> Optional[FlowStepTemplate]:
    return (
        db.query(FlowStepTemplate)
        .filter(
            FlowStepTemplate.parent_step_id == parent_step_id,
            FlowStepTemplate.branch_option_index.is_(None),
        )
        .order_by(FlowStepTemplate.sort_order, FlowStepTemplate.id)
        .first()
    )


def get_next_chain_step(db: Session, step: FlowStepTemplate) -> Optional[FlowStepTemplate]:
    if not step.parent_step_id or step.branch_option_index is not None:
        return None
    siblings = get_chain_steps(db, step.parent_step_id)
    for index, sibling in enumerate(siblings):
        if sibling.id == step.id:
            if index + 1 < len(siblings):
                return siblings[index + 1]
            return None
    return None


def get_next_step(db: Session, scenario_key: str, current_step: FlowStepTemplate) -> Optional[FlowStepTemplate]:
    steps = get_scenario_steps(db, scenario_key)
    for idx, step in enumerate(steps):
        if step.step_key == current_step.step_key:
            if idx + 1 < len(steps):
                return steps[idx + 1]
            return None
    return None


def resolve_followup_step(
    db: Session,
    scenario_key: str,
    current_step: FlowStepTemplate,
) -> Optional[FlowStepTemplate]:
    def resolve_after_parent(step: Optional[FlowStepTemplate]) -> Optional[FlowStepTemplate]:
        if not step:
            return None
        if step.parent_step_id and step.branch_option_index is None:
            next_chain_step = get_next_chain_step(db, step)
            if next_chain_step:
                return next_chain_step
            return resolve_after_parent(db.get(FlowStepTemplate, step.parent_step_id))
        if step.parent_step_id and step.branch_option_index is not None:
            parent_step = db.get(FlowStepTemplate, step.parent_step_id)
            if not parent_step:
                return None
            return get_next_step(db, scenario_key, parent_step)
        return get_next_step(db, scenario_key, step)

    if current_step.response_type == "chain":
        first_chain_step = get_first_chain_step(db, current_step.id)
        if first_chain_step:
            return first_chain_step

    if current_step.parent_step_id and current_step.branch_option_index is None:
        next_chain_step = get_next_chain_step(db, current_step)
        if next_chain_step:
            return next_chain_step
        return resolve_after_parent(db.get(FlowStepTemplate, current_step.parent_step_id))

    if current_step.parent_step_id and current_step.branch_option_index is not None:
        return resolve_after_parent(db.get(FlowStepTemplate, current_step.parent_step_id))

    return get_next_step(db, scenario_key, current_step)


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
        employee.employee_stage = "staff"


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


def format_message(db: Session, template: str, employee: Employee, anchor_date: date, step_time: Optional[str]) -> str:
    full_name_parts = (employee.full_name or "").strip().split()
    if len(full_name_parts) >= 2:
        name = full_name_parts[1]
    elif full_name_parts:
        name = full_name_parts[0]
    else:
        name = "коллега"
    full_name = (employee.full_name or "").strip() or "коллега"
    time_text = step_time or "10:00"
    links = (
        db.query(EmployeeDocumentLink)
        .filter(EmployeeDocumentLink.employee_id == employee.id)
        .all()
    )
    links_by_title = {(link.title or "").strip().lower(): link for link in links}

    def replace_document_tag(match: re.Match[str]) -> str:
        document_title = match.group(1).strip()
        if not document_title:
            return ""
        link = links_by_title.get(document_title.lower())
        if not link or not (link.url or "").strip():
            return document_title
        href = html.escape(link.url.strip(), quote=True)
        title = html.escape(link.title.strip() or document_title)
        return f'<a href="{href}">{title}</a>'

    rendered_template = DOCUMENT_TAG_RE.sub(replace_document_tag, template)
    return rendered_template.format(
        name=name,
        full_name=full_name,
        date=anchor_date.strftime("%d.%m.%Y"),
        time=time_text,
        test_url=settings.TEST_URL,
        practice_url=settings.PRACTICE_URL,
        tasks_url=settings.TASKS_URL,
        feedback_url=settings.FEEDBACK_URL,
    )


def _split_notification_recipients(value: Optional[str]) -> list[str]:
    recipients: list[str] = []
    for chunk in (value or "").replace("\n", ",").split(","):
        normalized = chunk.strip()
        if normalized and normalized not in recipients:
            recipients.append(normalized)
    return recipients


def resolve_notification_recipients(employee: Employee, explicit_ids: Optional[str], recipient_scope: Optional[str]) -> list[str]:
    recipients = _split_notification_recipients(explicit_ids)
    for scope_key in _split_notification_recipients(recipient_scope):
        employee_field = NOTIFICATION_SCOPE_TO_EMPLOYEE_FIELD.get(scope_key)
        if not employee_field:
            continue
        employee_chat_id = (getattr(employee, employee_field, None) or "").strip()
        if employee_chat_id and employee_chat_id not in recipients:
            recipients.append(employee_chat_id)
    return recipients


async def send_custom_notification(
    messenger_or_bot: Any,
    db: Session,
    employee: Employee,
    message_template: Optional[str],
    recipient_ids: Optional[str],
    recipient_scope: Optional[str],
    step_time: Optional[str],
) -> None:
    messenger = as_messenger(messenger_or_bot)
    recipients = resolve_notification_recipients(employee, recipient_ids, recipient_scope)
    message_template = (message_template or "").strip()
    if not recipients or not message_template:
        return
    anchor_date = datetime.now(_get_tz()).date()
    message_text = format_message(db, message_template, employee, anchor_date, step_time)
    if not message_text.strip():
        return
    for chat_id in recipients:
        try:
            await messenger.send_text(chat_id=chat_id, text=message_text)
        except Exception:
            continue


def get_button_notification(db: Session, step_id: int, option_index: int) -> Optional[StepButtonNotification]:
    return (
        db.query(StepButtonNotification)
        .filter(
            StepButtonNotification.step_id == step_id,
            StepButtonNotification.option_index == option_index,
        )
        .order_by(StepButtonNotification.id.asc())
        .first()
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


async def send_step_attachment(messenger_or_bot: Any, chat_id: str, step: FlowStepTemplate) -> None:
    messenger = as_messenger(messenger_or_bot)
    attachment_path = (getattr(step, "attachment_path", None) or "").strip()
    if not attachment_path:
        return
    path = Path(attachment_path)
    if not path.exists():
        return
    filename = getattr(step, "attachment_filename", None) or path.name
    if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}:
        await messenger.send_photo_path(chat_id=chat_id, path=path, filename=filename)
        return
    await messenger.send_document_path(chat_id=chat_id, path=path, filename=filename)


async def send_employee_card_image(messenger_or_bot: Any, chat_id: str, employee: Employee) -> None:
    messenger = as_messenger(messenger_or_bot)
    try:
        image_bytes = render_employee_card_png(employee)
    except ImportError:
        return
    await messenger.send_photo_bytes(chat_id=chat_id, data=image_bytes, filename=f"employee_card_{employee.id}.png")


async def send_step_buttons(messenger_or_bot: Any, chat_id: str, step: FlowStepTemplate) -> None:
    messenger = as_messenger(messenger_or_bot)
    reply_markup = step_reply_markup(step)
    if not reply_markup:
        return
    await messenger.send_text(
        chat_id=chat_id,
        text="Выберите вариант ответа:",
        reply_markup=reply_markup,
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


def _compute_followup_run_at(step: FlowStepTemplate) -> Optional[datetime]:
    if step.send_mode != "specific_time" or not (step.send_time or "").strip():
        return None
    try:
        hour, minute = [int(part) for part in step.send_time.strip().split(":", 1)]
    except ValueError:
        return None
    now = datetime.now()
    run_at = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if run_at <= now:
        return None
    return run_at


def queue_followup_step(db: Session, employee: Employee, scenario: ScenarioTemplate, step: FlowStepTemplate) -> bool:
    run_at = _compute_followup_run_at(step)
    if not run_at:
        return False
    db.add(
        FlowLaunchRequest(
            employee_id=employee.id,
            flow_key=scenario.scenario_key,
            requested_at=run_at,
            processed_at=None,
            launch_type="scheduled",
            skip_step_key=f"{SINGLE_STEP_REQUEST_PREFIX}{step.step_key}",
        )
    )
    db.commit()
    return True


async def send_step(
    messenger_or_bot: Any,
    db: Session,
    employee: Employee,
    scenario: ScenarioTemplate,
    step: FlowStepTemplate,
    scheduled_at: Optional[datetime] = None,
    auto_follow: bool = True,
) -> None:
    messenger = as_messenger(messenger_or_bot)
    chat_id = get_primary_chat_id(employee)
    if not chat_id:
        return

    anchor_date = scenario_anchor_date(employee, scenario) or datetime.now(_get_tz()).date()
    message_text = format_message(db, resolve_step_message_template(step), employee, anchor_date, step.send_time)
    has_attachment = bool((getattr(step, "attachment_path", None) or "").strip())
    send_employee_card = bool(getattr(step, "send_employee_card", False))
    reply_markup = step_reply_markup(step)
    inline_buttons_after_attachment = (has_attachment or send_employee_card) and reply_markup is not None

    if message_text.strip():
        await messenger.send_text(
            chat_id=chat_id,
            text=message_text,
            reply_markup=None if inline_buttons_after_attachment else reply_markup,
        )
    if send_employee_card:
        await send_employee_card_image(messenger, chat_id, employee)
    await send_step_attachment(messenger, chat_id, step)
    if inline_buttons_after_attachment:
        await send_step_buttons(messenger, chat_id, step)
    await send_custom_notification(
        messenger,
        db,
        employee,
        getattr(step, "notify_on_send_text", None),
        getattr(step, "notify_on_send_recipient_ids", None),
        getattr(step, "notify_on_send_recipient_scope", None),
        step.send_time,
    )

    progress = get_or_create_progress(db, employee.id, scenario.scenario_key)
    progress.current_step_key = step.step_key
    progress.waiting_for_response = step.response_type in {"text", "file", "buttons", "branching"}
    progress.updated_at = datetime.utcnow()

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

    if step.response_type == "launch_scenario" or not auto_follow:
        return

    if not progress.waiting_for_response:
        next_step = resolve_followup_step(db, scenario.scenario_key, step)
        if not next_step:
            progress.is_completed = True
            progress.completed_at = datetime.utcnow()
            progress.updated_at = datetime.utcnow()
            db.commit()
            try:
                await notify_hr_stage(messenger, employee, step.step_key)
            except Exception:
                pass
            return
        if settings.DEMO_MODE or next_step.send_mode == "immediate":
            await send_step(messenger, db, employee, scenario, next_step)
        else:
            if not queue_followup_step(db, employee, scenario, next_step):
                await send_step(messenger, db, employee, scenario, next_step)


async def advance_after_response(
    messenger_or_bot: Any,
    db: Session,
    employee: Employee,
    scenario: ScenarioTemplate,
    current_step: FlowStepTemplate,
) -> None:
    messenger = as_messenger(messenger_or_bot)
    progress = get_or_create_progress(db, employee.id, scenario.scenario_key)
    progress.waiting_for_response = False
    progress.updated_at = datetime.utcnow()
    next_step = resolve_followup_step(db, scenario.scenario_key, current_step)
    if not next_step:
        progress.is_completed = True
        progress.completed_at = datetime.utcnow()
        db.commit()
        return

    if settings.DEMO_MODE or next_step.send_mode == "immediate":
        db.commit()
        await send_step(messenger, db, employee, scenario, next_step)
        return

    if not queue_followup_step(db, employee, scenario, next_step):
        db.commit()
        await send_step(messenger, db, employee, scenario, next_step)


async def handle_text_response(messenger_or_bot: Any, db: Session, employee: Employee, message: Message) -> bool:
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
    await advance_after_response(messenger_or_bot, db, employee, scenario, step)
    return True


async def handle_button_response(messenger_or_bot: Any, db: Session, employee: Employee, scenario_key: str, step_key: str, option_index: int) -> bool:
    messenger = as_messenger(messenger_or_bot)
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
    button_notification = get_button_notification(db, step.id, option_index)
    if button_notification:
        await send_custom_notification(
            messenger,
            db,
            employee,
            button_notification.message_text,
            button_notification.recipient_ids,
            button_notification.recipient_scope,
            step.send_time,
        )
    employee.candidate_status = step.step_key
    db.commit()
    if step.target_field in {"personal_data_consent", "employee_data_consent"} and not getattr(employee, step.target_field):
        progress.waiting_for_response = False
        progress.is_completed = True
        progress.completed_at = datetime.utcnow()
        db.commit()
        try:
            await notify_hr_stage(messenger, employee, "recruitment_consent_no")
        except Exception:
            pass
        return True
    if step.response_type == "branching":
        branch_step = get_branch_step(db, step.id, option_index)
        if branch_step:
            if branch_step.response_type == "chain":
                await send_step(messenger, db, employee, scenario, branch_step, auto_follow=False)
                first_chain_step = get_first_chain_step(db, branch_step.id)
                if first_chain_step:
                    await send_step(messenger, db, employee, scenario, first_chain_step)
                return True

            await send_step(messenger, db, employee, scenario, branch_step)
            if branch_step.response_type == "launch_scenario" and branch_step.launch_scenario_key:
                progress.waiting_for_response = False
                progress.is_completed = True
                progress.completed_at = datetime.utcnow()
                progress.updated_at = datetime.utcnow()
                db.commit()
                await start_scenario(messenger, db, employee, branch_step.launch_scenario_key)
            return True
    await advance_after_response(messenger, db, employee, scenario, step)
    return True


async def handle_button_response_by_step_id(
    messenger_or_bot: Any,
    db: Session,
    employee: Employee,
    step_id: int,
    option_index: int,
) -> bool:
    step = db.get(FlowStepTemplate, step_id)
    if not step:
        return False
    return await handle_button_response(
        messenger_or_bot,
        db,
        employee,
        step.flow_key,
        step.step_key,
        option_index,
    )


async def handle_file_response(
    messenger_or_bot: Any,
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
    await advance_after_response(messenger_or_bot, db, employee, scenario, step)
    return True


async def start_scenario(messenger_or_bot: Any, db: Session, employee: Employee, scenario_key: str) -> bool:
    messenger = as_messenger(messenger_or_bot)
    scenario = db.query(ScenarioTemplate).filter(ScenarioTemplate.scenario_key == scenario_key).first()
    if not scenario or not matches_role_scope(employee, scenario):
        return False
    first_step = get_first_step(db, scenario_key)
    if not first_step:
        return False
    reset_progress(db, employee.id, scenario_key)
    db.commit()
    await send_step(messenger, db, employee, scenario, first_step)
    return True
