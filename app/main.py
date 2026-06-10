from datetime import datetime, date, timedelta
from typing import List, Optional

from fastapi import Body, Depends, FastAPI, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import RedirectResponse
from fastapi.routing import APIRoute
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .auth import authenticate_account, hash_password
from .config import settings
from .database import get_session, init_db
from .employee_card import render_employee_card_png
from .flow_templates import EMPLOYEE_SCOPE_LABELS, ROLE_SCOPE_LABELS, TRIGGER_MODE_LABELS
from .file_storage import build_employee_profile_photo_path
from .messaging.identity import (
    EmployeeIdentityConflictError,
    get_primary_chat_id,
    get_public_chat_handle,
    set_primary_chat_id,
    set_public_chat_handle,
    sync_legacy_telegram_account,
)
from .mass_targeting import (
    MASS_TARGET_NONE,
    build_legacy_target_statuses,
    mass_target_employee_query,
    normalize_mass_target_candidate_stages,
    normalize_mass_target_employee_stages,
    resolve_target_groups,
    serialize_target_values,
)
from .models import (
    AdminAccount,
    Employee,
    EmployeeDocumentLink,
    EmployeeFile,
    FlowStepTemplate,
    HrSettings,
    MassMessageAction,
    MassScenarioAction,
    ScenarioTemplate,
)
from .scenario_engine import format_message, get_first_step, get_scenario_steps, matches_role_scope, start_scenario
from .web.bulk_action_routes import router as bulk_action_router
from .web.document_routes import router as document_router
from .web.bulk_actions import (
    MASS_TARGET_CANDIDATE_STAGE_OPTIONS,
    MASS_TARGET_EMPLOYEE_STAGE_OPTIONS,
    _bulk_target_recipients,
    _bulk_workspace_payload,
    _ensure_confirmed,
    _mass_actions_redirect,
    _mass_target_employees,
    _parse_bulk_run_at,
    _parse_mass_action_targets,
    _recipient_scope_label,
    _send_mass_message,
    _serialize_bulk_scenario,
    _serialize_mass_message_action,
    _serialize_mass_scenario_action,
    _bulk_scenario_options,
    _format_dt,
)
from .web.dashboard_routes import router as dashboard_router
from .web.employee_routes import router as employee_router
from .web.employees import (
    CANDIDATE_WORK_STAGE_VALUES,
    EMPLOYEE_STAGE_VALUES,
    _apply_employee_telegram_identity,
    _apply_employee_update,
    _available_scenarios_for_employee,
    _build_employee_detail_payload,
    _build_employee_views,
    _candidate_work_stage_label,
    _create_employee_record,
    _delete_employee_record,
    _employee_display_name,
    _employee_identity_conflict_detail,
    _employee_identity_integrity_detail,
    _employee_list_kind,
    _employee_list_meta,
    _employee_status_label,
    _full_years_between,
    _is_employee_identity_integrity_error,
    _launch_employee_flow_now,
    _parse_employee_stage_for_create,
    _save_offer_document_link,
    _schedule_employee_flow_request,
    _send_file_to_telegram,
    _serialize_document_link,
    _serialize_employee_file,
    _serialize_employee_view,
    _serialize_launch_request,
    _telegram_profile_url,
)
from .web.scenario_routes import router as scenario_router
from .web.settings import (
    _apply_menu_button_payload,
    _delete_menu_set_relations,
    _get_or_create_hr_settings,
    _serialize_admin_account,
    _serialize_hr_settings,
    _serialize_menu_button,
    _serialize_menu_set,
    _settings_workspace_payload,
)
from .web.settings_routes import router as settings_router
from .web.support import (
    redirect_login as _redirect_login,
    render_template as _render_template,
    require_admin as _require_admin,
    require_api_admin as _require_api_admin,
    require_api_auth as _require_api_auth,
    require_auth as _require_auth,
)


AUTH_COOKIE_NAME = "hr_admin_auth"

OPENAPI_TAGS = [
    {
        "name": "Employees",
        "description": "React admin API for employee and candidate lists, detail cards, files, schedules, and launches.",
    },
    {
        "name": "Dashboard",
        "description": "Read-only operational dashboard API for upcoming actions, fresh links, inbound files, and attention items.",
    },
    {
        "name": "Flows and surveys",
        "description": "React workspace API for scenario and survey metadata, steps, branching, ordering, and attachments.",
    },
    {
        "name": "Bulk actions",
        "description": "React bulk actions API for audience preview, scheduled runs, immediate launches, and mass messages.",
    },
    {
        "name": "Settings",
        "description": "React settings API for HR settings, bot menu sets, and menu buttons.",
    },
    {
        "name": "Documents",
        "description": "React document library API for shared bot files and links.",
    },
    {
        "name": "Admin accounts",
        "description": "Admin-only API for account management.",
    },
]

app = FastAPI(
    title="HR Bot Admin",
    openapi_tags=OPENAPI_TAGS,
    swagger_ui_parameters={
        "docExpansion": "none",
        "filter": True,
        "persistAuthorization": True,
    },
)

templates = Jinja2Templates(directory="app/templates")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(dashboard_router)
app.include_router(document_router)
app.include_router(employee_router)
app.include_router(bulk_action_router)
app.include_router(scenario_router)
app.include_router(settings_router)


def _api_tag_for_path(path: str) -> str:
    if path.startswith("/api/dashboard"):
        return "Dashboard"
    if path.startswith("/api/employees"):
        return "Employees"
    if path.startswith("/api/flows"):
        return "Flows and surveys"
    if path.startswith("/api/bulk-actions"):
        return "Bulk actions"
    if path.startswith("/api/settings"):
        return "Settings"
    if path.startswith("/api/documents"):
        return "Documents"
    if path.startswith("/api/accounts"):
        return "Admin accounts"
    return "API"


def _configure_openapi_routes() -> None:
    """Keep Swagger focused on JSON API contracts, not browser/form surfaces."""
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        route.include_in_schema = route.path.startswith("/api/")
        if route.include_in_schema:
            route.tags = [_api_tag_for_path(route.path)]
    app.openapi_schema = None


def _render(request: Request, template_name: str, context: dict):
    return _render_template(request, templates, template_name, context)


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


def _scenario_matches_employee_role(scenario: ScenarioTemplate, employee: Employee) -> bool:
    return matches_role_scope(employee, scenario)


LEGACY_MASS_TARGET_OPTIONS = [
    (MASS_TARGET_NONE, "Не указан"),
    ("candidate", "Кандидат"),
    ("adaptation", "Адаптация"),
    ("ipr", "ИПР"),
    ("staff", "В штате"),
]
MASS_TARGET_EMPLOYEE_STAGE_OPTIONS = [
    (MASS_TARGET_NONE, "Не указан"),
    ("adaptation", "Адаптация"),
    ("ipr", "ИПР"),
    ("staff", "В штате"),
]
MASS_TARGET_CANDIDATE_STAGE_OPTIONS = [
    (MASS_TARGET_NONE, "Не указан"),
    ("testing", "Тестирование"),
    ("offer", "Оффер"),
    ("candidate_decline", "Отказ кандидата"),
    ("company_decline", "Наш отказ"),
    ("preonboarding", "Преонбординг"),
    ("contract", "Заключение договора"),
]


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/login")
def login_page(request: Request):
    if getattr(request.state, "current_user", None):
        return RedirectResponse(url="/app/dashboard", status_code=status.HTTP_303_SEE_OTHER)
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
    response = RedirectResponse(url="/app/dashboard", status_code=status.HTTP_303_SEE_OTHER)
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
    return RedirectResponse(url="/app/dashboard", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/swagger", include_in_schema=False)
def swagger_ui_alias():
    return RedirectResponse(url="/docs", status_code=status.HTTP_303_SEE_OTHER)





_configure_openapi_routes()

