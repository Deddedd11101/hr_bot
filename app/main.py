from datetime import datetime, date, timedelta
from io import BytesIO
from pathlib import Path
import shutil
from typing import List, Optional
from collections import defaultdict

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import FSInputFile
from fastapi import Depends, FastAPI, File, Form, Request, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .auth import ROLE_LABELS, authenticate_account, hash_password
from .config import settings
from .database import get_session, init_db
from .flow_templates import (
    EMPLOYEE_ROLE_VALUES,
    RESPONSE_TYPE_LABELS,
    ROLE_SCOPE_LABELS,
    SEND_MODE_LABELS,
    TARGET_FIELD_LABELS,
    TRIGGER_MODE_LABELS,
)
from .file_storage import build_employee_file_path, build_step_attachment_path
from .models import (
    AdminAccount,
    BotMenuButton,
    BotMenuSet,
    Employee,
    EmployeeFile,
    FlowLaunchRequest,
    FlowStepTemplate,
    HrSettings,
    MassMessageAction,
    MassScenarioAction,
    ScenarioProgress,
    ScenarioTemplate,
    SurveyAnswer,
)
from .scenario_engine import format_message, get_first_step, get_scenario_steps, start_scenario


AUTH_COOKIE_NAME = "hr_admin_auth"

app = FastAPI(title="HR Bot Admin")

templates = Jinja2Templates(directory="app/templates")

app.mount("/static", StaticFiles(directory="app/static"), name="static")


def get_db():
    with get_session() as db:
        yield db


@app.middleware("http")
async def load_current_user(request: Request, call_next):
    request.state.current_user = None
    user_id = request.cookies.get(AUTH_COOKIE_NAME)
    if user_id and str(user_id).isdigit():
        with get_session() as db:
            request.state.current_user = db.get(AdminAccount, int(user_id))
    return await call_next(request)


def _render(request: Request, template_name: str, context: dict):
    context = dict(context)
    context["request"] = request
    context["current_user"] = getattr(request.state, "current_user", None)
    context["role_labels"] = ROLE_LABELS
    return templates.TemplateResponse(template_name, context)


def _redirect_login() -> RedirectResponse:
    return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)


def _require_auth(request: Request) -> Optional[RedirectResponse]:
    if getattr(request.state, "current_user", None):
        return None
    return _redirect_login()


def _require_admin(request: Request) -> Optional[RedirectResponse]:
    current_user = getattr(request.state, "current_user", None)
    if not current_user:
        return _redirect_login()
    if current_user and current_user.role == "admin":
        return None
    return RedirectResponse(url="/settings", status_code=status.HTTP_303_SEE_OTHER)


def _is_workday(d: date) -> bool:
    return d.weekday() < 5


def _workdays_between(start: Optional[date], end: date) -> int:
    if not start:
        return 0
    if end <= start:
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


def _scenario_matches_employee_role(scenario: ScenarioTemplate, employee: Employee) -> bool:
    if scenario.role_scope == "all":
        return True
    role_map = {
        "designer": "Дизайнер",
        "project_manager": "Project manager",
        "analyst": "Аналитик",
    }
    return (employee.desired_position or "") == role_map.get(scenario.role_scope, "")


EMPLOYEE_STAGE_VALUES = {
    "candidate": "Кандидат",
    "first_day": "Первый день",
    "probation": "Испытательный срок",
    "employee": "Сотрудник (в штате)",
}

MASS_TARGET_NONE = "__none__"
MASS_TARGET_OPTIONS = [
    (MASS_TARGET_NONE, "Не указан"),
    ("candidate", "Кандидат"),
    ("first_day", "Первый день"),
    ("probation", "Испытательный срок"),
    ("employee", "Сотрудник (в штате)"),
]


def _employee_edit_redirect(employee_id: int, flash_message: Optional[str] = None, flash_type: str = "success") -> RedirectResponse:
    url = f"/employees/{employee_id}/edit"
    if flash_message:
        from urllib.parse import urlencode

        url = f"{url}?{urlencode({'flash_message': flash_message, 'flash_type': flash_type})}"
    return RedirectResponse(url=url, status_code=status.HTTP_303_SEE_OTHER)


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
            "default_employee_stage": "candidate",
        }
    return {
        "active_tab": "employees",
        "list_title": "Сотрудники",
        "empty_message": "Сотрудников пока нет. Нажмите «Добавить сотрудника».",
        "create_button_label": "Добавить сотрудника",
        "create_modal_title": "Новый сотрудник",
        "create_intro": "Добавьте сотрудника, чтобы запустить сценарий онбординга.",
        "default_employee_stage": "employee",
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


def _available_scenarios_for_employee(db: Session, employee: Employee) -> list[ScenarioTemplate]:
    return [
        scenario
        for scenario in db.query(ScenarioTemplate).filter(ScenarioTemplate.scenario_kind == "scenario").order_by(ScenarioTemplate.id).all()
        if _scenario_matches_employee_role(scenario, employee)
    ]


def _menu_sets(db: Session) -> list[BotMenuSet]:
    return db.query(BotMenuSet).order_by(BotMenuSet.sort_order, BotMenuSet.id).all()


def _menu_buttons_by_set(db: Session) -> dict[int, list[BotMenuButton]]:
    result: dict[int, list[BotMenuButton]] = defaultdict(list)
    buttons = db.query(BotMenuButton).order_by(BotMenuButton.menu_set_id, BotMenuButton.sort_order, BotMenuButton.id).all()
    for button in buttons:
        result[button.menu_set_id].append(button)
    return dict(result)


def _template_entity_meta(kind: str) -> dict[str, str]:
    if kind == "survey":
        return {
            "kind": "survey",
            "active_tab": "surveys",
            "collection_title": "Опросы",
            "collection_title_single": "Опрос",
            "collection_description": "Список всех опросов проекта. Детальные вопросы редактируются на отдельной странице опроса.",
            "create_label": "Создать опрос",
            "new_title": "Новый опрос",
            "collection_path": "/surveys",
            "item_label": "опрос",
            "item_label_cap": "Опрос",
            "edit_title": "Редактировать опрос",
            "back_label": "К списку опросов",
        }
    return {
        "kind": "scenario",
        "active_tab": "flows",
        "collection_title": "Сценарии",
        "collection_title_single": "Сценарий",
        "collection_description": "Список всех сценариев проекта. Детальные шаги редактируются на отдельной странице сценария.",
        "create_label": "Создать сценарий",
        "new_title": "Новый сценарий",
        "collection_path": "/flows",
        "item_label": "сценарий",
        "item_label_cap": "Сценарий",
        "edit_title": "Редактировать сценарий",
        "back_label": "К списку сценариев",
    }


def _template_edit_redirect(scenario: ScenarioTemplate, flash_message: Optional[str] = None, flash_type: str = "success") -> RedirectResponse:
    meta = _template_entity_meta(getattr(scenario, "scenario_kind", "scenario"))
    url = f"{meta['collection_path']}/{scenario.id}"
    if flash_message:
        from urllib.parse import urlencode

        url = f"{url}?{urlencode({'flash_message': flash_message, 'flash_type': flash_type})}"
    return RedirectResponse(url=url, status_code=status.HTTP_303_SEE_OTHER)


def _mass_actions_redirect(flash_message: Optional[str] = None, flash_type: str = "success") -> RedirectResponse:
    url = "/bulk-actions"
    if flash_message:
        from urllib.parse import urlencode

        url = f"{url}?{urlencode({'flash_message': flash_message, 'flash_type': flash_type})}"
    return RedirectResponse(url=url, status_code=status.HTTP_303_SEE_OTHER)


def _normalize_mass_target_statuses(values: list[str]) -> list[str]:
    allowed = {value for value, _ in MASS_TARGET_OPTIONS}
    normalized: list[str] = []
    for value in values:
        key = (value or "").strip()
        if key and key in allowed and key not in normalized:
            normalized.append(key)
    return normalized


def _serialize_mass_target_statuses(values: list[str]) -> Optional[str]:
    normalized = _normalize_mass_target_statuses(values)
    return ",".join(normalized) if normalized else None


def _deserialize_mass_target_statuses(value: Optional[str]) -> list[str]:
    if not value:
        return []
    return _normalize_mass_target_statuses([item.strip() for item in value.split(",")])


def _recipient_scope_label(target_all: bool, target_statuses: Optional[str]) -> str:
    if target_all:
        return "Все"
    labels = dict(MASS_TARGET_OPTIONS)
    values = _deserialize_mass_target_statuses(target_statuses)
    if not values:
        return "Не выбраны"
    return ", ".join(labels.get(value, value) for value in values)


def _mass_target_employee_query(db: Session, target_all: bool, target_statuses: list[str]):
    query = db.query(Employee)
    if target_all:
        return query
    normalized = _normalize_mass_target_statuses(target_statuses)
    if not normalized:
        return query.filter(Employee.id == -1)

    conditions = []
    for value in normalized:
        if value == MASS_TARGET_NONE:
            conditions.append(Employee.employee_stage.is_(None))
            conditions.append(Employee.employee_stage == "")
        else:
            conditions.append(Employee.employee_stage == value)
    return query.filter(or_(*conditions))


def _mass_target_employees(db: Session, target_all: bool, target_statuses: list[str]) -> list[Employee]:
    return (
        _mass_target_employee_query(db, target_all, target_statuses)
        .order_by(Employee.id.asc())
        .all()
    )


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/login")
def login_page(request: Request):
    if getattr(request.state, "current_user", None):
        return RedirectResponse(url="/employees", status_code=status.HTTP_303_SEE_OTHER)
    return _render(request, "login.html", {"error_message": None})


@app.post("/login")
def login_submit(
    request: Request,
    login: str = Form(""),
    password: str = Form(""),
    db: Session = Depends(get_db),
):
    account = authenticate_account(db, login, password)
    if not account:
        return _render(
            request,
            "login.html",
            {"error_message": "Неверный логин или пароль."},
        )
    response = RedirectResponse(url="/employees", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        AUTH_COOKIE_NAME,
        str(account.id),
        httponly=True,
        samesite="lax",
    )
    return response


@app.post("/logout")
def logout(request: Request):
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(AUTH_COOKIE_NAME)
    return response


@app.get("/")
def index(request: Request):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    return RedirectResponse(url="/candidates", status_code=status.HTTP_303_SEE_OTHER)


def _employees_page(
    request: Request,
    list_kind: str,
    db: Session = Depends(get_db),
):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    query = db.query(Employee)
    if list_kind == "candidates":
        query = query.filter(Employee.employee_stage == "candidate")
    else:
        query = query.filter((Employee.employee_stage != "candidate") | (Employee.employee_stage.is_(None)))
    employees = query.order_by(Employee.id.desc()).all()
    employee_ids = [employee.id for employee in employees]
    scenario_titles = {
        scenario.scenario_key: scenario.title
        for scenario in db.query(ScenarioTemplate).all()
    }
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
    employee_views = [
        {
            "employee": emp,
            "status": _employee_status_label(emp),
            "workdays": _workdays_between(emp.first_workday, today),
            "planned_scenario_title": scenario_titles.get(
                getattr(launch_requests_by_employee.get(emp.id), "flow_key", ""),
                "—",
            ),
            "telegram_link": _telegram_profile_url(getattr(emp, "telegram_username", None), emp.telegram_user_id),
        }
        for emp in employees
    ]
    page_meta = _employee_list_meta(list_kind)
    return _render(
        request,
        "index.html",
        {
            "employee_views": employee_views,
            **page_meta,
        },
    )


@app.get("/candidates")
def candidates_page(
    request: Request,
    db: Session = Depends(get_db),
):
    return _employees_page(request, "candidates", db)


@app.get("/employees")
def employees_page(
    request: Request,
    db: Session = Depends(get_db),
):
    return _employees_page(request, "employees", db)


@app.get("/bulk-actions")
def bulk_actions_page(
    request: Request,
    db: Session = Depends(get_db),
):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect

    scenarios = (
        db.query(ScenarioTemplate)
        .filter(ScenarioTemplate.scenario_kind == "scenario")
        .order_by(ScenarioTemplate.title, ScenarioTemplate.id)
        .all()
    )
    surveys = (
        db.query(ScenarioTemplate)
        .filter(ScenarioTemplate.scenario_kind == "survey")
        .order_by(ScenarioTemplate.title, ScenarioTemplate.id)
        .all()
    )
    scenario_by_key = {scenario.scenario_key: scenario for scenario in scenarios}
    survey_by_key = {survey.scenario_key: survey for survey in surveys}
    scheduled_scenario_actions = (
        db.query(MassScenarioAction)
        .filter(
            MassScenarioAction.scenario_kind == "scenario",
            MassScenarioAction.launch_type == "scheduled",
            MassScenarioAction.processed_at.is_(None),
        )
        .order_by(MassScenarioAction.requested_at.asc(), MassScenarioAction.id.asc())
        .all()
    )
    manual_scenario_history = (
        db.query(MassScenarioAction)
        .filter(
            MassScenarioAction.scenario_kind == "scenario",
            MassScenarioAction.launch_type == "manual",
            MassScenarioAction.processed_at.is_not(None),
        )
        .order_by(MassScenarioAction.processed_at.desc(), MassScenarioAction.id.desc())
        .all()
    )
    scheduled_survey_actions = (
        db.query(MassScenarioAction)
        .filter(
            MassScenarioAction.scenario_kind == "survey",
            MassScenarioAction.launch_type == "scheduled",
            MassScenarioAction.processed_at.is_(None),
        )
        .order_by(MassScenarioAction.requested_at.asc(), MassScenarioAction.id.asc())
        .all()
    )
    manual_survey_history = (
        db.query(MassScenarioAction)
        .filter(
            MassScenarioAction.scenario_kind == "survey",
            MassScenarioAction.launch_type == "manual",
            MassScenarioAction.processed_at.is_not(None),
        )
        .order_by(MassScenarioAction.processed_at.desc(), MassScenarioAction.id.desc())
        .all()
    )
    scheduled_message_actions = (
        db.query(MassMessageAction)
        .filter(
            MassMessageAction.launch_type == "scheduled",
            MassMessageAction.processed_at.is_(None),
        )
        .order_by(MassMessageAction.requested_at.asc(), MassMessageAction.id.asc())
        .all()
    )
    manual_message_history = (
        db.query(MassMessageAction)
        .filter(
            MassMessageAction.launch_type == "manual",
            MassMessageAction.processed_at.is_not(None),
        )
        .order_by(MassMessageAction.processed_at.desc(), MassMessageAction.id.desc())
        .all()
    )
    return _render(
        request,
        "mass_actions.html",
        {
            "active_tab": "bulk_actions",
            "scenarios": scenarios,
            "surveys": surveys,
            "scenario_by_key": scenario_by_key,
            "survey_by_key": survey_by_key,
            "target_status_options": MASS_TARGET_OPTIONS,
            "scheduled_scenario_actions": scheduled_scenario_actions,
            "manual_scenario_history": manual_scenario_history,
            "scheduled_survey_actions": scheduled_survey_actions,
            "manual_survey_history": manual_survey_history,
            "scheduled_message_actions": scheduled_message_actions,
            "manual_message_history": manual_message_history,
            "recipient_scope_label": _recipient_scope_label,
            "flash_message": request.query_params.get("flash_message"),
            "flash_type": request.query_params.get("flash_type", "success"),
        },
    )


@app.get("/employees/{employee_id}/edit")
def edit_employee_form(
    request: Request,
    employee_id: int,
    db: Session = Depends(get_db),
):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    employee = db.get(Employee, employee_id)
    if not employee:
        return RedirectResponse(url="/employees", status_code=status.HTTP_303_SEE_OTHER)
    employee_files = (
        db.query(EmployeeFile)
        .filter(EmployeeFile.employee_id == employee.id)
        .order_by(EmployeeFile.id.desc())
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
    return _render(
        request,
        "employee_edit.html",
        {
            "active_tab": list_kind,
            "employee": employee,
            "employee_files": employee_files,
            "status": _employee_status_label(employee),
            "workdays": _workdays_between(employee.first_workday, today),
            "employee_role_values": employee_role_values,
            "employee_stage_values": EMPLOYEE_STAGE_VALUES,
            "scenarios": scenarios,
            "scheduled_launches": pending_scheduled_launches,
            "manual_launch_history": manual_launch_history,
            "scenario_by_key": scenario_by_key,
            "flash_message": request.query_params.get("flash_message"),
            "flash_type": request.query_params.get("flash_type", "success"),
            "list_url": "/candidates" if list_kind == "candidates" else "/employees",
            "list_title": "к списку кандидатов" if list_kind == "candidates" else "к списку сотрудников",
        },
    )


@app.post("/employees/{employee_id}")
def update_employee(
    request: Request,
    employee_id: int,
    full_name: str = Form(""),
    telegram_user_id: str = Form(""),
    first_workday: str = Form(""),
    desired_position: str = Form(""),
    employee_stage: str = Form(""),
    salary_expectation: str = Form(""),
    candidate_status: str = Form(""),
    personal_data_consent: str = Form("false"),
    employee_data_consent: str = Form("false"),
    test_task_link: str = Form(""),
    test_task_due_at: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    employee = db.get(Employee, employee_id)
    if not employee:
        return RedirectResponse(url="/employees", status_code=status.HTTP_303_SEE_OTHER)
    first_day = datetime.strptime(first_workday, "%Y-%m-%d").date() if first_workday else None
    employee.full_name = full_name.strip() or None
    employee.telegram_user_id = (telegram_user_id or "").strip() or None
    employee.first_workday = first_day
    desired_position = desired_position.strip()
    employee.desired_position = desired_position or None
    normalized_stage = employee_stage.strip()
    employee.employee_stage = normalized_stage if normalized_stage in EMPLOYEE_STAGE_VALUES else None
    employee.salary_expectation = salary_expectation.strip() or None
    employee.candidate_status = candidate_status.strip() or None
    employee.personal_data_consent = personal_data_consent == "true"
    employee.employee_data_consent = employee_data_consent == "true"
    employee.test_task_link = test_task_link.strip() or None
    employee.test_task_due_at = (
        datetime.strptime(test_task_due_at, "%Y-%m-%dT%H:%M")
        if (test_task_due_at or "").strip()
        else None
    )
    employee.notes = notes.strip() or None
    db.commit()
    return RedirectResponse(
        url="/candidates" if _employee_list_kind(employee) == "candidates" else "/employees",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@app.post("/employees/{employee_id}/delete")
def delete_employee(
    request: Request,
    employee_id: int,
    db: Session = Depends(get_db),
):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    employee = db.get(Employee, employee_id)
    if employee:
        redirect_url = "/candidates" if _employee_list_kind(employee) == "candidates" else "/employees"
        # Удаляем связанные файлы из БД и с диска.
        employee_files = db.query(EmployeeFile).filter(EmployeeFile.employee_id == employee_id).all()
        for file_row in employee_files:
            path = Path(file_row.stored_path)
            try:
                if path.exists():
                    path.unlink()
            except OSError:
                pass
            db.delete(file_row)

        employee_dir = Path(settings.FILE_STORAGE_DIR).expanduser().resolve() / str(employee_id)
        if employee_dir.exists():
            shutil.rmtree(employee_dir, ignore_errors=True)

        db.delete(employee)
        db.commit()
        return RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)
    return RedirectResponse(url="/employees", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/employees")
def create_employee(
    request: Request,
    full_name: str = Form(""),
    telegram_user_id: str = Form(""),
    first_workday: str = Form(""),
    employee_stage: str = Form(""),
    db: Session = Depends(get_db),
):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    first_day = datetime.strptime(first_workday, "%Y-%m-%d").date() if first_workday else None

    employee = Employee(
        full_name=full_name.strip() or None,
        telegram_user_id=str(telegram_user_id).strip() or None,
        first_workday=first_day,
        created_at=datetime.utcnow(),
        is_flow_scheduled=False,
        candidate_status="new",
        employee_stage=employee_stage.strip() if employee_stage.strip() in EMPLOYEE_STAGE_VALUES else None,
    )
    db.add(employee)
    db.flush()
    db.add(
        FlowLaunchRequest(
            employee_id=employee.id,
            flow_key="recruitment_hiring",
            requested_at=datetime.utcnow(),
            processed_at=None,
        )
    )
    db.commit()

    return RedirectResponse(
        url="/candidates" if _employee_list_kind(employee) == "candidates" else "/employees",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@app.post("/employees/{employee_id}/launch")
async def launch_flow(
    request: Request,
    employee_id: int,
    flow_key: str = Form(...),
    db: Session = Depends(get_db),
):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    employee = db.get(Employee, employee_id)
    if not employee:
        return RedirectResponse(url="/employees", status_code=status.HTTP_303_SEE_OTHER)
    scenario = db.query(ScenarioTemplate).filter(ScenarioTemplate.scenario_key == flow_key).first()
    if not scenario:
        return _employee_edit_redirect(employee_id, "Сценарий не найден.", "error")
    if not employee.telegram_user_id:
        return _employee_edit_redirect(employee_id, "У сотрудника не указан Telegram user_id.", "error")
    if not _scenario_matches_employee_role(scenario, employee):
        return _employee_edit_redirect(employee_id, "Сценарий недоступен для роли этого сотрудника.", "error")
    if not settings.TELEGRAM_BOT_TOKEN:
        return _employee_edit_redirect(employee_id, "Не задан TELEGRAM_BOT_TOKEN.", "error")

    first_step = get_first_step(db, scenario.scenario_key)
    if not first_step:
        return _employee_edit_redirect(employee_id, "В сценарии нет шагов для запуска.", "error")

    bot = Bot(
        token=settings.TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    try:
        started = await start_scenario(bot, db, employee, scenario.scenario_key)
        if not started:
            return _employee_edit_redirect(employee_id, "Сценарий не удалось запустить.", "error")

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
        return _employee_edit_redirect(employee_id, "Сценарий успешно запущен.", "success")
    except Exception as exc:
        return _employee_edit_redirect(employee_id, f"Ошибка запуска сценария: {exc}", "error")
    finally:
        await bot.session.close()


@app.post("/employees/{employee_id}/schedule")
def schedule_flow(
    request: Request,
    employee_id: int,
    flow_key: str = Form(""),
    requested_at: str = Form(""),
    db: Session = Depends(get_db),
):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    employee = db.get(Employee, employee_id)
    if not employee:
        return RedirectResponse(url="/employees", status_code=status.HTTP_303_SEE_OTHER)
    scenario = db.query(ScenarioTemplate).filter(ScenarioTemplate.scenario_key == flow_key).first()
    if not scenario:
        return _employee_edit_redirect(employee_id, "Сценарий не найден.", "error")
    if not _scenario_matches_employee_role(scenario, employee):
        return _employee_edit_redirect(employee_id, "Сценарий недоступен для роли этого сотрудника.", "error")
    if not (requested_at or "").strip():
        return _employee_edit_redirect(employee_id, "Укажи дату и время запуска сценария.", "error")
    try:
        run_at = datetime.strptime(requested_at.strip(), "%Y-%m-%dT%H:%M")
    except ValueError:
        return _employee_edit_redirect(employee_id, "Неверный формат даты и времени.", "error")

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
    return _employee_edit_redirect(employee_id, "Сценарий запланирован.", "success")


@app.post("/employees/{employee_id}/schedule/{launch_request_id}/delete")
def delete_scheduled_flow(
    request: Request,
    employee_id: int,
    launch_request_id: int,
    db: Session = Depends(get_db),
):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    launch_request = db.get(FlowLaunchRequest, launch_request_id)
    if (
        not launch_request
        or launch_request.employee_id != employee_id
        or launch_request.launch_type != "scheduled"
        or launch_request.processed_at is not None
    ):
        return _employee_edit_redirect(employee_id, "Запланированный сценарий не найден.", "error")
    db.delete(launch_request)
    db.commit()
    return _employee_edit_redirect(employee_id, "Запланированная отправка удалена.", "success")


async def _send_mass_message(bot: Bot, employee: Employee, message_text: str) -> bool:
    if not employee.telegram_user_id:
        return False
    rendered_text = format_message(
        message_text,
        employee,
        datetime.now().date(),
        datetime.now().strftime("%H:%M"),
    ).strip()
    if not rendered_text:
        return False
    await bot.send_message(chat_id=employee.telegram_user_id, text=rendered_text)
    return True


async def _parse_mass_action_targets(request: Request) -> tuple[bool, list[str]]:
    form = await request.form()
    target_all = form.get("target_all") == "true"
    target_statuses = _normalize_mass_target_statuses(form.getlist("target_statuses"))
    return target_all, target_statuses


@app.post("/bulk-actions/scenarios/schedule")
async def bulk_schedule_scenario(
    request: Request,
    flow_key: str = Form(""),
    requested_at: str = Form(""),
    db: Session = Depends(get_db),
):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    scenario = db.query(ScenarioTemplate).filter(ScenarioTemplate.scenario_key == flow_key).first()
    if not scenario:
        return _mass_actions_redirect("Сценарий не найден.", "error")
    target_all, target_statuses = await _parse_mass_action_targets(request)
    recipients = _mass_target_employees(db, target_all, target_statuses)
    if not recipients:
        return _mass_actions_redirect("Не найдено ни одного получателя для выбранных статусов.", "error")
    if not (requested_at or "").strip():
        return _mass_actions_redirect("Укажи дату и время отправки сценария.", "error")
    try:
        run_at = datetime.strptime(requested_at.strip(), "%Y-%m-%dT%H:%M")
    except ValueError:
        return _mass_actions_redirect("Неверный формат даты и времени.", "error")

    db.add(
        MassScenarioAction(
            flow_key=scenario.scenario_key,
            requested_at=run_at,
            processed_at=None,
            launch_type="scheduled",
            target_all=target_all,
            target_statuses=_serialize_mass_target_statuses(target_statuses),
            recipient_count=len(recipients),
            created_at=datetime.utcnow(),
        )
    )
    db.commit()
    return _mass_actions_redirect("Массовый запуск сценария запланирован.", "success")


@app.post("/bulk-actions/surveys/schedule")
async def bulk_schedule_survey(
    request: Request,
    flow_key: str = Form(""),
    requested_at: str = Form(""),
    db: Session = Depends(get_db),
):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    scenario = (
        db.query(ScenarioTemplate)
        .filter(
            ScenarioTemplate.scenario_key == flow_key,
            ScenarioTemplate.scenario_kind == "survey",
        )
        .first()
    )
    if not scenario:
        return _mass_actions_redirect("Опрос не найден.", "error")
    target_all, target_statuses = await _parse_mass_action_targets(request)
    recipients = _mass_target_employees(db, target_all, target_statuses)
    if not recipients:
        return _mass_actions_redirect("Не найдено ни одного получателя для выбранных статусов.", "error")
    if not (requested_at or "").strip():
        return _mass_actions_redirect("Укажи дату и время отправки опроса.", "error")
    try:
        run_at = datetime.strptime(requested_at.strip(), "%Y-%m-%dT%H:%M")
    except ValueError:
        return _mass_actions_redirect("Неверный формат даты и времени.", "error")

    db.add(
        MassScenarioAction(
            flow_key=scenario.scenario_key,
            scenario_kind="survey",
            requested_at=run_at,
            processed_at=None,
            launch_type="scheduled",
            target_all=target_all,
            target_statuses=_serialize_mass_target_statuses(target_statuses),
            recipient_count=len(recipients),
            created_at=datetime.utcnow(),
        )
    )
    db.commit()
    return _mass_actions_redirect("Массовый запуск опроса запланирован.", "success")


@app.post("/bulk-actions/scenarios/launch")
async def bulk_launch_scenario(
    request: Request,
    flow_key: str = Form(""),
    db: Session = Depends(get_db),
):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    scenario = db.query(ScenarioTemplate).filter(ScenarioTemplate.scenario_key == flow_key).first()
    if not scenario:
        return _mass_actions_redirect("Сценарий не найден.", "error")
    target_all, target_statuses = await _parse_mass_action_targets(request)
    recipients = _mass_target_employees(db, target_all, target_statuses)
    if not recipients:
        return _mass_actions_redirect("Не найдено ни одного получателя для выбранных статусов.", "error")
    if not settings.TELEGRAM_BOT_TOKEN:
        return _mass_actions_redirect("Не задан TELEGRAM_BOT_TOKEN.", "error")

    bot = Bot(
        token=settings.TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    started_count = 0
    try:
        for employee in recipients:
            if not employee.telegram_user_id:
                continue
            if not _scenario_matches_employee_role(scenario, employee):
                continue
            started = await start_scenario(bot, db, employee, scenario.scenario_key)
            if started:
                started_count += 1
        db.add(
            MassScenarioAction(
                flow_key=scenario.scenario_key,
                requested_at=datetime.utcnow(),
                processed_at=datetime.utcnow(),
                launch_type="manual",
                target_all=target_all,
                target_statuses=_serialize_mass_target_statuses(target_statuses),
                recipient_count=started_count,
                created_at=datetime.utcnow(),
            )
        )
        db.commit()
    finally:
        await bot.session.close()

    if not started_count:
        return _mass_actions_redirect("Не удалось запустить сценарий ни для одного получателя.", "error")
    return _mass_actions_redirect(f"Сценарий запущен для {started_count} получателей.", "success")


@app.post("/bulk-actions/surveys/launch")
async def bulk_launch_survey(
    request: Request,
    flow_key: str = Form(""),
    db: Session = Depends(get_db),
):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    scenario = (
        db.query(ScenarioTemplate)
        .filter(
            ScenarioTemplate.scenario_key == flow_key,
            ScenarioTemplate.scenario_kind == "survey",
        )
        .first()
    )
    if not scenario:
        return _mass_actions_redirect("Опрос не найден.", "error")
    target_all, target_statuses = await _parse_mass_action_targets(request)
    recipients = _mass_target_employees(db, target_all, target_statuses)
    if not recipients:
        return _mass_actions_redirect("Не найдено ни одного получателя для выбранных статусов.", "error")
    if not settings.TELEGRAM_BOT_TOKEN:
        return _mass_actions_redirect("Не задан TELEGRAM_BOT_TOKEN.", "error")

    bot = Bot(
        token=settings.TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    started_count = 0
    try:
        for employee in recipients:
            if not employee.telegram_user_id:
                continue
            if not _scenario_matches_employee_role(scenario, employee):
                continue
            started = await start_scenario(bot, db, employee, scenario.scenario_key)
            if started:
                started_count += 1
        db.add(
            MassScenarioAction(
                flow_key=scenario.scenario_key,
                scenario_kind="survey",
                requested_at=datetime.utcnow(),
                processed_at=datetime.utcnow(),
                launch_type="manual",
                target_all=target_all,
                target_statuses=_serialize_mass_target_statuses(target_statuses),
                recipient_count=started_count,
                created_at=datetime.utcnow(),
            )
        )
        db.commit()
    finally:
        await bot.session.close()

    if not started_count:
        return _mass_actions_redirect("Не удалось запустить опрос ни для одного получателя.", "error")
    return _mass_actions_redirect(f"Опрос запущен для {started_count} получателей.", "success")


@app.post("/bulk-actions/messages/schedule")
async def bulk_schedule_message(
    request: Request,
    message_text: str = Form(""),
    requested_at: str = Form(""),
    db: Session = Depends(get_db),
):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    if not message_text.strip():
        return _mass_actions_redirect("Введите текст сообщения.", "error")
    target_all, target_statuses = await _parse_mass_action_targets(request)
    recipients = _mass_target_employees(db, target_all, target_statuses)
    if not recipients:
        return _mass_actions_redirect("Не найдено ни одного получателя для выбранных статусов.", "error")
    if not (requested_at or "").strip():
        return _mass_actions_redirect("Укажи дату и время отправки сообщения.", "error")
    try:
        run_at = datetime.strptime(requested_at.strip(), "%Y-%m-%dT%H:%M")
    except ValueError:
        return _mass_actions_redirect("Неверный формат даты и времени.", "error")

    db.add(
        MassMessageAction(
            message_text=message_text,
            requested_at=run_at,
            processed_at=None,
            launch_type="scheduled",
            target_all=target_all,
            target_statuses=_serialize_mass_target_statuses(target_statuses),
            recipient_count=len(recipients),
            created_at=datetime.utcnow(),
        )
    )
    db.commit()
    return _mass_actions_redirect("Массовая отправка сообщения запланирована.", "success")


@app.post("/bulk-actions/messages/send")
async def bulk_send_message(
    request: Request,
    message_text: str = Form(""),
    db: Session = Depends(get_db),
):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    if not message_text.strip():
        return _mass_actions_redirect("Введите текст сообщения.", "error")
    target_all, target_statuses = await _parse_mass_action_targets(request)
    recipients = _mass_target_employees(db, target_all, target_statuses)
    if not recipients:
        return _mass_actions_redirect("Не найдено ни одного получателя для выбранных статусов.", "error")
    if not settings.TELEGRAM_BOT_TOKEN:
        return _mass_actions_redirect("Не задан TELEGRAM_BOT_TOKEN.", "error")

    bot = Bot(
        token=settings.TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    sent_count = 0
    try:
        for employee in recipients:
            if await _send_mass_message(bot, employee, message_text):
                sent_count += 1
        db.add(
            MassMessageAction(
                message_text=message_text,
                requested_at=datetime.utcnow(),
                processed_at=datetime.utcnow(),
                launch_type="manual",
                target_all=target_all,
                target_statuses=_serialize_mass_target_statuses(target_statuses),
                recipient_count=sent_count,
                created_at=datetime.utcnow(),
            )
        )
        db.commit()
    finally:
        await bot.session.close()

    if not sent_count:
        return _mass_actions_redirect("Не удалось отправить сообщение ни одному получателю.", "error")
    return _mass_actions_redirect(f"Сообщение отправлено {sent_count} получателям.", "success")


@app.post("/bulk-actions/scenarios/{action_id}/delete")
def delete_bulk_scenario_action(
    request: Request,
    action_id: int,
    db: Session = Depends(get_db),
):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    action = db.get(MassScenarioAction, action_id)
    if not action or action.launch_type != "scheduled" or action.processed_at is not None:
        return _mass_actions_redirect("Запланированный запуск не найден.", "error")
    db.delete(action)
    db.commit()
    return _mass_actions_redirect("Запланированный запуск удалён.", "success")


@app.post("/bulk-actions/messages/{action_id}/delete")
def delete_bulk_message_action(
    request: Request,
    action_id: int,
    db: Session = Depends(get_db),
):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    action = db.get(MassMessageAction, action_id)
    if not action or action.launch_type != "scheduled" or action.processed_at is not None:
        return _mass_actions_redirect("Запланированная отправка не найдена.", "error")
    db.delete(action)
    db.commit()
    return _mass_actions_redirect("Запланированная отправка удалена.", "success")


@app.post("/employees/{employee_id}/files")
async def upload_employee_file(
    request: Request,
    employee_id: int,
    upload: UploadFile = File(...),
    category: str = Form("hr_file"),
    send_to_telegram: str = Form("false"),
    db: Session = Depends(get_db),
):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    employee = db.get(Employee, employee_id)
    if not employee:
        return RedirectResponse(url="/employees", status_code=status.HTTP_303_SEE_OTHER)

    filename = upload.filename or "file.bin"
    destination = build_employee_file_path(employee_id, filename)
    content = await upload.read()
    destination.write_bytes(content)

    db_file = EmployeeFile(
        employee_id=employee_id,
        direction="outbound",
        category=(category or "hr_file").strip(),
        telegram_file_id=None,
        telegram_file_unique_id=None,
        original_filename=filename,
        stored_path=str(destination),
        mime_type=upload.content_type,
        file_size=len(content),
        created_at=datetime.utcnow(),
    )
    db.add(db_file)
    db.commit()

    if send_to_telegram == "true" and employee.telegram_user_id and settings.TELEGRAM_BOT_TOKEN:
        await _send_file_to_telegram(employee.telegram_user_id, destination, filename)

    return RedirectResponse(
        url=f"/employees/{employee_id}/edit",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@app.get("/employees/{employee_id}/files/{file_id}/download")
def download_employee_file(
    request: Request,
    employee_id: int,
    file_id: int,
    db: Session = Depends(get_db),
):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    db_file = db.get(EmployeeFile, file_id)
    if not db_file or db_file.employee_id != employee_id:
        return RedirectResponse(url="/employees", status_code=status.HTTP_303_SEE_OTHER)
    path = Path(db_file.stored_path)
    if not path.exists():
        return RedirectResponse(url=f"/employees/{employee_id}/edit", status_code=status.HTTP_303_SEE_OTHER)
    return FileResponse(
        path=str(path),
        filename=db_file.original_filename,
        media_type=db_file.mime_type or "application/octet-stream",
    )


@app.post("/employees/{employee_id}/files/{file_id}/send")
async def send_employee_file(
    request: Request,
    employee_id: int,
    file_id: int,
    db: Session = Depends(get_db),
):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    employee = db.get(Employee, employee_id)
    db_file = db.get(EmployeeFile, file_id)
    if not employee or not db_file or db_file.employee_id != employee_id:
        return RedirectResponse(url="/employees", status_code=status.HTTP_303_SEE_OTHER)
    if not employee.telegram_user_id or not settings.TELEGRAM_BOT_TOKEN:
        return RedirectResponse(url=f"/employees/{employee_id}/edit", status_code=status.HTTP_303_SEE_OTHER)

    path = Path(db_file.stored_path)
    if path.exists():
        await _send_file_to_telegram(employee.telegram_user_id, path, db_file.original_filename)
    return RedirectResponse(url=f"/employees/{employee_id}/edit", status_code=status.HTTP_303_SEE_OTHER)


async def _send_file_to_telegram(chat_id: str, path: Path, filename: str) -> None:
    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    try:
        await bot.send_document(chat_id=chat_id, document=FSInputFile(str(path), filename=filename))
    finally:
        await bot.session.close()


def _delete_step_attachment_file(step: FlowStepTemplate) -> None:
    attachment_path = (getattr(step, "attachment_path", None) or "").strip()
    if attachment_path:
        path = Path(attachment_path)
        if path.exists():
            path.unlink()
    setattr(step, "attachment_path", None)
    setattr(step, "attachment_filename", None)


async def _save_step_attachment(step: FlowStepTemplate, upload: UploadFile) -> None:
    filename = (upload.filename or "").strip()
    if not filename:
        return
    destination = build_step_attachment_path(step.flow_key, step.step_key, filename)
    content = await upload.read()
    destination.write_bytes(content)
    _delete_step_attachment_file(step)
    step.attachment_path = str(destination)
    step.attachment_filename = filename


def _template_list_page(request: Request, kind: str, db: Session):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    meta = _template_entity_meta(kind)
    scenarios = (
        db.query(ScenarioTemplate)
        .filter(ScenarioTemplate.scenario_kind == kind)
        .order_by(ScenarioTemplate.id)
        .all()
    )
    return _render(
        request,
        "scenarios.html",
        {
            "active_tab": meta["active_tab"],
            "scenarios": scenarios,
            "role_scope_labels": ROLE_SCOPE_LABELS,
            "trigger_mode_labels": TRIGGER_MODE_LABELS,
            "collection_title": meta["collection_title"],
            "collection_title_single": meta["collection_title_single"],
            "collection_description": meta["collection_description"],
            "create_label": meta["create_label"],
            "collection_path": meta["collection_path"],
            "new_title": meta["new_title"],
            "kind": meta["kind"],
        },
    )


@app.get("/flows")
def scenarios_page(request: Request, db: Session = Depends(get_db)):
    return _template_list_page(request, "scenario", db)


@app.get("/surveys")
def surveys_page(request: Request, db: Session = Depends(get_db)):
    return _template_list_page(request, "survey", db)


def _create_template_entity(
    request: Request,
    kind: str,
    title: str,
    role_scope: str,
    trigger_mode: str,
    description: str,
    db: Session,
):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    meta = _template_entity_meta(kind)
    scenario = ScenarioTemplate(
        scenario_key=f"custom_{kind}_{int(datetime.utcnow().timestamp())}",
        scenario_kind=kind,
        title=title.strip() or meta["new_title"],
        role_scope=role_scope if role_scope in ROLE_SCOPE_LABELS else "all",
        trigger_mode=trigger_mode if trigger_mode in TRIGGER_MODE_LABELS else "manual_only",
        description=description.strip() or None,
    )
    db.add(scenario)
    db.commit()
    db.refresh(scenario)
    return RedirectResponse(url=f"{meta['collection_path']}/{scenario.id}", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/flows")
def create_scenario(
    request: Request,
    title: str = Form("Новый сценарий"),
    role_scope: str = Form("all"),
    trigger_mode: str = Form("manual_only"),
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    return _create_template_entity(request, "scenario", title, role_scope, trigger_mode, description, db)


@app.post("/surveys")
def create_survey(
    request: Request,
    title: str = Form("Новый опрос"),
    role_scope: str = Form("all"),
    trigger_mode: str = Form("manual_only"),
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    return _create_template_entity(request, "survey", title, role_scope, trigger_mode, description, db)


def _edit_template_page(
    request: Request,
    scenario_id: int,
    kind: str,
    db: Session = Depends(get_db),
):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    scenario = db.get(ScenarioTemplate, scenario_id)
    meta = _template_entity_meta(kind)
    if not scenario or scenario.scenario_kind != kind:
        return RedirectResponse(url=meta["collection_path"], status_code=status.HTTP_303_SEE_OTHER)
    steps = (
        db.query(FlowStepTemplate)
        .filter(
            FlowStepTemplate.flow_key == scenario.scenario_key,
            FlowStepTemplate.parent_step_id.is_(None),
        )
        .order_by(FlowStepTemplate.sort_order)
        .all()
    )
    branch_steps = (
        db.query(FlowStepTemplate)
        .filter(
            FlowStepTemplate.flow_key == scenario.scenario_key,
            FlowStepTemplate.parent_step_id.is_not(None),
        )
        .order_by(FlowStepTemplate.parent_step_id, FlowStepTemplate.branch_option_index, FlowStepTemplate.id)
        .all()
    )
    branch_steps_by_parent = defaultdict(list)
    for branch_step in branch_steps:
        branch_steps_by_parent[branch_step.parent_step_id].append(branch_step)
    available_scenarios = (
        db.query(ScenarioTemplate)
        .order_by(ScenarioTemplate.title, ScenarioTemplate.id)
        .all()
    )
    return _render(
        request,
        "scenario_edit.html",
        {
            "active_tab": meta["active_tab"],
            "scenario": scenario,
            "steps": steps,
            "role_scope_labels": ROLE_SCOPE_LABELS,
            "trigger_mode_labels": TRIGGER_MODE_LABELS,
            "response_type_labels": RESPONSE_TYPE_LABELS,
            "send_mode_labels": SEND_MODE_LABELS,
            "target_field_labels": TARGET_FIELD_LABELS,
            "branch_steps_by_parent": dict(branch_steps_by_parent),
            "available_scenarios": available_scenarios,
            "collection_path": meta["collection_path"],
            "collection_title": meta["collection_title"],
            "collection_title_single": meta["collection_title_single"],
            "edit_title": meta["edit_title"],
            "item_label_cap": meta["item_label_cap"],
            "back_label": meta["back_label"],
            "kind": meta["kind"],
            "flash_message": request.query_params.get("flash_message"),
            "flash_type": request.query_params.get("flash_type", "success"),
        },
    )


@app.get("/flows/{scenario_id}")
def edit_scenario_page(
    request: Request,
    scenario_id: int,
    db: Session = Depends(get_db),
):
    return _edit_template_page(request, scenario_id, "scenario", db)


@app.get("/surveys/{scenario_id}")
def edit_survey_page(
    request: Request,
    scenario_id: int,
    db: Session = Depends(get_db),
):
    return _edit_template_page(request, scenario_id, "survey", db)


@app.get("/flows/steps/{step_id}/attachment")
def download_step_attachment(
    request: Request,
    step_id: int,
    db: Session = Depends(get_db),
):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    step = db.get(FlowStepTemplate, step_id)
    attachment_path = (getattr(step, "attachment_path", None) or "").strip() if step else ""
    if not step or not attachment_path:
        return RedirectResponse(url="/flows", status_code=status.HTTP_303_SEE_OTHER)
    path = Path(attachment_path)
    if not path.exists():
        return RedirectResponse(url="/flows", status_code=status.HTTP_303_SEE_OTHER)
    return FileResponse(path, filename=getattr(step, "attachment_filename", None) or path.name)


@app.post("/flows/steps/{step_id}/attachment/delete")
def delete_step_attachment(
    request: Request,
    step_id: int,
    db: Session = Depends(get_db),
):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    step = db.get(FlowStepTemplate, step_id)
    if not step:
        return RedirectResponse(url="/flows", status_code=status.HTTP_303_SEE_OTHER)
    scenario = db.query(ScenarioTemplate).filter(ScenarioTemplate.scenario_key == step.flow_key).first()
    _delete_step_attachment_file(step)
    db.commit()
    if scenario:
        base_path = _template_entity_meta(getattr(scenario, "scenario_kind", "scenario"))["collection_path"]
        return RedirectResponse(url=f"{base_path}/{scenario.id}", status_code=status.HTTP_303_SEE_OTHER)
    return RedirectResponse(url="/flows", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/flows/{scenario_id}")
@app.post("/surveys/{scenario_id}")
async def update_scenario(
    request: Request,
    scenario_id: int,
    title: str = Form(...),
    role_scope: str = Form("all"),
    trigger_mode: str = Form("manual_only"),
    description: str = Form(""),
    action: str = Form("save"),
    target_step_id: str = Form(""),
    step_id: Optional[List[int]] = Form(None),
    step_title: Optional[List[str]] = Form(None),
    custom_text: Optional[List[str]] = Form(None),
    response_type: Optional[List[str]] = Form(None),
    button_options: Optional[List[str]] = Form(None),
    send_mode: Optional[List[str]] = Form(None),
    send_time: Optional[List[str]] = Form(None),
    day_offset_workdays: Optional[List[int]] = Form(None),
    target_field: Optional[List[str]] = Form(None),
    remove_attachment_step_id: Optional[List[int]] = Form(None),
    branch_parent_step_id: Optional[List[str]] = Form(None),
    branch_option_index: Optional[List[str]] = Form(None),
    branch_step_id: Optional[List[str]] = Form(None),
    branch_step_title: Optional[List[str]] = Form(None),
    branch_custom_text: Optional[List[str]] = Form(None),
    branch_response_type: Optional[List[str]] = Form(None),
    branch_button_options: Optional[List[str]] = Form(None),
    branch_launch_scenario_key: Optional[List[str]] = Form(None),
    branch_remove_attachment_key: Optional[List[str]] = Form(None),
    db: Session = Depends(get_db),
):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    scenario = db.get(ScenarioTemplate, scenario_id)
    if scenario:
        request_form = await request.form()
        def form_list(name: str) -> list[str]:
            return [str(value) for value in request_form.getlist(name)]

        target_step_id_int = int(target_step_id) if (target_step_id or "").strip().isdigit() else None
        scenario.title = title.strip() or scenario.title
        scenario.role_scope = role_scope if role_scope in ROLE_SCOPE_LABELS else "all"
        scenario.trigger_mode = "manual_only" if scenario.scenario_kind == "survey" else (trigger_mode if trigger_mode in TRIGGER_MODE_LABELS else "manual_only")
        scenario.description = description.strip() or None
        step_ids = step_id or []
        step_titles = step_title or []
        custom_texts = custom_text or []
        response_types = response_type or []
        button_values = button_options or []
        send_modes = send_mode or []
        send_times = send_time or []
        day_offsets = day_offset_workdays or []
        target_fields = target_field or []
        removed_attachment_step_ids = set(remove_attachment_step_id or [])
        branch_parent_ids = form_list("branch_parent_step_id")
        branch_option_indexes = form_list("branch_option_index")
        branch_step_ids = form_list("branch_step_id")
        branch_step_titles = form_list("branch_step_title")
        branch_custom_texts = form_list("branch_custom_text")
        branch_response_types = form_list("branch_response_type")
        branch_button_values = form_list("branch_button_options")
        branch_launch_scenario_keys = form_list("branch_launch_scenario_key")
        removed_branch_attachment_keys = set(form_list("branch_remove_attachment_key"))

        for index, current_step_id in enumerate(step_ids):
            step = db.get(FlowStepTemplate, current_step_id)
            if not step or step.flow_key != scenario.scenario_key:
                continue
            step.sort_order = (index + 1) * 10
            if index < len(step_titles):
                step.step_title = step_titles[index].strip() or step.step_title
            if index < len(custom_texts):
                step.custom_text = custom_texts[index].strip()
            if index < len(response_types):
                current_response_type = response_types[index]
                step.response_type = current_response_type if current_response_type in {"none", "text", "file", "buttons", "branching"} else "none"
            if index < len(button_values):
                step.button_options = button_values[index].strip() or None
            if index < len(send_modes):
                current_send_mode = send_modes[index]
                step.send_mode = current_send_mode if current_send_mode in {"immediate", "specific_time"} else "immediate"
            if index < len(send_times):
                step.send_time = send_times[index].strip() or None
            if index < len(day_offsets):
                step.day_offset_workdays = int(day_offsets[index])
            if index < len(target_fields):
                step.target_field = target_fields[index].strip() or None
            if scenario.scenario_kind == "survey":
                step.send_mode = "immediate"
                step.send_time = None
                step.day_offset_workdays = 0
                step.target_field = None
            if step.id in removed_attachment_step_ids:
                _delete_step_attachment_file(step)
            upload = request_form.get(f"step_attachment_{step.id}")
            if upload is not None and getattr(upload, "filename", ""):
                await _save_step_attachment(step, upload)

        if action == "delete_step" and target_step_id_int is not None:
            step = db.get(FlowStepTemplate, target_step_id_int)
            if step and step.flow_key == scenario.scenario_key:
                for child in (
                    db.query(FlowStepTemplate)
                    .filter(FlowStepTemplate.parent_step_id == step.id)
                    .all()
                ):
                    _delete_step_attachment_file(child)
                    db.delete(child)
                _delete_step_attachment_file(step)
                db.delete(step)
        elif action == "reset_step" and target_step_id_int is not None:
            step = db.get(FlowStepTemplate, target_step_id_int)
            if step and step.flow_key == scenario.scenario_key:
                step.custom_text = None
                step.button_options = None
        elif action == "add_step":
            last_step = (
                db.query(FlowStepTemplate)
                .filter(
                    FlowStepTemplate.flow_key == scenario.scenario_key,
                    FlowStepTemplate.parent_step_id.is_(None),
                )
                .order_by(FlowStepTemplate.sort_order.desc(), FlowStepTemplate.id.desc())
                .first()
            )
            next_order = (last_step.sort_order + 10) if last_step else 10
            db.add(
                FlowStepTemplate(
                    flow_key=scenario.scenario_key,
                    step_key=f"{scenario.scenario_key}_step_{int(datetime.utcnow().timestamp())}",
                    step_title="Новый вопрос" if scenario.scenario_kind == "survey" else "Новый шаг",
                    sort_order=next_order,
                    default_text="Новое сообщение опроса." if scenario.scenario_kind == "survey" else "Новое сообщение сценария.",
                    custom_text=None,
                    response_type="none",
                    button_options=None,
                    send_mode="immediate",
                    send_time=None,
                    day_offset_workdays=0,
                    target_field=None,
                )
            )

        submitted_branch_rows = {}
        for index, parent_id in enumerate(branch_parent_ids):
            parent_id_value = int(parent_id) if str(parent_id).strip().isdigit() else None
            option_idx_raw = branch_option_indexes[index] if index < len(branch_option_indexes) else None
            option_idx = int(option_idx_raw) if str(option_idx_raw).strip().isdigit() else None
            branch_step_id_raw = branch_step_ids[index] if index < len(branch_step_ids) else None
            branch_step_id_value = int(branch_step_id_raw) if str(branch_step_id_raw).strip().isdigit() else None
            if parent_id_value is None or option_idx is None:
                continue
            submitted_branch_rows[(parent_id_value, option_idx)] = {
                "branch_step_id": branch_step_id_value,
                "title": branch_step_titles[index] if index < len(branch_step_titles) else "",
                "custom_text": branch_custom_texts[index] if index < len(branch_custom_texts) else "",
                "response_type": branch_response_types[index] if index < len(branch_response_types) else "none",
                "button_options": branch_button_values[index] if index < len(branch_button_values) else "",
                "launch_scenario_key": branch_launch_scenario_keys[index] if index < len(branch_launch_scenario_keys) else "",
            }

        top_level_steps = (
            db.query(FlowStepTemplate)
            .filter(
                FlowStepTemplate.flow_key == scenario.scenario_key,
                FlowStepTemplate.parent_step_id.is_(None),
            )
            .order_by(FlowStepTemplate.sort_order, FlowStepTemplate.id)
            .all()
        )
        for step in top_level_steps:
            existing_children = {
                child.branch_option_index: child
                for child in db.query(FlowStepTemplate)
                .filter(FlowStepTemplate.parent_step_id == step.id)
                .all()
            }
            if step.response_type != "branching":
                for child in existing_children.values():
                    _delete_step_attachment_file(child)
                    db.delete(child)
                continue

            options = [item.strip() for item in (step.button_options or "").splitlines() if item.strip()]
            for option_idx, option_label in enumerate(options):
                payload = submitted_branch_rows.get((step.id, option_idx), {})
                branch_step = None
                branch_step_id_value = payload.get("branch_step_id")
                if branch_step_id_value is not None:
                    branch_step = db.get(FlowStepTemplate, branch_step_id_value)
                    if branch_step and branch_step.parent_step_id != step.id:
                        branch_step = None
                if branch_step is None:
                    branch_step = existing_children.pop(option_idx, None)
                else:
                    existing_children.pop(option_idx, None)
                if not branch_step:
                    branch_step = FlowStepTemplate(
                        flow_key=scenario.scenario_key,
                        step_key=f"{step.step_key}__branch_{option_idx}",
                        parent_step_id=step.id,
                        branch_option_index=option_idx,
                        step_title=f"Ветка: {option_label}",
                        sort_order=step.sort_order * 100 + option_idx + 1,
                        default_text=f"Сообщение для варианта \"{option_label}\".",
                        custom_text=None,
                        response_type="none",
                        button_options=None,
                        send_mode="immediate",
                        send_time=None,
                        day_offset_workdays=0,
                        target_field=None,
                        launch_scenario_key=None,
                    )
                    db.add(branch_step)
                branch_step.flow_key = scenario.scenario_key
                branch_step.parent_step_id = step.id
                branch_step.branch_option_index = option_idx
                branch_step.sort_order = step.sort_order * 100 + option_idx + 1
                branch_step.step_title = (payload.get("title") or "").strip() or f"Ветка: {option_label}"
                branch_step.custom_text = (payload.get("custom_text") or "").strip()
                current_branch_response_type = (payload.get("response_type") or "none").strip()
                branch_step.response_type = (
                    current_branch_response_type
                    if current_branch_response_type in {
                        "none",
                        "text",
                        "file",
                        "buttons",
                        "launch_scenario",
                    }
                    else "none"
                )
                branch_step.button_options = (
                    (payload.get("button_options") or "").strip() or None
                    if branch_step.response_type == "buttons"
                    else None
                )
                branch_step.launch_scenario_key = (
                    (payload.get("launch_scenario_key") or "").strip() or None
                    if branch_step.response_type == "launch_scenario"
                    else None
                )
                branch_attachment_key = f"{step.id}:{option_idx}"
                if branch_attachment_key in removed_branch_attachment_keys:
                    _delete_step_attachment_file(branch_step)
                branch_upload = request_form.get(f"branch_attachment_{step.id}_{option_idx}")
                if branch_upload is not None and getattr(branch_upload, "filename", ""):
                    await _save_step_attachment(branch_step, branch_upload)
                branch_step.send_mode = "immediate"
                branch_step.send_time = None
                branch_step.day_offset_workdays = 0
                branch_step.target_field = None
            for child in existing_children.values():
                _delete_step_attachment_file(child)
                db.delete(child)
        db.commit()
        base_path = _template_entity_meta(getattr(scenario, "scenario_kind", "scenario"))["collection_path"]
        return RedirectResponse(url=f"{base_path}/{scenario_id}", status_code=status.HTTP_303_SEE_OTHER)
    return RedirectResponse(url="/flows", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/flows/{scenario_id}/delete")
@app.post("/surveys/{scenario_id}/delete")
def delete_scenario(
    request: Request,
    scenario_id: int,
    db: Session = Depends(get_db),
):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    scenario = db.get(ScenarioTemplate, scenario_id)
    if not scenario:
        return RedirectResponse(url="/flows", status_code=status.HTTP_303_SEE_OTHER)
    collection_path = _template_entity_meta(getattr(scenario, "scenario_kind", "scenario"))["collection_path"]

    for step in db.query(FlowStepTemplate).filter(FlowStepTemplate.flow_key == scenario.scenario_key).all():
        _delete_step_attachment_file(step)
    db.query(FlowStepTemplate).filter(FlowStepTemplate.flow_key == scenario.scenario_key).delete()
    db.query(ScenarioProgress).filter(ScenarioProgress.scenario_key == scenario.scenario_key).delete()
    db.query(SurveyAnswer).filter(SurveyAnswer.scenario_key == scenario.scenario_key).delete()
    db.query(FlowLaunchRequest).filter(FlowLaunchRequest.flow_key == scenario.scenario_key).delete()
    db.delete(scenario)
    db.commit()
    return RedirectResponse(url=collection_path, status_code=status.HTTP_303_SEE_OTHER)


@app.get("/surveys/{scenario_id}/export")
def export_survey_results(
    request: Request,
    scenario_id: int,
    db: Session = Depends(get_db),
):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    scenario = db.get(ScenarioTemplate, scenario_id)
    if not scenario or scenario.scenario_kind != "survey":
        return RedirectResponse(url="/surveys", status_code=status.HTTP_303_SEE_OTHER)

    try:
        from openpyxl import Workbook
    except Exception:
        return _template_edit_redirect(scenario, "Для выгрузки Excel нужен пакет openpyxl.", "error")

    steps = (
        db.query(FlowStepTemplate)
        .filter(FlowStepTemplate.flow_key == scenario.scenario_key)
        .order_by(
            FlowStepTemplate.parent_step_id.is_not(None),
            FlowStepTemplate.sort_order,
            FlowStepTemplate.id,
        )
        .all()
    )
    answers = (
        db.query(SurveyAnswer)
        .filter(SurveyAnswer.scenario_key == scenario.scenario_key)
        .order_by(SurveyAnswer.employee_id, SurveyAnswer.answered_at, SurveyAnswer.id)
        .all()
    )

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Результаты"
    columns = ["ID сотрудника", "ФИО", "Telegram", "Username"]
    step_columns = []
    for step in steps:
        label = (step.custom_text if step.custom_text is not None else step.default_text or "").strip()
        if not label:
            label = (step.step_title or step.step_key).strip() or step.step_key
        label = " ".join(label.split())
        if len(label) > 120:
            label = f"{label[:117]}..."
        if step.parent_step_id:
            label = f"{label} ({step.step_key})"
        step_columns.append((step.step_key, label))
    sheet.append(columns + [label for _, label in step_columns])

    employee_ids = sorted({answer.employee_id for answer in answers})
    answer_map: dict[tuple[int, str], SurveyAnswer] = {}
    for answer in answers:
        answer_map[(answer.employee_id, answer.step_key)] = answer

    for employee_id in employee_ids:
        employee = db.get(Employee, employee_id)
        if not employee:
            continue
        row = [
            employee.id,
            employee.full_name or "",
            employee.telegram_user_id or "",
            getattr(employee, "telegram_username", None) or "",
        ]
        for step_key, _label in step_columns:
            answer = answer_map.get((employee.id, step_key))
            if not answer:
                row.append("")
            elif answer.file_name:
                row.append(answer.file_name)
            else:
                row.append(answer.answer_value or "")
        sheet.append(row)

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    filename = f"survey_{scenario.id}_results.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )




def _get_or_create_hr_settings(db: Session) -> HrSettings:
    settings_row = db.get(HrSettings, 1)
    if settings_row:
        return settings_row
    now = datetime.utcnow()
    settings_row = HrSettings(
        id=1,
        hr_name=None,
        telegram_user_id=None,
        notification_recipient_ids=None,
        notify_scenario_completed=True,
        notify_test_task_received=True,
        notify_user_actions=True,
        default_menu_set_id=None,
        created_at=now,
        updated_at=now,
    )
    db.add(settings_row)
    db.commit()
    db.refresh(settings_row)
    return settings_row


@app.get("/settings")
def settings_page(request: Request, db: Session = Depends(get_db)):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    hr_settings = _get_or_create_hr_settings(db)
    accounts = db.query(AdminAccount).order_by(AdminAccount.id).all()
    menu_sets = _menu_sets(db)
    menu_buttons_by_set = _menu_buttons_by_set(db)
    scenarios = db.query(ScenarioTemplate).order_by(ScenarioTemplate.title, ScenarioTemplate.id).all()
    return _render(
        request,
        "settings.html",
        {
            "active_tab": "settings",
            "hr_settings": hr_settings,
            "accounts": accounts,
            "menu_sets": menu_sets,
            "menu_buttons_by_set": menu_buttons_by_set,
            "available_scenarios": scenarios,
        },
    )


@app.post("/settings")
def update_settings(
    request: Request,
    hr_name: str = Form(""),
    telegram_user_id: str = Form(""),
    notification_recipient_ids: str = Form(""),
    default_menu_set_id: str = Form(""),
    notify_scenario_completed: Optional[str] = Form(None),
    notify_test_task_received: Optional[str] = Form(None),
    notify_user_actions: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    hr_settings = _get_or_create_hr_settings(db)
    hr_settings.hr_name = hr_name.strip() or None
    hr_settings.telegram_user_id = telegram_user_id.strip() or None
    hr_settings.notification_recipient_ids = notification_recipient_ids.strip() or None
    hr_settings.default_menu_set_id = int(default_menu_set_id) if default_menu_set_id.strip().isdigit() else None
    hr_settings.notify_scenario_completed = notify_scenario_completed == "on"
    hr_settings.notify_test_task_received = notify_test_task_received == "on"
    hr_settings.notify_user_actions = notify_user_actions == "on"
    hr_settings.updated_at = datetime.utcnow()
    db.commit()
    return RedirectResponse(url="/settings", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/settings/menu-sets")
def create_menu_set(
    request: Request,
    title: str = Form(""),
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    last_set = db.query(BotMenuSet).order_by(BotMenuSet.sort_order.desc(), BotMenuSet.id.desc()).first()
    next_order = (last_set.sort_order + 10) if last_set else 10
    db.add(
        BotMenuSet(
            title=title.strip() or "Новый набор кнопок",
            description=description.strip() or None,
            sort_order=next_order,
        )
    )
    db.commit()
    return RedirectResponse(url="/settings", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/settings/menu-sets/{menu_set_id}")
def update_menu_set(
    request: Request,
    menu_set_id: int,
    title: str = Form(""),
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    menu_set = db.get(BotMenuSet, menu_set_id)
    if menu_set:
        menu_set.title = title.strip() or menu_set.title
        menu_set.description = description.strip() or None
        db.commit()
    return RedirectResponse(url="/settings", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/settings/menu-sets/{menu_set_id}/delete")
def delete_menu_set(
    request: Request,
    menu_set_id: int,
    db: Session = Depends(get_db),
):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    menu_set = db.get(BotMenuSet, menu_set_id)
    if menu_set:
        db.query(BotMenuButton).filter(BotMenuButton.menu_set_id == menu_set_id).delete(synchronize_session=False)
        db.query(BotMenuButton).filter(BotMenuButton.target_menu_set_id == menu_set_id).update(
            {
                BotMenuButton.action_type: "inactive",
                BotMenuButton.target_menu_set_id: None,
            },
            synchronize_session=False,
        )
        db.query(Employee).filter(Employee.current_menu_set_id == menu_set_id).update(
            {Employee.current_menu_set_id: None},
            synchronize_session=False,
        )
        hr_settings = _get_or_create_hr_settings(db)
        if hr_settings.default_menu_set_id == menu_set_id:
            hr_settings.default_menu_set_id = None
        db.delete(menu_set)
        db.commit()
    return RedirectResponse(url="/settings", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/settings/menu-sets/{menu_set_id}/buttons")
def create_menu_button(
    request: Request,
    menu_set_id: int,
    label: str = Form(""),
    action_type: str = Form("inactive"),
    scenario_key: str = Form(""),
    target_menu_set_id: str = Form(""),
    db: Session = Depends(get_db),
):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    menu_set = db.get(BotMenuSet, menu_set_id)
    if not menu_set:
        return RedirectResponse(url="/settings", status_code=status.HTTP_303_SEE_OTHER)
    last_button = (
        db.query(BotMenuButton)
        .filter(BotMenuButton.menu_set_id == menu_set_id)
        .order_by(BotMenuButton.sort_order.desc(), BotMenuButton.id.desc())
        .first()
    )
    next_order = (last_button.sort_order + 10) if last_button else 10
    normalized_action = action_type if action_type in {"inactive", "launch_scenario", "open_set"} else "inactive"
    db.add(
        BotMenuButton(
            menu_set_id=menu_set_id,
            label=label.strip() or "Новая кнопка",
            sort_order=next_order,
            action_type=normalized_action,
            scenario_key=(scenario_key.strip() or None) if normalized_action == "launch_scenario" else None,
            target_menu_set_id=(
                int(target_menu_set_id)
                if target_menu_set_id.strip().isdigit() and normalized_action == "open_set"
                else None
            ),
        )
    )
    db.commit()
    return RedirectResponse(url="/settings", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/settings/menu-buttons/{button_id}")
def update_menu_button(
    request: Request,
    button_id: int,
    label: str = Form(""),
    action_type: str = Form("inactive"),
    scenario_key: str = Form(""),
    target_menu_set_id: str = Form(""),
    db: Session = Depends(get_db),
):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    button = db.get(BotMenuButton, button_id)
    if button:
        normalized_action = action_type if action_type in {"inactive", "launch_scenario", "open_set"} else "inactive"
        button.label = label.strip() or button.label
        button.action_type = normalized_action
        button.scenario_key = (scenario_key.strip() or None) if normalized_action == "launch_scenario" else None
        button.target_menu_set_id = (
            int(target_menu_set_id)
            if target_menu_set_id.strip().isdigit() and normalized_action == "open_set"
            else None
        )
        db.commit()
    return RedirectResponse(url="/settings", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/settings/menu-buttons/{button_id}/delete")
def delete_menu_button(
    request: Request,
    button_id: int,
    db: Session = Depends(get_db),
):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    button = db.get(BotMenuButton, button_id)
    if button:
        db.delete(button)
        db.commit()
    return RedirectResponse(url="/settings", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/accounts")
def create_account(
    request: Request,
    login: str = Form(""),
    password: str = Form(""),
    role: str = Form("hr"),
    is_active: str = Form("true"),
    db: Session = Depends(get_db),
):
    admin_redirect = _require_admin(request)
    if admin_redirect:
        return admin_redirect
    normalized_login = login.strip()
    existing_account = db.query(AdminAccount).filter(AdminAccount.login == normalized_login).first()
    if normalized_login and not existing_account:
        now = datetime.utcnow()
        db.add(
            AdminAccount(
                login=normalized_login,
                password_hash=hash_password(password or "change-me"),
                role=role if role in ROLE_LABELS else "hr",
                is_active=is_active == "true",
                created_at=now,
                updated_at=now,
            )
        )
        db.commit()
    return RedirectResponse(url="/settings", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/accounts/{account_id}")
def update_account(
    request: Request,
    account_id: int,
    login: str = Form(""),
    password: str = Form(""),
    role: str = Form("hr"),
    is_active: str = Form("true"),
    db: Session = Depends(get_db),
):
    admin_redirect = _require_admin(request)
    if admin_redirect:
        return admin_redirect
    account = db.get(AdminAccount, account_id)
    if account:
        account.login = login.strip() or account.login
        account.role = role if role in ROLE_LABELS else "hr"
        account.is_active = is_active == "true"
        if password.strip():
            account.password_hash = hash_password(password.strip())
        account.updated_at = datetime.utcnow()
        db.commit()
    return RedirectResponse(url="/settings", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/accounts/{account_id}/delete")
def delete_account(
    request: Request,
    account_id: int,
    db: Session = Depends(get_db),
):
    admin_redirect = _require_admin(request)
    if admin_redirect:
        return admin_redirect
    current_user = getattr(request.state, "current_user", None)
    account = db.get(AdminAccount, account_id)
    if account and (not current_user or account.id != current_user.id):
        db.delete(account)
        db.commit()
    return RedirectResponse(url="/settings", status_code=status.HTTP_303_SEE_OTHER)
