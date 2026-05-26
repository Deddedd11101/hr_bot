from datetime import datetime

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..auth import ROLE_LABELS, hash_password
from ..database import get_session
from ..models import AdminAccount, BotMenuButton, BotMenuSet
from .settings import (
    _apply_menu_button_payload,
    _delete_menu_set_relations,
    _get_or_create_hr_settings,
    _settings_workspace_payload,
)
from .support import render_template, require_api_admin, require_api_auth, require_auth

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def get_db():
    with get_session() as db:
        yield db


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
    hr_settings.updated_at = datetime.utcnow()
    db.commit()
    return _settings_workspace_payload(db, current_user)


@router.post("/api/settings/menu-sets")
def create_menu_set_api(
    request: Request,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    current_user = require_api_auth(request)
    last_set = db.query(BotMenuSet).order_by(BotMenuSet.sort_order.desc(), BotMenuSet.id.desc()).first()
    next_order = (last_set.sort_order + 10) if last_set else 10
    db.add(
        BotMenuSet(
            title=str(payload.get("title") or "").strip() or "Новый набор кнопок",
            description=str(payload.get("description") or "").strip() or None,
            sort_order=next_order,
        )
    )
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
    menu_set.title = str(payload.get("title") or "").strip() or menu_set.title
    menu_set.description = str(payload.get("description") or "").strip() or None
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
    now = datetime.utcnow()
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
    account.updated_at = datetime.utcnow()
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
