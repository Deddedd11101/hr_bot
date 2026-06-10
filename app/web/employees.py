import shutil
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from aiogram.exceptions import TelegramBadRequest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import settings
from ..file_storage import build_employee_file_path
from ..flow_templates import EMPLOYEE_ROLE_VALUES
from ..messaging import create_telegram_messenger
from ..messaging.identity import (
    EmployeeIdentityConflictError,
    get_primary_chat_id,
    get_public_chat_handle,
    set_primary_chat_id,
    set_public_chat_handle,
    sync_legacy_telegram_account,
)
from ..models import Employee, EmployeeDocumentLink, EmployeeFile, FlowLaunchRequest, ScenarioTemplate
from ..scenario_engine import add_workdays, get_first_step, get_scenario_steps, matches_role_scope, start_scenario
from ..time_utils import utc_now

OFFER_DOCUMENT_TITLE = "Оффер"

EMPLOYEE_STAGE_VALUES = {
    "candidate": "Кандидат",
    "adaptation": "Адаптация",
    "ipr": "ИПР",
    "staff": "В штате",
}

CANDIDATE_WORK_STAGE_VALUES = {
    "testing": "Тестирование",
    "offer": "Оффер",
    "candidate_decline": "Отказ кандидата",
    "company_decline": "Наш отказ",
    "preonboarding": "Преонбординг",
    "contract": "Заключение договора",
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
    return related_employee


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
) -> Employee:
    is_candidate = _employee_list_kind(employee) == "candidates"
    first_day = _parse_optional_date(first_workday)
    parsed_birth_date = _parse_optional_date(birth_date)

    employee.full_name = full_name.strip() or None
    _apply_employee_telegram_identity(employee, chat_id=chat_id, chat_handle=chat_handle, db=db)
    employee.first_workday = first_day
    normalized_position = desired_position.strip()
    employee.desired_position = normalized_position or None
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
        )
        mentor_adaptation_employee = _resolve_staff_employee_reference(
            db,
            employee=employee,
            related_employee_id=_parse_optional_int(mentor_adaptation_employee_id),
            field_title="Наставник адаптации",
        )
        mentor_ipr_employee = _resolve_staff_employee_reference(
            db,
            employee=employee,
            related_employee_id=_parse_optional_int(mentor_ipr_employee_id),
            field_title="Наставник ИПР",
        )
        employee.birth_date = parsed_birth_date
        employee.work_email = work_email.strip() or None
        employee.work_hours = work_hours.strip() or None
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

    employee.notes = notes.strip() or None
    db.commit()
    sync_legacy_telegram_account(db, employee)
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
    return {
        "id": link_row.id,
        "title": link_row.title,
        "url": link_row.url,
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


def _save_offer_document_link(db: Session, employee_id: int, url: str) -> tuple[Optional[EmployeeDocumentLink], Optional[str]]:
    url_value = url.strip()
    if not url_value:
        return None, "Укажи ссылку на оффер."

    existing_link = (
        db.query(EmployeeDocumentLink)
        .filter(
            EmployeeDocumentLink.employee_id == employee_id,
            EmployeeDocumentLink.title == OFFER_DOCUMENT_TITLE,
        )
        .order_by(EmployeeDocumentLink.id.asc())
        .first()
    )
    if existing_link:
        existing_link.url = url_value
        link_row = existing_link
    else:
        link_row = EmployeeDocumentLink(
            employee_id=employee_id,
            title=OFFER_DOCUMENT_TITLE,
            url=url_value,
            created_at=utc_now(),
        )
        db.add(link_row)
    db.commit()
    db.refresh(link_row)
    return link_row, None


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
    if employee.adaptation_midpoint is None:
        employee.adaptation_midpoint = add_workdays(employee.first_workday, settings.PROBATION_WORKDAYS // 2)
    if employee.adaptation_end is None:
        employee.adaptation_end = add_workdays(employee.first_workday, settings.PROBATION_WORKDAYS)
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

        steps = get_scenario_steps(db, scenario.scenario_key)
        if first_step.response_type == "none" and len(steps) > 1:
            db.add(
                FlowLaunchRequest(
                    employee_id=employee.id,
                    flow_key=flow_key,
                    requested_at=datetime.now(),
                    processed_at=None,
                    launch_type="manual",
                    skip_step_key=first_step.step_key,
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
            EmployeeDocumentLink.title == OFFER_DOCUMENT_TITLE,
        )
        .order_by(EmployeeDocumentLink.created_at.desc(), EmployeeDocumentLink.id.desc())
        .all()
    )
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
    employee_role_values = list(EMPLOYEE_ROLE_VALUES)
    current_position = (employee.desired_position or "").strip()
    if current_position and current_position not in employee_role_values:
        employee_role_values.append(current_position)

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
                for value, label in CANDIDATE_WORK_STAGE_VALUES.items()
            ],
            "staff_employee_values": _staff_employee_options(db, employee.id),
            "scenarios": [{"value": scenario.scenario_key, "label": scenario.title} for scenario in scenarios],
        },
        "files": [_serialize_employee_file(file_row, employee.id, bool(primary_chat_id)) for file_row in employee_files],
        "document_links": [_serialize_document_link(link_row, employee.id) for link_row in employee_document_links],
        "scheduled_launches": [
            _serialize_launch_request(launch_request, scenario_by_key, employee.id)
            for launch_request in pending_scheduled_launches
        ],
        "manual_launch_history": [
            _serialize_launch_request(launch_request, scenario_by_key, employee.id)
            for launch_request in manual_launch_history
        ],
    }


