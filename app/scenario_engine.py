from __future__ import annotations

import calendar
import html
import json
import logging
import re
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Literal, NamedTuple, Optional

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, Message, ReplyKeyboardMarkup
from pytz import timezone as tz_get
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .config import settings
from .employee_card import render_employee_card_png
from .messaging import as_messenger, find_employee_by_channel_user_id
from .messaging.identity import get_primary_chat_id
from .models import Employee, EmployeeDocumentLink, EmployeeFile, FlowLaunchRequest, FlowStepTemplate, HrSettings, OnboardingEvent, ScenarioProgress, ScenarioTemplate, StepButtonNotification, StepSendNotification, SurveyAnswer
from .notifications import notify_hr_stage
from .positions import position_matches_scope
from .time_utils import utc_now


logger = logging.getLogger(__name__)


CALLBACK_PREFIX = "scenario:"
BACK_CALLBACK_DATA = f"{CALLBACK_PREFIX}back"
DATE_CALLBACK_PREFIX = f"{CALLBACK_PREFIX}date:"
SCENARIO_BACK_BUTTON_TEXT = "Назад"
RECRUITMENT_SCENARIO_KEY = "recruitment_hiring"
FIRST_DAY_SCENARIO_KEY = "first_day"
PROBATION_SCENARIO_KEYS = {"mid_probation", "end_probation"}
DOCUMENT_TAG_RE = re.compile(r"\{doc:([^}]+)\}")
SINGLE_STEP_REQUEST_PREFIX = "__single_step__:"
INTERACTIVE_RESPONSE_TYPES = {"text", "date", "file", "buttons", "branching"}
DATE_WEEKDAY_LABELS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
DATE_MONTH_LABELS = [
    "Январь",
    "Февраль",
    "Март",
    "Апрель",
    "Май",
    "Июнь",
    "Июль",
    "Август",
    "Сентябрь",
    "Октябрь",
    "Ноябрь",
    "Декабрь",
]
NOTIFICATION_SCOPE_TO_EMPLOYEE_FIELD = {
    "manager": ("manager_employee_id", "manager_telegram_id"),
    "mentor_adaptation": ("mentor_adaptation_employee_id", "mentor_adaptation_telegram_id"),
    "mentor_ipr": ("mentor_ipr_employee_id", "mentor_ipr_telegram_id"),
}
RECIPIENT_MODE_SELF = "self"
RECIPIENT_MODE_MANAGER = "manager"
RECIPIENT_MODE_MENTOR_ADAPTATION = "mentor_adaptation"
RECIPIENT_MODE_MENTOR_IPR = "mentor_ipr"
RECIPIENT_MODE_HR = "hr"
SCENARIO_RECIPIENT_MODES = {
    RECIPIENT_MODE_SELF,
    RECIPIENT_MODE_MANAGER,
    RECIPIENT_MODE_MENTOR_ADAPTATION,
    RECIPIENT_MODE_MENTOR_IPR,
    RECIPIENT_MODE_HR,
}


class DateCallbackResult(NamedTuple):
    handled: bool
    action: Literal["noop", "updated", "selected"]
    reply_markup: InlineKeyboardMarkup | None = None


class ScenarioRecipientResolution(NamedTuple):
    mode: str
    employee_id: int | None
    chat_id: str | None
    label: str
    error: str | None = None


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


def get_root_step_by_key(db: Session, scenario_key: str, step_key: str) -> Optional[FlowStepTemplate]:
    return (
        db.query(FlowStepTemplate)
        .filter(
            FlowStepTemplate.flow_key == scenario_key,
            FlowStepTemplate.step_key == step_key,
            FlowStepTemplate.parent_step_id.is_(None),
        )
        .first()
    )


def get_root_ancestor_step(db: Session, step: FlowStepTemplate | None) -> Optional[FlowStepTemplate]:
    current = step
    while current and current.parent_step_id is not None:
        current = db.get(FlowStepTemplate, current.parent_step_id)
    return current


def resolve_branch_return_step(
    db: Session,
    scenario_key: str,
    branch_step: FlowStepTemplate | None,
) -> Optional[FlowStepTemplate]:
    if not branch_step:
        return None
    target_step_key = (getattr(branch_step, "return_to_step_key", None) or "").strip()
    if not target_step_key:
        return None
    target_step = get_root_step_by_key(db, scenario_key, target_step_key)
    if not target_step:
        return None
    branch_root = get_root_ancestor_step(db, branch_step)
    if branch_root and branch_root.step_key == target_step.step_key:
        return None
    return target_step


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
            branch_return_step = resolve_branch_return_step(db, scenario_key, step)
            if branch_return_step:
                return branch_return_step
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
        branch_return_step = resolve_branch_return_step(db, scenario_key, current_step)
        if branch_return_step:
            return branch_return_step
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
            answered_at=utc_now(),
        )
        db.add(answer)
    answer.answer_value = (answer_value or "").strip() or None
    answer.file_name = (file_name or "").strip() or None
    answer.answered_at = utc_now()


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
    now = utc_now()
    progress = ScenarioProgress(
        employee_id=employee_id,
        scenario_key=scenario_key,
        recipient_mode=RECIPIENT_MODE_SELF,
        recipient_employee_id=employee_id,
        recipient_chat_id=None,
        current_step_key=None,
        step_history=None,
        response_undo_history=None,
        waiting_for_response=False,
        is_completed=False,
        last_delivery_error=None,
        started_at=now,
        updated_at=now,
        completed_at=None,
    )
    db.add(progress)
    db.flush()
    return progress


def reset_progress(db: Session, employee_id: int, scenario_key: str) -> ScenarioProgress:
    now = utc_now()
    progress = get_or_create_progress(db, employee_id, scenario_key)
    progress.current_step_key = None
    progress.recipient_mode = RECIPIENT_MODE_SELF
    progress.recipient_employee_id = employee_id
    progress.recipient_chat_id = None
    progress.step_history = None
    progress.response_undo_history = None
    progress.waiting_for_response = False
    progress.is_completed = False
    progress.last_delivery_error = None
    progress.started_at = now
    progress.updated_at = now
    progress.completed_at = None
    return progress


def get_waiting_progress(db: Session, employee_id: int) -> Optional[ScenarioProgress]:
    return (
        db.query(ScenarioProgress)
        .filter(
            or_(
                ScenarioProgress.recipient_employee_id == employee_id,
                (
                    ScenarioProgress.recipient_employee_id.is_(None)
                    & (ScenarioProgress.employee_id == employee_id)
                ),
            ),
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
            or_(
                ScenarioProgress.recipient_employee_id == employee_id,
                (
                    ScenarioProgress.recipient_employee_id.is_(None)
                    & (ScenarioProgress.employee_id == employee_id)
                ),
            ),
            ScenarioProgress.scenario_key == scenario_key,
            ScenarioProgress.current_step_key == step_key,
            ScenarioProgress.waiting_for_response.is_(True),
            ScenarioProgress.is_completed.is_(False),
        )
        .order_by(ScenarioProgress.updated_at.desc())
        .first()
    )


def _normalize_recipient_mode(value: str | None) -> str:
    normalized = (value or "").strip()
    return normalized if normalized in SCENARIO_RECIPIENT_MODES else RECIPIENT_MODE_SELF


def _scenario_recipient_mode(scenario: ScenarioTemplate) -> str:
    configured = _normalize_recipient_mode(getattr(scenario, "recipient_mode", None))
    if getattr(scenario, "trigger_mode", None) == "manager_assigned_adaptation" and configured == RECIPIENT_MODE_SELF:
        return RECIPIENT_MODE_MANAGER
    return configured


def _resolve_related_recipient_employee(db: Session, employee: Employee, relation_field: str) -> Employee | None:
    related_employee_id = getattr(employee, relation_field, None)
    if not related_employee_id:
        return None
    return db.get(Employee, related_employee_id)


def resolve_scenario_recipient(
    db: Session,
    employee: Employee,
    scenario: ScenarioTemplate,
    *,
    requires_response: bool,
) -> ScenarioRecipientResolution:
    mode = _scenario_recipient_mode(scenario)
    if mode == RECIPIENT_MODE_SELF:
        chat_id = get_primary_chat_id(employee, db=db)
        if not chat_id:
            return ScenarioRecipientResolution(mode, employee.id, None, employee.full_name or f"Employee #{employee.id}", "У получателя не привязан Telegram.")
        return ScenarioRecipientResolution(mode, employee.id, chat_id, employee.full_name or f"Employee #{employee.id}")

    if mode == RECIPIENT_MODE_MANAGER:
        recipient = _resolve_related_recipient_employee(db, employee, "manager_employee_id")
    elif mode == RECIPIENT_MODE_MENTOR_ADAPTATION:
        recipient = _resolve_related_recipient_employee(db, employee, "mentor_adaptation_employee_id")
    elif mode == RECIPIENT_MODE_MENTOR_IPR:
        recipient = _resolve_related_recipient_employee(db, employee, "mentor_ipr_employee_id")
    else:
        recipient = None

    if mode in {RECIPIENT_MODE_MANAGER, RECIPIENT_MODE_MENTOR_ADAPTATION, RECIPIENT_MODE_MENTOR_IPR}:
        if recipient is None:
            return ScenarioRecipientResolution(mode, None, None, mode, "Получатель не назначен в карточке сотрудника.")
        chat_id = get_primary_chat_id(recipient, db=db)
        if not chat_id:
            return ScenarioRecipientResolution(mode, recipient.id, None, recipient.full_name or f"Employee #{recipient.id}", "У получателя не привязан Telegram.")
        return ScenarioRecipientResolution(mode, recipient.id, chat_id, recipient.full_name or f"Employee #{recipient.id}")

    hr_settings = db.get(HrSettings, 1)
    hr_chat_id = (getattr(hr_settings, "telegram_user_id", None) or "").strip()
    hr_label = (getattr(hr_settings, "hr_name", None) or "").strip() or "HR"
    if not hr_chat_id:
        return ScenarioRecipientResolution(mode, None, None, hr_label, "В HR-настройках не указан Telegram user id.")
    hr_employee = find_employee_by_channel_user_id(db, channel="telegram", external_user_id=hr_chat_id)
    if requires_response and hr_employee is None:
        return ScenarioRecipientResolution(
            mode,
            None,
            hr_chat_id,
            hr_label,
            "HR-адресат не связан с карточкой сотрудника, поэтому интерактивный шаг не сможет принять ответ.",
        )
    return ScenarioRecipientResolution(mode, hr_employee.id if hr_employee else None, hr_chat_id, hr_label)


def _store_progress_recipient(progress: ScenarioProgress, resolution: ScenarioRecipientResolution) -> None:
    progress.recipient_mode = resolution.mode
    progress.recipient_employee_id = resolution.employee_id
    progress.recipient_chat_id = resolution.chat_id


def _mark_delivery_failure(
    db: Session,
    progress: ScenarioProgress,
    employee: Employee,
    scenario: ScenarioTemplate,
    step: FlowStepTemplate,
    resolution: ScenarioRecipientResolution,
) -> None:
    _store_progress_recipient(progress, resolution)
    progress.current_step_key = step.step_key
    progress.waiting_for_response = False
    progress.is_completed = False
    progress.last_delivery_error = resolution.error
    progress.updated_at = utc_now()
    db.commit()
    logger.warning(
        "Scenario delivery skipped: scenario=%s step=%s subject_employee_id=%s recipient_mode=%s recipient_employee_id=%s error=%s",
        scenario.scenario_key,
        step.step_key,
        employee.id,
        resolution.mode,
        resolution.employee_id,
        resolution.error,
    )


def step_requires_response(step: FlowStepTemplate | None) -> bool:
    if not step:
        return False
    return step.response_type in INTERACTIVE_RESPONSE_TYPES


def _deserialize_step_history(progress: ScenarioProgress) -> list[str]:
    raw_value = (progress.step_history or "").strip()
    if not raw_value:
        return []
    result: list[str] = []
    for line in raw_value.splitlines():
        step_key = line.strip()
        if step_key:
            result.append(step_key)
    return result


def _serialize_step_history(progress: ScenarioProgress, history: list[str]) -> None:
    normalized = [item.strip() for item in history if item and item.strip()]
    progress.step_history = "\n".join(normalized) if normalized else None


def _deserialize_response_undo_history(progress: ScenarioProgress) -> list[dict[str, Any]]:
    raw_value = (getattr(progress, "response_undo_history", None) or "").strip()
    if not raw_value:
        return []
    try:
        payload = json.loads(raw_value)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def _serialize_response_undo_history(progress: ScenarioProgress, history: list[dict[str, Any]]) -> None:
    progress.response_undo_history = json.dumps(history, ensure_ascii=False) if history else None


def _get_latest_survey_answer(
    db: Session,
    employee: Employee,
    scenario: ScenarioTemplate,
    step: FlowStepTemplate,
) -> SurveyAnswer | None:
    if not is_survey(scenario):
        return None
    return (
        db.query(SurveyAnswer)
        .filter(
            SurveyAnswer.employee_id == employee.id,
            SurveyAnswer.scenario_key == scenario.scenario_key,
            SurveyAnswer.step_key == step.step_key,
        )
        .order_by(SurveyAnswer.id.desc())
        .first()
    )


def _capture_response_undo_snapshot(
    db: Session,
    employee: Employee,
    scenario: ScenarioTemplate,
    step: FlowStepTemplate,
    uploaded_file: EmployeeFile | None = None,
) -> dict[str, Any]:
    employee_before: dict[str, Any] = {
        "candidate_status": employee.candidate_status,
    }
    target_field = (step.target_field or "").strip()
    if target_field and hasattr(employee, target_field):
        employee_before[target_field] = getattr(employee, target_field)
    if scenario.scenario_key == RECRUITMENT_SCENARIO_KEY and step.response_type == "branching":
        employee_before["employee_stage"] = employee.employee_stage
    survey_answer = _get_latest_survey_answer(db, employee, scenario, step)
    survey_before: dict[str, Any] | None = None
    if is_survey(scenario):
        survey_before = {
            "existed": survey_answer is not None,
            "answer_value": survey_answer.answer_value if survey_answer else None,
            "file_name": survey_answer.file_name if survey_answer else None,
        }
    file_before: dict[str, Any] | None = None
    if uploaded_file is not None:
        file_before = {
            "id": uploaded_file.id,
            "stored_path": uploaded_file.stored_path,
        }
    return {
        "step_key": step.step_key,
        "employee_before": employee_before,
        "survey_before": survey_before,
        "file_before": file_before,
    }


def _restore_response_undo_snapshot(
    db: Session,
    employee: Employee,
    scenario: ScenarioTemplate,
    step: FlowStepTemplate,
    snapshot: dict[str, Any],
) -> None:
    employee_before = snapshot.get("employee_before")
    if isinstance(employee_before, dict):
        for field_name, previous_value in employee_before.items():
            if hasattr(employee, field_name):
                setattr(employee, field_name, previous_value)

    survey_before = snapshot.get("survey_before")
    if isinstance(survey_before, dict) and is_survey(scenario):
        current_answer = _get_latest_survey_answer(db, employee, scenario, step)
        existed_before = bool(survey_before.get("existed"))
        if not existed_before:
            if current_answer is not None:
                db.delete(current_answer)
        elif current_answer is not None:
            current_answer.answer_value = survey_before.get("answer_value")
            current_answer.file_name = survey_before.get("file_name")
            current_answer.answered_at = utc_now()

    file_before = snapshot.get("file_before")
    if isinstance(file_before, dict):
        file_id = file_before.get("id")
        db_file = db.get(EmployeeFile, file_id) if file_id is not None else None
        if db_file is not None:
            path_value = (db_file.stored_path or "").strip()
            if path_value:
                path = Path(path_value)
                if path.exists():
                    try:
                        path.unlink()
                    except OSError:
                        pass
            db.delete(db_file)


def _push_response_undo_snapshot(progress: ScenarioProgress, snapshot: dict[str, Any]) -> None:
    history = _deserialize_response_undo_history(progress)
    history.append(snapshot)
    _serialize_response_undo_history(progress, history)


def _pop_response_undo_snapshot(progress: ScenarioProgress) -> dict[str, Any] | None:
    history = _deserialize_response_undo_history(progress)
    if not history:
        return None
    snapshot = history.pop()
    _serialize_response_undo_history(progress, history)
    return snapshot


def progress_has_back_step(progress: ScenarioProgress | None) -> bool:
    return bool(progress and _deserialize_step_history(progress))


def _load_progress_context_employee(db: Session, progress: ScenarioProgress) -> Employee | None:
    return db.get(Employee, progress.employee_id) if progress.employee_id else None


def _get_tz():
    return tz_get(settings.TIMEZONE)


def _parse_iso_date(value: str) -> date | None:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_year_month(value: str) -> date | None:
    try:
        parsed = datetime.strptime(value, "%Y-%m").date()
    except ValueError:
        return None
    return parsed.replace(day=1)


def _month_shift(value: date, delta: int) -> date:
    month_index = value.month - 1 + delta
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def _date_step_markup(
    step: FlowStepTemplate,
    include_back: bool = False,
    month_cursor: date | None = None,
) -> InlineKeyboardMarkup:
    month = (month_cursor or datetime.now(_get_tz()).date()).replace(day=1)
    cal = calendar.Calendar(firstweekday=0)
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text="◀",
                callback_data=f"{DATE_CALLBACK_PREFIX}{step.id}:nav:{_month_shift(month, -1).strftime('%Y-%m')}",
            ),
            InlineKeyboardButton(
                text=f"{DATE_MONTH_LABELS[month.month - 1]} {month.year}",
                callback_data=f"{DATE_CALLBACK_PREFIX}{step.id}:noop",
            ),
            InlineKeyboardButton(
                text="▶",
                callback_data=f"{DATE_CALLBACK_PREFIX}{step.id}:nav:{_month_shift(month, 1).strftime('%Y-%m')}",
            ),
        ],
        [
            InlineKeyboardButton(text=label, callback_data=f"{DATE_CALLBACK_PREFIX}{step.id}:noop")
            for label in DATE_WEEKDAY_LABELS
        ],
    ]
    for week in cal.monthdayscalendar(month.year, month.month):
        week_row: list[InlineKeyboardButton] = []
        for day_value in week:
            if day_value <= 0:
                week_row.append(InlineKeyboardButton(text=" ", callback_data=f"{DATE_CALLBACK_PREFIX}{step.id}:noop"))
                continue
            selected = date(month.year, month.month, day_value)
            week_row.append(
                InlineKeyboardButton(
                    text=str(day_value),
                    callback_data=f"{DATE_CALLBACK_PREFIX}{step.id}:set:{selected.strftime('%Y-%m-%d')}",
                )
            )
        rows.append(week_row)
    if include_back:
        rows.append([InlineKeyboardButton(text=SCENARIO_BACK_BUTTON_TEXT, callback_data=BACK_CALLBACK_DATA)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


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
        return employee.adaptation_midpoint or add_workdays(employee.first_workday, settings.PROBATION_WORKDAYS // 2)
    if scenario.trigger_mode == "end_probation":
        return employee.adaptation_end or add_workdays(employee.first_workday, settings.PROBATION_WORKDAYS)
    return employee.first_workday


def matches_role_scope(employee: Employee, scenario: ScenarioTemplate) -> bool:
    employee_scope = (getattr(scenario, "employee_scope", None) or "all").strip() or "all"
    is_candidate = (getattr(employee, "employee_stage", None) or "").strip() == "candidate"
    if employee_scope == "employees" and is_candidate:
        return False
    if employee_scope == "candidates" and not is_candidate:
        return False

    if getattr(scenario, "target_employee_id", None) and scenario.target_employee_id != employee.id:
        return False

    return position_matches_scope(employee.desired_position, scenario.role_scope)


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
    links_by_slot = {
        (getattr(link, "slot_key", None) or "").strip().lower(): link
        for link in links
        if (getattr(link, "slot_key", None) or "").strip()
    }

    def replace_document_tag(match: re.Match[str]) -> str:
        document_title = match.group(1).strip()
        if not document_title:
            return ""
        normalized_key = document_title.lower()
        link = links_by_title.get(normalized_key) or links_by_slot.get(normalized_key)
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


def _resolve_explicit_notification_recipient(db: Session | None, raw_value: str) -> str | None:
    normalized = (raw_value or "").strip()
    if not normalized:
        return None
    if normalized == "hr" and db is not None:
        hr_settings = db.get(HrSettings, 1)
        hr_chat_id = (getattr(hr_settings, "telegram_user_id", None) or "").strip()
        return hr_chat_id or None
    if normalized.startswith("employee:") and db is not None:
        employee_id_raw = normalized.split(":", 1)[1].strip()
        if employee_id_raw.isdigit():
            linked_employee = db.get(Employee, int(employee_id_raw))
            if linked_employee:
                linked_chat_id = get_primary_chat_id(linked_employee, db=db)
                if linked_chat_id:
                    return linked_chat_id
        return None
    return normalized


def _resolve_related_employee_chat_id(
    db: Session | None,
    employee: Employee,
    relation_field: str,
    legacy_chat_field: str,
) -> str | None:
    related_employee_id = getattr(employee, relation_field, None)
    if db is not None and related_employee_id:
        related_employee = db.get(Employee, related_employee_id)
        if related_employee:
            related_chat_id = get_primary_chat_id(related_employee, db=db)
            if related_chat_id:
                return related_chat_id
    legacy_chat_id = (getattr(employee, legacy_chat_field, None) or "").strip()
    return legacy_chat_id or None


def resolve_notification_recipients(
    db: Session | None,
    employee: Employee,
    explicit_ids: Optional[str],
    recipient_scope: Optional[str],
) -> list[str]:
    recipients: list[str] = []
    for raw_value in _split_notification_recipients(explicit_ids):
        resolved_value = _resolve_explicit_notification_recipient(db, raw_value)
        if resolved_value and resolved_value not in recipients:
            recipients.append(resolved_value)
    for scope_key in _split_notification_recipients(recipient_scope):
        employee_fields = NOTIFICATION_SCOPE_TO_EMPLOYEE_FIELD.get(scope_key)
        if not employee_fields:
            continue
        relation_field, legacy_chat_field = employee_fields
        employee_chat_id = _resolve_related_employee_chat_id(db, employee, relation_field, legacy_chat_field)
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
    recipients = resolve_notification_recipients(db, employee, recipient_ids, recipient_scope)
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


def get_step_send_notifications(db: Session, step_id: int) -> list[StepSendNotification]:
    return (
        db.query(StepSendNotification)
        .filter(StepSendNotification.step_id == step_id)
        .order_by(StepSendNotification.rule_index.asc(), StepSendNotification.id.asc())
        .all()
    )


def resolve_tagged_employee_documents(db: Session, template: str, employee: Employee) -> list[EmployeeFile]:
    if not template.strip():
        return []
    links = (
        db.query(EmployeeDocumentLink)
        .filter(EmployeeDocumentLink.employee_id == employee.id)
        .all()
    )
    links_by_title = {(link.title or "").strip().lower(): link for link in links}
    links_by_slot = {
        (getattr(link, "slot_key", None) or "").strip().lower(): link
        for link in links
        if (getattr(link, "slot_key", None) or "").strip()
    }
    files: list[EmployeeFile] = []
    seen_file_ids: set[int] = set()
    for match in DOCUMENT_TAG_RE.finditer(template):
        document_key = match.group(1).strip().lower()
        link = links_by_title.get(document_key) or links_by_slot.get(document_key)
        if not link or (getattr(link, "item_kind", "link") or "link") != "file":
            continue
        employee_file_id = getattr(link, "employee_file_id", None)
        if not employee_file_id or employee_file_id in seen_file_ids:
            continue
        employee_file = db.get(EmployeeFile, employee_file_id)
        if employee_file:
            seen_file_ids.add(employee_file_id)
            files.append(employee_file)
    return files


async def send_tagged_employee_documents(
    messenger_or_bot: Any,
    db: Session,
    chat_id: str,
    template: str,
    employee: Employee,
) -> None:
    messenger = as_messenger(messenger_or_bot)
    for employee_file in resolve_tagged_employee_documents(db, template, employee):
        file_path = Path(employee_file.stored_path)
        if not file_path.exists():
            continue
        filename = employee_file.original_filename or file_path.name
        if file_path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}:
            await messenger.send_photo_path(chat_id=chat_id, path=file_path, filename=filename)
        else:
            await messenger.send_document_path(chat_id=chat_id, path=file_path, filename=filename)


def get_button_notifications(db: Session, step_id: int, option_index: int) -> list[StepButtonNotification]:
    return (
        db.query(StepButtonNotification)
        .filter(
            StepButtonNotification.step_id == step_id,
            StepButtonNotification.option_index == option_index,
        )
        .order_by(StepButtonNotification.rule_index.asc(), StepButtonNotification.id.asc())
        .all()
    )


def step_reply_markup(step: FlowStepTemplate, include_back: bool = False) -> Optional[InlineKeyboardMarkup]:
    if step.response_type == "date":
        return _date_step_markup(step, include_back=include_back)
    if step.response_type not in {"text", "buttons", "branching"}:
        return None
    buttons = []
    options = [item.strip() for item in (step.button_options or "").splitlines() if item.strip()]
    for index, option in enumerate(options):
        buttons.append(
            [
                InlineKeyboardButton(
                    text=option,
                    callback_data=f"{CALLBACK_PREFIX}{step.id}:{index}",
                )
            ]
        )
    if include_back and (options or step.response_type in {"buttons", "branching"}):
        buttons.append([InlineKeyboardButton(text=SCENARIO_BACK_BUTTON_TEXT, callback_data=BACK_CALLBACK_DATA)])
    return InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None


def step_back_keyboard(step: FlowStepTemplate, include_back: bool = False) -> Optional[ReplyKeyboardMarkup]:
    if not include_back or step.response_type not in {"text", "file"}:
        return None
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=SCENARIO_BACK_BUTTON_TEXT)]],
        resize_keyboard=True,
    )


def step_has_sendable_content(step: FlowStepTemplate) -> bool:
    return bool(
        resolve_step_message_template(step).strip()
        or (getattr(step, "attachment_path", None) or "").strip()
        or bool(getattr(step, "send_employee_card", False))
        or step_reply_markup(step)
    )


def resolve_branch_followup_step(
    db: Session,
    scenario_key: str,
    branch_step: FlowStepTemplate,
) -> Optional[FlowStepTemplate]:
    if branch_step.response_type != "chain":
        return branch_step
    first_chain_step = get_first_chain_step(db, branch_step.id)
    if first_chain_step:
        return first_chain_step
    return resolve_followup_step(db, scenario_key, branch_step)


async def send_step_attachment(
    messenger_or_bot: Any,
    chat_id: str,
    step: FlowStepTemplate,
    reply_markup: Any | None = None,
    caption: str | None = None,
) -> bool:
    messenger = as_messenger(messenger_or_bot)
    attachment_path = (getattr(step, "attachment_path", None) or "").strip()
    if not attachment_path:
        return False
    path = Path(attachment_path)
    if not path.exists():
        return False
    filename = getattr(step, "attachment_filename", None) or path.name
    if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}:
        await messenger.send_photo_path(
            chat_id=chat_id,
            path=path,
            filename=filename,
            reply_markup=reply_markup,
            caption=caption,
        )
        return True
    await messenger.send_document_path(
        chat_id=chat_id,
        path=path,
        filename=filename,
        reply_markup=reply_markup,
        caption=caption,
    )
    return True


async def send_employee_card_image(
    messenger_or_bot: Any,
    chat_id: str,
    employee: Employee,
    reply_markup: Any | None = None,
    caption: str | None = None,
) -> bool:
    messenger = as_messenger(messenger_or_bot)
    try:
        image_bytes = render_employee_card_png(employee)
    except ImportError:
        return False
    await messenger.send_photo_bytes(
        chat_id=chat_id,
        data=image_bytes,
        filename=f"employee_card_{employee.id}.png",
        reply_markup=reply_markup,
        caption=caption,
    )
    return True


async def send_step_buttons(messenger_or_bot: Any, chat_id: str, step: FlowStepTemplate) -> None:
    messenger = as_messenger(messenger_or_bot)
    reply_markup = step_reply_markup(step, include_back=False)
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
    if target_field == "first_workday":
        parsed_date = _parse_iso_date(normalized)
        if not parsed_date:
            return False
        employee.first_workday = parsed_date
        return True
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


async def _finish_launch_transition(
    messenger_or_bot: Any,
    db: Session,
    employee: Employee,
    scenario: ScenarioTemplate,
    progress: ScenarioProgress,
    step: FlowStepTemplate,
) -> None:
    messenger = as_messenger(messenger_or_bot)
    progress.waiting_for_response = False
    progress.is_completed = True
    progress.completed_at = utc_now()
    progress.updated_at = utc_now()
    db.commit()
    if step.launch_scenario_key:
        await start_scenario(messenger, db, employee, step.launch_scenario_key)


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
) -> bool:
    messenger = as_messenger(messenger_or_bot)
    if employee.is_bot_blocked:
        return False

    progress = get_or_create_progress(db, employee.id, scenario.scenario_key)
    resolution = resolve_scenario_recipient(
        db,
        employee,
        scenario,
        requires_response=step_requires_response(step),
    )
    if resolution.error or not resolution.chat_id:
        _mark_delivery_failure(db, progress, employee, scenario, step, resolution)
        return False

    chat_id = resolution.chat_id
    _store_progress_recipient(progress, resolution)
    progress.last_delivery_error = None
    include_back = progress_has_back_step(progress)
    previous_step_key = progress.current_step_key
    if previous_step_key and previous_step_key != step.step_key:
        previous_step = get_step_by_key(db, scenario.scenario_key, previous_step_key)
        if step_requires_response(previous_step):
            history = _deserialize_step_history(progress)
            if not history or history[-1] != previous_step_key:
                history.append(previous_step_key)
                _serialize_step_history(progress, history)

    anchor_date = scenario_anchor_date(employee, scenario) or datetime.now(_get_tz()).date()
    message_template = resolve_step_message_template(step)
    message_text = format_message(db, message_template, employee, anchor_date, step.send_time)
    has_attachment = bool((getattr(step, "attachment_path", None) or "").strip())
    send_employee_card = bool(getattr(step, "send_employee_card", False))
    reply_markup = step_reply_markup(step, include_back=include_back)
    back_keyboard = step_back_keyboard(step, include_back=include_back)
    media_can_host_inline_buttons = bool(reply_markup and (has_attachment or send_employee_card))
    needs_fallback_inline_buttons_message = bool(reply_markup and not message_text.strip() and not media_can_host_inline_buttons)

    if message_text.strip():
        await messenger.send_text(
            chat_id=chat_id,
            text=message_text,
            reply_markup=None if media_can_host_inline_buttons else (reply_markup or back_keyboard),
        )
    media_reply_markup = reply_markup if media_can_host_inline_buttons else None
    if send_employee_card:
        employee_card_reply_markup = media_reply_markup if not has_attachment else None
        await send_employee_card_image(
            messenger,
            chat_id,
            employee,
            reply_markup=employee_card_reply_markup,
        )
    if has_attachment:
        await send_step_attachment(
            messenger,
            chat_id,
            step,
            reply_markup=media_reply_markup,
        )
    await send_tagged_employee_documents(messenger, db, chat_id, message_template, employee)
    if needs_fallback_inline_buttons_message:
        await messenger.send_text(
            chat_id=chat_id,
            text="Выберите дату:" if step.response_type == "date" else "\u2060",
            reply_markup=reply_markup,
        )

    progress.current_step_key = step.step_key
    progress.waiting_for_response = step_requires_response(step)
    progress.updated_at = utc_now()
    db.add(
        OnboardingEvent(
            employee_id=employee.id,
            scheduled_at=scheduled_at or utc_now(),
            sent_at=utc_now(),
            event_key=step.step_key,
            message=message_text,
        )
    )
    db.commit()

    step_send_notifications = get_step_send_notifications(db, step.id)
    if step_send_notifications:
        for step_send_notification in step_send_notifications:
            await send_custom_notification(
                messenger,
                db,
                employee,
                step_send_notification.message_text,
                step_send_notification.recipient_ids,
                step_send_notification.recipient_scope,
                step.send_time,
            )
    else:
        await send_custom_notification(
            messenger,
            db,
            employee,
            getattr(step, "notify_on_send_text", None),
            getattr(step, "notify_on_send_recipient_ids", None),
            getattr(step, "notify_on_send_recipient_scope", None),
            step.send_time,
        )

    if step.response_type == "launch_scenario":
        await _finish_launch_transition(messenger, db, employee, scenario, progress, step)
        return True

    if not auto_follow:
        return True

    if not progress.waiting_for_response:
        next_step = resolve_followup_step(db, scenario.scenario_key, step)
        if not next_step:
            progress.is_completed = True
            progress.completed_at = utc_now()
            progress.updated_at = utc_now()
            db.commit()
            try:
                await notify_hr_stage(messenger, employee, step.step_key)
            except Exception:
                pass
            return True
        if scheduled_at is not None and next_step.send_mode == "specific_time":
            return True
        if settings.DEMO_MODE or next_step.send_mode == "immediate":
            return await send_step(messenger, db, employee, scenario, next_step)
        else:
            if not queue_followup_step(db, employee, scenario, next_step):
                return await send_step(messenger, db, employee, scenario, next_step)
    return True


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
    progress.updated_at = utc_now()
    next_step = resolve_followup_step(db, scenario.scenario_key, current_step)
    if not next_step:
        progress.is_completed = True
        progress.completed_at = utc_now()
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
    if employee.is_bot_blocked:
        return False
    progress = get_waiting_progress(db, employee.id)
    if not progress or not progress.current_step_key:
        return False
    context_employee = _load_progress_context_employee(db, progress)
    if not context_employee:
        return False
    scenario = db.query(ScenarioTemplate).filter(ScenarioTemplate.scenario_key == progress.scenario_key).first()
    if not scenario:
        return False
    step = get_step_by_key(db, scenario.scenario_key, progress.current_step_key)
    if not step or step.response_type != "text":
        return False
    undo_snapshot = _capture_response_undo_snapshot(db, context_employee, scenario, step)
    store_survey_answer(db, context_employee, scenario, step, message.text)
    if not apply_response_to_employee(db, context_employee, step, message.text):
        _restore_response_undo_snapshot(db, context_employee, scenario, step, undo_snapshot)
        return False
    context_employee.candidate_status = step.step_key
    _push_response_undo_snapshot(progress, undo_snapshot)
    db.commit()
    await advance_after_response(messenger_or_bot, db, context_employee, scenario, step)
    return True


async def handle_date_response_by_step_id(
    messenger_or_bot: Any,
    db: Session,
    employee: Employee,
    step_id: int,
    action: str,
    value: str,
) -> DateCallbackResult:
    if employee.is_bot_blocked:
        return DateCallbackResult(False, "noop", None)
    step = db.get(FlowStepTemplate, step_id)
    if not step or step.response_type != "date":
        return DateCallbackResult(False, "noop", None)
    progress = get_waiting_progress_for_step(db, employee.id, step.flow_key, step.step_key)
    if not progress:
        return DateCallbackResult(False, "noop", None)
    context_employee = _load_progress_context_employee(db, progress)
    if not context_employee:
        return DateCallbackResult(False, "noop", None)
    scenario = db.query(ScenarioTemplate).filter(ScenarioTemplate.scenario_key == step.flow_key).first()
    if not scenario:
        return DateCallbackResult(False, "noop", None)
    if action == "noop":
        return DateCallbackResult(True, "noop", None)
    if action == "nav":
        month_cursor = _parse_year_month(value)
        if not month_cursor:
            return DateCallbackResult(False, "noop", None)
        return DateCallbackResult(
            True,
            "updated",
            _date_step_markup(step, include_back=progress_has_back_step(progress), month_cursor=month_cursor),
        )
    if action != "set":
        return DateCallbackResult(False, "noop", None)

    selected_date = _parse_iso_date(value)
    if not selected_date:
        return DateCallbackResult(False, "noop", None)
    undo_snapshot = _capture_response_undo_snapshot(db, context_employee, scenario, step)
    store_survey_answer(db, context_employee, scenario, step, selected_date.isoformat())
    if not apply_response_to_employee(db, context_employee, step, selected_date.isoformat()):
        _restore_response_undo_snapshot(db, context_employee, scenario, step, undo_snapshot)
        return DateCallbackResult(False, "noop", None)
    context_employee.candidate_status = step.step_key
    _push_response_undo_snapshot(progress, undo_snapshot)
    db.commit()
    await advance_after_response(messenger_or_bot, db, context_employee, scenario, step)
    return DateCallbackResult(True, "selected", None)


async def handle_button_response(messenger_or_bot: Any, db: Session, employee: Employee, scenario_key: str, step_key: str, option_index: int) -> bool:
    if employee.is_bot_blocked:
        return False
    messenger = as_messenger(messenger_or_bot)
    progress = get_waiting_progress_for_step(db, employee.id, scenario_key, step_key)
    if not progress:
        return False
    context_employee = _load_progress_context_employee(db, progress)
    if not context_employee:
        return False
    scenario = db.query(ScenarioTemplate).filter(ScenarioTemplate.scenario_key == scenario_key).first()
    step = get_step_by_key(db, scenario_key, step_key) if scenario else None
    if not scenario or not step:
        return False
    allows_survey_option_buttons = is_survey(scenario) and step.response_type == "text" and bool((step.button_options or "").strip())
    if step.response_type not in {"buttons", "branching"} and not allows_survey_option_buttons:
        return False
    options = [item.strip() for item in (step.button_options or "").splitlines() if item.strip()]
    if option_index < 0 or option_index >= len(options):
        return False
    selected_value = options[option_index]
    undo_snapshot = _capture_response_undo_snapshot(db, context_employee, scenario, step)
    store_survey_answer(db, context_employee, scenario, step, selected_value)
    if not apply_response_to_employee(db, context_employee, step, selected_value):
        _restore_response_undo_snapshot(db, context_employee, scenario, step, undo_snapshot)
        return False
    apply_status_from_recruitment_choice(db, context_employee, scenario, step, selected_value)
    button_notifications = get_button_notifications(db, step.id, option_index)
    for button_notification in button_notifications:
        await send_custom_notification(
            messenger,
            db,
            context_employee,
            button_notification.message_text,
            button_notification.recipient_ids,
            button_notification.recipient_scope,
            step.send_time,
        )
    context_employee.candidate_status = step.step_key
    _push_response_undo_snapshot(progress, undo_snapshot)
    db.commit()
    if step.target_field in {"personal_data_consent", "employee_data_consent"} and not getattr(context_employee, step.target_field):
        progress.waiting_for_response = False
        progress.is_completed = True
        progress.completed_at = utc_now()
        db.commit()
        try:
            await notify_hr_stage(messenger, context_employee, "recruitment_consent_no")
        except Exception:
            pass
        return True
    if step.response_type == "branching":
        branch_step = get_branch_step(db, step.id, option_index)
        if branch_step:
            if branch_step.response_type == "chain":
                if step_has_sendable_content(branch_step):
                    await send_step(messenger, db, context_employee, scenario, branch_step, auto_follow=False)
                next_branch_step = resolve_branch_followup_step(db, scenario.scenario_key, branch_step)
                if next_branch_step:
                    await send_step(messenger, db, context_employee, scenario, next_branch_step)
                else:
                    await advance_after_response(messenger, db, context_employee, scenario, branch_step)
                return True

            await send_step(messenger, db, context_employee, scenario, branch_step)
            return True
    await advance_after_response(messenger, db, context_employee, scenario, step)
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
    if employee.is_bot_blocked:
        return False
    progress = get_waiting_progress(db, employee.id)
    if not progress or not progress.current_step_key:
        return False
    context_employee = _load_progress_context_employee(db, progress)
    if not context_employee:
        return False
    scenario = db.query(ScenarioTemplate).filter(ScenarioTemplate.scenario_key == progress.scenario_key).first()
    if not scenario:
        return False
    step = get_step_by_key(db, scenario.scenario_key, progress.current_step_key)
    if not step or step.response_type != "file":
        return False
    if uploaded_file.employee_id != context_employee.id:
        uploaded_file.employee_id = context_employee.id
    undo_snapshot = _capture_response_undo_snapshot(db, context_employee, scenario, step, uploaded_file)
    store_survey_answer(db, context_employee, scenario, step, uploaded_file.original_filename, uploaded_file.original_filename)
    if step.target_field == "resume":
        uploaded_file.category = "resume"
    if not apply_response_to_employee(db, context_employee, step, uploaded_file.original_filename, uploaded_file):
        _restore_response_undo_snapshot(db, context_employee, scenario, step, undo_snapshot)
        return False
    context_employee.candidate_status = step.step_key
    _push_response_undo_snapshot(progress, undo_snapshot)
    db.commit()
    await advance_after_response(messenger_or_bot, db, context_employee, scenario, step)
    return True


async def handle_back_response(messenger_or_bot: Any, db: Session, employee: Employee) -> bool:
    if employee.is_bot_blocked:
        return False
    messenger = as_messenger(messenger_or_bot)
    progress = get_waiting_progress(db, employee.id)
    if not progress or not progress.current_step_key:
        return False
    context_employee = _load_progress_context_employee(db, progress)
    if not context_employee:
        return False
    scenario = db.query(ScenarioTemplate).filter(ScenarioTemplate.scenario_key == progress.scenario_key).first()
    if not scenario:
        return False

    undo_snapshot = _pop_response_undo_snapshot(progress)
    undo_step_key = (undo_snapshot or {}).get("step_key") if isinstance(undo_snapshot, dict) else None
    undo_step = get_step_by_key(db, scenario.scenario_key, undo_step_key) if undo_step_key else None
    if undo_snapshot and undo_step:
        _restore_response_undo_snapshot(db, context_employee, scenario, undo_step, undo_snapshot)

    history = _deserialize_step_history(progress)
    previous_step: Optional[FlowStepTemplate] = None
    while history:
        previous_step = get_step_by_key(db, scenario.scenario_key, history.pop())
        if step_requires_response(previous_step):
            break
        previous_step = None

    if not previous_step:
        chat_id = progress.recipient_chat_id or get_primary_chat_id(employee, db=db)
        if chat_id:
            await messenger.send_text(chat_id=chat_id, text="Это первый шаг сценария, назад идти некуда.")
        _serialize_step_history(progress, [])
        progress.updated_at = utc_now()
        db.commit()
        return True

    _serialize_step_history(progress, history)
    progress.current_step_key = previous_step.step_key
    progress.waiting_for_response = True
    progress.is_completed = False
    progress.completed_at = None
    progress.updated_at = utc_now()
    db.commit()
    await send_step(messenger, db, context_employee, scenario, previous_step, auto_follow=False)
    return True


async def start_scenario(messenger_or_bot: Any, db: Session, employee: Employee, scenario_key: str) -> bool:
    messenger = as_messenger(messenger_or_bot)
    if employee.is_bot_blocked:
        return False
    scenario = db.query(ScenarioTemplate).filter(ScenarioTemplate.scenario_key == scenario_key).first()
    if not scenario or not matches_role_scope(employee, scenario):
        return False
    first_step = get_first_step(db, scenario_key)
    if not first_step:
        return False
    reset_progress(db, employee.id, scenario_key)
    progress = get_or_create_progress(db, employee.id, scenario_key)
    progress.recipient_mode = _scenario_recipient_mode(scenario)
    db.commit()
    return await send_step(messenger, db, employee, scenario, first_step)
