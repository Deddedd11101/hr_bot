import shutil
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from aiogram.exceptions import TelegramBadRequest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import settings
from ..file_storage import build_employee_file_path
from ..flow_templates import CANDIDATE_WORK_STAGE_LABELS
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
    Employee,
    EmployeeAssignmentHistory,
    EmployeeDocumentLink,
    EmployeeFile,
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
    if not next_candidate_stage:
        return []
    return [
        scenario
        for scenario in db.query(ScenarioTemplate)
        .filter(
            ScenarioTemplate.scenario_kind == "scenario",
            ScenarioTemplate.trigger_mode == "candidate_hr_stage",
            ScenarioTemplate.candidate_work_stage_trigger == next_candidate_stage,
        )
        .order_by(ScenarioTemplate.sort_order.asc(), ScenarioTemplate.id.asc())
        .all()
        if _scenario_matches_employee_role(scenario, employee)
    ]


def _queue_candidate_stage_transition_launches(
    db: Session,
    employee: Employee,
    previous_candidate_stage: str | None,
    next_candidate_stage: str | None,
) -> None:
    previous_value = (previous_candidate_stage or "").strip()
    next_value = (next_candidate_stage or "").strip()
    if previous_value == next_value or not next_value:
        return
    if _employee_list_kind(employee) != "candidates":
        return
    scenarios = _candidate_stage_transition_scenarios(db, employee, next_value)
    if not scenarios:
        return
    requested_at = utc_now()
    for scenario in scenarios:
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
    normalized_candidate_stage = (candidate_work_stage or "").strip()
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
            if list_kind == "candidates" and normalized_candidate_stage in CANDIDATE_WORK_STAGE_VALUES
            else ("testing" if list_kind == "candidates" else None)
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
        normalized_candidate_work_stage = candidate_work_stage.strip()
        employee.candidate_work_stage = (
            normalized_candidate_work_stage
            if normalized_candidate_work_stage in CANDIDATE_WORK_STAGE_VALUES
            else None
        )
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
        "original_filename": file_row.original_filename or "",
        "created_at_label": file_row.created_at.strftime("%d.%m.%Y %H:%M") if file_row.created_at else "—",
        "download_url": f"/employees/{employee_id}/files/{file_row.id}/download",
        "send_url": f"/employees/{employee_id}/files/{file_row.id}/send",
        "delete_url": f"/api/employees/{employee_id}/files/{file_row.id}",
        "can_send_to_channel": can_send_to_channel,
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
        "url": effective_url,
        "item_kind": getattr(link_row, "item_kind", "link") or "link",
        "employee_file_id": getattr(link_row, "employee_file_id", None),
        "scenario_tag": f"{{doc:{link_row.title}}}",
        "delete_url": f"/employees/{employee_id}/document-links/{link_row.id}/delete",
    }


def _serialize_launch_request(
    launch_request: FlowLaunchRequest,
    scenario_by_key: dict[str, ScenarioTemplate],
    employee_id: int,
) -> dict:
    scenario = scenario_by_key.get(launch_request.flow_key)
    return {
        "id": launch_request.id,
        "flow_key": launch_request.flow_key,
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
    else:
        query = query.filter(EmployeeDocumentLink.slot_key == slot_key)
    return query.order_by(EmployeeDocumentLink.id.asc()).first()


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


def _delete_employee_document_link(db: Session, link_row: EmployeeDocumentLink) -> None:
    employee_file_id = getattr(link_row, "employee_file_id", None)
    db.delete(link_row)
    if employee_file_id:
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


def _build_employee_detail_payload(db: Session, employee: Employee) -> dict:
    employee_files = (
        db.query(EmployeeFile)
        .filter(EmployeeFile.employee_id == employee.id)
        .order_by(EmployeeFile.id.desc())
        .all()
    )
    employee_document_links = (
        db.query(EmployeeDocumentLink)
        .filter(
            EmployeeDocumentLink.employee_id == employee.id,
        )
        .order_by(EmployeeDocumentLink.created_at.desc(), EmployeeDocumentLink.id.desc())
        .all()
    )
    offer_document_link = _get_employee_document_slot(db, employee.id, slot_key=OFFER_DOCUMENT_SLOT)
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
        "scheduled_launches": [
            _serialize_launch_request(launch_request, scenario_by_key, employee.id)
            for launch_request in pending_scheduled_launches
        ],
        "manual_launch_history": [
            _serialize_launch_request(launch_request, scenario_by_key, employee.id)
            for launch_request in manual_launch_history
        ],
        "assignment_history": _serialize_assignment_history(db, employee.id),
    }
