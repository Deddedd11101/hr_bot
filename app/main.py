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
from sqlalchemy import or_, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .auth import ROLE_LABELS, authenticate_account, hash_password
from .config import settings
from .database import get_session, init_db
from .flow_templates import (
    EMPLOYEE_ROLE_VALUES,
    NOTIFICATION_RECIPIENT_SCOPE_LABELS,
    RESPONSE_TYPE_LABELS,
    ROLE_SCOPE_LABELS,
    SEND_MODE_LABELS,
    TARGET_FIELD_LABELS,
    TRIGGER_MODE_LABELS,
)
from .employee_card import render_employee_card_png
from .file_storage import (
    build_employee_file_path,
    build_employee_profile_photo_path,
    build_step_attachment_path,
)
from .messaging import create_telegram_messenger
from .messaging.identity import (
    get_primary_chat_id,
    get_public_chat_handle,
    set_primary_chat_id,
    set_public_chat_handle,
    sync_legacy_telegram_account,
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
from .scenario_engine import format_message, get_first_step, get_scenario_steps, start_scenario


AUTH_COOKIE_NAME = "hr_admin_auth"
OFFER_DOCUMENT_TITLE = "Оффер"

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


def _require_api_auth(request: Request) -> AdminAccount:
    current_user = getattr(request.state, "current_user", None)
    if current_user:
        return current_user
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Требуется авторизация")


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
    if getattr(scenario, "target_employee_id", None) and scenario.target_employee_id != employee.id:
        return False
    if scenario.role_scope == "all":
        return True
    role_map = {
        "designer": "Дизайнер",
        "project_manager": "Project manager",
        "analyst": "Аналитик",
    }
    return (employee.desired_position or "") == role_map.get(scenario.role_scope, "")


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
):
    scenarios = (
        db.query(ScenarioTemplate)
        .filter(ScenarioTemplate.scenario_kind == "scenario")
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
                "trigger_mode_label": TRIGGER_MODE_LABELS.get(scenario.trigger_mode, scenario.trigger_mode),
                "steps_count": steps_count,
                "classic_url": f"/flows/{scenario.id}",
                "workspace_url": f"/app/flows/workspace-v2?scenario_id={scenario.id}",
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
                "role_scope_label": ROLE_SCOPE_LABELS.get(selected_scenario.role_scope, selected_scenario.role_scope),
                "trigger_mode_label": TRIGGER_MODE_LABELS.get(selected_scenario.trigger_mode, selected_scenario.trigger_mode),
                "classic_url": f"/flows/{selected_scenario.id}",
            },
            "root_steps": root_steps,
            "stats": {
                "steps_count": len(root_steps),
            },
            "response_type_labels": _workspace_response_type_labels(),
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

MASS_TARGET_NONE = "__none__"
MASS_TARGET_OPTIONS = [
    (MASS_TARGET_NONE, "Не указан"),
    ("candidate", "Кандидат"),
    ("adaptation", "Адаптация"),
    ("ipr", "ИПР"),
    ("staff", "В штате"),
]


def _employee_edit_redirect(employee_id: int, flash_message: Optional[str] = None, flash_type: str = "success") -> RedirectResponse:
    url = f"/employees/{employee_id}/edit"
    if flash_message:
        from urllib.parse import urlencode

        url = f"{url}?{urlencode({'flash_message': flash_message, 'flash_type': flash_type})}"
    return RedirectResponse(url=url, status_code=status.HTTP_303_SEE_OTHER)


def _delete_employee_profile_photo(employee: Employee) -> None:
    profile_photo_path = (getattr(employee, "profile_photo_path", None) or "").strip()
    if profile_photo_path:
        path = Path(profile_photo_path)
        try:
            if path.exists():
                path.unlink()
        except OSError:
            pass
    employee.profile_photo_path = None
    employee.profile_photo_filename = None


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


def _recipient_scope_label(
    db: Session,
    target_all: bool,
    target_statuses: Optional[str],
    target_employee_id: Optional[int] = None,
    target_role_scope: Optional[str] = None,
) -> str:
    if target_employee_id:
        employee = db.get(Employee, target_employee_id)
        if employee:
            return _employee_display_name(employee)
        return f"Сотрудник #{target_employee_id}"
    if (target_role_scope or "").strip() == "all":
        return "Все"
    if (target_role_scope or "").strip() and target_role_scope in ROLE_SCOPE_LABELS:
        return ROLE_SCOPE_LABELS[target_role_scope]
    if target_all:
        return "Все"
    labels = dict(MASS_TARGET_OPTIONS)
    values = _deserialize_mass_target_statuses(target_statuses)
    if not values:
        return "Не выбраны"
    return ", ".join(labels.get(value, value) for value in values)


def _mass_target_employee_query(
    db: Session,
    target_all: bool,
    target_statuses: list[str],
    target_employee_id: Optional[int] = None,
    target_role_scope: Optional[str] = None,
):
    query = db.query(Employee)
    if target_employee_id:
        return query.filter(Employee.id == target_employee_id)
    if (target_role_scope or "").strip() and target_role_scope != "all" and target_role_scope in ROLE_SCOPE_LABELS:
        return query.filter(Employee.desired_position == {
            "designer": "Дизайнер",
            "project_manager": "Project manager",
            "analyst": "Аналитик",
        }.get(target_role_scope, ""))
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


def _mass_target_employees(
    db: Session,
    target_all: bool,
    target_statuses: list[str],
    target_employee_id: Optional[int] = None,
    target_role_scope: Optional[str] = None,
) -> list[Employee]:
    return (
        _mass_target_employee_query(db, target_all, target_statuses, target_employee_id, target_role_scope)
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
    employee_views = _build_employee_views(list_kind, db)
    page_meta = _employee_list_meta(list_kind)
    return _render(
        request,
        "index.html",
        {
            "employee_views": employee_views,
            **page_meta,
        },
    )


def _build_employee_views(list_kind: str, db: Session) -> list[dict]:
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
        created_at=datetime.utcnow(),
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
            requested_at=datetime.utcnow(),
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
    manager_chat_id: str,
    mentor_adaptation_chat_id: str,
    mentor_ipr_chat_id: str,
    employee_stage: str,
    candidate_work_stage: str,
    salary_expectation: str,
    personal_data_consent: bool,
    employee_data_consent: bool,
    test_task_due_at: str,
    notes: str,
) -> Employee:
    is_candidate = _employee_list_kind(employee) == "candidates"
    first_day = datetime.strptime(first_workday, "%Y-%m-%d").date() if first_workday else None
    parsed_birth_date = datetime.strptime(birth_date, "%Y-%m-%d").date() if birth_date else None

    employee.full_name = full_name.strip() or None
    _apply_employee_telegram_identity(employee, chat_id=chat_id, chat_handle=chat_handle, db=db)
    employee.first_workday = first_day
    normalized_position = desired_position.strip()
    employee.desired_position = normalized_position or None

    if is_candidate:
        normalized_candidate_work_stage = candidate_work_stage.strip()
        employee.candidate_work_stage = (
            normalized_candidate_work_stage
            if normalized_candidate_work_stage in CANDIDATE_WORK_STAGE_VALUES
            else None
        )
        employee.salary_expectation = salary_expectation.strip() or None
        employee.personal_data_consent = personal_data_consent
        employee.test_task_due_at = (
            datetime.strptime(test_task_due_at, "%Y-%m-%dT%H:%M")
            if (test_task_due_at or "").strip()
            else None
        )
    else:
        employee.birth_date = parsed_birth_date
        employee.work_email = work_email.strip() or None
        employee.work_hours = work_hours.strip() or None
        employee.manager_telegram_id = manager_chat_id.strip() or None
        employee.mentor_adaptation_telegram_id = mentor_adaptation_chat_id.strip() or None
        employee.mentor_ipr_telegram_id = mentor_ipr_chat_id.strip() or None
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


def _serialize_launch_request(launch_request: FlowLaunchRequest, scenario_by_key: dict[str, ScenarioTemplate], employee_id: int) -> dict:
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
            created_at=datetime.utcnow(),
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

    employee_document_links = (
        db.query(EmployeeDocumentLink)
        .filter(EmployeeDocumentLink.employee_id == employee_id)
        .all()
    )
    for link_row in employee_document_links:
        db.delete(link_row)

    employee_dir = Path(settings.FILE_STORAGE_DIR).expanduser().resolve() / str(employee_id)
    if employee_dir.exists():
        shutil.rmtree(employee_dir, ignore_errors=True)

    db.delete(employee)
    db.commit()
    return redirect_url


def _schedule_employee_flow_request(
    db: Session,
    employee: Employee,
    *,
    flow_key: str,
    requested_at: str,
) -> Optional[str]:
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


@app.get("/api/employees")
def employees_api(
    request: Request,
    list_kind: str = "employees",
    db: Session = Depends(get_db),
):
    _require_api_auth(request)
    normalized_kind = "candidates" if list_kind == "candidates" else "employees"
    employee_views = _build_employee_views(normalized_kind, db)
    return {
        "meta": {
            **_employee_list_meta(normalized_kind),
            "list_kind": normalized_kind,
            "classic_page_url": "/candidates" if normalized_kind == "candidates" else "/employees",
        },
        "items": [_serialize_employee_view(item, normalized_kind) for item in employee_views],
    }


@app.post("/api/employees")
def create_employee_api(
    request: Request,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    _require_api_auth(request)
    list_kind = "candidates" if (payload.get("list_kind") or "").strip() == "candidates" else "employees"
    employee = _create_employee_record(
        db,
        full_name=str(payload.get("full_name") or ""),
        chat_id=str(payload.get("chat_id") or ""),
        chat_handle=str(payload.get("chat_handle") or ""),
        first_workday=str(payload.get("first_workday") or ""),
        employee_stage=str(payload.get("employee_stage") or ""),
        candidate_work_stage=str(payload.get("candidate_work_stage") or ""),
        list_kind=list_kind,
    )
    views = _build_employee_views(list_kind, db)
    item = next((row for row in views if row["employee"].id == employee.id), None)
    return {
        "meta": {
            **_employee_list_meta(list_kind),
            "list_kind": list_kind,
            "classic_page_url": "/candidates" if list_kind == "candidates" else "/employees",
        },
        "item": _serialize_employee_view(item, list_kind) if item else None,
    }


@app.get("/api/employees/{employee_id}")
def employee_detail_api(
    request: Request,
    employee_id: int,
    db: Session = Depends(get_db),
):
    _require_api_auth(request)
    employee = db.get(Employee, employee_id)
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сотрудник не найден")
    return _build_employee_detail_payload(db, employee)


@app.post("/api/employees/{employee_id}")
def update_employee_api(
    request: Request,
    employee_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    _require_api_auth(request)
    employee = db.get(Employee, employee_id)
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сотрудник не найден")
    employee = _apply_employee_update(
        db,
        employee,
        full_name=str(payload.get("full_name") or ""),
        chat_id=str(payload.get("chat_id") or ""),
        chat_handle=str(payload.get("chat_handle") or ""),
        first_workday=str(payload.get("first_workday") or ""),
        desired_position=str(payload.get("desired_position") or ""),
        birth_date=str(payload.get("birth_date") or ""),
        work_email=str(payload.get("work_email") or ""),
        work_hours=str(payload.get("work_hours") or ""),
        manager_chat_id=str(payload.get("manager_chat_id") or ""),
        mentor_adaptation_chat_id=str(payload.get("mentor_adaptation_chat_id") or ""),
        mentor_ipr_chat_id=str(payload.get("mentor_ipr_chat_id") or ""),
        employee_stage=str(payload.get("employee_stage") or ""),
        candidate_work_stage=str(payload.get("candidate_work_stage") or ""),
        salary_expectation=str(payload.get("salary_expectation") or ""),
        personal_data_consent=bool(payload.get("personal_data_consent")),
        employee_data_consent=bool(payload.get("employee_data_consent")),
        test_task_due_at=str(payload.get("test_task_due_at") or ""),
        notes=str(payload.get("notes") or ""),
    )
    return _build_employee_detail_payload(db, employee)


@app.post("/api/employees/{employee_id}/document-links")
def create_employee_document_link_api(
    request: Request,
    employee_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    _require_api_auth(request)
    employee = db.get(Employee, employee_id)
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сотрудник не найден")
    link_row, error_message = _save_offer_document_link(db, employee_id, str(payload.get("url") or ""))
    if error_message:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_message)
    return {
        "item": _serialize_document_link(link_row, employee_id),
        "payload": _build_employee_detail_payload(db, employee),
    }


@app.delete("/api/employees/{employee_id}/document-links/{link_id}")
def delete_employee_document_link_api(
    request: Request,
    employee_id: int,
    link_id: int,
    db: Session = Depends(get_db),
):
    _require_api_auth(request)
    employee = db.get(Employee, employee_id)
    link_row = db.get(EmployeeDocumentLink, link_id)
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сотрудник не найден")
    if not link_row or link_row.employee_id != employee_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ссылка на документ не найдена")
    db.delete(link_row)
    db.commit()
    return _build_employee_detail_payload(db, employee)


@app.post("/api/employees/{employee_id}/schedule")
def schedule_employee_flow_api(
    request: Request,
    employee_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    _require_api_auth(request)
    employee = db.get(Employee, employee_id)
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сотрудник не найден")
    error_message = _schedule_employee_flow_request(
        db,
        employee,
        flow_key=str(payload.get("flow_key") or ""),
        requested_at=str(payload.get("requested_at") or ""),
    )
    if error_message:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_message)
    return _build_employee_detail_payload(db, employee)


@app.delete("/api/employees/{employee_id}/schedule/{launch_request_id}")
def delete_scheduled_flow_api(
    request: Request,
    employee_id: int,
    launch_request_id: int,
    db: Session = Depends(get_db),
):
    _require_api_auth(request)
    employee = db.get(Employee, employee_id)
    launch_request = db.get(FlowLaunchRequest, launch_request_id)
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сотрудник не найден")
    if (
        not launch_request
        or launch_request.employee_id != employee_id
        or launch_request.launch_type != "scheduled"
        or launch_request.processed_at is not None
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Запланированный сценарий не найден")
    db.delete(launch_request)
    db.commit()
    return _build_employee_detail_payload(db, employee)


@app.post("/api/employees/{employee_id}/launch")
async def launch_flow_api(
    request: Request,
    employee_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    _require_api_auth(request)
    employee = db.get(Employee, employee_id)
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сотрудник не найден")
    error_message = await _launch_employee_flow_now(
        db,
        employee,
        flow_key=str(payload.get("flow_key") or ""),
    )
    if error_message:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_message)
    return _build_employee_detail_payload(db, employee)


@app.post("/api/employees/{employee_id}/files")
async def upload_employee_file_api(
    request: Request,
    employee_id: int,
    upload: UploadFile = File(...),
    category: str = Form("hr_file"),
    send_to_channel: str = Form("false"),
    db: Session = Depends(get_db),
):
    _require_api_auth(request)
    employee = db.get(Employee, employee_id)
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сотрудник не найден")

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

    chat_id = get_primary_chat_id(employee, db=db)
    if send_to_channel == "true" and chat_id and settings.TELEGRAM_BOT_TOKEN:
        await _send_file_to_telegram(chat_id, destination, filename)

    return _build_employee_detail_payload(db, employee)


@app.post("/api/employees/{employee_id}/files/{file_id}/send")
async def send_employee_file_api(
    request: Request,
    employee_id: int,
    file_id: int,
    db: Session = Depends(get_db),
):
    _require_api_auth(request)
    employee = db.get(Employee, employee_id)
    db_file = db.get(EmployeeFile, file_id)
    if not employee or not db_file or db_file.employee_id != employee_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Файл не найден")
    chat_id = get_primary_chat_id(employee, db=db)
    if not chat_id or not settings.TELEGRAM_BOT_TOKEN:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="У сотрудника не настроен канал для отправки")

    path = Path(db_file.stored_path)
    if path.exists():
        await _send_file_to_telegram(chat_id, path, db_file.original_filename)
    return _build_employee_detail_payload(db, employee)


@app.delete("/api/employees/{employee_id}")
def delete_employee_api(
    request: Request,
    employee_id: int,
    db: Session = Depends(get_db),
):
    _require_api_auth(request)
    employee = db.get(Employee, employee_id)
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сотрудник не найден")
    redirect_url = _delete_employee_record(db, employee)
    return {"redirect_url": redirect_url}


@app.get("/app/employees")
def react_employees_page(
    request: Request,
    list_kind: str = "employees",
):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    normalized_kind = "candidates" if list_kind == "candidates" else "employees"
    return _render(
        request,
        "react_employees.html",
        {
            "active_tab": normalized_kind,
            "react_page_title": "Список сотрудников 2.0",
            "react_api_url": f"/api/employees?list_kind={normalized_kind}",
            "react_create_url": "/api/employees",
            "react_default_list_kind": normalized_kind,
            "classic_page_url": "/candidates" if normalized_kind == "candidates" else "/employees",
        },
    )


@app.get("/app/employees/{employee_id}")
def react_employee_edit_page(
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
    list_kind = _employee_list_kind(employee)
    return _render(
        request,
        "react_employee_edit.html",
        {
            "active_tab": list_kind,
            "employee_id": employee_id,
            "react_api_url": f"/api/employees/{employee_id}",
            "react_save_url": f"/api/employees/{employee_id}",
            "classic_page_url": f"/employees/{employee_id}/edit",
            "list_url": "/candidates" if list_kind == "candidates" else "/employees",
        },
    )


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
    document_tag_titles = [OFFER_DOCUMENT_TITLE]
    employee_options = _all_employee_options(db)
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
            "role_scope_labels": ROLE_SCOPE_LABELS,
            "scheduled_scenario_actions": scheduled_scenario_actions,
            "manual_scenario_history": manual_scenario_history,
            "scheduled_survey_actions": scheduled_survey_actions,
            "manual_survey_history": manual_survey_history,
            "scheduled_message_actions": scheduled_message_actions,
            "manual_message_history": manual_message_history,
            "employee_options": employee_options,
            "document_tag_titles": document_tag_titles,
            "recipient_scope_label": lambda target_all, target_statuses, target_employee_id=None, target_role_scope=None: _recipient_scope_label(
                db, target_all, target_statuses, target_employee_id, target_role_scope
            ),
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
    return _render(
        request,
        "employee_edit.html",
        {
            "active_tab": list_kind,
            "is_candidate": is_candidate,
            "employee": employee,
            "employee_files": employee_files,
            "employee_document_links": employee_document_links,
            "status": _employee_status_label(employee),
            "candidate_work_stage_label": _candidate_work_stage_label(employee),
            "tenure_years": _full_years_between(employee.first_workday, today),
            "employee_role_values": employee_role_values,
            "employee_stage_values": EMPLOYEE_STAGE_VALUES,
            "candidate_work_stage_values": CANDIDATE_WORK_STAGE_VALUES,
            "scenarios": scenarios,
            "scheduled_launches": pending_scheduled_launches,
            "manual_launch_history": manual_launch_history,
            "scenario_by_key": scenario_by_key,
            "flash_message": request.query_params.get("flash_message"),
            "flash_type": request.query_params.get("flash_type", "success"),
            "list_url": "/candidates" if list_kind == "candidates" else "/employees",
            "list_title": "к списку кандидатов" if list_kind == "candidates" else "к списку сотрудников",
            "employee_card_image_url": f"/employees/{employee.id}/card-image",
        },
    )


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
            "list_url": "/candidates" if is_candidate else "/employees",
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
            "manager_chat_id": employee.manager_telegram_id or "",
            "mentor_adaptation_chat_id": employee.mentor_adaptation_telegram_id or "",
            "mentor_ipr_chat_id": employee.mentor_ipr_telegram_id or "",
            "employee_stage": employee.employee_stage or "",
            "candidate_work_stage": employee.candidate_work_stage or "",
            "salary_expectation": employee.salary_expectation or "",
            "personal_data_consent": bool(employee.personal_data_consent),
            "employee_data_consent": bool(employee.employee_data_consent),
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
            "scenarios": [
                {"value": scenario.scenario_key, "label": scenario.title}
                for scenario in scenarios
            ],
        },
        "files": [
            _serialize_employee_file(file_row, employee.id, bool(primary_chat_id))
            for file_row in employee_files
        ],
        "document_links": [
            _serialize_document_link(link_row, employee.id)
            for link_row in employee_document_links
        ],
        "scheduled_launches": [
            _serialize_launch_request(launch_request, scenario_by_key, employee.id)
            for launch_request in pending_scheduled_launches
        ],
        "manual_launch_history": [
            _serialize_launch_request(launch_request, scenario_by_key, employee.id)
            for launch_request in manual_launch_history
        ],
    }


@app.post("/employees/{employee_id}")
def update_employee(
    request: Request,
    employee_id: int,
    full_name: str = Form(""),
    telegram_user_id: str = Form(""),
    telegram_username: str = Form(""),
    first_workday: str = Form(""),
    desired_position: str = Form(""),
    birth_date: str = Form(""),
    work_email: str = Form(""),
    work_hours: str = Form(""),
    manager_telegram_id: str = Form(""),
    mentor_adaptation_telegram_id: str = Form(""),
    mentor_ipr_telegram_id: str = Form(""),
    employee_stage: str = Form(""),
    candidate_work_stage: str = Form(""),
    salary_expectation: str = Form(""),
    personal_data_consent: str = Form("false"),
    employee_data_consent: str = Form("false"),
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
    employee = _apply_employee_update(
        db,
        employee,
        full_name=full_name,
        chat_id=telegram_user_id,
        chat_handle=telegram_username,
        first_workday=first_workday,
        desired_position=desired_position,
        birth_date=birth_date,
        work_email=work_email,
        work_hours=work_hours,
        manager_chat_id=manager_telegram_id,
        mentor_adaptation_chat_id=mentor_adaptation_telegram_id,
        mentor_ipr_chat_id=mentor_ipr_telegram_id,
        employee_stage=employee_stage,
        candidate_work_stage=candidate_work_stage,
        salary_expectation=salary_expectation,
        personal_data_consent=personal_data_consent == "true",
        employee_data_consent=employee_data_consent == "true",
        test_task_due_at=test_task_due_at,
        notes=notes,
    )
    return RedirectResponse(
        url="/candidates" if _employee_list_kind(employee) == "candidates" else "/employees",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@app.post("/employees/{employee_id}/profile-photo")
async def upload_employee_profile_photo(
    request: Request,
    employee_id: int,
    upload: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    employee = db.get(Employee, employee_id)
    if not employee:
        return RedirectResponse(url="/employees", status_code=status.HTTP_303_SEE_OTHER)
    filename = (upload.filename or "").strip()
    if not filename:
        return _employee_edit_redirect(employee_id, "Выберите файл фотографии.", "error")
    destination = build_employee_profile_photo_path(employee_id, filename)
    content = await upload.read()
    destination.write_bytes(content)
    _delete_employee_profile_photo(employee)
    employee.profile_photo_path = str(destination)
    employee.profile_photo_filename = filename
    db.commit()
    return _employee_edit_redirect(employee_id, "Фотография сотрудника сохранена.", "success")


@app.post("/employees/{employee_id}/profile-photo/delete")
def delete_employee_profile_photo(
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
    _delete_employee_profile_photo(employee)
    db.commit()
    return _employee_edit_redirect(employee_id, "Фотография сотрудника удалена.", "success")


@app.get("/employees/{employee_id}/card-image")
def employee_card_image(
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
    try:
        image_bytes = render_employee_card_png(employee)
    except ImportError:
        return RedirectResponse(url=f"/employees/{employee_id}/edit", status_code=status.HTTP_303_SEE_OTHER)
    return StreamingResponse(BytesIO(image_bytes), media_type="image/png")


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
        redirect_url = _delete_employee_record(db, employee)
        return RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)
    return RedirectResponse(url="/employees", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/employees")
def create_employee(
    request: Request,
    full_name: str = Form(""),
    telegram_user_id: str = Form(""),
    telegram_username: str = Form(""),
    first_workday: str = Form(""),
    employee_stage: str = Form(""),
    candidate_work_stage: str = Form(""),
    db: Session = Depends(get_db),
):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    list_kind = "candidates" if (employee_stage or "").strip() == "candidate" else "employees"
    employee = _create_employee_record(
        db,
        full_name=full_name,
        chat_id=telegram_user_id,
        chat_handle=telegram_username,
        first_workday=first_workday,
        employee_stage=employee_stage,
        candidate_work_stage=candidate_work_stage,
        list_kind=list_kind,
    )

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
    error_message = await _launch_employee_flow_now(db, employee, flow_key=flow_key)
    if error_message:
        return _employee_edit_redirect(employee_id, error_message, "error")
    return _employee_edit_redirect(employee_id, "Сценарий успешно запущен.", "success")


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
    error_message = _schedule_employee_flow_request(
        db,
        employee,
        flow_key=flow_key,
        requested_at=requested_at,
    )
    if error_message:
        return _employee_edit_redirect(employee_id, error_message, "error")
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


async def _send_mass_message(db: Session, messenger, employee: Employee, message_text: str) -> bool:
    chat_id = get_primary_chat_id(employee, db=db)
    if not chat_id:
        return False
    rendered_text = format_message(
        db,
        message_text,
        employee,
        datetime.now().date(),
        datetime.now().strftime("%H:%M"),
    ).strip()
    if not rendered_text:
        return False
    await messenger.send_text(chat_id=chat_id, text=rendered_text)
    return True


async def _parse_mass_action_targets(request: Request) -> tuple[bool, list[str], Optional[int], Optional[str]]:
    form = await request.form()
    target_all = form.get("target_all") == "true"
    target_statuses = _normalize_mass_target_statuses(form.getlist("target_statuses"))
    target_employee_id_value = str(form.get("target_employee_id", "") or "").strip()
    target_employee_id = int(target_employee_id_value) if target_employee_id_value.isdigit() else None
    target_role_scope = str(form.get("target_role_scope", "") or "").strip()
    if target_role_scope not in ROLE_SCOPE_LABELS:
        target_role_scope = ""
    return target_all, target_statuses, target_employee_id, (target_role_scope or None)


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
    target_all, target_statuses, target_employee_id, target_role_scope = await _parse_mass_action_targets(request)
    recipients = _mass_target_employees(db, target_all, target_statuses, target_employee_id, target_role_scope)
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
            target_role_scope=target_role_scope,
            target_employee_id=target_employee_id,
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
    target_all, target_statuses, target_employee_id, target_role_scope = await _parse_mass_action_targets(request)
    recipients = _mass_target_employees(db, target_all, target_statuses, target_employee_id, target_role_scope)
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
            target_role_scope=target_role_scope,
            target_employee_id=target_employee_id,
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
    target_all, target_statuses, target_employee_id, target_role_scope = await _parse_mass_action_targets(request)
    recipients = _mass_target_employees(db, target_all, target_statuses, target_employee_id, target_role_scope)
    if not recipients:
        return _mass_actions_redirect("Не найдено ни одного получателя для выбранных статусов.", "error")
    if not settings.TELEGRAM_BOT_TOKEN:
        return _mass_actions_redirect("Не задан TELEGRAM_BOT_TOKEN.", "error")

    messenger = create_telegram_messenger(settings.TELEGRAM_BOT_TOKEN)
    started_count = 0
    try:
        for employee in recipients:
            if not employee.telegram_user_id:
                continue
            if not _scenario_matches_employee_role(scenario, employee):
                continue
            started = await start_scenario(messenger, db, employee, scenario.scenario_key)
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
                target_role_scope=target_role_scope,
                target_employee_id=target_employee_id,
                recipient_count=started_count,
                created_at=datetime.utcnow(),
            )
        )
        db.commit()
    finally:
        await messenger.close()

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
    target_all, target_statuses, target_employee_id, target_role_scope = await _parse_mass_action_targets(request)
    recipients = _mass_target_employees(db, target_all, target_statuses, target_employee_id, target_role_scope)
    if not recipients:
        return _mass_actions_redirect("Не найдено ни одного получателя для выбранных статусов.", "error")
    if not settings.TELEGRAM_BOT_TOKEN:
        return _mass_actions_redirect("Не задан TELEGRAM_BOT_TOKEN.", "error")

    messenger = create_telegram_messenger(settings.TELEGRAM_BOT_TOKEN)
    started_count = 0
    try:
        for employee in recipients:
            if not employee.telegram_user_id:
                continue
            if not _scenario_matches_employee_role(scenario, employee):
                continue
            started = await start_scenario(messenger, db, employee, scenario.scenario_key)
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
                target_role_scope=target_role_scope,
                target_employee_id=target_employee_id,
                recipient_count=started_count,
                created_at=datetime.utcnow(),
            )
        )
        db.commit()
    finally:
        await messenger.close()

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
    target_all, target_statuses, target_employee_id, target_role_scope = await _parse_mass_action_targets(request)
    recipients = _mass_target_employees(db, target_all, target_statuses, target_employee_id, target_role_scope)
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
            target_role_scope=target_role_scope,
            target_employee_id=target_employee_id,
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
    target_all, target_statuses, target_employee_id, target_role_scope = await _parse_mass_action_targets(request)
    recipients = _mass_target_employees(db, target_all, target_statuses, target_employee_id, target_role_scope)
    if not recipients:
        return _mass_actions_redirect("Не найдено ни одного получателя для выбранных статусов.", "error")
    if not settings.TELEGRAM_BOT_TOKEN:
        return _mass_actions_redirect("Не задан TELEGRAM_BOT_TOKEN.", "error")

    messenger = create_telegram_messenger(settings.TELEGRAM_BOT_TOKEN)
    sent_count = 0
    try:
        for employee in recipients:
            if await _send_mass_message(db, messenger, employee, message_text):
                sent_count += 1
        db.add(
            MassMessageAction(
                message_text=message_text,
                requested_at=datetime.utcnow(),
                processed_at=datetime.utcnow(),
                launch_type="manual",
                target_all=target_all,
                target_statuses=_serialize_mass_target_statuses(target_statuses),
                target_role_scope=target_role_scope,
                target_employee_id=target_employee_id,
                recipient_count=sent_count,
                created_at=datetime.utcnow(),
            )
        )
        db.commit()
    finally:
        await messenger.close()

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

    chat_id = get_primary_chat_id(employee, db=db)
    if send_to_telegram == "true" and chat_id and settings.TELEGRAM_BOT_TOKEN:
        await _send_file_to_telegram(chat_id, destination, filename)

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
    chat_id = get_primary_chat_id(employee, db=db)
    if not chat_id or not settings.TELEGRAM_BOT_TOKEN:
        return RedirectResponse(url=f"/employees/{employee_id}/edit", status_code=status.HTTP_303_SEE_OTHER)

    path = Path(db_file.stored_path)
    if path.exists():
        await _send_file_to_telegram(chat_id, path, db_file.original_filename)
    return RedirectResponse(url=f"/employees/{employee_id}/edit", status_code=status.HTTP_303_SEE_OTHER)


async def _send_file_to_telegram(chat_id: str, path: Path, filename: str) -> None:
    messenger = create_telegram_messenger(settings.TELEGRAM_BOT_TOKEN, parse_mode=None)
    try:
        await messenger.send_document_path(chat_id=chat_id, path=path, filename=filename)
    finally:
        await messenger.close()


@app.post("/employees/{employee_id}/document-links")
def create_employee_document_link(
    request: Request,
    employee_id: int,
    url: str = Form(""),
    db: Session = Depends(get_db),
):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    employee = db.get(Employee, employee_id)
    if not employee:
        return RedirectResponse(url="/employees", status_code=status.HTTP_303_SEE_OTHER)
    _, error_message = _save_offer_document_link(db, employee_id, url)
    if error_message:
        return _employee_edit_redirect(employee_id, error_message, "error")
    return _employee_edit_redirect(employee_id, "Ссылка на оффер сохранена.", "success")


@app.post("/employees/{employee_id}/document-links/{link_id}/delete")
def delete_employee_document_link(
    request: Request,
    employee_id: int,
    link_id: int,
    db: Session = Depends(get_db),
):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    link_row = db.get(EmployeeDocumentLink, link_id)
    if not link_row or link_row.employee_id != employee_id:
        return _employee_edit_redirect(employee_id, "Ссылка на документ не найдена.", "error")
    db.delete(link_row)
    db.commit()
    return _employee_edit_redirect(employee_id, "Ссылка на документ удалена.", "success")


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


@app.post("/flows/reorder")
@app.post("/surveys/reorder")
async def reorder_templates(
    request: Request,
    db: Session = Depends(get_db),
):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    form = await request.form()
    scenario_ids = [int(value) for value in form.getlist("scenario_id") if str(value).isdigit()]
    if not scenario_ids:
        return RedirectResponse(url=request.url.path.rsplit("/", 1)[0], status_code=status.HTTP_303_SEE_OTHER)
    scenarios = db.query(ScenarioTemplate).filter(ScenarioTemplate.id.in_(scenario_ids)).all()
    scenario_map = {scenario.id: scenario for scenario in scenarios}
    for index, scenario_id in enumerate(scenario_ids):
        scenario = scenario_map.get(scenario_id)
        if scenario:
            scenario.sort_order = (index + 1) * 10
    db.commit()
    return RedirectResponse(url=request.url.path.rsplit("/", 1)[0], status_code=status.HTTP_303_SEE_OTHER)


@app.get("/flows")
def scenarios_page(request: Request, db: Session = Depends(get_db)):
    return _template_list_page(request, "scenario", db)


@app.get("/api/flows/workspace")
def scenario_workspace_api(
    request: Request,
    scenario_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    _require_api_auth(request)
    return _build_scenario_workspace_payload(db, scenario_id)


@app.post("/api/flows/workspace/scenarios")
def create_workspace_scenario_api(
    request: Request,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    _require_api_auth(request)
    try:
        title = (str(payload.get("title") or "").strip() or "Новый сценарий")
        description = str(payload.get("description") or "").strip() or None

        last_scenario = (
            db.query(ScenarioTemplate)
            .filter(ScenarioTemplate.scenario_kind == "scenario")
            .order_by(ScenarioTemplate.sort_order.desc(), ScenarioTemplate.id.desc())
            .first()
        )
        next_order = ((last_scenario.sort_order or 0) + 10) if last_scenario else 10
        now = datetime.utcnow()
        scenario_key = _generate_workspace_scenario_key("scenario")

        table_info = db.execute(text("PRAGMA table_info(scenario_templates)")).fetchall()
        table_columns = {row[1] for row in table_info}

        insert_values = {
            "scenario_key": scenario_key,
            "title": title,
            "sort_order": next_order,
            "scenario_kind": "scenario",
            "role_scope": "all",
            "trigger_mode": "manual_only",
            "target_employee_id": None,
            "description": description,
        }
        if "created_at" in table_columns:
            insert_values["created_at"] = now
        if "updated_at" in table_columns:
            insert_values["updated_at"] = now

        required_columns_without_default = {
            row[1]
            for row in table_info
            if row[5] == 0 and row[3] == 1 and row[4] is None
        }
        missing_required_columns = sorted(required_columns_without_default - set(insert_values.keys()))
        if missing_required_columns:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Не удалось создать сценарий: в БД есть обязательные колонки без поддержки в UI ({', '.join(missing_required_columns)}).",
            )

        columns_sql = ", ".join(insert_values.keys())
        placeholders_sql = ", ".join(f":{key}" for key in insert_values.keys())
        db.execute(
            text(f"INSERT INTO scenario_templates ({columns_sql}) VALUES ({placeholders_sql})"),
            insert_values,
        )
        db.commit()
        scenario = (
            db.query(ScenarioTemplate)
            .filter(ScenarioTemplate.scenario_key == scenario_key)
            .first()
        )
        if not scenario:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Не удалось создать сценарий: запись не найдена после сохранения.",
            )
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Не удалось создать сценарий. Попробуй ещё раз.")
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Не удалось создать сценарий.")

    return {
        "message": "Сценарий создан",
        "scenario_id": scenario.id,
        "payload": _build_scenario_workspace_payload(db, scenario.id),
    }


@app.post("/api/flows/workspace/scenarios/reorder")
def reorder_workspace_scenarios_api(
    request: Request,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    _require_api_auth(request)
    scenario_ids = [int(value) for value in (payload.get("scenario_ids") or []) if str(value).isdigit()]
    if not scenario_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Не передан порядок сценариев")

    scenarios = (
        db.query(ScenarioTemplate)
        .filter(
            ScenarioTemplate.id.in_(scenario_ids),
            ScenarioTemplate.scenario_kind == "scenario",
        )
        .all()
    )
    scenario_map = {scenario.id: scenario for scenario in scenarios}
    for index, scenario_id in enumerate(scenario_ids):
        scenario = scenario_map.get(scenario_id)
        if scenario:
            scenario.sort_order = (index + 1) * 10
    db.commit()

    selected_scenario_id = next((scenario_id for scenario_id in scenario_ids if scenario_id in scenario_map), None)
    return {
        "message": "Порядок сценариев обновлён",
        "payload": _build_scenario_workspace_payload(db, selected_scenario_id),
    }


@app.post("/api/flows/workspace/scenarios/bulk-copy")
def copy_workspace_scenarios_api(
    request: Request,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    _require_api_auth(request)
    scenario_ids = [int(value) for value in (payload.get("scenario_ids") or []) if str(value).isdigit()]
    if not scenario_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Не выбраны сценарии для копирования")

    scenarios = (
        db.query(ScenarioTemplate)
        .filter(
            ScenarioTemplate.id.in_(scenario_ids),
            ScenarioTemplate.scenario_kind == "scenario",
        )
        .order_by(ScenarioTemplate.sort_order, ScenarioTemplate.id)
        .all()
    )
    if not scenarios:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сценарии не найдены")

    copied_items = [_copy_template_entity(db, scenario) for scenario in scenarios]
    db.commit()

    return {
        "message": f"Скопировано: {len(copied_items)}",
        "payload": _build_scenario_workspace_payload(db, copied_items[-1].id),
    }


@app.post("/api/flows/workspace/scenarios/bulk-delete")
def delete_workspace_scenarios_api(
    request: Request,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    _require_api_auth(request)
    scenario_ids = [int(value) for value in (payload.get("scenario_ids") or []) if str(value).isdigit()]
    if not scenario_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Не выбраны сценарии для удаления")

    scenarios = (
        db.query(ScenarioTemplate)
        .filter(
            ScenarioTemplate.id.in_(scenario_ids),
            ScenarioTemplate.scenario_kind == "scenario",
        )
        .all()
    )
    if not scenarios:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сценарии не найдены")

    deleted_ids = {scenario.id for scenario in scenarios}
    for scenario in scenarios:
        _delete_template_entity(db, scenario)
    db.commit()

    remaining = (
        db.query(ScenarioTemplate)
        .filter(ScenarioTemplate.scenario_kind == "scenario")
        .order_by(ScenarioTemplate.sort_order, ScenarioTemplate.id)
        .all()
    )
    selected_scenario_id = next((scenario.id for scenario in remaining if scenario.id not in deleted_ids), None)

    return {
        "message": f"Удалено: {len(deleted_ids)}",
        "payload": _build_scenario_workspace_payload(db, selected_scenario_id),
    }


@app.post("/api/flows/workspace/steps/{step_id}")
def update_workspace_step_api(
    request: Request,
    step_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    _require_api_auth(request)
    step = db.get(FlowStepTemplate, step_id)
    if not step:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Шаг не найден")

    scenario = (
        db.query(ScenarioTemplate)
        .filter(
            ScenarioTemplate.scenario_key == step.flow_key,
            ScenarioTemplate.scenario_kind == "scenario",
        )
        .first()
    )
    if not scenario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сценарий не найден")

    _apply_workspace_step_update(step, payload)
    db.commit()

    return {
        "message": "Шаг сохранён",
        "payload": _build_scenario_workspace_payload(db, scenario.id),
        "step_id": step.id,
    }


@app.post("/api/flows/workspace/scenarios/{scenario_id}/steps")
def create_workspace_root_step_api(
    request: Request,
    scenario_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    _require_api_auth(request)
    scenario = db.get(ScenarioTemplate, scenario_id)
    if not scenario or scenario.scenario_kind != "scenario":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сценарий не найден")

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
    title = str(payload.get("title") or "Новый шаг").strip() or "Новый шаг"

    step = FlowStepTemplate(
        flow_key=scenario.scenario_key,
        step_key=f"{scenario.scenario_key}_step_{int(datetime.utcnow().timestamp())}",
        step_title=title,
        sort_order=next_order,
        default_text="Новое сообщение сценария.",
        custom_text=None,
        response_type="none",
        button_options=None,
        send_mode="immediate",
        send_time=None,
        day_offset_workdays=0,
        target_field=None,
        send_employee_card=False,
    )
    db.add(step)
    db.commit()

    return {
        "message": "Шаг добавлен",
        "payload": _build_scenario_workspace_payload(db, scenario.id),
        "step_id": step.id,
    }


@app.post("/api/flows/workspace/scenarios/{scenario_id}/steps/reorder")
def reorder_workspace_root_steps_api(
    request: Request,
    scenario_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    _require_api_auth(request)
    scenario = db.get(ScenarioTemplate, scenario_id)
    if not scenario or scenario.scenario_kind != "scenario":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сценарий не найден")

    step_ids = [int(value) for value in (payload.get("step_ids") or []) if str(value).isdigit()]
    if not step_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Не передан порядок шагов")

    steps = (
        db.query(FlowStepTemplate)
        .filter(
            FlowStepTemplate.flow_key == scenario.scenario_key,
            FlowStepTemplate.parent_step_id.is_(None),
            FlowStepTemplate.id.in_(step_ids),
        )
        .all()
    )
    step_map = {step.id: step for step in steps}
    for index, step_id in enumerate(step_ids):
        step = step_map.get(step_id)
        if step:
            step.sort_order = (index + 1) * 10
    db.commit()

    return {
        "message": "Порядок шагов обновлён",
        "payload": _build_scenario_workspace_payload(db, scenario.id),
    }


@app.post("/api/flows/workspace/steps/{step_id}/branches")
def create_workspace_branch_step_api(
    request: Request,
    step_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    _require_api_auth(request)
    parent_step = db.get(FlowStepTemplate, step_id)
    if not parent_step:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Шаг не найден")

    scenario = (
        db.query(ScenarioTemplate)
        .filter(
            ScenarioTemplate.scenario_key == parent_step.flow_key,
            ScenarioTemplate.scenario_kind == "scenario",
        )
        .first()
    )
    if not scenario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сценарий не найден")
    if parent_step.response_type != "branching":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ветки можно создавать только для шага с ветвлением")

    try:
        option_index = int(payload.get("option_index"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Не удалось определить кнопку для ветки")

    button_labels = [item.strip() for item in (parent_step.button_options or "").splitlines() if item.strip()]
    if option_index < 0 or option_index >= len(button_labels):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Кнопка для ветки не найдена")

    existing_branch = (
        db.query(FlowStepTemplate)
        .filter(
            FlowStepTemplate.flow_key == parent_step.flow_key,
            FlowStepTemplate.parent_step_id == parent_step.id,
            FlowStepTemplate.branch_option_index == option_index,
        )
        .first()
    )
    if existing_branch:
        return {
            "message": "Ветка уже существует",
            "payload": _build_scenario_workspace_payload(db, scenario.id),
            "step_id": existing_branch.id,
        }

    button_label = button_labels[option_index]
    branch_step = FlowStepTemplate(
        flow_key=parent_step.flow_key,
        step_key=f"{parent_step.step_key}__branch_{option_index}",
        parent_step_id=parent_step.id,
        branch_option_index=option_index,
        step_title=f"Ветка: {button_label}",
        sort_order=(parent_step.sort_order or 0) * 100 + option_index + 1,
        default_text="Новое сообщение сценария.",
        custom_text=None,
        response_type="none",
        button_options=None,
        send_mode="immediate",
        send_time=None,
        day_offset_workdays=0,
        target_field=None,
        send_employee_card=False,
    )
    db.add(branch_step)
    db.commit()

    return {
        "message": "Ветка создана",
        "payload": _build_scenario_workspace_payload(db, scenario.id),
        "step_id": branch_step.id,
    }


@app.post("/api/flows/workspace/steps/{step_id}/chain")
def create_workspace_chain_step_api(
    request: Request,
    step_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    _require_api_auth(request)
    parent_step = db.get(FlowStepTemplate, step_id)
    if not parent_step:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Шаг не найден")

    scenario = (
        db.query(ScenarioTemplate)
        .filter(
            ScenarioTemplate.scenario_key == parent_step.flow_key,
            ScenarioTemplate.scenario_kind == "scenario",
        )
        .first()
    )
    if not scenario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сценарий не найден")
    if parent_step.parent_step_id is None or parent_step.branch_option_index is None or parent_step.response_type != "chain":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Шаг цепочки можно добавить только внутри ветки с типом «Цепочка шагов»")

    last_step = (
        db.query(FlowStepTemplate)
        .filter(
            FlowStepTemplate.flow_key == parent_step.flow_key,
            FlowStepTemplate.parent_step_id == parent_step.id,
            FlowStepTemplate.branch_option_index.is_(None),
        )
        .order_by(FlowStepTemplate.sort_order.desc(), FlowStepTemplate.id.desc())
        .first()
    )
    next_order = (last_step.sort_order + 10) if last_step else 10
    title = str(payload.get("title") or "Шаг цепочки").strip() or "Шаг цепочки"

    chain_step = FlowStepTemplate(
        flow_key=parent_step.flow_key,
        step_key=f"{parent_step.step_key}__chain_{int(datetime.utcnow().timestamp())}",
        parent_step_id=parent_step.id,
        branch_option_index=None,
        step_title=title,
        sort_order=next_order,
        default_text="Новое сообщение сценария.",
        custom_text=None,
        response_type="none",
        button_options=None,
        send_mode="immediate",
        send_time=None,
        day_offset_workdays=0,
        target_field=None,
        send_employee_card=False,
    )
    db.add(chain_step)
    db.commit()

    return {
        "message": "Шаг цепочки добавлен",
        "payload": _build_scenario_workspace_payload(db, scenario.id),
        "step_id": chain_step.id,
    }


@app.post("/api/flows/workspace/steps/{step_id}/delete")
def delete_workspace_step_api(
    request: Request,
    step_id: int,
    db: Session = Depends(get_db),
):
    _require_api_auth(request)
    step = db.get(FlowStepTemplate, step_id)
    if not step:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Шаг не найден")

    scenario = (
        db.query(ScenarioTemplate)
        .filter(
            ScenarioTemplate.scenario_key == step.flow_key,
            ScenarioTemplate.scenario_kind == "scenario",
        )
        .first()
    )
    if not scenario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сценарий не найден")

    deleted_kind = _workspace_node_kind(step)
    _delete_step_subtree(db, step)
    db.commit()

    return {
        "message": "Элемент удалён",
        "payload": _build_scenario_workspace_payload(db, scenario.id),
        "deleted_kind": deleted_kind,
    }


@app.get("/app/flows/workspace")
def scenario_workspace_legacy_redirect(
    request: Request,
    scenario_id: Optional[int] = None,
):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    target = f"/app/flows/workspace-v2?scenario_id={scenario_id}" if scenario_id else "/app/flows/workspace-v2"
    return RedirectResponse(url=target, status_code=status.HTTP_303_SEE_OTHER)


@app.post("/api/flows/workspace/steps/{step_id}/attachment")
async def upload_workspace_step_attachment_api(
    request: Request,
    step_id: int,
    upload: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    _require_api_auth(request)
    step = db.get(FlowStepTemplate, step_id)
    if not step:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Шаг не найден")
    scenario = (
        db.query(ScenarioTemplate)
        .filter(
            ScenarioTemplate.scenario_key == step.flow_key,
            ScenarioTemplate.scenario_kind == "scenario",
        )
        .first()
    )
    if not scenario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сценарий не найден")
    await _save_step_attachment(step, upload)
    db.commit()
    return {
        "message": "Вложение добавлено",
        "payload": _build_scenario_workspace_payload(db, scenario.id),
        "step_id": step.id,
    }


@app.post("/api/flows/workspace/steps/{step_id}/attachment/delete")
def delete_workspace_step_attachment_api(
    request: Request,
    step_id: int,
    db: Session = Depends(get_db),
):
    _require_api_auth(request)
    step = db.get(FlowStepTemplate, step_id)
    if not step:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Шаг не найден")
    scenario = (
        db.query(ScenarioTemplate)
        .filter(
            ScenarioTemplate.scenario_key == step.flow_key,
            ScenarioTemplate.scenario_kind == "scenario",
        )
        .first()
    )
    if not scenario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сценарий не найден")
    _delete_step_attachment_file(step)
    db.commit()
    return {
        "message": "Вложение удалено",
        "payload": _build_scenario_workspace_payload(db, scenario.id),
        "step_id": step.id,
    }


@app.get("/app/flows/workspace-v2")
def scenario_workspace_v2_page(
    request: Request,
    scenario_id: Optional[int] = None,
):
    auth_redirect = _require_auth(request)
    if auth_redirect:
        return auth_redirect
    return _render(
        request,
        "react_scenario_workspace_v2.html",
        {
            "active_tab": "flows",
            "react_api_url": "/api/flows/workspace",
            "react_selected_scenario_id": scenario_id or "",
            "classic_list_url": "/flows",
        },
    )


@app.get("/surveys")
def surveys_page(request: Request, db: Session = Depends(get_db)):
    return _template_list_page(request, "survey", db)


def _create_template_entity(
    request: Request,
    kind: str,
    title: str,
    role_scope: str,
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
    target_employee_id: str = Form(""),
    trigger_mode: str = Form("manual_only"),
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    return _create_template_entity(request, "scenario", title, role_scope, target_employee_id, trigger_mode, description, db)


@app.post("/surveys")
def create_survey(
    request: Request,
    title: str = Form("Новый опрос"),
    role_scope: str = Form("all"),
    target_employee_id: str = Form(""),
    trigger_mode: str = Form("manual_only"),
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    return _create_template_entity(request, "survey", title, role_scope, target_employee_id, trigger_mode, description, db)


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
