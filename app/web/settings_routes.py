from datetime import datetime

from fastapi import APIRouter, Body, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..auth import ROLE_LABELS, hash_password
from ..database import get_session
from ..models import AdminAccount, BotMenuButton, BotMenuSet
from ..time_utils import utc_now
from .settings import (
    _apply_menu_button_payload,
    _apply_menu_set_payload,
    _delete_menu_set_relations,
    _get_or_create_hr_settings,
    _menu_target_conflicts,
    _settings_workspace_payload,
    _validate_menu_button_payload_refs,
)
from .support import render_template, require_admin, require_api_admin, require_api_auth, require_auth

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def get_db():
    with get_session() as db:
        yield db


@router.post("/settings")
def update_settings(
    request: Request,
    hr_name: str = Form(""),
    telegram_user_id: str = Form(""),
    notification_recipient_ids: str = Form(""),
    default_menu_set_id: str = Form(""),
    notify_scenario_completed: str | None = Form(None),
    notify_test_task_received: str | None = Form(None),
    notify_user_actions: str | None = Form(None),
    db: Session = Depends(get_db),
):
    auth_redirect = require_auth(request)
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
    hr_settings.updated_at = utc_now()
    db.commit()
    return RedirectResponse(url="/settings", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/settings/menu-sets")
def create_menu_set(
    request: Request,
    title: str = Form(""),
    description: str = Form(""),
    role_scope: str = Form("all"),
    employee_scope: str = Form("all"),
    target_employee_id: str = Form(""),
    target_employee_stages: list[str] = Form([]),
    target_candidate_stages: list[str] = Form([]),
    db: Session = Depends(get_db),
):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    last_set = db.query(BotMenuSet).order_by(BotMenuSet.sort_order.desc(), BotMenuSet.id.desc()).first()
    next_order = (last_set.sort_order + 10) if last_set else 10
    menu_set = BotMenuSet(
        title=title.strip() or "Новый набор кнопок",
        description=description.strip() or None,
        sort_order=next_order,
    )
    _apply_menu_set_payload(
        menu_set,
        {
            "title": title,
            "description": description,
            "role_scope": role_scope,
            "employee_scope": employee_scope,
            "target_employee_id": target_employee_id,
            "target_employee_stages": target_employee_stages,
            "target_candidate_stages": target_candidate_stages,
        },
    )
    db.add(menu_set)
    db.commit()
    return RedirectResponse(url="/settings", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/settings/menu-sets/{menu_set_id}")
def update_menu_set(
    request: Request,
    menu_set_id: int,
    title: str = Form(""),
    description: str = Form(""),
    role_scope: str = Form("all"),
    employee_scope: str = Form("all"),
    target_employee_id: str = Form(""),
    target_employee_stages: list[str] = Form([]),
    target_candidate_stages: list[str] = Form([]),
    db: Session = Depends(get_db),
):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    menu_set = db.get(BotMenuSet, menu_set_id)
    if menu_set:
        _apply_menu_set_payload(
            menu_set,
            {
                "title": title,
                "description": description,
                "role_scope": role_scope,
                "employee_scope": employee_scope,
                "target_employee_id": target_employee_id,
                "target_employee_stages": target_employee_stages,
                "target_candidate_stages": target_candidate_stages,
            },
        )
        db.commit()
    return RedirectResponse(url="/settings", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/settings/menu-sets/{menu_set_id}/delete")
def delete_menu_set(
    request: Request,
    menu_set_id: int,
    db: Session = Depends(get_db),
):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    menu_set = db.get(BotMenuSet, menu_set_id)
    if menu_set:
        _delete_menu_set_relations(db, menu_set_id)
        hr_settings = _get_or_create_hr_settings(db)
        if hr_settings.default_menu_set_id == menu_set_id:
            hr_settings.default_menu_set_id = None
        db.delete(menu_set)
        db.commit()
    return RedirectResponse(url="/settings", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/settings/menu-sets/{menu_set_id}/buttons")
def create_menu_button(
    request: Request,
    menu_set_id: int,
    label: str = Form(""),
    action_type: str = Form("inactive"),
    scenario_key: str = Form(""),
    target_menu_set_id: str = Form(""),
    db: Session = Depends(get_db),
):
    auth_redirect = require_auth(request)
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
    button = BotMenuButton(
        menu_set_id=menu_set_id,
        label=label.strip() or "Новая кнопка",
        sort_order=next_order,
        action_type="inactive",
        scenario_key=None,
        target_menu_set_id=None,
    )
    _apply_menu_button_payload(
        button,
        {
            "label": label,
            "action_type": action_type,
            "scenario_key": scenario_key,
            "target_menu_set_id": target_menu_set_id,
        },
    )
    db.add(button)
    db.commit()
    return RedirectResponse(url="/settings", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/settings/menu-buttons/{button_id}")
def update_menu_button(
    request: Request,
    button_id: int,
    label: str = Form(""),
    action_type: str = Form("inactive"),
    scenario_key: str = Form(""),
    target_menu_set_id: str = Form(""),
    db: Session = Depends(get_db),
):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    button = db.get(BotMenuButton, button_id)
    if button:
        _apply_menu_button_payload(
            button,
            {
                "label": label,
                "action_type": action_type,
                "scenario_key": scenario_key,
                "target_menu_set_id": target_menu_set_id,
            },
        )
        db.commit()
    return RedirectResponse(url="/settings", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/settings/menu-sets/{menu_set_id}/buttons/save")
async def update_menu_set_buttons(
    request: Request,
    menu_set_id: int,
    db: Session = Depends(get_db),
):
    auth_redirect = require_auth(request)
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
        _apply_menu_button_payload(
            button,
            {
                "label": labels[index].strip() if index < len(labels) else "",
                "action_type": action_types[index] if index < len(action_types) else "inactive",
                "scenario_key": scenario_keys[index].strip() if index < len(scenario_keys) else "",
                "target_menu_set_id": target_menu_set_ids[index].strip() if index < len(target_menu_set_ids) else "",
            },
        )

    db.commit()
    return RedirectResponse(url="/settings", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/settings/menu-buttons/save-all")
async def update_all_menu_buttons(
    request: Request,
    db: Session = Depends(get_db),
):
    auth_redirect = require_auth(request)
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
        _apply_menu_button_payload(
            button,
            {
                "label": labels[index].strip() if index < len(labels) else "",
                "action_type": action_types[index] if index < len(action_types) else "inactive",
                "scenario_key": scenario_keys[index].strip() if index < len(scenario_keys) else "",
                "target_menu_set_id": target_menu_set_ids[index].strip() if index < len(target_menu_set_ids) else "",
            },
        )

    db.commit()
    return RedirectResponse(url="/settings", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/settings/menu-buttons/{button_id}/delete")
def delete_menu_button(
    request: Request,
    button_id: int,
    db: Session = Depends(get_db),
):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    button = db.get(BotMenuButton, button_id)
    if button:
        db.delete(button)
        db.commit()
    return RedirectResponse(url="/settings", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/accounts")
def create_account(
    request: Request,
    login: str = Form(""),
    password: str = Form(""),
    role: str = Form("hr"),
    is_active: str = Form("true"),
    db: Session = Depends(get_db),
):
    admin_redirect = require_admin(request)
    if admin_redirect:
        return admin_redirect
    normalized_login = login.strip()
    existing_account = db.query(AdminAccount).filter(AdminAccount.login == normalized_login).first()
    if normalized_login and not existing_account:
        now = utc_now()
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


@router.post("/accounts/{account_id}")
def update_account(
    request: Request,
    account_id: int,
    login: str = Form(""),
    password: str = Form(""),
    role: str = Form("hr"),
    is_active: str = Form("true"),
    db: Session = Depends(get_db),
):
    admin_redirect = require_admin(request)
    if admin_redirect:
        return admin_redirect
    account = db.get(AdminAccount, account_id)
    if account:
        account.login = login.strip() or account.login
        account.role = role if role in ROLE_LABELS else "hr"
        account.is_active = is_active == "true"
        if password.strip():
            account.password_hash = hash_password(password.strip())
        account.updated_at = utc_now()
        db.commit()
    return RedirectResponse(url="/settings", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/accounts/{account_id}/delete")
def delete_account(
    request: Request,
    account_id: int,
    db: Session = Depends(get_db),
):
    admin_redirect = require_admin(request)
    if admin_redirect:
        return admin_redirect
    current_user = getattr(request.state, "current_user", None)
    account = db.get(AdminAccount, account_id)
    if account and (not current_user or account.id != current_user.id):
        db.delete(account)
        db.commit()
    return RedirectResponse(url="/settings", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/settings")
def settings_page(request: Request):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    return RedirectResponse(url="/app/settings", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/app/settings")
def react_settings_page(request: Request):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    return render_template(
        request,
        templates,
        "react_settings.html",
        {
            "active_tab": "settings",
            "react_api_url": "/api/settings/workspace",
            "classic_page_url": "/settings",
        },
    )


@router.get("/bot-menu")
def bot_menu_page(request: Request):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    return RedirectResponse(url="/app/bot-menu", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/app/bot-menu")
def react_bot_menu_page(request: Request):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    return render_template(
        request,
        templates,
        "react_bot_menu.html",
        {
            "active_tab": "bot_menu",
            "react_api_url": "/api/settings/workspace",
        },
    )


@router.get("/design-system")
def design_system_page(request: Request):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    return RedirectResponse(url="/app/design-system", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/app/design-system")
def react_design_system_page(request: Request):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    return render_template(
        request,
        templates,
        "react_design_system.html",
        {
            "active_tab": "design_system",
        },
    )


@router.get("/api/settings/workspace")
def settings_workspace_api(request: Request, db: Session = Depends(get_db)):
    current_user = require_api_auth(request)
    return _settings_workspace_payload(db, current_user)


@router.post("/api/settings/hr")
def update_hr_settings_api(
    request: Request,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    current_user = require_api_auth(request)
    hr_settings = _get_or_create_hr_settings(db)
    default_menu_set_id = payload.get("default_menu_set_id")
    hr_settings.hr_name = str(payload.get("hr_name") or "").strip() or None
    hr_settings.telegram_user_id = str(payload.get("telegram_user_id") or "").strip() or None
    hr_settings.notification_recipient_ids = str(payload.get("notification_recipient_ids") or "").strip() or None
    hr_settings.default_menu_set_id = int(default_menu_set_id) if str(default_menu_set_id or "").isdigit() else None
    hr_settings.notify_scenario_completed = bool(payload.get("notify_scenario_completed"))
    hr_settings.notify_test_task_received = bool(payload.get("notify_test_task_received"))
    hr_settings.notify_user_actions = bool(payload.get("notify_user_actions"))
    hr_settings.updated_at = utc_now()
    db.commit()
    return _settings_workspace_payload(db, current_user)


@router.post("/api/settings/menu-sets")
def create_menu_set_api(
    request: Request,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    current_user = require_api_auth(request)
    target_employee_ids = [
        int(str(value))
        for value in payload.get("target_employee_ids") or []
        if str(value or "").isdigit()
    ]
    conflicts = _menu_target_conflicts(db, None, target_employee_ids)
    if conflicts:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Некоторые сотрудники или кандидаты уже привязаны к другим наборам меню.",
        )
    last_set = db.query(BotMenuSet).order_by(BotMenuSet.sort_order.desc(), BotMenuSet.id.desc()).first()
    next_order = (last_set.sort_order + 10) if last_set else 10
    menu_set = BotMenuSet(
        title=str(payload.get("title") or "").strip() or "Новый набор кнопок",
        description=str(payload.get("description") or "").strip() or None,
        sort_order=next_order,
    )
    _apply_menu_set_payload(menu_set, payload)
    db.add(menu_set)
    db.commit()
    return _settings_workspace_payload(db, current_user)


@router.post("/api/settings/menu-sets/{menu_set_id}")
def update_menu_set_api(
    request: Request,
    menu_set_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    current_user = require_api_auth(request)
    menu_set = db.get(BotMenuSet, menu_set_id)
    if not menu_set:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Набор кнопок не найден")
    target_employee_ids = [
        int(str(value))
        for value in payload.get("target_employee_ids") or []
        if str(value or "").isdigit()
    ]
    conflicts = _menu_target_conflicts(db, menu_set_id, target_employee_ids)
    if conflicts:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Некоторые сотрудники или кандидаты уже привязаны к другим наборам меню.",
        )
    _apply_menu_set_payload(menu_set, payload)
    db.commit()
    return _settings_workspace_payload(db, current_user)


@router.delete("/api/settings/menu-sets/{menu_set_id}")
def delete_menu_set_api(
    request: Request,
    menu_set_id: int,
    db: Session = Depends(get_db),
):
    current_user = require_api_auth(request)
    menu_set = db.get(BotMenuSet, menu_set_id)
    if not menu_set:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Набор кнопок не найден")
    _delete_menu_set_relations(db, menu_set_id)
    hr_settings = _get_or_create_hr_settings(db)
    if hr_settings.default_menu_set_id == menu_set_id:
        hr_settings.default_menu_set_id = None
    db.delete(menu_set)
    db.commit()
    return _settings_workspace_payload(db, current_user)


@router.post("/api/settings/menu-sets/{menu_set_id}/buttons")
def create_menu_button_api(
    request: Request,
    menu_set_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    current_user = require_api_auth(request)
    menu_set = db.get(BotMenuSet, menu_set_id)
    if not menu_set:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Набор кнопок не найден")
    last_button = (
        db.query(BotMenuButton)
        .filter(BotMenuButton.menu_set_id == menu_set_id)
        .order_by(BotMenuButton.sort_order.desc(), BotMenuButton.id.desc())
        .first()
    )
    next_order = (last_button.sort_order + 10) if last_button else 10
    button = BotMenuButton(
        menu_set_id=menu_set_id,
        label=str(payload.get("label") or "").strip() or "Новая кнопка",
        sort_order=next_order,
        action_type="inactive",
        scenario_key=None,
        target_menu_set_id=None,
    )
    _apply_menu_button_payload(button, payload)
    validation_error = _validate_menu_button_payload_refs(db, button)
    if validation_error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=validation_error)
    db.add(button)
    db.commit()
    return _settings_workspace_payload(db, current_user)


@router.post("/api/settings/menu-buttons/{button_id}")
def update_menu_button_api(
    request: Request,
    button_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    current_user = require_api_auth(request)
    button = db.get(BotMenuButton, button_id)
    if not button:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Кнопка не найдена")
    _apply_menu_button_payload(button, payload)
    validation_error = _validate_menu_button_payload_refs(db, button)
    if validation_error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=validation_error)
    db.commit()
    return _settings_workspace_payload(db, current_user)


@router.post("/api/settings/menu-buttons/bulk")
def update_menu_buttons_bulk_api(
    request: Request,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    current_user = require_api_auth(request)
    for item in payload.get("buttons") or []:
        button_id = item.get("id")
        if not str(button_id or "").isdigit():
            continue
        button = db.get(BotMenuButton, int(button_id))
        if button:
            _apply_menu_button_payload(button, item)
            validation_error = _validate_menu_button_payload_refs(db, button)
            if validation_error:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=validation_error)
    db.commit()
    return _settings_workspace_payload(db, current_user)


@router.delete("/api/settings/menu-buttons/{button_id}")
def delete_menu_button_api(
    request: Request,
    button_id: int,
    db: Session = Depends(get_db),
):
    current_user = require_api_auth(request)
    button = db.get(BotMenuButton, button_id)
    if not button:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Кнопка не найдена")
    db.delete(button)
    db.commit()
    return _settings_workspace_payload(db, current_user)


@router.post("/api/accounts")
def create_account_api(
    request: Request,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    current_user = require_api_admin(request)
    normalized_login = str(payload.get("login") or "").strip()
    if not normalized_login:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Укажите логин")
    existing_account = db.query(AdminAccount).filter(AdminAccount.login == normalized_login).first()
    if existing_account:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Аккаунт с таким логином уже есть")
    now = utc_now()
    db.add(
        AdminAccount(
            login=normalized_login,
            password_hash=hash_password(str(payload.get("password") or "change-me")),
            role=str(payload.get("role") or "hr") if str(payload.get("role") or "hr") in ROLE_LABELS else "hr",
            is_active=bool(payload.get("is_active", True)),
            created_at=now,
            updated_at=now,
        )
    )
    db.commit()
    return _settings_workspace_payload(db, current_user)


@router.post("/api/accounts/{account_id}")
def update_account_api(
    request: Request,
    account_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    current_user = require_api_admin(request)
    account = db.get(AdminAccount, account_id)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Аккаунт не найден")
    next_login = str(payload.get("login") or "").strip() or account.login
    duplicate = db.query(AdminAccount).filter(AdminAccount.login == next_login, AdminAccount.id != account.id).first()
    if duplicate:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Аккаунт с таким логином уже есть")
    account.login = next_login
    account.role = str(payload.get("role") or "hr") if str(payload.get("role") or "hr") in ROLE_LABELS else "hr"
    account.is_active = bool(payload.get("is_active", account.is_active))
    password = str(payload.get("password") or "").strip()
    if password:
        account.password_hash = hash_password(password)
    account.updated_at = utc_now()
    db.commit()
    return _settings_workspace_payload(db, current_user)


@router.delete("/api/accounts/{account_id}")
def delete_account_api(
    request: Request,
    account_id: int,
    db: Session = Depends(get_db),
):
    current_user = require_api_admin(request)
    account = db.get(AdminAccount, account_id)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Аккаунт не найден")
    if account.id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нельзя удалить текущий аккаунт")
    db.delete(account)
    db.commit()
    return _settings_workspace_payload(db, current_user)


