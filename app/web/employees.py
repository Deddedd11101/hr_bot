import shutil
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from aiogram.exceptions import TelegramBadRequest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import settings
from ..file_storage import build_employee_file_path
from ..flow_templates import CANDIDATE_WORK_STAGE_LABELS, normalize_candidate_work_stage
from ..messaging import create_telegram_messenger
from ..messaging.identity import (
    EmployeeIdentityConflictError,
    get_primary_chat_id,
    get_public_chat_handle,
    set_primary_chat_id,
    set_public_chat_handle,
    sync_legacy_telegram_account,
)
from ..models import (
    AdminAccount,
    Employee,
    EmployeeAssignmentHistory,
    EmployeeDocumentLink,
    EmployeeFile,
    EmployeeHrNote,
    EmployeeManualBotMessage,
    EmployeeMessengerAccount,
    FlowLaunchRequest,
    ScenarioProgress,
    ScenarioTemplate,
)
from ..positions import employee_position_values, resolve_employee_position_value
from ..scenario_engine import SINGLE_STEP_REQUEST_PREFIX, add_workdays, get_first_step, matches_role_scope, start_scenario
from ..time_utils import utc_now

OFFER_DOCUMENT_TITLE = "Оффер"
OFFER_DOCUMENT_SLOT = "offer"
RESUME_DOCUMENT_TITLE = "Резюме"
RESUME_DOCUMENT_SLOT = "resume"
TEST_TASK_RESULT_TITLE = "Ответ на тестовое"
TEST_TASK_RESULT_SLOT = "test_task_result"
SEMANTIC_DOCUMENT_SLOTS = {OFFER_DOCUMENT_SLOT, RESUME_DOCUMENT_SLOT, TEST_TASK_RESULT_SLOT}
SEMANTIC_FILE_CATEGORIES = {"offer_document", RESUME_DOCUMENT_SLOT, "test_result"}
AUTOMATIC_LAUNCH_TYPES = {"status_transition"}
SYSTEM_LAUNCH_TYPES = {"registration", "bot_registration", "trigger", "system"}
LAUNCH_TYPE_LABELS = {
    "manual": "Ручной запуск",
    "scheduled": "Запланированный запуск",
    "status_transition": "Автозапуск по статусу",
    "registration": "Регистрация",
    "bot_registration": "Регистрация в боте",
    "trigger": "Системный триггер",
    "system": "Системный запуск",
}
MANAGER_ASSIGNMENT_TRIGGER_MODE = "manager_assigned_adaptation"
ASSIGNMENT_ROLE_MANAGER = "manager"
ASSIGNMENT_ROLE_MENTOR_ADAPTATION = "mentor_adaptation"
ASSIGNMENT_ROLE_MENTOR_IPR = "mentor_ipr"

EMPLOYEE_STAGE_VALUES = {
    "candidate": "Кандидат",
    "adaptation": "Адаптация",
    "ipr": "ИПР",
    "staff": "В штате",
}

CANDIDATE_WORK_STAGE_VALUES = {
    "company_decline": "Наш отказ",
    "hr_interview": "Собеседование с HR",
    "manager_interview": "Собеседование с руководителем",
    "testing": "Тестирование",
    "offer": "Оффер",
    "preonboarding": "Преонбординг",
    "candidate_decline": "Отказ кандидата",
    "contract": "Заключение договора",
}

VISIBLE_CANDIDATE_WORK_STAGE_VALUES = {
    value: label
    for value, label in CANDIDATE_WORK_STAGE_VALUES.items()
    if value != "contract"
}

ASSIGNMENT_ROLE_FIELD_MAP = {
    ASSIGNMENT_ROLE_MANAGER: "manager_employee_id",
    ASSIGNMENT_ROLE_MENTOR_ADAPTATION: "mentor_adaptation_employee_id",
    ASSIGNMENT_ROLE_MENTOR_IPR: "mentor_ipr_employee_id",
}

ASSIGNMENT_ROLE_LABELS = {
    ASSIGNMENT_ROLE_MANAGER: "Руководитель",
    ASSIGNMENT_ROLE_MENTOR_ADAPTATION: "Наставник адаптации",
    ASSIGNMENT_ROLE_MENTOR_IPR: "Наставник ИПР",
}
MANUAL_BOT_MESSAGE_STATUS_SENT = "sent"
MANUAL_BOT_MESSAGE_STATUS_FAILED = "failed"


def _is_workday(day: date) -> bool:
    return day.weekday() < 5


def _workdays_between(start: Optional[date], end: date) -> int:
    if not start or end <= start:
        return 0
    days = 0
    current = start
    while current < end:
        if _is_workday(current):
            days += 1
        current += timedelta(days=1)
    return days


def _employee_status_label(employee: Employee) -> str:
    return EMPLOYEE_STAGE_VALUES.get((employee.employee_stage or "").strip(), "Не указан")


def _candidate_work_stage_label(employee: Employee) -> str:
    return CANDIDATE_WORK_STAGE_VALUES.get((employee.candidate_work_stage or "").strip(), "Не указан")


def _full_years_between(start: Optional[date], end: date) -> int:
    if not start or start > end:
        return 0
    years = end.year - start.year
    if (end.month, end.day) < (start.month, start.day):
        years -= 1
    return max(years, 0)


def _scenario_matches_employee_role(scenario: ScenarioTemplate, employee: Employee) -> bool:
    return matches_role_scope(employee, scenario)


def _employee_identity_conflict_detail(exc: EmployeeIdentityConflictError) -> str:
    return str(exc)


def _employee_identity_integrity_detail(chat_id: str) -> str:
    normalized_chat_id = (chat_id or "").strip()
    if normalized_chat_id:
        return f"Идентификатор {normalized_chat_id} уже привязан к другому сотруднику."
    return "Указанный идентификатор уже привязан к другому сотруднику."


def _is_employee_identity_integrity_error(exc: IntegrityError) -> bool:
    return "employee_messenger_accounts.channel, employee_messenger_accounts.external_user_id" in str(exc)


def _employee_list_kind(employee: Optional[Employee]) -> str:
    if (getattr(employee, "employee_stage", None) or "").strip() == "candidate":
        return "candidates"
    return "employees"


def _is_internal_followup_request(launch_request: FlowLaunchRequest) -> bool:
    skip_step_key = (getattr(launch_request, "skip_step_key", None) or "").strip()
    return bool(skip_step_key) and skip_step_key.startswith(SINGLE_STEP_REQUEST_PREFIX)


def _employee_list_meta(list_kind: str) -> dict:
    if list_kind == "candidates":
        return {
            "active_tab": "candidates",
            "list_title": "Кандидаты",
            "empty_message": "Кандидатов пока нет. Нажмите «Добавить кандидата».",
            "create_button_label": "Добавить кандидата",
            "create_modal_title": "Новый кандидат",
            "create_intro": "Добавьте кандидата, чтобы начать работу с подбором и наймом.",
            "first_workday_label": "Предварительная дата выхода на работу",
            "default_employee_stage": "candidate",
        }
    return {
        "active_tab": "employees",
        "list_title": "Сотрудники",
        "empty_message": "Сотрудников пока нет. Нажмите «Добавить сотрудника».",
        "create_button_label": "Добавить сотрудника",
        "create_modal_title": "Новый сотрудник",
        "create_intro": "Добавьте сотрудника, чтобы запустить сценарий онбординга.",
        "first_workday_label": "Дата выхода на работу",
        "default_employee_stage": "staff",
    }


def _telegram_profile_url(telegram_username: Optional[str], telegram_user_id: Optional[str]) -> Optional[str]:
    username = (telegram_username or "").strip().lstrip("@")
    if username:
        return f"https://t.me/{username}"
    value = (telegram_user_id or "").strip()
    if not value:
        return None
    if value.startswith("@"):
        return f"https://t.me/{value[1:]}"
    if value.startswith("http://") or value.startswith("https://") or value.startswith("tg://"):
        return value
    if value.isdigit():
        return None
    return f"https://t.me/{value}"


def _employee_display_name(employee: Employee) -> str:
    name = (employee.full_name or "").strip()
    if name:
        return f"{name} (ID {employee.id})"
    chat_id = get_primary_chat_id(employee)
    if chat_id:
        return f"{chat_id} (ID {employee.id})"
    return f"Сотрудник #{employee.id}"


def _all_employee_options(db: Session) -> list[dict]:
    employees = db.query(Employee).order_by(Employee.full_name.asc(), Employee.id.asc()).all()
    return [
        {
            "id": employee.id,
            "label": _employee_display_name(employee),
            "kind": _employee_list_kind(employee),
        }
        for employee in employees
    ]


def _staff_employee_options(db: Session, current_employee_id: int | None = None) -> list[dict]:
    employees = (
        db.query(Employee)
        .filter(Employee.employee_stage == "staff")
        .order_by(Employee.full_name.asc(), Employee.id.asc())
        .all()
    )
    return [
        {
            "value": str(employee.id),
            "label": _employee_display_name(employee),
        }
        for employee in employees
        if current_employee_id is None or employee.id != current_employee_id
    ]


def _staff_employee_options_by_flag(
    db: Session,
    *,
    current_employee_id: int | None = None,
    role_flag: str | None = None,
    selected_employee_ids: list[int] | None = None,
) -> list[dict]:
    employees = (
        db.query(Employee)
        .filter(Employee.employee_stage == "staff")
        .order_by(Employee.full_name.asc(), Employee.id.asc())
        .all()
    )
    result: list[dict] = []
    included_ids: set[int] = set()
    selected_ids = {value for value in (selected_employee_ids or []) if value}
    for employee in employees:
        if current_employee_id is not None and employee.id == current_employee_id:
            continue
        is_selected = employee.id in selected_ids
        if role_flag == "is_manager" and not bool(employee.is_manager) and not is_selected:
            continue
        if role_flag == "is_mentor" and not bool(employee.is_mentor) and not is_selected:
            continue
        result.append(
            {
                "value": str(employee.id),
                "label": _employee_display_name(employee),
            }
        )
        included_ids.add(employee.id)
    for selected_employee_id in selected_ids:
        if selected_employee_id in included_ids:
            continue
        selected_employee = db.get(Employee, selected_employee_id)
        if selected_employee is not None and (current_employee_id is None or selected_employee.id != current_employee_id):
            result.append(
                {
                    "value": str(selected_employee.id),
                    "label": _employee_display_name(selected_employee),
                }
            )
    return result


def _parse_optional_date(value: str) -> date | None:
    normalized = (value or "").strip()
    return datetime.strptime(normalized, "%Y-%m-%d").date() if normalized else None


def _parse_optional_int(value: str) -> int | None:
    normalized = (value or "").strip()
    if not normalized:
        return None
    try:
        parsed = int(normalized)
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def _resolve_staff_employee_reference(
    db: Session,
    *,
    employee: Employee,
    related_employee_id: int | None,
    field_title: str,
    required_flag: str | None = None,
) -> Employee | None:
    if related_employee_id is None:
        return None
    if employee.id is not None and related_employee_id == employee.id:
        raise ValueError(f"{field_title} не может совпадать с текущим сотрудником.")
    related_employee = db.get(Employee, related_employee_id)
    if not related_employee:
        raise ValueError(f"{field_title} не найден в базе сотрудников.")
    if (related_employee.employee_stage or "").strip() != "staff":
        raise ValueError(f"{field_title} должен быть выбран из сотрудников в штате.")
    if required_flag == "is_manager" and not bool(related_employee.is_manager):
        raise ValueError(f"{field_title} должен быть отмечен как руководитель.")
    if required_flag == "is_mentor" and not bool(related_employee.is_mentor):
        raise ValueError(f"{field_title} должен быть отмечен как наставник.")
    return related_employee


def _manager_assignment_trigger_scenario(db: Session, employee: Employee) -> ScenarioTemplate | None:
    scenarios = (
        db.query(ScenarioTemplate)
        .filter(
            ScenarioTemplate.scenario_kind == "scenario",
            ScenarioTemplate.trigger_mode == MANAGER_ASSIGNMENT_TRIGGER_MODE,
        )
        .order_by(ScenarioTemplate.sort_order, ScenarioTemplate.id)
        .all()
    )
    for scenario in scenarios:
        if matches_role_scope(employee, scenario):
            return scenario
    return None


def _enqueue_manager_assignment_trigger(
    db: Session,
    *,
    subject_employee: Employee,
    previous_stage: str,
    previous_manager_employee_id: int | None,
) -> None:
    current_stage = (subject_employee.employee_stage or "").strip()
    current_manager_employee_id = subject_employee.manager_employee_id
    entered_adaptation = previous_stage != "adaptation" and current_stage == "adaptation"
    manager_changed = previous_manager_employee_id != current_manager_employee_id
    if current_stage != "adaptation":
        return
    if not current_manager_employee_id:
        return
    if not entered_adaptation and not manager_changed:
        return

    manager_employee = db.get(Employee, current_manager_employee_id)
    if not manager_employee:
        return
    scenario = _manager_assignment_trigger_scenario(db, subject_employee)
    if not scenario:
        return

    duplicate_request = (
        db.query(FlowLaunchRequest)
        .filter(
            FlowLaunchRequest.employee_id == subject_employee.id,
            FlowLaunchRequest.flow_key == scenario.scenario_key,
            FlowLaunchRequest.processed_at.is_(None),
            FlowLaunchRequest.launch_type == "trigger",
        )
        .first()
    )
    if duplicate_request:
        return

    db.add(
        FlowLaunchRequest(
            employee_id=subject_employee.id,
            flow_key=scenario.scenario_key,
            requested_at=datetime.now(),
            processed_at=None,
            launch_type="trigger",
            skip_step_key=None,
        )
    )


def _sync_assignment_history_entry(
    db: Session,
    *,
    subject_employee_id: int,
    assignment_role: str,
    previous_assigned_employee_id: int | None,
    current_assigned_employee_id: int | None,
    assigned_by_account_id: int | None,
) -> None:
    if previous_assigned_employee_id == current_assigned_employee_id:
        return

    now = utc_now()
    active_rows = (
        db.query(EmployeeAssignmentHistory)
        .filter(
            EmployeeAssignmentHistory.subject_employee_id == subject_employee_id,
            EmployeeAssignmentHistory.assignment_role == assignment_role,
            EmployeeAssignmentHistory.ended_at.is_(None),
        )
        .order_by(EmployeeAssignmentHistory.started_at.asc(), EmployeeAssignmentHistory.id.asc())
        .all()
    )
    for row in active_rows:
        row.ended_at = now

    if not current_assigned_employee_id:
        return

    active_duplicate = next((row for row in active_rows if row.assigned_employee_id == current_assigned_employee_id), None)
    if active_duplicate is not None:
        active_duplicate.ended_at = None
        return

    db.add(
        EmployeeAssignmentHistory(
            subject_employee_id=subject_employee_id,
            assigned_employee_id=current_assigned_employee_id,
            assignment_role=assignment_role,
            started_at=now,
            ended_at=None,
            assigned_by_account_id=assigned_by_account_id,
            created_at=now,
        )
    )


def _sync_assignment_history(
    db: Session,
    *,
    employee: Employee,
    previous_assignments: dict[str, int | None],
    assigned_by_account_id: int | None,
) -> None:
    current_assignments = {
        ASSIGNMENT_ROLE_MANAGER: employee.manager_employee_id,
        ASSIGNMENT_ROLE_MENTOR_ADAPTATION: employee.mentor_adaptation_employee_id,
        ASSIGNMENT_ROLE_MENTOR_IPR: employee.mentor_ipr_employee_id,
    }
    for assignment_role, field_name in ASSIGNMENT_ROLE_FIELD_MAP.items():
        _sync_assignment_history_entry(
            db,
            subject_employee_id=employee.id,
            assignment_role=assignment_role,
            previous_assigned_employee_id=previous_assignments.get(field_name),
            current_assigned_employee_id=current_assignments.get(assignment_role),
            assigned_by_account_id=assigned_by_account_id,
        )


def _sync_hr_note_history(
    db: Session,
    *,
    employee: Employee,
    previous_notes: str | None,
    next_notes: str | None,
    author_account_id: int | None,
) -> None:
    previous_value = (previous_notes or "").strip()
    next_value = (next_notes or "").strip()
    if not next_value or next_value == previous_value:
        return
    db.add(
        EmployeeHrNote(
            employee_id=employee.id,
            author_account_id=author_account_id,
            note_text=next_value,
            created_at=utc_now(),
        )
    )


def _serialize_assignment_history(db: Session, employee_id: int) -> list[dict]:
    history_rows = (
        db.query(EmployeeAssignmentHistory)
        .filter(EmployeeAssignmentHistory.subject_employee_id == employee_id)
        .order_by(
            EmployeeAssignmentHistory.started_at.desc(),
            EmployeeAssignmentHistory.id.desc(),
        )
        .all()
    )
    if not history_rows:
        return []

    assigned_employee_ids = {
        row.assigned_employee_id
        for row in history_rows
        if row.assigned_employee_id is not None
    }
    assigned_names_by_id = {
        employee_row.id: employee_row.full_name or ""
        for employee_row in db.query(Employee)
        .filter(Employee.id.in_(assigned_employee_ids))
        .all()
    }
    return [
        {
            "id": row.id,
            "assignment_role": row.assignment_role or "",
            "role_label": ASSIGNMENT_ROLE_LABELS.get(row.assignment_role or "", row.assignment_role or ""),
            "assigned_employee_id": row.assigned_employee_id,
            "assigned_employee_name": assigned_names_by_id.get(row.assigned_employee_id, ""),
            "started_at": row.started_at.isoformat() if row.started_at else "",
            "ended_at": row.ended_at.isoformat() if row.ended_at else None,
            "is_active": row.ended_at is None,
            "assigned_by_account_id": row.assigned_by_account_id,
        }
        for row in history_rows
    ]


def _sender_account_label(account: Optional[AdminAccount]) -> str:
    if account is None:
        return ""
    login = (account.login or "").strip()
    if login:
        return login
    return f"Account #{account.id}"


def _serialize_manual_bot_message_history(db: Session, employee_id: int) -> list[dict]:
    history_rows = (
        db.query(EmployeeManualBotMessage, AdminAccount)
        .outerjoin(AdminAccount, AdminAccount.id == EmployeeManualBotMessage.sender_account_id)
        .filter(EmployeeManualBotMessage.employee_id == employee_id)
        .order_by(EmployeeManualBotMessage.created_at.desc(), EmployeeManualBotMessage.id.desc())
        .all()
    )
    return [
        {
            "id": row.id,
            "sender_account_id": row.sender_account_id,
            "sender_label": _sender_account_label(account),
            "message_text": row.message_text or "",
            "status": row.status or "",
            "error_text": row.error_text or "",
            "sent_at": row.sent_at.isoformat() if row.sent_at else "",
            "created_at": row.created_at.isoformat() if row.created_at else "",
        }
        for row, account in history_rows
    ]


def _serialize_hr_notes_history(db: Session, employee_id: int) -> list[dict]:
    history_rows = (
        db.query(EmployeeHrNote, AdminAccount)
        .outerjoin(AdminAccount, AdminAccount.id == EmployeeHrNote.author_account_id)
        .filter(EmployeeHrNote.employee_id == employee_id)
        .order_by(EmployeeHrNote.created_at.desc(), EmployeeHrNote.id.desc())
        .all()
    )
    return [
        {
            "id": row.id,
            "author_account_id": row.author_account_id,
            "author_label": _sender_account_label(account),
            "note_text": row.note_text or "",
            "created_at": row.created_at.isoformat() if row.created_at else "",
        }
        for row, account in history_rows
    ]


def _available_scenarios_for_employee(db: Session, employee: Employee) -> list[ScenarioTemplate]:
    return [
        scenario
        for scenario in db.query(ScenarioTemplate).filter(ScenarioTemplate.scenario_kind == "scenario").order_by(ScenarioTemplate.id).all()
        if _scenario_matches_employee_role(scenario, employee)
    ]


def _build_employee_views(list_kind: str, db: Session) -> list[dict]:
    query = db.query(Employee)
    if list_kind == "candidates":
        query = query.filter(Employee.employee_stage == "candidate")
    else:
        query = query.filter((Employee.employee_stage != "candidate") | (Employee.employee_stage.is_(None)))

    employees = query.order_by(Employee.id.desc()).all()
    employee_ids = [employee.id for employee in employees]
    scenario_titles = {scenario.scenario_key: scenario.title for scenario in db.query(ScenarioTemplate).all()}
    launch_requests_by_employee: dict[int, FlowLaunchRequest] = {}
    if employee_ids:
        pending_launch_requests = (
            db.query(FlowLaunchRequest)
            .filter(
                FlowLaunchRequest.employee_id.in_(employee_ids),
                FlowLaunchRequest.processed_at.is_(None),
            )
            .order_by(FlowLaunchRequest.requested_at.desc(), FlowLaunchRequest.id.desc())
            .all()
        )
        for launch_request in pending_launch_requests:
            if _is_internal_followup_request(launch_request):
                continue
            launch_requests_by_employee.setdefault(launch_request.employee_id, launch_request)

    today = datetime.now().date()
    employee_views: list[dict] = []
    for employee in employees:
        chat_handle = get_public_chat_handle(employee, db=db)
        chat_id = get_primary_chat_id(employee, db=db)
        employee_views.append(
            {
                "employee": employee,
                "status": _employee_status_label(employee),
                "work_stage": _candidate_work_stage_label(employee),
                "workdays": _workdays_between(employee.first_workday, today),
                "planned_scenario_title": scenario_titles.get(
                    getattr(launch_requests_by_employee.get(employee.id), "flow_key", ""),
                    "—",
                ),
                "chat_id": chat_id,
                "chat_handle": chat_handle,
                "chat_link": _telegram_profile_url(chat_handle, chat_id),
            }
        )
    return employee_views


def _serialize_employee_view(item: dict, list_kind: str) -> dict:
    employee = item["employee"]
    return {
        "id": employee.id,
        "full_name": employee.full_name or "",
        "chat_id": item.get("chat_id") or "",
        "chat_handle": item.get("chat_handle") or "",
        "chat_link": item.get("chat_link"),
        "position": employee.desired_position or "",
        "status_label": item.get("status") or "",
        "candidate_work_stage_label": item.get("work_stage") or "",
        "planned_scenario_title": item.get("planned_scenario_title") or "—",
        "first_workday": employee.first_workday.isoformat() if employee.first_workday else None,
        "first_workday_label": employee.first_workday.strftime("%d.%m.%Y") if employee.first_workday else "—",
        "test_task_due_at": employee.test_task_due_at.isoformat() if employee.test_task_due_at else None,
        "test_task_due_at_label": employee.test_task_due_at.strftime("%d.%m.%Y %H:%M") if employee.test_task_due_at else "—",
        "workdays": item.get("workdays", 0),
        "edit_url": f"/employees/{employee.id}/edit",
        "react_edit_url": f"/app/employees/{employee.id}",
        "list_kind": list_kind,
    }


def _parse_employee_stage_for_create(employee_stage: str, list_kind: str) -> Optional[str]:
    normalized_stage = (employee_stage or "").strip()
    if list_kind == "candidates":
        return "candidate"
    if normalized_stage in EMPLOYEE_STAGE_VALUES:
        return normalized_stage
    return "staff"


def _looks_like_numeric_chat_id(value: Optional[str]) -> bool:
    normalized = (value or "").strip()
    return bool(normalized) and (normalized.isdigit() or (normalized.startswith("-") and normalized[1:].isdigit()))


def _apply_employee_telegram_identity(
    employee: Employee,
    *,
    chat_id: str = "",
    chat_handle: str = "",
    db: Session | None = None,
) -> None:
    normalized_chat_id = (chat_id or "").strip()
    normalized_chat_handle = (chat_handle or "").strip()

    if normalized_chat_id:
        if _looks_like_numeric_chat_id(normalized_chat_id):
            set_primary_chat_id(employee, normalized_chat_id, db=db)
        else:
            set_public_chat_handle(employee, normalized_chat_id, db=db)

    if normalized_chat_handle:
        set_public_chat_handle(employee, normalized_chat_handle, db=db)


def _candidate_stage_transition_scenarios(
    db: Session,
    employee: Employee,
    next_candidate_stage: str,
) -> list[ScenarioTemplate]:
    normalized_next_candidate_stage = normalize_candidate_work_stage(next_candidate_stage)
    if not normalized_next_candidate_stage:
        return []
    return [
        scenario
        for scenario in db.query(ScenarioTemplate)
        .filter(
            ScenarioTemplate.scenario_kind == "scenario",
            ScenarioTemplate.trigger_mode == "candidate_hr_stage",
        )
        .order_by(ScenarioTemplate.sort_order.asc(), ScenarioTemplate.id.asc())
        .all()
        if normalize_candidate_work_stage(getattr(scenario, "candidate_work_stage_trigger", None))
        == normalized_next_candidate_stage
        and _scenario_matches_employee_role(scenario, employee)
    ]


def _queue_candidate_stage_transition_launches(
    db: Session,
    employee: Employee,
    previous_candidate_stage: str | None,
    next_candidate_stage: str | None,
) -> None:
    previous_value = normalize_candidate_work_stage(previous_candidate_stage) or ""
    next_value = normalize_candidate_work_stage(next_candidate_stage) or ""
    if previous_value == next_value or not next_value:
        return
    if _employee_list_kind(employee) != "candidates":
        return
    scenarios = _candidate_stage_transition_scenarios(db, employee, next_value)
    if not scenarios:
        return
    requested_at = utc_now()
    for scenario in scenarios:
        existing_request = (
            db.query(FlowLaunchRequest)
            .filter(
                FlowLaunchRequest.employee_id == employee.id,
                FlowLaunchRequest.flow_key == scenario.scenario_key,
                FlowLaunchRequest.launch_type == "status_transition",
                FlowLaunchRequest.processed_at.is_(None),
            )
            .first()
        )
        if existing_request:
            continue
        db.add(
            FlowLaunchRequest(
                employee_id=employee.id,
                flow_key=scenario.scenario_key,
                requested_at=requested_at,
                processed_at=None,
                launch_type="status_transition",
                skip_step_key=None,
            )
        )


def _create_employee_record(
    db: Session,
    *,
    full_name: str,
    chat_id: str,
    chat_handle: str = "",
    first_workday: str,
    employee_stage: str,
    candidate_work_stage: str,
    list_kind: str,
) -> Employee:
    first_day = datetime.strptime(first_workday, "%Y-%m-%d").date() if first_workday else None
    normalized_candidate_stage = normalize_candidate_work_stage(candidate_work_stage)
    employee = Employee(
        full_name=full_name.strip() or None,
        telegram_user_id=None,
        first_workday=first_day,
        created_at=utc_now(),
        is_flow_scheduled=False,
        candidate_status="new",
        employee_stage=_parse_employee_stage_for_create(employee_stage, list_kind),
        candidate_work_stage=(
            normalized_candidate_stage
            if list_kind == "candidates" and normalized_candidate_stage
            else None
        ),
    )
    _apply_employee_telegram_identity(employee, chat_id=chat_id, chat_handle=chat_handle)
    db.add(employee)
    db.flush()
    sync_legacy_telegram_account(db, employee)
    db.add(
        FlowLaunchRequest(
            employee_id=employee.id,
            flow_key="recruitment_hiring",
            requested_at=utc_now(),
            processed_at=None,
            launch_type="registration",
        )
    )
    db.commit()
    db.refresh(employee)
    return employee


def _apply_employee_update(
    db: Session,
    employee: Employee,
    *,
    full_name: str,
    chat_id: str,
    chat_handle: str,
    first_workday: str,
    desired_position: str,
    birth_date: str,
    work_email: str,
    work_hours: str,
    is_manager: bool,
    is_mentor: bool,
    manager_employee_id: str,
    mentor_adaptation_employee_id: str,
    mentor_ipr_employee_id: str,
    adaptation_tasks_url: str,
    adaptation_feedback_url: str,
    adaptation_midpoint: str,
    adaptation_end: str,
    employee_stage: str,
    candidate_work_stage: str,
    salary_expectation: str,
    personal_data_consent: bool,
    employee_data_consent: bool,
    is_bot_blocked: bool,
    test_task_due_at: str,
    notes: str,
    assigned_by_account_id: int | None = None,
) -> Employee:
    is_candidate = _employee_list_kind(employee) == "candidates"
    previous_candidate_work_stage = (employee.candidate_work_stage or "").strip() or None
    previous_notes = employee.notes
    first_day = _parse_optional_date(first_workday)
    parsed_birth_date = _parse_optional_date(birth_date)
    previous_stage = (employee.employee_stage or "").strip()
    previous_manager_employee_id = employee.manager_employee_id
    previous_assignments = {
        "manager_employee_id": employee.manager_employee_id,
        "mentor_adaptation_employee_id": employee.mentor_adaptation_employee_id,
        "mentor_ipr_employee_id": employee.mentor_ipr_employee_id,
    }

    employee.full_name = full_name.strip() or None
    _apply_employee_telegram_identity(employee, chat_id=chat_id, chat_handle=chat_handle, db=db)
    employee.first_workday = first_day
    employee.desired_position = resolve_employee_position_value(db, desired_position)
    employee.salary_expectation = salary_expectation.strip() or None
    employee.is_bot_blocked = is_bot_blocked

    if is_candidate:
        employee.candidate_work_stage = normalize_candidate_work_stage(candidate_work_stage)
        employee.personal_data_consent = personal_data_consent
        employee.test_task_due_at = (
            datetime.strptime(test_task_due_at, "%Y-%m-%dT%H:%M")
            if (test_task_due_at or "").strip()
            else None
        )
    else:
        manager_employee = _resolve_staff_employee_reference(
            db,
            employee=employee,
            related_employee_id=_parse_optional_int(manager_employee_id),
            field_title="Руководитель сотрудника",
            required_flag="is_manager",
        )
        mentor_adaptation_employee = _resolve_staff_employee_reference(
            db,
            employee=employee,
            related_employee_id=_parse_optional_int(mentor_adaptation_employee_id),
            field_title="Наставник адаптации",
            required_flag="is_mentor",
        )
        mentor_ipr_employee = _resolve_staff_employee_reference(
            db,
            employee=employee,
            related_employee_id=_parse_optional_int(mentor_ipr_employee_id),
            field_title="Наставник ИПР",
            required_flag="is_mentor",
        )
        employee.birth_date = parsed_birth_date
        employee.work_email = work_email.strip() or None
        employee.work_hours = work_hours.strip() or None
        employee.is_manager = is_manager
        employee.is_mentor = is_mentor
        employee.manager_employee_id = manager_employee.id if manager_employee else None
        employee.mentor_adaptation_employee_id = mentor_adaptation_employee.id if mentor_adaptation_employee else None
        employee.mentor_ipr_employee_id = mentor_ipr_employee.id if mentor_ipr_employee else None
        employee.manager_telegram_id = get_primary_chat_id(manager_employee, db=db) if manager_employee else None
        employee.mentor_adaptation_telegram_id = (
            get_primary_chat_id(mentor_adaptation_employee, db=db) if mentor_adaptation_employee else None
        )
        employee.mentor_ipr_telegram_id = get_primary_chat_id(mentor_ipr_employee, db=db) if mentor_ipr_employee else None
        employee.adaptation_tasks_url = adaptation_tasks_url.strip() or None
        employee.adaptation_feedback_url = adaptation_feedback_url.strip() or None
        employee.adaptation_midpoint = _parse_optional_date(adaptation_midpoint)
        employee.adaptation_end = _parse_optional_date(adaptation_end)
        normalized_stage = employee_stage.strip()
        employee.employee_stage = normalized_stage if normalized_stage in EMPLOYEE_STAGE_VALUES else None
        employee.employee_data_consent = employee_data_consent
        _sync_assignment_history(
            db,
            employee=employee,
            previous_assignments=previous_assignments,
            assigned_by_account_id=assigned_by_account_id,
        )

    employee.notes = notes.strip() or None
    _sync_hr_note_history(
        db,
        employee=employee,
        previous_notes=previous_notes,
        next_notes=employee.notes,
        author_account_id=assigned_by_account_id,
    )
    db.commit()
    _queue_candidate_stage_transition_launches(db, employee, previous_candidate_work_stage, employee.candidate_work_stage)
    db.commit()
    sync_legacy_telegram_account(db, employee)
    _enqueue_manager_assignment_trigger(
        db,
        subject_employee=employee,
        previous_stage=previous_stage,
        previous_manager_employee_id=previous_manager_employee_id,
    )
    db.commit()
    db.refresh(employee)
    return employee


def _serialize_employee_file(file_row: EmployeeFile, employee_id: int, can_send_to_channel: bool) -> dict:
    return {
        "id": file_row.id,
        "direction": file_row.direction,
        "category": file_row.category or "",
        "original_filename": file_row.original_filename or "",
        "created_at_label": file_row.created_at.strftime("%d.%m.%Y %H:%M") if file_row.created_at else "—",
        "download_url": f"/employees/{employee_id}/files/{file_row.id}/download",
        "send_url": f"/employees/{employee_id}/files/{file_row.id}/send",
        "delete_url": f"/api/employees/{employee_id}/files/{file_row.id}",
        "can_send_to_channel": can_send_to_channel,
    }


def _file_kind(file_row: EmployeeFile) -> str:
    mime_type = (file_row.mime_type or "").strip().lower()
    if mime_type.startswith("image/"):
        return "photo"
    if mime_type.startswith("video/"):
        return "video"
    return "file"


def _serialize_explicit_file_document(file_row: EmployeeFile, employee_id: int, *, source: str) -> dict:
    return {
        "id": file_row.id,
        "source": source,
        "label": file_row.original_filename or f"Файл #{file_row.id}",
        "kind": _file_kind(file_row),
        "employee_file_id": file_row.id,
        "original_filename": file_row.original_filename or "",
        "mime_type": file_row.mime_type or "",
        "file_size": file_row.file_size,
        "download_url": f"/employees/{employee_id}/files/{file_row.id}/download",
        "open_url": f"/employees/{employee_id}/files/{file_row.id}/download",
        "created_at": file_row.created_at.isoformat() if file_row.created_at else "",
        "created_at_label": file_row.created_at.strftime("%d.%m.%Y %H:%M") if file_row.created_at else "—",
    }


def _serialize_explicit_link_document(link_row: EmployeeDocumentLink, employee_id: int, *, source: str) -> dict:
    return {
        "id": link_row.id,
        "source": source,
        "label": link_row.title or link_row.url or f"Документ #{link_row.id}",
        "kind": "link",
        "slot_key": getattr(link_row, "slot_key", None) or "",
        "employee_file_id": getattr(link_row, "employee_file_id", None),
        "download_url": None,
        "open_url": link_row.url or "",
        "created_at": link_row.created_at.isoformat() if link_row.created_at else "",
        "created_at_label": link_row.created_at.strftime("%d.%m.%Y %H:%M") if link_row.created_at else "—",
    }


def _serialize_explicit_document_link(
    db: Session,
    link_row: EmployeeDocumentLink,
    employee_id: int,
    *,
    source: str,
) -> Optional[dict]:
    if link_row.employee_file_id:
        file_row = db.get(EmployeeFile, link_row.employee_file_id)
        if file_row:
            payload = _serialize_explicit_file_document(file_row, employee_id, source=source)
            payload["slot_key"] = getattr(link_row, "slot_key", None) or ""
            payload["document_link_id"] = link_row.id
            return payload
    if (link_row.url or "").strip():
        return _serialize_explicit_link_document(link_row, employee_id, source=source)
    return None


def _serialize_resume_file_fallback(file_row: EmployeeFile, employee_id: int) -> dict:
    return {
        "id": None,
        "slot_key": RESUME_DOCUMENT_SLOT,
        "title": RESUME_DOCUMENT_TITLE,
        "label": file_row.original_filename or f"Файл #{file_row.id}",
        "kind": _file_kind(file_row),
        "url": f"/employees/{employee_id}/files/{file_row.id}/download",
        "item_kind": "file",
        "employee_file_id": file_row.id,
        "original_filename": file_row.original_filename or "",
        "source": "legacy_file",
        "download_url": f"/employees/{employee_id}/files/{file_row.id}/download",
        "open_url": f"/employees/{employee_id}/files/{file_row.id}/download",
        "created_at": file_row.created_at.isoformat() if file_row.created_at else "",
        "created_at_label": file_row.created_at.strftime("%d.%m.%Y %H:%M") if file_row.created_at else "—",
    }


def _serialize_document_link(link_row: EmployeeDocumentLink, employee_id: int) -> dict:
    file_download_url = (
        f"/employees/{employee_id}/files/{link_row.employee_file_id}/download"
        if getattr(link_row, "employee_file_id", None)
        else None
    )
    effective_url = file_download_url or link_row.url
    return {
        "id": link_row.id,
        "slot_key": getattr(link_row, "slot_key", None) or "",
        "title": link_row.title,
        "label": link_row.title or effective_url or f"Документ #{link_row.id}",
        "url": effective_url,
        "item_kind": getattr(link_row, "item_kind", "link") or "link",
        "kind": "file" if file_download_url else "link",
        "employee_file_id": getattr(link_row, "employee_file_id", None),
        "source": "slot",
        "download_url": file_download_url,
        "open_url": effective_url,
        "created_at": link_row.created_at.isoformat() if link_row.created_at else "",
        "scenario_tag": f"{{doc:{link_row.title}}}",
        "delete_url": f"/employees/{employee_id}/document-links/{link_row.id}/delete",
    }


def _serialize_launch_request(
    launch_request: FlowLaunchRequest,
    scenario_by_key: dict[str, ScenarioTemplate],
    employee_id: int,
) -> dict:
    scenario = scenario_by_key.get(launch_request.flow_key)
    launch_type = launch_request.launch_type or "manual"
    return {
        "id": launch_request.id,
        "flow_key": launch_request.flow_key,
        "launch_type": launch_type,
        "launch_type_label": LAUNCH_TYPE_LABELS.get(launch_type, launch_type),
        "scenario_title": scenario.title if scenario else launch_request.flow_key,
        "scenario_url": f"/flows/{scenario.id}" if scenario else None,
        "requested_at_label": launch_request.requested_at.strftime("%d.%m.%Y %H:%M") if launch_request.requested_at else "—",
        "processed_at_label": launch_request.processed_at.strftime("%d.%m.%Y %H:%M") if launch_request.processed_at else "—",
        "delete_url": f"/employees/{employee_id}/schedule/{launch_request.id}/delete",
    }


def _get_employee_document_slot(
    db: Session,
    employee_id: int,
    *,
    slot_key: str,
) -> Optional[EmployeeDocumentLink]:
    query = db.query(EmployeeDocumentLink).filter(EmployeeDocumentLink.employee_id == employee_id)
    if slot_key == OFFER_DOCUMENT_SLOT:
        query = query.filter(
            (EmployeeDocumentLink.slot_key == slot_key)
            | (EmployeeDocumentLink.title == OFFER_DOCUMENT_TITLE)
        )
    elif slot_key == RESUME_DOCUMENT_SLOT:
        query = query.filter(
            (EmployeeDocumentLink.slot_key == slot_key)
            | (EmployeeDocumentLink.title == RESUME_DOCUMENT_TITLE)
        )
    else:
        query = query.filter(EmployeeDocumentLink.slot_key == slot_key)
    return query.order_by(EmployeeDocumentLink.id.asc()).first()


def _get_latest_resume_file(db: Session, employee_id: int) -> Optional[EmployeeFile]:
    return (
        db.query(EmployeeFile)
        .filter(
            EmployeeFile.employee_id == employee_id,
            EmployeeFile.category == RESUME_DOCUMENT_SLOT,
        )
        .order_by(EmployeeFile.created_at.desc(), EmployeeFile.id.desc())
        .first()
    )


def _get_latest_test_task_result_file(db: Session, employee_id: int) -> Optional[EmployeeFile]:
    return (
        db.query(EmployeeFile)
        .filter(
            EmployeeFile.employee_id == employee_id,
            EmployeeFile.category == "test_result",
        )
        .order_by(EmployeeFile.created_at.desc(), EmployeeFile.id.desc())
        .first()
    )


def _get_employee_resume_document_payload(db: Session, employee_id: int) -> Optional[dict]:
    resume_slot = _get_employee_document_slot(db, employee_id, slot_key=RESUME_DOCUMENT_SLOT)
    if resume_slot:
        payload = _serialize_document_link(resume_slot, employee_id)
        if resume_slot.employee_file_id:
            file_row = db.get(EmployeeFile, resume_slot.employee_file_id)
            if file_row:
                payload["original_filename"] = file_row.original_filename or ""
        return payload
    latest_resume_file = _get_latest_resume_file(db, employee_id)
    if latest_resume_file:
        return _serialize_resume_file_fallback(latest_resume_file, employee_id)
    return None


def _get_employee_test_task_result_payload(db: Session, employee_id: int) -> Optional[dict]:
    test_result_slot = _get_employee_document_slot(db, employee_id, slot_key=TEST_TASK_RESULT_SLOT)
    if test_result_slot:
        payload = _serialize_explicit_document_link(db, test_result_slot, employee_id, source="slot")
        if payload:
            return payload
    latest_test_result_file = _get_latest_test_task_result_file(db, employee_id)
    if latest_test_result_file:
        return _serialize_explicit_file_document(latest_test_result_file, employee_id, source="legacy_file")
    return None


def _save_offer_document_link(db: Session, employee_id: int, url: str) -> tuple[Optional[EmployeeDocumentLink], Optional[str]]:
    url_value = url.strip()
    if not url_value:
        return None, "Укажи ссылку на оффер."

    existing_link = _get_employee_document_slot(db, employee_id, slot_key=OFFER_DOCUMENT_SLOT)
    if existing_link:
        previous_file_id = existing_link.employee_file_id
        existing_link.slot_key = OFFER_DOCUMENT_SLOT
        existing_link.url = url_value
        existing_link.item_kind = "link"
        existing_link.employee_file_id = None
        link_row = existing_link
    else:
        link_row = EmployeeDocumentLink(
            employee_id=employee_id,
            slot_key=OFFER_DOCUMENT_SLOT,
            title=OFFER_DOCUMENT_TITLE,
            url=url_value,
            item_kind="link",
            employee_file_id=None,
            created_at=utc_now(),
        )
        db.add(link_row)
        previous_file_id = None
    if previous_file_id:
        previous_file = db.get(EmployeeFile, previous_file_id)
        if previous_file:
            previous_path = Path(previous_file.stored_path)
            try:
                if previous_path.exists():
                    previous_path.unlink()
            except OSError:
                pass
            db.delete(previous_file)
    db.commit()
    db.refresh(link_row)
    return link_row, None


def _save_offer_document_file(
    db: Session,
    employee: Employee,
    *,
    filename: str,
    content: bytes,
    mime_type: Optional[str],
) -> EmployeeDocumentLink:
    destination = build_employee_file_path(employee.id, filename)
    destination.write_bytes(content)
    db_file = EmployeeFile(
        employee_id=employee.id,
        direction="outbound",
        category="offer_document",
        telegram_file_id=None,
        telegram_file_unique_id=None,
        original_filename=filename,
        stored_path=str(destination),
        mime_type=mime_type,
        file_size=len(content),
        created_at=utc_now(),
    )
    db.add(db_file)
    db.flush()

    existing_link = _get_employee_document_slot(db, employee.id, slot_key=OFFER_DOCUMENT_SLOT)
    previous_file_id = existing_link.employee_file_id if existing_link else None
    if existing_link:
        existing_link.slot_key = OFFER_DOCUMENT_SLOT
        existing_link.url = ""
        existing_link.item_kind = "file"
        existing_link.employee_file_id = db_file.id
        existing_link.title = OFFER_DOCUMENT_TITLE
        link_row = existing_link
    else:
        link_row = EmployeeDocumentLink(
            employee_id=employee.id,
            slot_key=OFFER_DOCUMENT_SLOT,
            title=OFFER_DOCUMENT_TITLE,
            url="",
            item_kind="file",
            employee_file_id=db_file.id,
            created_at=utc_now(),
        )
        db.add(link_row)

    if previous_file_id and previous_file_id != db_file.id:
        previous_file = db.get(EmployeeFile, previous_file_id)
        if previous_file:
            previous_path = Path(previous_file.stored_path)
            try:
                if previous_path.exists():
                    previous_path.unlink()
            except OSError:
                pass
            db.delete(previous_file)

    db.commit()
    db.refresh(link_row)
    return link_row


def _upsert_resume_document_slot(db: Session, employee_id: int, employee_file_id: int) -> EmployeeDocumentLink:
    link_row = _get_employee_document_slot(db, employee_id, slot_key=RESUME_DOCUMENT_SLOT)
    if link_row:
        link_row.slot_key = RESUME_DOCUMENT_SLOT
        link_row.title = RESUME_DOCUMENT_TITLE
        link_row.url = ""
        link_row.item_kind = "file"
        link_row.employee_file_id = employee_file_id
    else:
        link_row = EmployeeDocumentLink(
            employee_id=employee_id,
            slot_key=RESUME_DOCUMENT_SLOT,
            title=RESUME_DOCUMENT_TITLE,
            url="",
            item_kind="file",
            employee_file_id=employee_file_id,
            created_at=utc_now(),
        )
        db.add(link_row)
    return link_row


def _save_resume_document_file(
    db: Session,
    employee: Employee,
    *,
    filename: str,
    content: bytes,
    mime_type: Optional[str],
) -> EmployeeDocumentLink:
    destination = build_employee_file_path(employee.id, filename)
    destination.write_bytes(content)
    db_file = EmployeeFile(
        employee_id=employee.id,
        direction="inbound",
        category=RESUME_DOCUMENT_SLOT,
        telegram_file_id=None,
        telegram_file_unique_id=None,
        original_filename=filename,
        stored_path=str(destination),
        mime_type=mime_type,
        file_size=len(content),
        created_at=utc_now(),
    )
    db.add(db_file)
    db.flush()
    link_row = _upsert_resume_document_slot(db, employee.id, db_file.id)
    db.commit()
    db.refresh(link_row)
    return link_row


def _clear_resume_document_slot(db: Session, employee_id: int) -> None:
    link_row = _get_employee_document_slot(db, employee_id, slot_key=RESUME_DOCUMENT_SLOT)
    if link_row:
        db.delete(link_row)
        db.commit()


def _delete_employee_document_link(db: Session, link_row: EmployeeDocumentLink) -> None:
    employee_file_id = getattr(link_row, "employee_file_id", None)
    is_resume_slot = (getattr(link_row, "slot_key", None) or "").strip() == RESUME_DOCUMENT_SLOT
    db.delete(link_row)
    if employee_file_id and not is_resume_slot:
        employee_file = db.get(EmployeeFile, employee_file_id)
        if employee_file:
            file_path = Path(employee_file.stored_path)
            try:
                if file_path.exists():
                    file_path.unlink()
            except OSError:
                pass
            db.delete(employee_file)
    db.commit()


def _delete_employee_record(db: Session, employee: Employee) -> str:
    redirect_url = "/candidates" if _employee_list_kind(employee) == "candidates" else "/employees"
    employee_id = employee.id
    employee_files = db.query(EmployeeFile).filter(EmployeeFile.employee_id == employee_id).all()
    for file_row in employee_files:
        path = Path(file_row.stored_path)
        try:
            if path.exists():
                path.unlink()
        except OSError:
            pass
        db.delete(file_row)

    employee_document_links = db.query(EmployeeDocumentLink).filter(EmployeeDocumentLink.employee_id == employee_id).all()
    for link_row in employee_document_links:
        db.delete(link_row)

    employee_dir = Path(settings.FILE_STORAGE_DIR).expanduser().resolve() / str(employee_id)
    if employee_dir.exists():
        shutil.rmtree(employee_dir, ignore_errors=True)

    db.delete(employee)
    db.commit()
    return redirect_url


def _promote_candidate_to_adaptation(db: Session, employee: Employee) -> Employee:
    normalized_stage = (employee.employee_stage or "").strip()
    if normalized_stage != "candidate":
        raise ValueError("В адаптацию можно перевести только кандидата.")
    if not employee.first_workday:
        raise ValueError("Для перевода в адаптацию сначала укажите первый день сотрудника.")

    employee.employee_stage = "adaptation"
    employee.candidate_work_stage = None
    employee.current_menu_set_id = None
    employee.current_menu_path = None
    if employee.adaptation_midpoint is None:
        employee.adaptation_midpoint = add_workdays(employee.first_workday, settings.PROBATION_WORKDAYS // 2)
    if employee.adaptation_end is None:
        employee.adaptation_end = add_workdays(employee.first_workday, settings.PROBATION_WORKDAYS)
    db.commit()
    db.refresh(employee)
    return employee


def _reset_employee_bot_linkage(db: Session, employee: Employee) -> Employee:
    db.query(EmployeeMessengerAccount).filter(
        EmployeeMessengerAccount.employee_id == employee.id,
    ).delete(synchronize_session=False)
    db.query(ScenarioProgress).filter(
        ScenarioProgress.employee_id == employee.id,
    ).delete(synchronize_session=False)
    db.query(FlowLaunchRequest).filter(
        FlowLaunchRequest.employee_id == employee.id,
        FlowLaunchRequest.processed_at.is_(None),
    ).delete(synchronize_session=False)

    employee.telegram_user_id = None
    employee.telegram_username = None
    employee.current_menu_set_id = None
    employee.is_flow_scheduled = False

    db.commit()
    db.refresh(employee)
    return employee


def _schedule_employee_flow_request(
    db: Session,
    employee: Employee,
    *,
    flow_key: str,
    requested_at: str,
) -> Optional[str]:
    if employee.is_bot_blocked:
        return "Для этого сотрудника доступ к боту заблокирован."
    scenario = db.query(ScenarioTemplate).filter(ScenarioTemplate.scenario_key == flow_key).first()
    if not scenario:
        return "Сценарий не найден."
    if not _scenario_matches_employee_role(scenario, employee):
        return "Сценарий недоступен для роли этого сотрудника."
    if not (requested_at or "").strip():
        return "Укажи дату и время запуска сценария."
    try:
        run_at = datetime.strptime(requested_at.strip(), "%Y-%m-%dT%H:%M")
    except ValueError:
        return "Неверный формат даты и времени."

    db.add(
        FlowLaunchRequest(
            employee_id=employee.id,
            flow_key=flow_key,
            requested_at=run_at,
            processed_at=None,
            launch_type="scheduled",
            skip_step_key=None,
        )
    )
    db.commit()
    return None


async def _launch_employee_flow_now(
    db: Session,
    employee: Employee,
    *,
    flow_key: str,
) -> Optional[str]:
    if employee.is_bot_blocked:
        return "Для этого сотрудника доступ к боту заблокирован."
    scenario = db.query(ScenarioTemplate).filter(ScenarioTemplate.scenario_key == flow_key).first()
    if not scenario:
        return "Сценарий не найден."
    if not get_primary_chat_id(employee, db=db):
        return "У сотрудника не указан ID пользователя в канале."
    chat_id = get_primary_chat_id(employee, db=db)
    if chat_id and not (chat_id.isdigit() or (chat_id.startswith("-") and chat_id[1:].isdigit())):
        return "У сотрудника указан не числовой Telegram chat id. Для запуска сценария нужен chat id из диалога с ботом."
    if not _scenario_matches_employee_role(scenario, employee):
        return "Сценарий недоступен для роли этого сотрудника."
    if not settings.TELEGRAM_BOT_TOKEN:
        return "Не задан TELEGRAM_BOT_TOKEN."

    first_step = get_first_step(db, scenario.scenario_key)
    if not first_step:
        return "В сценарии нет шагов для запуска."

    messenger = create_telegram_messenger(settings.TELEGRAM_BOT_TOKEN)
    try:
        started = await start_scenario(messenger, db, employee, scenario.scenario_key)
        if not started:
            return "Сценарий не удалось запустить."

        db.add(
            FlowLaunchRequest(
                employee_id=employee.id,
                flow_key=flow_key,
                requested_at=datetime.now(),
                processed_at=datetime.now(),
                launch_type="manual",
                skip_step_key=None,
            )
        )
        db.commit()
        return None
    except TelegramBadRequest as exc:
        message = str(exc)
        if "chat not found" in message.lower():
            return "Telegram не находит этот чат. Сотрудник должен сначала открыть бота и нажать Start, а в карточке должен быть сохранен его chat id."
        return f"Telegram отказал в запуске сценария: {exc}"
    except Exception as exc:
        return f"Ошибка запуска сценария: {exc}"
    finally:
        await messenger.close()


async def _send_file_to_telegram(chat_id: str, path: Path, filename: str) -> None:
    messenger = create_telegram_messenger(settings.TELEGRAM_BOT_TOKEN, parse_mode=None)
    try:
        await messenger.send_document_path(chat_id=chat_id, path=path, filename=filename)
    finally:
        await messenger.close()


def _append_manual_bot_message_log(
    db: Session,
    *,
    employee_id: int,
    sender_account_id: Optional[int],
    message_text: str,
    status: str,
    error_text: Optional[str] = None,
    sent_at: Optional[datetime] = None,
) -> EmployeeManualBotMessage:
    row = EmployeeManualBotMessage(
        employee_id=employee_id,
        sender_account_id=sender_account_id,
        message_text=message_text,
        status=status,
        error_text=error_text,
        sent_at=sent_at,
        created_at=utc_now(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


async def _send_manual_bot_message(
    db: Session,
    employee: Employee,
    *,
    text: str,
    sender_account_id: Optional[int],
) -> Optional[str]:
    message_text = str(text or "").strip()
    if not message_text:
        return "Введите текст сообщения."
    if employee.is_bot_blocked:
        error_message = "Для этого сотрудника доступ к боту заблокирован."
        _append_manual_bot_message_log(
            db,
            employee_id=employee.id,
            sender_account_id=sender_account_id,
            message_text=message_text,
            status=MANUAL_BOT_MESSAGE_STATUS_FAILED,
            error_text=error_message,
        )
        return error_message

    chat_id = (get_primary_chat_id(employee, db=db) or "").strip()
    if not chat_id:
        error_message = "У сотрудника не указан Telegram chat id."
        _append_manual_bot_message_log(
            db,
            employee_id=employee.id,
            sender_account_id=sender_account_id,
            message_text=message_text,
            status=MANUAL_BOT_MESSAGE_STATUS_FAILED,
            error_text=error_message,
        )
        return error_message
    if not (chat_id.isdigit() or (chat_id.startswith("-") and chat_id[1:].isdigit())):
        error_message = (
            "У сотрудника указан не числовой Telegram chat id. Для отправки нужен chat id из диалога с ботом."
        )
        _append_manual_bot_message_log(
            db,
            employee_id=employee.id,
            sender_account_id=sender_account_id,
            message_text=message_text,
            status=MANUAL_BOT_MESSAGE_STATUS_FAILED,
            error_text=error_message,
        )
        return error_message
    if not settings.TELEGRAM_BOT_TOKEN:
        error_message = "Не задан TELEGRAM_BOT_TOKEN."
        _append_manual_bot_message_log(
            db,
            employee_id=employee.id,
            sender_account_id=sender_account_id,
            message_text=message_text,
            status=MANUAL_BOT_MESSAGE_STATUS_FAILED,
            error_text=error_message,
        )
        return error_message

    messenger = create_telegram_messenger(settings.TELEGRAM_BOT_TOKEN)
    try:
        await messenger.send_text(chat_id=chat_id, text=message_text)
    except Exception as exc:
        error_message = str(exc).strip() or exc.__class__.__name__
        _append_manual_bot_message_log(
            db,
            employee_id=employee.id,
            sender_account_id=sender_account_id,
            message_text=message_text,
            status=MANUAL_BOT_MESSAGE_STATUS_FAILED,
            error_text=error_message,
        )
        return error_message
    finally:
        try:
            await messenger.close()
        except Exception:
            pass

    _append_manual_bot_message_log(
        db,
        employee_id=employee.id,
        sender_account_id=sender_account_id,
        message_text=message_text,
        status=MANUAL_BOT_MESSAGE_STATUS_SENT,
        sent_at=utc_now(),
    )
    return None


def _build_employee_detail_payload(db: Session, employee: Employee) -> dict:
    employee_files = (
        db.query(EmployeeFile)
        .filter(
            EmployeeFile.employee_id == employee.id,
            (EmployeeFile.category.is_(None)) | (~EmployeeFile.category.in_(SEMANTIC_FILE_CATEGORIES)),
        )
        .order_by(EmployeeFile.id.desc())
        .all()
    )
    employee_document_links = (
        db.query(EmployeeDocumentLink)
        .filter(
            EmployeeDocumentLink.employee_id == employee.id,
            (EmployeeDocumentLink.slot_key.is_(None)) | (~EmployeeDocumentLink.slot_key.in_(SEMANTIC_DOCUMENT_SLOTS)),
        )
        .order_by(EmployeeDocumentLink.created_at.desc(), EmployeeDocumentLink.id.desc())
        .all()
    )
    offer_document_link = _get_employee_document_slot(db, employee.id, slot_key=OFFER_DOCUMENT_SLOT)
    resume_document = _get_employee_resume_document_payload(db, employee.id)
    test_task_result = _get_employee_test_task_result_payload(db, employee.id)
    scenarios = _available_scenarios_for_employee(db, employee)
    scenario_by_key = {scenario.scenario_key: scenario for scenario in db.query(ScenarioTemplate).all()}
    pending_scheduled_launches = (
        db.query(FlowLaunchRequest)
        .filter(
            FlowLaunchRequest.employee_id == employee.id,
            FlowLaunchRequest.launch_type == "scheduled",
            FlowLaunchRequest.processed_at.is_(None),
        )
        .order_by(FlowLaunchRequest.requested_at.asc(), FlowLaunchRequest.id.asc())
        .all()
    )
    pending_scheduled_launches = [
        launch_request
        for launch_request in pending_scheduled_launches
        if not _is_internal_followup_request(launch_request)
    ]
    manual_launch_history = (
        db.query(FlowLaunchRequest)
        .filter(
            FlowLaunchRequest.employee_id == employee.id,
            FlowLaunchRequest.launch_type == "manual",
            FlowLaunchRequest.processed_at.is_not(None),
        )
        .order_by(FlowLaunchRequest.processed_at.desc(), FlowLaunchRequest.id.desc())
        .all()
    )
    automatic_launch_history = (
        db.query(FlowLaunchRequest)
        .filter(
            FlowLaunchRequest.employee_id == employee.id,
            FlowLaunchRequest.launch_type.in_(AUTOMATIC_LAUNCH_TYPES),
            FlowLaunchRequest.processed_at.is_not(None),
        )
        .order_by(FlowLaunchRequest.processed_at.desc(), FlowLaunchRequest.id.desc())
        .all()
    )
    system_launch_history = (
        db.query(FlowLaunchRequest)
        .filter(
            FlowLaunchRequest.employee_id == employee.id,
            FlowLaunchRequest.launch_type.in_(SYSTEM_LAUNCH_TYPES),
            FlowLaunchRequest.processed_at.is_not(None),
        )
        .order_by(FlowLaunchRequest.processed_at.desc(), FlowLaunchRequest.id.desc())
        .all()
    )
    employee_role_values = employee_position_values(db, current_value=employee.desired_position or "")

    today = datetime.now().date()
    list_kind = _employee_list_kind(employee)
    is_candidate = list_kind == "candidates"
    primary_chat_id = get_primary_chat_id(employee, db=db) or ""

    return {
        "meta": {
            "list_kind": list_kind,
            "is_candidate": is_candidate,
            "status_label": _employee_status_label(employee),
            "candidate_work_stage_label": _candidate_work_stage_label(employee),
            "tenure_years": _full_years_between(employee.first_workday, today),
            "list_url": "/app/employees?list_kind=candidates" if is_candidate else "/app/employees",
            "list_title": "к списку кандидатов" if is_candidate else "к списку сотрудников",
            "classic_edit_url": f"/employees/{employee.id}/edit",
            "react_edit_url": f"/app/employees/{employee.id}",
            "employee_card_image_url": f"/employees/{employee.id}/card-image",
        },
        "employee": {
            "id": employee.id,
            "full_name": employee.full_name or "",
            "chat_id": primary_chat_id or "",
            "chat_handle": get_public_chat_handle(employee, db=db) or "",
            "first_workday": employee.first_workday.isoformat() if employee.first_workday else "",
            "desired_position": employee.desired_position or "",
            "birth_date": employee.birth_date.isoformat() if employee.birth_date else "",
            "work_email": employee.work_email or "",
            "work_hours": employee.work_hours or "",
            "manager_employee_id": str(employee.manager_employee_id or ""),
            "mentor_adaptation_employee_id": str(employee.mentor_adaptation_employee_id or ""),
            "mentor_ipr_employee_id": str(employee.mentor_ipr_employee_id or ""),
            "is_manager": bool(employee.is_manager),
            "is_mentor": bool(employee.is_mentor),
            "adaptation_tasks_url": employee.adaptation_tasks_url or "",
            "adaptation_feedback_url": employee.adaptation_feedback_url or "",
            "adaptation_midpoint": employee.adaptation_midpoint.isoformat() if employee.adaptation_midpoint else "",
            "adaptation_end": employee.adaptation_end.isoformat() if employee.adaptation_end else "",
            "employee_stage": employee.employee_stage or "",
            "candidate_work_stage": employee.candidate_work_stage or "",
            "salary_expectation": employee.salary_expectation or "",
            "personal_data_consent": bool(employee.personal_data_consent),
            "employee_data_consent": bool(employee.employee_data_consent),
            "is_bot_blocked": bool(employee.is_bot_blocked),
            "test_task_due_at": employee.test_task_due_at.strftime("%Y-%m-%dT%H:%M") if employee.test_task_due_at else "",
            "notes": employee.notes or "",
            "is_flow_scheduled": bool(employee.is_flow_scheduled),
        },
        "options": {
            "employee_role_values": employee_role_values,
            "employee_stage_values": [
                {"value": value, "label": label}
                for value, label in EMPLOYEE_STAGE_VALUES.items()
                if value != "candidate"
            ],
            "candidate_work_stage_values": [
                {"value": value, "label": label}
                for value, label in VISIBLE_CANDIDATE_WORK_STAGE_VALUES.items()
            ],
            "staff_employee_values": _staff_employee_options(db, employee.id),
            "manager_employee_values": _staff_employee_options_by_flag(
                db,
                current_employee_id=employee.id,
                role_flag="is_manager",
                selected_employee_ids=[employee.manager_employee_id] if employee.manager_employee_id else [],
            ),
            "mentor_employee_values": _staff_employee_options_by_flag(
                db,
                current_employee_id=employee.id,
                role_flag="is_mentor",
                selected_employee_ids=[
                    value
                    for value in [employee.mentor_adaptation_employee_id, employee.mentor_ipr_employee_id]
                    if value
                ],
            ),
            "scenarios": [{"value": scenario.scenario_key, "label": scenario.title} for scenario in scenarios],
        },
        "files": [_serialize_employee_file(file_row, employee.id, bool(primary_chat_id)) for file_row in employee_files],
        "document_links": [_serialize_document_link(link_row, employee.id) for link_row in employee_document_links],
        "offer_document": _serialize_document_link(offer_document_link, employee.id) if offer_document_link else None,
        "resume_document": resume_document,
        "test_assignment_answer": test_task_result,
        "test_task_result": test_task_result,
        "scheduled_launches": [
            _serialize_launch_request(launch_request, scenario_by_key, employee.id)
            for launch_request in pending_scheduled_launches
        ],
        "manual_launch_history": [
            _serialize_launch_request(launch_request, scenario_by_key, employee.id)
            for launch_request in manual_launch_history
        ],
        "automatic_launch_history": [
            _serialize_launch_request(launch_request, scenario_by_key, employee.id)
            for launch_request in automatic_launch_history
        ],
        "system_launch_history": [
            _serialize_launch_request(launch_request, scenario_by_key, employee.id)
            for launch_request in system_launch_history
        ],
        "assignment_history": _serialize_assignment_history(db, employee.id),
        "manual_bot_message_history": _serialize_manual_bot_message_history(db, employee.id),
        "hr_notes_history": _serialize_hr_notes_history(db, employee.id),
    }
