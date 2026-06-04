from __future__ import annotations

from typing import Literal, NamedTuple, Optional

from sqlalchemy.orm import Session

from ..models import BotMenuButton, BotMenuSet, Employee, EmployeeFile, HrSettings, ScenarioTemplate
from ..notifications import notify_hr_test_task_received
from ..scenario_engine import handle_button_response_by_step_id, handle_file_response, handle_text_response, start_scenario
from ..time_utils import utc_now
from .base import MessengerClient
from .identity import (
    find_employee_by_public_chat_handle,
    find_employee_by_channel_user_id,
    get_primary_chat_id,
    get_public_chat_handle,
    set_primary_chat_id,
    set_public_chat_handle,
)


UNKNOWN_USER_TEXT = "Ваш аккаунт пока не привязан к HR-боту. Обратитесь в HR."
BLOCKED_USER_TEXT = "Доступ к HR-боту отключен. Обратитесь в HR."


class InboundAccess(NamedTuple):
    employee: Optional[Employee]
    state: Literal["ok", "unknown", "blocked"]


def detect_category_from_caption(caption: Optional[str]) -> str:
    text = (caption or "").lower()
    if "резюм" in text:
        return "resume"
    if "инн" in text:
        return "inn"
    if "снилс" in text:
        return "snils"
    if "паспорт" in text:
        return "passport"
    if "тест" in text:
        return "test_result"
    return "candidate_file"


def _sync_employee_after_inbound(db: Session, employee: Employee, chat_user_id: str, username: Optional[str]) -> None:
    changed = False
    if get_public_chat_handle(employee, db=db) != username:
        set_public_chat_handle(employee, username, db=db)
        changed = True
    if get_primary_chat_id(employee, db=db) != chat_user_id:
        set_primary_chat_id(employee, chat_user_id, db=db)
        changed = True
    if employee.is_flow_scheduled:
        employee.is_flow_scheduled = False
        changed = True
    if changed:
        db.commit()


def default_menu_set(db: Session) -> Optional[BotMenuSet]:
    hr_settings = db.get(HrSettings, 1)
    if hr_settings and hr_settings.default_menu_set_id:
        return db.get(BotMenuSet, hr_settings.default_menu_set_id)
    return db.query(BotMenuSet).order_by(BotMenuSet.sort_order, BotMenuSet.id).first()


def current_menu_set(db: Session, employee: Employee) -> Optional[BotMenuSet]:
    if employee.current_menu_set_id:
        current_set = db.get(BotMenuSet, employee.current_menu_set_id)
        if current_set:
            return current_set
    default_set = default_menu_set(db)
    if default_set:
        employee.current_menu_set_id = default_set.id
        db.commit()
    return default_set


def menu_button_labels(db: Session, employee: Employee) -> list[str]:
    menu_set = current_menu_set(db, employee)
    if not menu_set:
        return []
    buttons = (
        db.query(BotMenuButton)
        .filter(BotMenuButton.menu_set_id == menu_set.id)
        .order_by(BotMenuButton.sort_order, BotMenuButton.id)
        .all()
    )
    return [button.label.strip() for button in buttons if button.label.strip()]


async def send_menu(messenger: MessengerClient, db: Session, employee: Employee, text: str) -> None:
    chat_id = get_primary_chat_id(employee, db=db)
    if not chat_id:
        return
    labels = menu_button_labels(db, employee)
    if not labels:
        return
    await messenger.send_menu(chat_id=chat_id, text=text, buttons=labels)


async def handle_menu_button(messenger: MessengerClient, db: Session, employee: Employee, text: str) -> bool:
    if employee.is_bot_blocked:
        return False
    menu_set = current_menu_set(db, employee)
    if not menu_set:
        return False
    button = (
        db.query(BotMenuButton)
        .filter(
            BotMenuButton.menu_set_id == menu_set.id,
            BotMenuButton.label == text.strip(),
        )
        .order_by(BotMenuButton.sort_order, BotMenuButton.id)
        .first()
    )
    if not button:
        return False

    if button.action_type == "launch_scenario" and button.scenario_key:
        scenario = db.query(ScenarioTemplate).filter(ScenarioTemplate.scenario_key == button.scenario_key).first()
        if not scenario:
            await send_menu(messenger, db, employee, "Этот сценарий сейчас недоступен.")
            return True
        started = await start_scenario(messenger, db, employee, scenario.scenario_key)
        if not started:
            await send_menu(messenger, db, employee, "Не удалось запустить этот сценарий.")
        return True

    if button.action_type == "open_set" and button.target_menu_set_id:
        target_set = db.get(BotMenuSet, button.target_menu_set_id)
        if not target_set:
            await send_menu(messenger, db, employee, "Этот раздел меню сейчас недоступен.")
            return True
        employee.current_menu_set_id = target_set.id
        db.commit()
        await send_menu(messenger, db, employee, target_set.description or f"Открыт раздел «{target_set.title}».")
        return True

    await send_menu(messenger, db, employee, "Эта кнопка пока неактивна.")
    return True


def resolve_inbound_access(db: Session, chat_user_id: str, username: Optional[str]) -> InboundAccess:
    employee = find_employee_by_channel_user_id(db, channel="telegram", external_user_id=chat_user_id)
    if employee:
        _sync_employee_after_inbound(db, employee, chat_user_id, username)
        return InboundAccess(employee, "blocked" if employee.is_bot_blocked else "ok")

    employee = find_employee_by_public_chat_handle(db, channel="telegram", external_username=username)
    if employee:
        _sync_employee_after_inbound(db, employee, chat_user_id, username)
        return InboundAccess(employee, "blocked" if employee.is_bot_blocked else "ok")
    return InboundAccess(None, "unknown")


def get_or_create_employee_by_chat(db: Session, chat_user_id: str, username: Optional[str]) -> tuple[Optional[Employee], bool]:
    access = resolve_inbound_access(db, chat_user_id, username)
    return access.employee, False


async def send_access_state_message(messenger: MessengerClient, chat_user_id: str, state: Literal["unknown", "blocked"]) -> None:
    if state == "blocked":
        await messenger.send_text(chat_id=chat_user_id, text=BLOCKED_USER_TEXT)
        return
    await messenger.send_text(chat_id=chat_user_id, text=UNKNOWN_USER_TEXT)


async def handle_start_command(messenger: MessengerClient, db: Session, chat_user_id: str, username: Optional[str]) -> None:
    access = resolve_inbound_access(db, chat_user_id, username)
    if access.state != "ok" or access.employee is None:
        await send_access_state_message(messenger, chat_user_id, access.state)
        return

    employee = access.employee
    await messenger.send_text(
        chat_id=chat_user_id,
        text="Привет! Я HR-бот.",
    )
    await send_menu(messenger, db, employee, "Меню обновлено. Выберите действие.")


async def save_incoming_file(
    db: Session,
    chat_user_id: str,
    username: Optional[str],
    *,
    original_name: str,
    stored_path: str,
    category: str,
    mime_type: Optional[str],
    file_size: Optional[int],
    external_file_id: Optional[str] = None,
    external_unique_id: Optional[str] = None,
) -> tuple[Optional[Employee], Optional[EmployeeFile], Literal["saved", "unknown", "blocked"]]:
    access = resolve_inbound_access(db, chat_user_id, username)
    if access.state != "ok" or access.employee is None:
        return None, None, access.state
    employee = access.employee

    db_file = EmployeeFile(
        employee_id=employee.id,
        direction="inbound",
        category=category,
        telegram_file_id=external_file_id,
        telegram_file_unique_id=external_unique_id,
        original_filename=original_name,
        stored_path=stored_path,
        mime_type=mime_type,
        file_size=file_size,
        created_at=utc_now(),
    )
    db.add(db_file)
    db.commit()
    db.refresh(db_file)
    return employee, db_file, "saved"


async def handle_saved_document(
    messenger: MessengerClient,
    db: Session,
    employee: Employee,
    db_file: EmployeeFile,
) -> bool:
    if db_file.category == "test_result":
        try:
            await notify_hr_test_task_received(messenger, employee, db_file.original_filename)
        except Exception:
            pass
    return await handle_file_response(messenger, db, employee, db_file)


async def handle_text_event(
    messenger: MessengerClient,
    db: Session,
    chat_user_id: str,
    username: Optional[str],
    text: str,
) -> Literal["handled", "ignored", "unknown", "blocked"]:
    access = resolve_inbound_access(db, chat_user_id, username)
    if access.state != "ok" or access.employee is None:
        return access.state
    employee = access.employee
    handled = await handle_text_response(messenger, db, employee, type("MessageStub", (), {"text": text})())
    if handled:
        return "handled"
    if await handle_menu_button(messenger, db, employee, text):
        return "handled"
    return "ignored"


async def handle_button_event(
    messenger: MessengerClient,
    db: Session,
    chat_user_id: str,
    username: Optional[str],
    step_id: int,
    option_index: int,
) -> Literal["handled", "ignored", "unknown", "blocked"]:
    access = resolve_inbound_access(db, chat_user_id, username)
    if access.state != "ok" or access.employee is None:
        return access.state
    handled = await handle_button_response_by_step_id(
        messenger,
        db,
        access.employee,
        step_id,
        option_index,
    )
    return "handled" if handled else "ignored"
