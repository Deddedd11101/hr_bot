from datetime import datetime, date, timedelta
from io import BytesIO
from pathlib import Path
import shutil
from typing import List, Optional
from collections import defaultdict
from uuid import uuid4

from fastapi import Body, Depends, FastAPI, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .auth import ROLE_LABELS, authenticate_account, hash_password
from .config import settings
from .database import get_session, init_db
from .employee_card import render_employee_card_png
from .flow_templates import (
    EMPLOYEE_SCOPE_LABELS,
    EMPLOYEE_ROLE_VALUES,
    NOTIFICATION_RECIPIENT_SCOPE_LABELS,
    RESPONSE_TYPE_LABELS,
    ROLE_SCOPE_LABELS,
    SEND_MODE_LABELS,
    TARGET_FIELD_LABELS,
    TRIGGER_MODE_LABELS,
)
from .file_storage import (
    build_employee_profile_photo_path,
    build_step_attachment_path,
)
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
    BotMenuButton,
    BotMenuSet,
    Employee,
    EmployeeDocumentLink,
    EmployeeFile,
    FlowLaunchRequest,
    FlowStepTemplate,
    HrSettings,
    MassMessageAction,
    MassScenarioAction,
    ScenarioProgress,
    ScenarioTemplate,
    StepButtonNotification,
    SurveyAnswer,
)
from .scenario_engine import format_message, get_first_step, get_scenario_steps, matches_role_scope, start_scenario
from .web.bulk_action_routes import router as bulk_action_router
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
from .web.employee_routes import router as employee_router
from .web.employees import (
    CANDIDATE_WORK_STAGE_VALUES,
    EMPLOYEE_STAGE_VALUES,
    OFFER_DOCUMENT_TITLE,
    _all_employee_options,
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
    _menu_buttons_by_set,
    _menu_sets,
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
OFFER_DOCUMENT_TITLE = "Оффер"

app = FastAPI(title="HR Bot Admin")

templates = Jinja2Templates(directory="app/templates")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(employee_router)
app.include_router(bulk_action_router)
app.include_router(scenario_router)
app.include_router(settings_router)


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


def _load_scenario_editor_data(db: Session, scenario: ScenarioTemplate):
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
            FlowStepTemplate.branch_option_index.is_not(None),
        )
        .order_by(FlowStepTemplate.parent_step_id, FlowStepTemplate.branch_option_index, FlowStepTemplate.id)
        .all()
    )
    chain_steps = (
        db.query(FlowStepTemplate)
        .filter(
            FlowStepTemplate.flow_key == scenario.scenario_key,
            FlowStepTemplate.parent_step_id.is_not(None),
            FlowStepTemplate.branch_option_index.is_(None),
        )
        .order_by(FlowStepTemplate.parent_step_id, FlowStepTemplate.sort_order, FlowStepTemplate.id)
        .all()
    )
    branch_steps_by_parent = defaultdict(list)
    for branch_step in branch_steps:
        branch_steps_by_parent[branch_step.parent_step_id].append(branch_step)
    chain_steps_by_parent = defaultdict(list)
    for chain_step in chain_steps:
        chain_steps_by_parent[chain_step.parent_step_id].append(chain_step)
    button_notifications = (
        db.query(StepButtonNotification)
        .filter(StepButtonNotification.flow_key == scenario.scenario_key)
        .order_by(StepButtonNotification.step_id, StepButtonNotification.option_index, StepButtonNotification.id)
        .all()
    )
    button_notifications_by_step: dict[int, dict[int, StepButtonNotification]] = defaultdict(dict)
    for notification in button_notifications:
        button_notifications_by_step[notification.step_id][notification.option_index] = notification
    available_scenarios = (
        db.query(ScenarioTemplate)
        .order_by(ScenarioTemplate.title, ScenarioTemplate.id)
        .all()
    )
    employee_options = _all_employee_options(db)
    return {
        "steps": steps,
        "branch_steps_by_parent": dict(branch_steps_by_parent),
        "chain_steps_by_parent": dict(chain_steps_by_parent),
        "button_notifications_by_step": {step_id: dict(option_map) for step_id, option_map in button_notifications_by_step.items()},
        "available_scenarios": available_scenarios,
        "employee_options": employee_options,
        "document_tag_titles": [OFFER_DOCUMENT_TITLE],
    }


def _workspace_response_label(step: FlowStepTemplate) -> str:
    response_type = (step.response_type or "").strip()
    if response_type == "buttons":
        response_type = "branching"
    extra_labels = {
        "chain": "Цепочка шагов",
        "launch_scenario": "Переход к сценарию",
    }
    return RESPONSE_TYPE_LABELS.get(response_type, extra_labels.get(response_type, response_type or "none"))


def _workspace_response_type_labels() -> dict[str, str]:
    labels = {key: value for key, value in RESPONSE_TYPE_LABELS.items() if key != "buttons"}
    labels["launch_scenario"] = "Переход к сценарию"
    labels["chain"] = "Цепочка шагов"
    return labels


def _generate_workspace_scenario_key(kind: str = "scenario") -> str:
    return f"{kind}_{uuid4().hex[:12]}"


def _normalize_workspace_kind(kind: Optional[str]) -> str:
    return "survey" if (kind or "").strip() == "survey" else "scenario"


def _workspace_collection_path(kind: str) -> str:
    return "/surveys" if kind == "survey" else "/flows"


def _workspace_app_path(kind: str) -> str:
    return "/app/surveys/workspace" if kind == "survey" else "/app/flows/workspace-v2"


def _workspace_item_label(kind: str) -> str:
    return "опрос" if kind == "survey" else "сценарий"


def _get_workspace_scenario_by_flow_key(db: Session, flow_key: str) -> Optional[ScenarioTemplate]:
    return (
        db.query(ScenarioTemplate)
        .filter(
            ScenarioTemplate.scenario_key == flow_key,
            ScenarioTemplate.scenario_kind.in_(["scenario", "survey"]),
        )
        .first()
    )


def _workspace_node_kind(step: FlowStepTemplate) -> str:
    if step.parent_step_id is None:
        return "step"
    if step.branch_option_index is None:
        return "chain_step"
    return "branch_step"


def _workspace_text_preview(step: FlowStepTemplate) -> str:
    raw = (step.custom_text or step.default_text or "").strip()
    if len(raw) <= 180:
        return raw
    return f"{raw[:177].rstrip()}..."


def _serialize_workspace_step(
    step: FlowStepTemplate,
    branch_steps_by_parent: dict[int, list[FlowStepTemplate]],
    chain_steps_by_parent: dict[int, list[FlowStepTemplate]],
):
    button_options = [item.strip() for item in (step.button_options or "").splitlines() if item.strip()]
    branch_items = []
    if step.response_type == "branching":
        existing_branch_steps = {
            child.branch_option_index: child
            for child in branch_steps_by_parent.get(step.id, [])
            if child.branch_option_index is not None
        }
        for option_index, label in enumerate(button_options):
            branch_step = existing_branch_steps.get(option_index)
            branch_items.append(
                {
                    "id": f"branch-slot-{step.id}-{option_index}",
                    "kind": "branch_slot",
                    "option_index": option_index,
                    "label": label,
                    "has_step": branch_step is not None,
                    "step": _serialize_workspace_step(branch_step, branch_steps_by_parent, chain_steps_by_parent) if branch_step else None,
                }
            )

    chain_steps = []
    if step.response_type == "chain":
        chain_steps = [
            _serialize_workspace_step(child, branch_steps_by_parent, chain_steps_by_parent)
            for child in chain_steps_by_parent.get(step.id, [])
        ]

    return {
        "id": step.id,
        "kind": _workspace_node_kind(step),
        "title": step.step_title,
        "text": (step.custom_text or "").strip() if (step.custom_text or "").strip() else (step.default_text or ""),
        "text_preview": _workspace_text_preview(step),
        "response_type": step.response_type or "none",
        "response_label": _workspace_response_label(step),
        "button_options": button_options,
        "has_attachment": bool(step.attachment_filename),
        "attachment_filename": step.attachment_filename or "",
        "send_employee_card": bool(getattr(step, "send_employee_card", False)),
        "send_mode": step.send_mode or "immediate",
        "send_mode_label": SEND_MODE_LABELS.get(step.send_mode or "immediate", step.send_mode or "immediate"),
        "send_time": step.send_time or "",
        "day_offset_workdays": step.day_offset_workdays or 0,
        "target_field": step.target_field or "",
        "target_field_label": TARGET_FIELD_LABELS.get(step.target_field or "", "Не сохранять"),
        "launch_scenario_key": step.launch_scenario_key or "",
        "notify_on_send": bool(
            (getattr(step, "notify_on_send_text", None) or "").strip()
            or (getattr(step, "notify_on_send_recipient_ids", None) or "").strip()
            or (getattr(step, "notify_on_send_recipient_scope", None) or "").strip()
        ),
        "notify_on_send_text": getattr(step, "notify_on_send_text", None) or "",
        "notify_on_send_recipient_ids": getattr(step, "notify_on_send_recipient_ids", None) or "",
        "notify_on_send_recipient_scope": getattr(step, "notify_on_send_recipient_scope", None) or "",
        "branch_items": branch_items,
        "chain_steps": chain_steps,
    }


def _build_scenario_workspace_payload(
    db: Session,
    selected_scenario_id: Optional[int] = None,
    kind: str = "scenario",
):
    kind = _normalize_workspace_kind(kind)
    scenarios = (
        db.query(ScenarioTemplate)
        .filter(ScenarioTemplate.scenario_kind == kind)
        .order_by(ScenarioTemplate.sort_order, ScenarioTemplate.id)
        .all()
    )

    selected_scenario = None
    if selected_scenario_id:
        selected_scenario = next((item for item in scenarios if item.id == selected_scenario_id), None)
    if selected_scenario is None and scenarios:
        selected_scenario = scenarios[0]

    scenario_items = []
    for scenario in scenarios:
        steps_count = (
            db.query(FlowStepTemplate)
            .filter(
                FlowStepTemplate.flow_key == scenario.scenario_key,
                FlowStepTemplate.parent_step_id.is_(None),
            )
            .count()
        )
        scenario_items.append(
            {
                "id": scenario.id,
                "title": scenario.title,
                "description": scenario.description or "",
                "role_scope_label": ROLE_SCOPE_LABELS.get(scenario.role_scope, scenario.role_scope),
                "employee_scope_label": EMPLOYEE_SCOPE_LABELS.get(
                    getattr(scenario, "employee_scope", "all"),
                    getattr(scenario, "employee_scope", "all"),
                ),
                "trigger_mode_label": TRIGGER_MODE_LABELS.get(scenario.trigger_mode, scenario.trigger_mode),
                "steps_count": steps_count,
                "classic_url": f"{_workspace_collection_path(kind)}/{scenario.id}",
                "workspace_url": f"{_workspace_app_path(kind)}?scenario_id={scenario.id}",
            }
        )

    workspace = None
    if selected_scenario is not None:
        editor_data = _load_scenario_editor_data(db, selected_scenario)
        root_steps = [
            _serialize_workspace_step(step, editor_data["branch_steps_by_parent"], editor_data["chain_steps_by_parent"])
            for step in editor_data["steps"]
        ]
        workspace = {
            "scenario": {
                "id": selected_scenario.id,
                "title": selected_scenario.title,
                "description": selected_scenario.description or "",
                "role_scope": selected_scenario.role_scope,
                "role_scope_label": ROLE_SCOPE_LABELS.get(selected_scenario.role_scope, selected_scenario.role_scope),
                "employee_scope": getattr(selected_scenario, "employee_scope", "all"),
                "employee_scope_label": EMPLOYEE_SCOPE_LABELS.get(
                    getattr(selected_scenario, "employee_scope", "all"),
                    getattr(selected_scenario, "employee_scope", "all"),
                ),
                "trigger_mode": selected_scenario.trigger_mode,
                "trigger_mode_label": TRIGGER_MODE_LABELS.get(selected_scenario.trigger_mode, selected_scenario.trigger_mode),
                "target_employee_id": getattr(selected_scenario, "target_employee_id", None),
                "classic_url": f"{_workspace_collection_path(kind)}/{selected_scenario.id}",
                "scenario_kind": kind,
            },
            "root_steps": root_steps,
            "stats": {
                "steps_count": len(root_steps),
            },
            "response_type_labels": _workspace_response_type_labels(),
            "role_scope_labels": ROLE_SCOPE_LABELS,
            "employee_scope_labels": EMPLOYEE_SCOPE_LABELS,
            "trigger_mode_labels": TRIGGER_MODE_LABELS,
            "target_field_labels": TARGET_FIELD_LABELS,
            "send_mode_labels": SEND_MODE_LABELS,
            "notification_recipient_scope_labels": NOTIFICATION_RECIPIENT_SCOPE_LABELS,
            "document_tag_titles": editor_data["document_tag_titles"],
            "employee_options": editor_data["employee_options"],
            "available_scenarios": [
                {
                    "value": item.scenario_key,
                    "label": item.title,
                }
                for item in editor_data["available_scenarios"]
            ],
        }

    return {
        "kind": kind,
        "item_label": _workspace_item_label(kind),
        "scenarios": scenario_items,
        "selected_scenario_id": selected_scenario.id if selected_scenario else None,
        "workspace": workspace,
    }


def _normalize_workspace_response_type(value: str, step: FlowStepTemplate) -> str:
    normalized = (value or "").strip()
    allowed = {"none", "text", "file", "buttons", "branching", "launch_scenario"}
    if step.parent_step_id is not None and step.branch_option_index is not None:
        allowed.add("chain")
    return normalized if normalized in allowed else (step.response_type or "none")


def _apply_workspace_step_update(step: FlowStepTemplate, payload: dict):
    step.step_title = (str(payload.get("title") or "").strip() or step.step_title or "Без названия")
    step.custom_text = str(payload.get("text") or "").strip()
    step.response_type = _normalize_workspace_response_type(str(payload.get("response_type") or ""), step)
    button_options = str(payload.get("button_options") or "").strip()
    step.button_options = button_options or None

    send_mode = (str(payload.get("send_mode") or "").strip() or "immediate")
    step.send_mode = send_mode if send_mode in SEND_MODE_LABELS else "immediate"
    step.send_time = (str(payload.get("send_time") or "").strip() or None) if step.send_mode == "specific_time" else None

    target_field = str(payload.get("target_field") or "").strip()
    step.target_field = target_field if target_field in TARGET_FIELD_LABELS else None
    step.launch_scenario_key = (
        str(payload.get("launch_scenario_key") or "").strip() or None
        if step.response_type == "launch_scenario"
        else None
    )
    step.send_employee_card = str(payload.get("send_employee_card") or "").strip().lower() in {"1", "true", "yes", "on"}
    step.notify_on_send_text = str(payload.get("notify_on_send_text") or "").strip() or None
    step.notify_on_send_recipient_ids = str(payload.get("notify_on_send_recipient_ids") or "").strip() or None
    step.notify_on_send_recipient_scope = _normalize_notification_scope(str(payload.get("notify_on_send_recipient_scope") or ""))

    if step.response_type not in {"buttons", "branching"}:
        step.button_options = None
    if step.response_type in {"branching", "chain"}:
        step.target_field = None

    return step


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


def _employee_matches_role_scope(employee: Employee, role_scope: Optional[str]) -> bool:
    normalized = (role_scope or "").strip()
    if not normalized or normalized == "all":
        return True
    role_map = {
        "designer": "Дизайнер",
        "project_manager": "Project manager",
        "analyst": "Аналитик",
    }
    return (employee.desired_position or "") == role_map.get(normalized, "")


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


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/login")
def login_page(request: Request):
    if getattr(request.state, "current_user", None):
        return RedirectResponse(url="/app/employees?list_kind=candidates", status_code=status.HTTP_303_SEE_OTHER)
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
    response = RedirectResponse(url="/app/employees?list_kind=candidates", status_code=status.HTTP_303_SEE_OTHER)
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
    return RedirectResponse(url="/app/employees?list_kind=candidates", status_code=status.HTTP_303_SEE_OTHER)


def _delete_step_attachment_file(step: FlowStepTemplate) -> None:
    attachment_path = (getattr(step, "attachment_path", None) or "").strip()
    if attachment_path:
        path = Path(attachment_path)
        if path.exists():
            path.unlink()
    setattr(step, "attachment_path", None)
    setattr(step, "attachment_filename", None)


def _delete_step_subtree(db: Session, step: FlowStepTemplate) -> None:
    child_steps = (
        db.query(FlowStepTemplate)
        .filter(FlowStepTemplate.parent_step_id == step.id)
        .order_by(FlowStepTemplate.id.asc())
        .all()
    )
    for child_step in child_steps:
        _delete_step_subtree(db, child_step)
    _delete_step_attachment_file(step)
    db.query(StepButtonNotification).filter(StepButtonNotification.step_id == step.id).delete()
    db.delete(step)


def _normalize_notification_scope(value: Optional[str]) -> Optional[str]:
    normalized = ",".join(
        chunk.strip()
        for chunk in (value or "").replace("\n", ",").split(",")
        if chunk.strip()
    )
    return normalized if normalized in NOTIFICATION_RECIPIENT_SCOPE_LABELS else None


def _sync_button_notification(
    db: Session,
    step: FlowStepTemplate,
    option_index: int,
    message_text: str,
    recipient_ids: str,
    recipient_scope: str,
) -> None:
    notification = (
        db.query(StepButtonNotification)
        .filter(
            StepButtonNotification.step_id == step.id,
            StepButtonNotification.option_index == option_index,
        )
        .order_by(StepButtonNotification.id.asc())
        .first()
    )
    normalized_text = message_text.strip() or None
    normalized_recipient_ids = recipient_ids.strip() or None
    normalized_scope = _normalize_notification_scope(recipient_scope)
    if not normalized_text and not normalized_recipient_ids and not normalized_scope:
        if notification:
            db.delete(notification)
        return
    if not notification:
        notification = StepButtonNotification(
            flow_key=step.flow_key,
            step_id=step.id,
            option_index=option_index,
        )
        db.add(notification)
    notification.flow_key = step.flow_key
    notification.step_id = step.id
    notification.option_index = option_index
    notification.message_text = normalized_text
    notification.recipient_ids = normalized_recipient_ids
    notification.recipient_scope = normalized_scope


def _copy_step_attachment_file(source_step: FlowStepTemplate, target_step: FlowStepTemplate) -> None:
    source_path = (getattr(source_step, "attachment_path", None) or "").strip()
    source_name = (getattr(source_step, "attachment_filename", None) or "").strip()
    if not source_path or not source_name:
        return
    source = Path(source_path)
    if not source.exists():
        return
    destination = build_step_attachment_path(target_step.flow_key, target_step.step_key, source_name)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    target_step.attachment_path = str(destination)
    target_step.attachment_filename = source_name


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


def _delete_step_tree(db: Session, step: FlowStepTemplate) -> None:
    db.query(StepButtonNotification).filter(StepButtonNotification.step_id == step.id).delete()
    children = (
        db.query(FlowStepTemplate)
        .filter(FlowStepTemplate.parent_step_id == step.id)
        .all()
    )
    for child in children:
        _delete_step_tree(db, child)
    _delete_step_attachment_file(step)
    db.delete(step)


def _copy_template_entity(db: Session, scenario: ScenarioTemplate) -> ScenarioTemplate:
    last_scenario = (
        db.query(ScenarioTemplate)
        .filter(ScenarioTemplate.scenario_kind == scenario.scenario_kind)
        .order_by(ScenarioTemplate.sort_order.desc(), ScenarioTemplate.id.desc())
        .first()
    )
    scenario_copy = ScenarioTemplate(
        scenario_key=_generate_workspace_scenario_key(f"custom_{scenario.scenario_kind}"),
        title=f"{scenario.title} (копия)",
        sort_order=(last_scenario.sort_order + 10) if last_scenario else 10,
        scenario_kind=scenario.scenario_kind,
        role_scope=scenario.role_scope,
        employee_scope=getattr(scenario, "employee_scope", "all"),
        target_employee_id=getattr(scenario, "target_employee_id", None),
        trigger_mode=scenario.trigger_mode,
        description=scenario.description,
    )
    db.add(scenario_copy)
    db.flush()

    original_steps = (
        db.query(FlowStepTemplate)
        .filter(FlowStepTemplate.flow_key == scenario.scenario_key)
        .order_by(FlowStepTemplate.id.asc())
        .all()
    )
    original_button_notifications = (
        db.query(StepButtonNotification)
        .filter(StepButtonNotification.flow_key == scenario.scenario_key)
        .order_by(StepButtonNotification.step_id.asc(), StepButtonNotification.option_index.asc(), StepButtonNotification.id.asc())
        .all()
    )
    step_id_map: dict[int, FlowStepTemplate] = {}
    for index, original_step in enumerate(original_steps, start=1):
        copied_step = FlowStepTemplate(
            flow_key=scenario_copy.scenario_key,
            step_key=f"{original_step.step_key}_copy_{scenario_copy.id}_{index}",
            parent_step_id=step_id_map.get(original_step.parent_step_id).id if original_step.parent_step_id in step_id_map else None,
            branch_option_index=original_step.branch_option_index,
            step_title=original_step.step_title,
            sort_order=original_step.sort_order,
            default_text=original_step.default_text,
            custom_text=original_step.custom_text,
            response_type=original_step.response_type,
            button_options=original_step.button_options,
            send_mode=original_step.send_mode,
            send_time=original_step.send_time,
            day_offset_workdays=original_step.day_offset_workdays,
            target_field=original_step.target_field,
            launch_scenario_key=original_step.launch_scenario_key,
            send_employee_card=getattr(original_step, "send_employee_card", False),
            notify_on_send_text=getattr(original_step, "notify_on_send_text", None),
            notify_on_send_recipient_ids=getattr(original_step, "notify_on_send_recipient_ids", None),
            notify_on_send_recipient_scope=getattr(original_step, "notify_on_send_recipient_scope", None),
        )
        db.add(copied_step)
        db.flush()
        _copy_step_attachment_file(original_step, copied_step)
        step_id_map[original_step.id] = copied_step

    for original_notification in original_button_notifications:
        copied_parent_step = step_id_map.get(original_notification.step_id)
        if not copied_parent_step:
            continue
        db.add(
            StepButtonNotification(
                flow_key=scenario_copy.scenario_key,
                step_id=copied_parent_step.id,
                option_index=original_notification.option_index,
                message_text=original_notification.message_text,
                recipient_ids=original_notification.recipient_ids,
                recipient_scope=original_notification.recipient_scope,
            )
        )

    db.commit()
    db.refresh(scenario_copy)
    return scenario_copy


def _delete_template_entity(db: Session, scenario: ScenarioTemplate) -> None:
    for step in db.query(FlowStepTemplate).filter(FlowStepTemplate.flow_key == scenario.scenario_key).all():
        _delete_step_attachment_file(step)
    db.query(StepButtonNotification).filter(StepButtonNotification.flow_key == scenario.scenario_key).delete()
    db.query(FlowStepTemplate).filter(FlowStepTemplate.flow_key == scenario.scenario_key).delete()
    db.query(ScenarioProgress).filter(ScenarioProgress.scenario_key == scenario.scenario_key).delete()
    db.query(SurveyAnswer).filter(SurveyAnswer.scenario_key == scenario.scenario_key).delete()
    db.query(FlowLaunchRequest).filter(FlowLaunchRequest.flow_key == scenario.scenario_key).delete()
    db.delete(scenario)


def _template_list_page(request: Request, kind: str, db: Session):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    meta = _template_entity_meta(kind)
    scenarios = (
        db.query(ScenarioTemplate)
        .filter(ScenarioTemplate.scenario_kind == kind)
        .order_by(ScenarioTemplate.sort_order, ScenarioTemplate.id)
        .all()
    )
    return _render(
        request,
        "scenarios.html",
        {
            "active_tab": meta["active_tab"],
            "scenarios": scenarios,
            "role_scope_labels": ROLE_SCOPE_LABELS,
            "employee_scope_labels": EMPLOYEE_SCOPE_LABELS,
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


def _create_template_entity(
    request: Request,
    kind: str,
    title: str,
    role_scope: str,
    employee_scope: str,
    target_employee_id: str,
    trigger_mode: str,
    description: str,
    db: Session,
):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    meta = _template_entity_meta(kind)
    last_scenario = (
        db.query(ScenarioTemplate)
        .filter(ScenarioTemplate.scenario_kind == kind)
        .order_by(ScenarioTemplate.sort_order.desc(), ScenarioTemplate.id.desc())
        .first()
    )
    scenario = ScenarioTemplate(
        scenario_key=f"custom_{kind}_{int(datetime.utcnow().timestamp())}",
        scenario_kind=kind,
        title=title.strip() or meta["new_title"],
        sort_order=(last_scenario.sort_order + 10) if last_scenario else 10,
        role_scope=role_scope if role_scope in ROLE_SCOPE_LABELS else "all",
        employee_scope=employee_scope if employee_scope in EMPLOYEE_SCOPE_LABELS else "all",
        target_employee_id=int(target_employee_id) if (target_employee_id or "").strip().isdigit() else None,
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
    employee_scope: str = Form("all"),
    target_employee_id: str = Form(""),
    trigger_mode: str = Form("manual_only"),
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    return _create_template_entity(request, "scenario", title, role_scope, employee_scope, target_employee_id, trigger_mode, description, db)


@app.post("/surveys")
def create_survey(
    request: Request,
    title: str = Form("Новый опрос"),
    role_scope: str = Form("all"),
    employee_scope: str = Form("all"),
    target_employee_id: str = Form(""),
    trigger_mode: str = Form("manual_only"),
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    return _create_template_entity(request, "survey", title, role_scope, employee_scope, target_employee_id, trigger_mode, description, db)


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
    editor_data = _load_scenario_editor_data(db, scenario)
    return _render(
        request,
        "scenario_edit.html",
        {
            "active_tab": meta["active_tab"],
            "scenario": scenario,
            "steps": editor_data["steps"],
            "role_scope_labels": ROLE_SCOPE_LABELS,
            "employee_scope_labels": EMPLOYEE_SCOPE_LABELS,
            "trigger_mode_labels": TRIGGER_MODE_LABELS,
            "response_type_labels": RESPONSE_TYPE_LABELS,
            "send_mode_labels": SEND_MODE_LABELS,
            "target_field_labels": TARGET_FIELD_LABELS,
            "notification_recipient_scope_labels": NOTIFICATION_RECIPIENT_SCOPE_LABELS,
            "branch_steps_by_parent": editor_data["branch_steps_by_parent"],
            "chain_steps_by_parent": editor_data["chain_steps_by_parent"],
            "button_notifications_by_step": editor_data["button_notifications_by_step"],
            "available_scenarios": editor_data["available_scenarios"],
            "employee_options": editor_data["employee_options"],
            "document_tag_titles": editor_data["document_tag_titles"],
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
    employee_scope: str = Form("all"),
    target_employee_id: str = Form(""),
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
    send_employee_card: Optional[List[str]] = Form(None),
    notify_on_send_text: Optional[List[str]] = Form(None),
    notify_on_send_recipient_ids: Optional[List[str]] = Form(None),
    notify_on_send_recipient_scope: Optional[List[str]] = Form(None),
    remove_attachment_step_id: Optional[List[int]] = Form(None),
    branch_parent_step_id: Optional[List[str]] = Form(None),
    branch_parent_step_ref: Optional[List[str]] = Form(None),
    branch_option_index: Optional[List[str]] = Form(None),
    branch_step_id: Optional[List[str]] = Form(None),
    branch_step_title: Optional[List[str]] = Form(None),
    branch_custom_text: Optional[List[str]] = Form(None),
    branch_response_type: Optional[List[str]] = Form(None),
    branch_button_options: Optional[List[str]] = Form(None),
    branch_launch_scenario_key: Optional[List[str]] = Form(None),
    branch_send_employee_card: Optional[List[str]] = Form(None),
    branch_notify_on_send_text: Optional[List[str]] = Form(None),
    branch_notify_on_send_recipient_ids: Optional[List[str]] = Form(None),
    branch_notify_on_send_recipient_scope: Optional[List[str]] = Form(None),
    branch_button_notification_text: Optional[List[str]] = Form(None),
    branch_button_notification_recipient_ids: Optional[List[str]] = Form(None),
    branch_button_notification_recipient_scope: Optional[List[str]] = Form(None),
    button_notification_parent_step_id: Optional[List[str]] = Form(None),
    button_notification_parent_step_ref: Optional[List[str]] = Form(None),
    button_notification_option_index: Optional[List[str]] = Form(None),
    button_notification_text: Optional[List[str]] = Form(None),
    button_notification_recipient_ids: Optional[List[str]] = Form(None),
    button_notification_recipient_scope: Optional[List[str]] = Form(None),
    branch_remove_attachment_key: Optional[List[str]] = Form(None),
    chain_parent_step_id: Optional[List[str]] = Form(None),
    chain_branch_option_index: Optional[List[str]] = Form(None),
    chain_step_id: Optional[List[str]] = Form(None),
    chain_row_ref: Optional[List[str]] = Form(None),
    chain_step_title: Optional[List[str]] = Form(None),
    chain_custom_text: Optional[List[str]] = Form(None),
    chain_response_type: Optional[List[str]] = Form(None),
    chain_button_options: Optional[List[str]] = Form(None),
    chain_send_mode: Optional[List[str]] = Form(None),
    chain_send_time: Optional[List[str]] = Form(None),
    chain_target_field: Optional[List[str]] = Form(None),
    chain_send_employee_card: Optional[List[str]] = Form(None),
    chain_notify_on_send_text: Optional[List[str]] = Form(None),
    chain_notify_on_send_recipient_ids: Optional[List[str]] = Form(None),
    chain_notify_on_send_recipient_scope: Optional[List[str]] = Form(None),
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
        scenario.employee_scope = employee_scope if employee_scope in EMPLOYEE_SCOPE_LABELS else "all"
        scenario.target_employee_id = int(target_employee_id) if (target_employee_id or "").strip().isdigit() else None
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
        send_employee_card_values = send_employee_card or []
        notify_on_send_text_values = notify_on_send_text or []
        notify_on_send_recipient_ids_values = notify_on_send_recipient_ids or []
        notify_on_send_recipient_scope_values = notify_on_send_recipient_scope or []
        removed_attachment_step_ids = set(remove_attachment_step_id or [])
        branch_parent_ids = form_list("branch_parent_step_id")
        branch_parent_refs = form_list("branch_parent_step_ref")
        branch_option_indexes = form_list("branch_option_index")
        branch_step_ids = form_list("branch_step_id")
        branch_step_titles = form_list("branch_step_title")
        branch_custom_texts = form_list("branch_custom_text")
        branch_response_types = form_list("branch_response_type")
        branch_button_values = form_list("branch_button_options")
        branch_launch_scenario_keys = form_list("branch_launch_scenario_key")
        branch_send_employee_card_values = form_list("branch_send_employee_card")
        branch_notify_on_send_text_values = form_list("branch_notify_on_send_text")
        branch_notify_on_send_recipient_ids_values = form_list("branch_notify_on_send_recipient_ids")
        branch_notify_on_send_recipient_scope_values = form_list("branch_notify_on_send_recipient_scope")
        branch_button_notification_texts = form_list("branch_button_notification_text")
        branch_button_notification_recipient_ids_values = form_list("branch_button_notification_recipient_ids")
        branch_button_notification_recipient_scope_values = form_list("branch_button_notification_recipient_scope")
        button_notification_parent_ids = form_list("button_notification_parent_step_id")
        button_notification_parent_refs = form_list("button_notification_parent_step_ref")
        button_notification_option_indexes = form_list("button_notification_option_index")
        button_notification_texts = form_list("button_notification_text")
        button_notification_recipient_ids_values = form_list("button_notification_recipient_ids")
        button_notification_recipient_scope_values = form_list("button_notification_recipient_scope")
        removed_branch_attachment_keys = set(form_list("branch_remove_attachment_key"))
        chain_parent_ids = form_list("chain_parent_step_id")
        chain_branch_option_indexes = form_list("chain_branch_option_index")
        chain_step_ids = form_list("chain_step_id")
        chain_row_refs = form_list("chain_row_ref")
        chain_step_titles = form_list("chain_step_title")
        chain_custom_texts = form_list("chain_custom_text")
        chain_response_types = form_list("chain_response_type")
        chain_button_values = form_list("chain_button_options")
        chain_send_modes = form_list("chain_send_mode")
        chain_send_times = form_list("chain_send_time")
        chain_target_fields = form_list("chain_target_field")
        chain_send_employee_card_values = form_list("chain_send_employee_card")
        chain_notify_on_send_text_values = form_list("chain_notify_on_send_text")
        chain_notify_on_send_recipient_ids_values = form_list("chain_notify_on_send_recipient_ids")
        chain_notify_on_send_recipient_scope_values = form_list("chain_notify_on_send_recipient_scope")

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
            if index < len(send_employee_card_values):
                step.send_employee_card = send_employee_card_values[index] == "true"
            if index < len(notify_on_send_text_values):
                step.notify_on_send_text = notify_on_send_text_values[index].strip() or None
            if index < len(notify_on_send_recipient_ids_values):
                step.notify_on_send_recipient_ids = notify_on_send_recipient_ids_values[index].strip() or None
            if index < len(notify_on_send_recipient_scope_values):
                step.notify_on_send_recipient_scope = _normalize_notification_scope(notify_on_send_recipient_scope_values[index])
            if scenario.scenario_kind == "survey":
                step.send_mode = "immediate"
                step.send_time = None
                step.day_offset_workdays = 0
                step.target_field = None
                step.send_employee_card = False
            if step.response_type == "buttons":
                options = [item.strip() for item in (step.button_options or "").splitlines() if item.strip()]
                preserved_option_indexes: set[int] = set()
                for option_idx, _ in enumerate(options):
                    payload = submitted_button_notification_rows.get((step.id, option_idx), {})
                    _sync_button_notification(
                        db,
                        step,
                        option_idx,
                        str(payload.get("text") or ""),
                        str(payload.get("recipient_ids") or ""),
                        str(payload.get("recipient_scope") or ""),
                    )
                    preserved_option_indexes.add(option_idx)
                for notification in db.query(StepButtonNotification).filter(StepButtonNotification.step_id == step.id).all():
                    if notification.option_index not in preserved_option_indexes:
                        db.delete(notification)
            else:
                db.query(StepButtonNotification).filter(StepButtonNotification.step_id == step.id).delete()
            if step.id in removed_attachment_step_ids:
                _delete_step_attachment_file(step)
            upload = request_form.get(f"step_attachment_{step.id}")
            if upload is not None and getattr(upload, "filename", ""):
                await _save_step_attachment(step, upload)

        if action == "delete_step" and target_step_id_int is not None:
            step = db.get(FlowStepTemplate, target_step_id_int)
            if step and step.flow_key == scenario.scenario_key:
                _delete_step_tree(db, step)
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
                    send_employee_card=False,
                )
            )

        submitted_branch_rows = {}
        submitted_branch_rows_by_ref = {}
        for index, parent_id in enumerate(branch_parent_ids):
            parent_id_value = int(parent_id) if str(parent_id).strip().isdigit() else None
            parent_ref_value = branch_parent_refs[index].strip() if index < len(branch_parent_refs) else ""
            option_idx_raw = branch_option_indexes[index] if index < len(branch_option_indexes) else None
            option_idx = int(option_idx_raw) if str(option_idx_raw).strip().isdigit() else None
            branch_step_id_raw = branch_step_ids[index] if index < len(branch_step_ids) else None
            branch_step_id_value = int(branch_step_id_raw) if str(branch_step_id_raw).strip().isdigit() else None
            if (parent_id_value is None and not parent_ref_value) or option_idx is None:
                continue
            payload = {
                "branch_step_id": branch_step_id_value,
                "title": branch_step_titles[index] if index < len(branch_step_titles) else "",
                "custom_text": branch_custom_texts[index] if index < len(branch_custom_texts) else "",
                "response_type": branch_response_types[index] if index < len(branch_response_types) else "none",
                "button_options": branch_button_values[index] if index < len(branch_button_values) else "",
                "launch_scenario_key": branch_launch_scenario_keys[index] if index < len(branch_launch_scenario_keys) else "",
                "send_employee_card": branch_send_employee_card_values[index] if index < len(branch_send_employee_card_values) else "false",
                "notify_on_send_text": branch_notify_on_send_text_values[index] if index < len(branch_notify_on_send_text_values) else "",
                "notify_on_send_recipient_ids": branch_notify_on_send_recipient_ids_values[index] if index < len(branch_notify_on_send_recipient_ids_values) else "",
                "notify_on_send_recipient_scope": branch_notify_on_send_recipient_scope_values[index] if index < len(branch_notify_on_send_recipient_scope_values) else "",
                "button_notification_text": branch_button_notification_texts[index] if index < len(branch_button_notification_texts) else "",
                "button_notification_recipient_ids": branch_button_notification_recipient_ids_values[index] if index < len(branch_button_notification_recipient_ids_values) else "",
                "button_notification_recipient_scope": branch_button_notification_recipient_scope_values[index] if index < len(branch_button_notification_recipient_scope_values) else "",
            }
            if parent_id_value is not None:
                submitted_branch_rows[(parent_id_value, option_idx)] = payload
            if parent_ref_value:
                submitted_branch_rows_by_ref[(parent_ref_value, option_idx)] = payload

        submitted_chain_rows: dict[tuple[int, int], list[dict[str, object]]] = defaultdict(list)
        for index, parent_id in enumerate(chain_parent_ids):
            parent_id_value = int(parent_id) if str(parent_id).strip().isdigit() else None
            branch_option_raw = chain_branch_option_indexes[index] if index < len(chain_branch_option_indexes) else None
            branch_option_value = int(branch_option_raw) if str(branch_option_raw).strip().isdigit() else None
            chain_step_id_raw = chain_step_ids[index] if index < len(chain_step_ids) else None
            chain_step_id_value = int(chain_step_id_raw) if str(chain_step_id_raw).strip().isdigit() else None
            if parent_id_value is None or branch_option_value is None:
                continue
            submitted_chain_rows[(parent_id_value, branch_option_value)].append(
                {
                    "chain_step_id": chain_step_id_value,
                    "row_ref": chain_row_refs[index] if index < len(chain_row_refs) else "",
                    "title": chain_step_titles[index] if index < len(chain_step_titles) else "",
                    "custom_text": chain_custom_texts[index] if index < len(chain_custom_texts) else "",
                    "response_type": chain_response_types[index] if index < len(chain_response_types) else "none",
                    "button_options": chain_button_values[index] if index < len(chain_button_values) else "",
                    "send_mode": chain_send_modes[index] if index < len(chain_send_modes) else "immediate",
                    "send_time": chain_send_times[index] if index < len(chain_send_times) else "",
                    "target_field": chain_target_fields[index] if index < len(chain_target_fields) else "",
                    "send_employee_card": chain_send_employee_card_values[index] if index < len(chain_send_employee_card_values) else "false",
                    "notify_on_send_text": chain_notify_on_send_text_values[index] if index < len(chain_notify_on_send_text_values) else "",
                    "notify_on_send_recipient_ids": chain_notify_on_send_recipient_ids_values[index] if index < len(chain_notify_on_send_recipient_ids_values) else "",
                    "notify_on_send_recipient_scope": chain_notify_on_send_recipient_scope_values[index] if index < len(chain_notify_on_send_recipient_scope_values) else "",
                    "row_index": len(submitted_chain_rows[(parent_id_value, branch_option_value)]),
                }
            )

        submitted_button_notification_rows = {}
        submitted_button_notification_rows_by_ref = {}
        for index, parent_id in enumerate(button_notification_parent_ids):
            parent_id_value = int(parent_id) if str(parent_id).strip().isdigit() else None
            parent_ref_value = button_notification_parent_refs[index].strip() if index < len(button_notification_parent_refs) else ""
            option_idx_raw = button_notification_option_indexes[index] if index < len(button_notification_option_indexes) else ""
            option_idx = int(option_idx_raw) if str(option_idx_raw).strip().isdigit() else None
            if (parent_id_value is None and not parent_ref_value) or option_idx is None:
                continue
            payload = {
                "text": button_notification_texts[index] if index < len(button_notification_texts) else "",
                "recipient_ids": button_notification_recipient_ids_values[index] if index < len(button_notification_recipient_ids_values) else "",
                "recipient_scope": button_notification_recipient_scope_values[index] if index < len(button_notification_recipient_scope_values) else "",
            }
            if parent_id_value is not None:
                submitted_button_notification_rows[(parent_id_value, option_idx)] = payload
            if parent_ref_value:
                submitted_button_notification_rows_by_ref[(parent_ref_value, option_idx)] = payload

        chain_step_id_by_ref: dict[str, int] = {}

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
                    _delete_step_tree(db, child)
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
                        send_employee_card=False,
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
                        "chain",
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
                branch_step.send_employee_card = str(payload.get("send_employee_card") or "false").strip() == "true"
                branch_step.notify_on_send_text = str(payload.get("notify_on_send_text") or "").strip() or None
                branch_step.notify_on_send_recipient_ids = str(payload.get("notify_on_send_recipient_ids") or "").strip() or None
                branch_step.notify_on_send_recipient_scope = _normalize_notification_scope(str(payload.get("notify_on_send_recipient_scope") or ""))
                _sync_button_notification(
                    db,
                    step,
                    option_idx,
                    str(payload.get("button_notification_text") or ""),
                    str(payload.get("button_notification_recipient_ids") or ""),
                    str(payload.get("button_notification_recipient_scope") or ""),
                )

                # New branch rows need a database id before nested chain steps can
                # be attached to them. Without this flush, first-save chain steps
                # are created without a real parent and disappear from the editor.
                db.flush()

                existing_chain_children = {
                    child.id: child
                    for child in db.query(FlowStepTemplate)
                    .filter(
                        FlowStepTemplate.parent_step_id == branch_step.id,
                        FlowStepTemplate.branch_option_index.is_(None),
                    )
                    .all()
                }
                chain_payloads = submitted_chain_rows.get((step.id, option_idx), [])
                if branch_step.response_type == "chain":
                    preserved_chain_ids: set[int] = set()
                    for chain_index, chain_payload in enumerate(chain_payloads):
                        chain_step = None
                        chain_step_id_value = chain_payload.get("chain_step_id")
                        is_new_chain_step = not isinstance(chain_step_id_value, int)
                        if isinstance(chain_step_id_value, int):
                            chain_step = existing_chain_children.get(chain_step_id_value)
                        if chain_step is None:
                            chain_step = FlowStepTemplate(
                                flow_key=scenario.scenario_key,
                                step_key=f"{branch_step.step_key}__chain_{chain_index}",
                                parent_step_id=branch_step.id,
                                branch_option_index=None,
                                step_title=f"Шаг {chain_index + 1}",
                                sort_order=(chain_index + 1) * 10,
                                default_text="Новое сообщение сценария.",
                                custom_text=None,
                                response_type="none",
                                button_options=None,
                                send_mode="immediate",
                                send_time=None,
                                day_offset_workdays=0,
                                target_field=None,
                                launch_scenario_key=None,
                                send_employee_card=False,
                            )
                            db.add(chain_step)
                            db.flush()
                        chain_step.flow_key = scenario.scenario_key
                        chain_step.parent_step_id = branch_step.id
                        chain_step.branch_option_index = None
                        chain_step.step_key = f"{branch_step.step_key}__chain_{chain_index}"
                        chain_step.sort_order = (chain_index + 1) * 10
                        chain_step.step_title = (str(chain_payload.get("title") or "").strip() or f"Шаг {chain_index + 1}")
                        chain_text_value = str(chain_payload.get("custom_text") or "").strip()
                        chain_step.custom_text = None if is_new_chain_step and not chain_text_value else chain_text_value
                        chain_response_type_value = str(chain_payload.get("response_type") or "none").strip()
                        chain_step.response_type = chain_response_type_value if chain_response_type_value in {"none", "text", "file", "buttons", "branching"} else "none"
                        chain_step.button_options = (
                            str(chain_payload.get("button_options") or "").strip() or None
                            if chain_step.response_type in {"buttons", "branching"}
                            else None
                        )
                        chain_step.launch_scenario_key = None
                        chain_send_mode_value = str(chain_payload.get("send_mode") or "immediate").strip()
                        chain_step.send_mode = chain_send_mode_value if chain_send_mode_value in {"immediate", "specific_time"} else "immediate"
                        chain_step.send_time = (
                            str(chain_payload.get("send_time") or "").strip() or None
                            if chain_step.send_mode == "specific_time"
                            else None
                        )
                        chain_step.day_offset_workdays = 0
                        chain_target_field_value = str(chain_payload.get("target_field") or "").strip()
                        chain_step.target_field = chain_target_field_value if chain_target_field_value in TARGET_FIELD_LABELS else None
                        chain_step.send_employee_card = str(chain_payload.get("send_employee_card") or "false").strip() == "true"
                        chain_step.notify_on_send_text = str(chain_payload.get("notify_on_send_text") or "").strip() or None
                        chain_step.notify_on_send_recipient_ids = str(chain_payload.get("notify_on_send_recipient_ids") or "").strip() or None
                        chain_step.notify_on_send_recipient_scope = _normalize_notification_scope(str(chain_payload.get("notify_on_send_recipient_scope") or ""))
                        chain_row_ref_value = str(chain_payload.get("row_ref") or "").strip()
                        if chain_row_ref_value:
                            chain_step_id_by_ref[chain_row_ref_value] = chain_step.id
                        preserved_chain_ids.add(chain_step.id)
                        chain_upload = request_form.get(f"chain_attachment_{step.id}_{option_idx}_{chain_index}")
                        if chain_upload is not None and getattr(chain_upload, "filename", ""):
                            await _save_step_attachment(chain_step, chain_upload)
                        if chain_step.response_type == "buttons":
                            child_options = [item.strip() for item in (chain_step.button_options or "").splitlines() if item.strip()]
                            preserved_child_option_indexes: set[int] = set()
                            for child_option_idx, _ in enumerate(child_options):
                                payload_by_id = submitted_button_notification_rows.get((chain_step.id, child_option_idx), {})
                                payload_by_ref = submitted_button_notification_rows_by_ref.get((chain_row_ref_value, child_option_idx), {}) if chain_row_ref_value else {}
                                button_payload = payload_by_id or payload_by_ref
                                _sync_button_notification(
                                    db,
                                    chain_step,
                                    child_option_idx,
                                    str(button_payload.get("text") or ""),
                                    str(button_payload.get("recipient_ids") or ""),
                                    str(button_payload.get("recipient_scope") or ""),
                                )
                                preserved_child_option_indexes.add(child_option_idx)
                            for notification in db.query(StepButtonNotification).filter(StepButtonNotification.step_id == chain_step.id).all():
                                if notification.option_index not in preserved_child_option_indexes:
                                    db.delete(notification)
                        else:
                            db.query(StepButtonNotification).filter(StepButtonNotification.step_id == chain_step.id).delete()
                    for existing_id, existing_child in existing_chain_children.items():
                        if existing_id not in preserved_chain_ids:
                            _delete_step_tree(db, existing_child)
                else:
                    db.query(StepButtonNotification).filter(StepButtonNotification.step_id == branch_step.id).delete()
                    for existing_child in existing_chain_children.values():
                        _delete_step_tree(db, existing_child)
            for child in existing_children.values():
                _delete_step_tree(db, child)

        chain_parent_steps = (
            db.query(FlowStepTemplate)
            .filter(
                FlowStepTemplate.flow_key == scenario.scenario_key,
                FlowStepTemplate.parent_step_id.is_not(None),
                FlowStepTemplate.branch_option_index.is_(None),
            )
            .all()
        )
        for chain_parent_step in chain_parent_steps:
            chain_parent_ref_candidates = [f"existing:{chain_parent_step.id}"]
            chain_parent_ref_candidates.extend(
                ref_value for ref_value, mapped_id in chain_step_id_by_ref.items() if mapped_id == chain_parent_step.id
            )
            if chain_parent_step.response_type == "buttons":
                options = [item.strip() for item in (chain_parent_step.button_options or "").splitlines() if item.strip()]
                preserved_option_indexes: set[int] = set()
                for option_idx, _ in enumerate(options):
                    payload = submitted_button_notification_rows.get((chain_parent_step.id, option_idx), {})
                    if not payload:
                        for parent_ref_candidate in chain_parent_ref_candidates:
                            payload = submitted_button_notification_rows_by_ref.get((parent_ref_candidate, option_idx), {})
                            if payload:
                                break
                    _sync_button_notification(
                        db,
                        chain_parent_step,
                        option_idx,
                        str(payload.get("text") or ""),
                        str(payload.get("recipient_ids") or ""),
                        str(payload.get("recipient_scope") or ""),
                    )
                    preserved_option_indexes.add(option_idx)
                for notification in db.query(StepButtonNotification).filter(StepButtonNotification.step_id == chain_parent_step.id).all():
                    if notification.option_index not in preserved_option_indexes:
                        db.delete(notification)
            elif chain_parent_step.response_type != "branching":
                db.query(StepButtonNotification).filter(StepButtonNotification.step_id == chain_parent_step.id).delete()
            existing_children = {
                child.branch_option_index: child
                for child in db.query(FlowStepTemplate)
                .filter(
                    FlowStepTemplate.parent_step_id == chain_parent_step.id,
                    FlowStepTemplate.branch_option_index.is_not(None),
                )
                .all()
            }
            if chain_parent_step.response_type != "branching":
                for child in existing_children.values():
                    _delete_step_tree(db, child)
                continue

            options = [item.strip() for item in (chain_parent_step.button_options or "").splitlines() if item.strip()]
            for option_idx, option_label in enumerate(options):
                payload = submitted_branch_rows.get((chain_parent_step.id, option_idx), {})
                if not payload:
                    for parent_ref_candidate in chain_parent_ref_candidates:
                        payload = submitted_branch_rows_by_ref.get((parent_ref_candidate, option_idx), {})
                        if payload:
                            break
                branch_step = None
                branch_step_id_value = payload.get("branch_step_id")
                if branch_step_id_value is not None:
                    branch_step = db.get(FlowStepTemplate, branch_step_id_value)
                    if branch_step and branch_step.parent_step_id != chain_parent_step.id:
                        branch_step = None
                if branch_step is None:
                    branch_step = existing_children.pop(option_idx, None)
                else:
                    existing_children.pop(option_idx, None)
                if not branch_step:
                    branch_step = FlowStepTemplate(
                        flow_key=scenario.scenario_key,
                        step_key=f"{chain_parent_step.step_key}__branch_{option_idx}",
                        parent_step_id=chain_parent_step.id,
                        branch_option_index=option_idx,
                        step_title=f"Ветка: {option_label}",
                        sort_order=chain_parent_step.sort_order * 100 + option_idx + 1,
                        default_text=f"Сообщение для варианта \"{option_label}\".",
                        custom_text=None,
                        response_type="none",
                        button_options=None,
                        send_mode="immediate",
                        send_time=None,
                        day_offset_workdays=0,
                        target_field=None,
                        launch_scenario_key=None,
                        send_employee_card=False,
                    )
                    db.add(branch_step)
                branch_step.flow_key = scenario.scenario_key
                branch_step.parent_step_id = chain_parent_step.id
                branch_step.branch_option_index = option_idx
                branch_step.sort_order = chain_parent_step.sort_order * 100 + option_idx + 1
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
                        "chain",
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
                branch_attachment_key = f"{chain_parent_step.id}:{option_idx}"
                if branch_attachment_key in removed_branch_attachment_keys:
                    _delete_step_attachment_file(branch_step)
                branch_upload = request_form.get(f"branch_attachment_{chain_parent_step.id}_{option_idx}")
                if branch_upload is not None and getattr(branch_upload, "filename", ""):
                    await _save_step_attachment(branch_step, branch_upload)
                branch_step.send_mode = "immediate"
                branch_step.send_time = None
                branch_step.day_offset_workdays = 0
                branch_step.target_field = None
                branch_step.send_employee_card = str(payload.get("send_employee_card") or "false").strip() == "true"
                branch_step.notify_on_send_text = str(payload.get("notify_on_send_text") or "").strip() or None
                branch_step.notify_on_send_recipient_ids = str(payload.get("notify_on_send_recipient_ids") or "").strip() or None
                branch_step.notify_on_send_recipient_scope = _normalize_notification_scope(str(payload.get("notify_on_send_recipient_scope") or ""))
                _sync_button_notification(
                    db,
                    chain_parent_step,
                    option_idx,
                    str(payload.get("button_notification_text") or ""),
                    str(payload.get("button_notification_recipient_ids") or ""),
                    str(payload.get("button_notification_recipient_scope") or ""),
                )

                db.flush()

                existing_chain_children = {
                    child.id: child
                    for child in db.query(FlowStepTemplate)
                    .filter(
                        FlowStepTemplate.parent_step_id == branch_step.id,
                        FlowStepTemplate.branch_option_index.is_(None),
                    )
                    .all()
                }
                chain_payloads = submitted_chain_rows.get((chain_parent_step.id, option_idx), [])
                if branch_step.response_type == "chain":
                    preserved_chain_ids: set[int] = set()
                    for chain_index, chain_payload in enumerate(chain_payloads):
                        child_chain_step = None
                        child_chain_step_id_value = chain_payload.get("chain_step_id")
                        is_new_chain_step = not isinstance(child_chain_step_id_value, int)
                        if isinstance(child_chain_step_id_value, int):
                            child_chain_step = existing_chain_children.get(child_chain_step_id_value)
                        if child_chain_step is None:
                            child_chain_step = FlowStepTemplate(
                                flow_key=scenario.scenario_key,
                                step_key=f"{branch_step.step_key}__chain_{chain_index}",
                                parent_step_id=branch_step.id,
                                branch_option_index=None,
                                step_title=f"Шаг {chain_index + 1}",
                                sort_order=(chain_index + 1) * 10,
                                default_text="Новое сообщение сценария.",
                                custom_text=None,
                                response_type="none",
                                button_options=None,
                                send_mode="immediate",
                                send_time=None,
                                day_offset_workdays=0,
                                target_field=None,
                                launch_scenario_key=None,
                                send_employee_card=False,
                            )
                            db.add(child_chain_step)
                            db.flush()
                        child_chain_step.flow_key = scenario.scenario_key
                        child_chain_step.parent_step_id = branch_step.id
                        child_chain_step.branch_option_index = None
                        child_chain_step.step_key = f"{branch_step.step_key}__chain_{chain_index}"
                        child_chain_step.sort_order = (chain_index + 1) * 10
                        child_chain_step.step_title = (str(chain_payload.get("title") or "").strip() or f"Шаг {chain_index + 1}")
                        chain_text_value = str(chain_payload.get("custom_text") or "").strip()
                        child_chain_step.custom_text = None if is_new_chain_step and not chain_text_value else chain_text_value
                        chain_response_type_value = str(chain_payload.get("response_type") or "none").strip()
                        child_chain_step.response_type = chain_response_type_value if chain_response_type_value in {"none", "text", "file", "buttons", "branching"} else "none"
                        child_chain_step.button_options = (
                            str(chain_payload.get("button_options") or "").strip() or None
                            if child_chain_step.response_type in {"buttons", "branching"}
                            else None
                        )
                        child_chain_step.launch_scenario_key = None
                        child_chain_send_mode_value = str(chain_payload.get("send_mode") or "immediate").strip()
                        child_chain_step.send_mode = child_chain_send_mode_value if child_chain_send_mode_value in {"immediate", "specific_time"} else "immediate"
                        child_chain_step.send_time = (
                            str(chain_payload.get("send_time") or "").strip() or None
                            if child_chain_step.send_mode == "specific_time"
                            else None
                        )
                        child_chain_step.day_offset_workdays = 0
                        child_chain_target_field_value = str(chain_payload.get("target_field") or "").strip()
                        child_chain_step.target_field = child_chain_target_field_value if child_chain_target_field_value in TARGET_FIELD_LABELS else None
                        child_chain_step.send_employee_card = str(chain_payload.get("send_employee_card") or "false").strip() == "true"
                        child_chain_step.notify_on_send_text = str(chain_payload.get("notify_on_send_text") or "").strip() or None
                        child_chain_step.notify_on_send_recipient_ids = str(chain_payload.get("notify_on_send_recipient_ids") or "").strip() or None
                        child_chain_step.notify_on_send_recipient_scope = _normalize_notification_scope(str(chain_payload.get("notify_on_send_recipient_scope") or ""))
                        child_chain_row_ref_value = str(chain_payload.get("row_ref") or "").strip()
                        if child_chain_row_ref_value:
                            chain_step_id_by_ref[child_chain_row_ref_value] = child_chain_step.id
                        preserved_chain_ids.add(child_chain_step.id)
                        chain_upload = request_form.get(f"chain_attachment_{chain_parent_step.id}_{option_idx}_{chain_index}")
                        if chain_upload is not None and getattr(chain_upload, "filename", ""):
                            await _save_step_attachment(child_chain_step, chain_upload)
                        if child_chain_step.response_type == "buttons":
                            child_options = [item.strip() for item in (child_chain_step.button_options or "").splitlines() if item.strip()]
                            preserved_child_option_indexes: set[int] = set()
                            for child_option_idx, _ in enumerate(child_options):
                                payload_by_id = submitted_button_notification_rows.get((child_chain_step.id, child_option_idx), {})
                                payload_by_ref = submitted_button_notification_rows_by_ref.get((child_chain_row_ref_value, child_option_idx), {}) if child_chain_row_ref_value else {}
                                button_payload = payload_by_id or payload_by_ref
                                _sync_button_notification(
                                    db,
                                    child_chain_step,
                                    child_option_idx,
                                    str(button_payload.get("text") or ""),
                                    str(button_payload.get("recipient_ids") or ""),
                                    str(button_payload.get("recipient_scope") or ""),
                                )
                                preserved_child_option_indexes.add(child_option_idx)
                            for notification in db.query(StepButtonNotification).filter(StepButtonNotification.step_id == child_chain_step.id).all():
                                if notification.option_index not in preserved_child_option_indexes:
                                    db.delete(notification)
                        else:
                            db.query(StepButtonNotification).filter(StepButtonNotification.step_id == child_chain_step.id).delete()
                    for existing_id, existing_child in existing_chain_children.items():
                        if existing_id not in preserved_chain_ids:
                            _delete_step_tree(db, existing_child)
                else:
                    db.query(StepButtonNotification).filter(StepButtonNotification.step_id == branch_step.id).delete()
                    for existing_child in existing_chain_children.values():
                        _delete_step_tree(db, existing_child)
            for child in existing_children.values():
                _delete_step_tree(db, child)
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
    _delete_template_entity(db, scenario)
    db.commit()
    return RedirectResponse(url=collection_path, status_code=status.HTTP_303_SEE_OTHER)


@app.post("/flows/{scenario_id}/copy")
@app.post("/surveys/{scenario_id}/copy")
def copy_scenario(
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
    scenario_copy = _copy_template_entity(db, scenario)
    collection_path = _template_entity_meta(getattr(scenario, "scenario_kind", "scenario"))["collection_path"]
    return RedirectResponse(url=f"{collection_path}/{scenario_copy.id}", status_code=status.HTTP_303_SEE_OTHER)


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


@app.post("/settings/menu-sets/{menu_set_id}/buttons/save")
async def update_menu_set_buttons(
    request: Request,
    menu_set_id: int,
    db: Session = Depends(get_db),
):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    menu_set = db.get(BotMenuSet, menu_set_id)
    if not menu_set:
        return RedirectResponse(url="/settings", status_code=status.HTTP_303_SEE_OTHER)

    request_form = await request.form()

    def form_list(name: str) -> list[str]:
        return [str(value) for value in request_form.getlist(name)]

    button_ids = form_list("button_id")
    labels = form_list("label")
    action_types = form_list("action_type")
    scenario_keys = form_list("scenario_key")
    target_menu_set_ids = form_list("target_menu_set_id")

    for index, button_id_raw in enumerate(button_ids):
        if not button_id_raw.strip().isdigit():
            continue
        button = db.get(BotMenuButton, int(button_id_raw))
        if not button or button.menu_set_id != menu_set_id:
            continue
        normalized_action = (
            action_types[index]
            if index < len(action_types) and action_types[index] in {"inactive", "launch_scenario", "open_set"}
            else "inactive"
        )
        button.label = (labels[index].strip() if index < len(labels) else "") or button.label
        button.action_type = normalized_action
        button.scenario_key = (
            (scenario_keys[index].strip() if index < len(scenario_keys) else "") or None
        ) if normalized_action == "launch_scenario" else None
        target_set_value = target_menu_set_ids[index].strip() if index < len(target_menu_set_ids) else ""
        button.target_menu_set_id = (
            int(target_set_value)
            if normalized_action == "open_set" and target_set_value.isdigit()
            else None
        )

    db.commit()
    return RedirectResponse(url="/settings", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/settings/menu-buttons/save-all")
async def update_all_menu_buttons(
    request: Request,
    db: Session = Depends(get_db),
):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect

    request_form = await request.form()

    def form_list(name: str) -> list[str]:
        return [str(value) for value in request_form.getlist(name)]

    button_ids = form_list("button_id")
    labels = form_list("label")
    action_types = form_list("action_type")
    scenario_keys = form_list("scenario_key")
    target_menu_set_ids = form_list("target_menu_set_id")

    for index, button_id_raw in enumerate(button_ids):
        if not button_id_raw.strip().isdigit():
            continue
        button = db.get(BotMenuButton, int(button_id_raw))
        if not button:
            continue
        normalized_action = (
            action_types[index]
            if index < len(action_types) and action_types[index] in {"inactive", "launch_scenario", "open_set"}
            else "inactive"
        )
        button.label = (labels[index].strip() if index < len(labels) else "") or button.label
        button.action_type = normalized_action
        button.scenario_key = (
            (scenario_keys[index].strip() if index < len(scenario_keys) else "") or None
        ) if normalized_action == "launch_scenario" else None
        target_set_value = target_menu_set_ids[index].strip() if index < len(target_menu_set_ids) else ""
        button.target_menu_set_id = (
            int(target_set_value)
            if normalized_action == "open_set" and target_set_value.isdigit()
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
