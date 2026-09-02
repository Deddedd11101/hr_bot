from __future__ import annotations

import logging
from typing import Literal, NamedTuple, Optional

from sqlalchemy.orm import Session

from ..flow_templates import CANDIDATE_WORK_STAGE_LABELS, EMPLOYEE_SCOPE_CANDIDATES, EMPLOYEE_SCOPE_EMPLOYEES
from ..models import BotMenuButton, BotMenuSet, DocumentLibraryItem, Employee, EmployeeFile, HrSettings, ScenarioTemplate
from ..notifications import notify_hr_test_task_received
from ..positions import position_matches_scope
from ..scenario_engine import (
    SCENARIO_BACK_BUTTON_TEXT,
    DATE_CALLBACK_PREFIX,
    get_waiting_progress,
    handle_back_response,
    handle_button_response_by_step_id,
    handle_date_response_by_step_id,
    handle_file_response,
    handle_text_response,
    matches_role_scope,
    start_scenario,
)
from ..time_utils import utc_now
from .base import MessengerClient
from .identity import (
    find_employees_by_public_chat_handle,
    find_employees_by_channel_user_id,
    get_primary_chat_id,
    get_public_chat_handle,
    normalize_public_chat_handle,
    set_primary_chat_id,
    set_public_chat_handle,
    sync_legacy_telegram_account,
)


logger = logging.getLogger(__name__)


UNKNOWN_USER_TEXT = "Не удалось автоматически привязать Telegram, обратитесь к HR."
BLOCKED_USER_TEXT = "Доступ к HR-боту отключен. Обратитесь в HR."
MENU_BACK_BUTTON_TEXT = "Назад"
MENU_HOME_BUTTON_TEXT = "Главное меню"
INITIAL_CANDIDATE_STAGE: str | None = None


class InboundAccess(NamedTuple):
    employee: Optional[Employee]
    state: Literal["ok", "unknown", "blocked", "conflict"]
    newly_linked: bool = False


class StartAccess(NamedTuple):
    employee: Optional[Employee]
    state: Literal["ok", "blocked", "conflict"]
    newly_linked: bool = False
    created: bool = False


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


def _sync_employee_after_inbound(db: Session, employee: Employee, chat_user_id: str, username: Optional[str]) -> bool:
    changed = False
    had_primary_chat_id = bool(get_primary_chat_id(employee, db=db))
    normalized_username = normalize_public_chat_handle(username)
    if get_public_chat_handle(employee, db=db) != normalized_username or employee.telegram_username != normalized_username:
        set_public_chat_handle(employee, username, db=db)
        changed = True
    if get_primary_chat_id(employee, db=db) != chat_user_id or employee.telegram_user_id != chat_user_id:
        set_primary_chat_id(employee, chat_user_id, db=db)
        changed = True
    if employee.is_flow_scheduled:
        employee.is_flow_scheduled = False
        changed = True
    if changed:
        db.commit()
    return not had_primary_chat_id and bool(get_primary_chat_id(employee, db=db))


def _registration_scenario(db: Session, employee: Employee) -> Optional[ScenarioTemplate]:
    scenarios = (
        db.query(ScenarioTemplate)
        .filter(
            ScenarioTemplate.trigger_mode == "bot_registration",
            ScenarioTemplate.scenario_kind == "scenario",
        )
        .order_by(ScenarioTemplate.sort_order.asc(), ScenarioTemplate.id.asc())
        .all()
    )
    for scenario in scenarios:
        if scenario and matches_role_scope(employee, scenario):
            return scenario
    return None


def _candidate_registration_allowed(employee: Employee) -> bool:
    return (employee.employee_stage or "").strip() == "candidate"


def _create_candidate_for_start(db: Session, chat_user_id: str, username: Optional[str]) -> Employee:
    initial_candidate_stage = (
        INITIAL_CANDIDATE_STAGE if INITIAL_CANDIDATE_STAGE in CANDIDATE_WORK_STAGE_LABELS else None
    )
    employee = Employee(
        full_name=None,
        telegram_user_id=chat_user_id,
        telegram_username=normalize_public_chat_handle(username),
        first_workday=None,
        created_at=utc_now(),
        is_flow_scheduled=False,
        candidate_status="new",
        employee_stage="candidate",
        candidate_work_stage=initial_candidate_stage,
    )
    db.add(employee)
    db.flush()
    sync_legacy_telegram_account(db, employee)
    db.commit()
    db.refresh(employee)
    return employee


def resolve_start_access(db: Session, chat_user_id: str, username: Optional[str]) -> StartAccess:
    access = resolve_inbound_access(db, chat_user_id, username)
    if access.employee is not None:
        if access.state == "blocked":
            return StartAccess(access.employee, "blocked", newly_linked=access.newly_linked, created=False)
        return StartAccess(access.employee, "ok", newly_linked=access.newly_linked, created=False)
    if access.state == "conflict":
        return StartAccess(None, "conflict", newly_linked=False, created=False)

    employee = _create_candidate_for_start(db, chat_user_id, username)
    return StartAccess(employee, "ok", newly_linked=True, created=True)


def default_menu_set(db: Session) -> Optional[BotMenuSet]:
    hr_settings = db.get(HrSettings, 1)
    if hr_settings and hr_settings.default_menu_set_id:
        return db.get(BotMenuSet, hr_settings.default_menu_set_id)
    return db.query(BotMenuSet).order_by(BotMenuSet.sort_order, BotMenuSet.id).first()


def _audience_default_menu_set(db: Session, employee: Employee) -> Optional[BotMenuSet]:
    hr_settings = db.get(HrSettings, 1)
    if not hr_settings:
        return None
    normalized_employee_stage = (employee.employee_stage or "").strip()
    if normalized_employee_stage == "candidate" and hr_settings.default_candidate_menu_set_id:
        return db.get(BotMenuSet, hr_settings.default_candidate_menu_set_id)
    if normalized_employee_stage != "candidate" and hr_settings.default_employee_menu_set_id:
        return db.get(BotMenuSet, hr_settings.default_employee_menu_set_id)
    return None


def _deserialize_menu_path(employee: Employee) -> list[int]:
    raw_value = (employee.current_menu_path or "").strip()
    if not raw_value:
        return []
    result: list[int] = []
    for item in raw_value.split(","):
        item = item.strip()
        if not item.isdigit():
            continue
        value = int(item)
        if value not in result:
            result.append(value)
    return result


def _serialize_menu_path(path_ids: list[int]) -> str | None:
    normalized = [str(value) for value in path_ids if int(value) > 0]
    return ",".join(normalized) if normalized else None


def _deserialize_menu_target_employee_ids(menu_set: BotMenuSet) -> list[int]:
    raw_value = (menu_set.target_employee_ids or "").strip()
    target_ids: list[int] = []
    if raw_value:
        for item in raw_value.split(","):
            item = item.strip()
            if item.isdigit():
                employee_id = int(item)
                if employee_id not in target_ids:
                    target_ids.append(employee_id)
    if target_ids:
        return target_ids
    if menu_set.target_employee_id:
        return [menu_set.target_employee_id]
    return []


def menu_set_matches_employee(employee: Employee, menu_set: BotMenuSet) -> bool:
    target_employee_ids = _deserialize_menu_target_employee_ids(menu_set)
    if target_employee_ids:
        return employee.id in target_employee_ids

    normalized_employee_stage = (employee.employee_stage or "").strip()
    normalized_employee_scope = (menu_set.employee_scope or "all").strip()
    if normalized_employee_scope == EMPLOYEE_SCOPE_CANDIDATES and normalized_employee_stage != "candidate":
        return False
    if normalized_employee_scope == EMPLOYEE_SCOPE_EMPLOYEES and normalized_employee_stage == "candidate":
        return False

    normalized_role_scope = (menu_set.role_scope or "all").strip()
    if normalized_role_scope and normalized_role_scope != "all":
        if not position_matches_scope(employee.desired_position, normalized_role_scope):
            return False

    return True


def _menu_set_score(employee: Employee, menu_set: BotMenuSet, default_menu_set_id: Optional[int]) -> tuple[int, int, int]:
    score = 0
    if _deserialize_menu_target_employee_ids(menu_set):
        score += 100
    if (menu_set.employee_scope or "all").strip() != "all":
        score += 20
    if (menu_set.role_scope or "all").strip() != "all":
        score += 20
    if default_menu_set_id and menu_set.id == default_menu_set_id:
        score += 5
    return score, -menu_set.sort_order, -menu_set.id


def resolve_menu_set(db: Session, employee: Employee) -> Optional[BotMenuSet]:
    hr_settings = db.get(HrSettings, 1)
    default_menu_set_id = hr_settings.default_menu_set_id if hr_settings else None
    menu_sets = db.query(BotMenuSet).order_by(BotMenuSet.sort_order, BotMenuSet.id).all()
    matching_sets = [menu_set for menu_set in menu_sets if menu_set_matches_employee(employee, menu_set)]
    if not matching_sets:
        return None
    return max(matching_sets, key=lambda item: _menu_set_score(employee, item, default_menu_set_id))


def resolve_root_menu_set(db: Session, employee: Employee) -> Optional[BotMenuSet]:
    candidate = _audience_default_menu_set(db, employee)
    if candidate and menu_set_matches_employee(employee, candidate):
        return candidate
    hr_settings = db.get(HrSettings, 1)
    if hr_settings and hr_settings.default_menu_set_id:
        candidate = db.get(BotMenuSet, hr_settings.default_menu_set_id)
        if candidate and menu_set_matches_employee(employee, candidate):
            return candidate
    return resolve_menu_set(db, employee)


def set_current_menu_set(
    db: Session,
    employee: Employee,
    menu_set: Optional[BotMenuSet],
    *,
    path_ids: Optional[list[int]] = None,
) -> Optional[BotMenuSet]:
    employee.current_menu_set_id = menu_set.id if menu_set else None
    if menu_set is None:
        employee.current_menu_path = None
    else:
        next_path = path_ids[:] if path_ids else [menu_set.id]
        if not next_path or next_path[-1] != menu_set.id:
            next_path.append(menu_set.id)
        employee.current_menu_path = _serialize_menu_path(next_path)
    db.commit()
    return menu_set


def current_menu_set(db: Session, employee: Employee) -> Optional[BotMenuSet]:
    if employee.current_menu_set_id:
        current_set = db.get(BotMenuSet, employee.current_menu_set_id)
        if current_set and menu_set_matches_employee(employee, current_set):
            current_path = _deserialize_menu_path(employee)
            if not current_path or current_path[-1] != current_set.id:
                employee.current_menu_path = _serialize_menu_path([current_set.id])
                db.commit()
            return current_set
    next_set = resolve_root_menu_set(db, employee)
    if next_set:
        set_current_menu_set(db, employee, next_set, path_ids=[next_set.id])
    return next_set


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
    labels = [button.label.strip() for button in buttons if button.label.strip()]
    root_set = resolve_root_menu_set(db, employee)
    current_path = _deserialize_menu_path(employee)
    if len(current_path) > 1:
        labels.append(MENU_BACK_BUTTON_TEXT)
    if root_set and menu_set.id != root_set.id:
        labels.append(MENU_HOME_BUTTON_TEXT)
    return labels


async def send_menu(messenger: MessengerClient, db: Session, employee: Employee, text: str) -> None:
    chat_id = get_primary_chat_id(employee, db=db)
    if not chat_id:
        return
    labels = menu_button_labels(db, employee)
    if not labels:
        return
    await messenger.send_menu(chat_id=chat_id, text=text, buttons=labels)


async def show_main_menu(messenger: MessengerClient, db: Session, employee: Employee, text: str) -> bool:
    root_set = resolve_root_menu_set(db, employee)
    if not root_set:
        return False
    set_current_menu_set(db, employee, root_set, path_ids=[root_set.id])
    await send_menu(messenger, db, employee, text)
    return True


async def handle_menu_navigation(messenger: MessengerClient, db: Session, employee: Employee, text: str) -> bool:
    normalized = text.strip()
    if normalized == MENU_HOME_BUTTON_TEXT:
        return await show_main_menu(messenger, db, employee, "Открыто главное меню.")
    if normalized != MENU_BACK_BUTTON_TEXT:
        return False

    current_set = current_menu_set(db, employee)
    if not current_set:
        return False
    path_ids = _deserialize_menu_path(employee)
    if len(path_ids) <= 1:
        return await show_main_menu(messenger, db, employee, "Вы уже в главном меню.")

    previous_set_id = path_ids[-2]
    previous_set = db.get(BotMenuSet, previous_set_id)
    if not previous_set or not menu_set_matches_employee(employee, previous_set):
        return await show_main_menu(
            messenger,
            db,
            employee,
            "Предыдущий раздел больше недоступен. Открываю главное меню.",
        )
    set_current_menu_set(db, employee, previous_set, path_ids=path_ids[:-1])
    await send_menu(messenger, db, employee, previous_set.description or f"Открыт раздел «{previous_set.title}».")
    return True


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
        if not menu_set_matches_employee(employee, target_set):
            await send_menu(messenger, db, employee, "Этот раздел меню вам недоступен.")
            return True
        current_path = _deserialize_menu_path(employee)
        if not current_path or current_path[-1] != menu_set.id:
            current_path = [menu_set.id]
        if target_set.id in current_path:
            next_path = current_path[: current_path.index(target_set.id) + 1]
        else:
            next_path = current_path + [target_set.id]
        set_current_menu_set(db, employee, target_set, path_ids=next_path)
        await send_menu(messenger, db, employee, target_set.description or f"Открыт раздел «{target_set.title}».")
        return True

    if button.action_type == "send_document" and button.document_item_id:
        item = db.get(DocumentLibraryItem, button.document_item_id)
        if not item or not item.is_active:
            await send_menu(messenger, db, employee, "Этот документ сейчас недоступен.")
            return True
        chat_id = get_primary_chat_id(employee, db=db)
        if not chat_id:
            return True
        if (item.item_kind or "").strip() == "link":
            link = (item.external_url or "").strip()
            if not link:
                await send_menu(messenger, db, employee, "Ссылка для этого документа не настроена.")
                return True
            message_parts = [item.title.strip()]
            if (item.description or "").strip():
                message_parts.append(item.description.strip())
            message_parts.append(link)
            await messenger.send_text(chat_id=chat_id, text="\n\n".join(message_parts))
            return True
        path_value = (item.stored_path or "").strip()
        if not path_value:
            await send_menu(messenger, db, employee, "Файл для этого документа не найден.")
            return True
        await messenger.send_document_path(chat_id=chat_id, path=path_value, filename=item.original_filename or None)
        return True

    await send_menu(messenger, db, employee, "Эта кнопка пока неактивна.")
    return True


def resolve_inbound_access(db: Session, chat_user_id: str, username: Optional[str]) -> InboundAccess:
    numeric_matches = find_employees_by_channel_user_id(
        db,
        channel="telegram",
        external_user_id=chat_user_id,
        repair_orphans=True,
    )
    if len(numeric_matches) > 1:
        logger.warning(
            "Telegram identity conflict by numeric id: chat_user_id=%s employee_ids=%s",
            chat_user_id,
            [employee.id for employee in numeric_matches],
        )
        return InboundAccess(None, "conflict", False)
    if numeric_matches:
        employee = numeric_matches[0]
        if employee.is_bot_blocked:
            return InboundAccess(employee, "blocked", False)
        newly_linked = _sync_employee_after_inbound(db, employee, chat_user_id, username)
        return InboundAccess(employee, "ok", newly_linked)

    username_matches = find_employees_by_public_chat_handle(
        db,
        channel="telegram",
        external_username=username,
        repair_orphans=True,
    )
    if len(username_matches) > 1:
        logger.warning(
            "Telegram identity conflict by username: username=%s employee_ids=%s",
            normalize_public_chat_handle(username),
            [employee.id for employee in username_matches],
        )
        return InboundAccess(None, "conflict", False)
    if username_matches:
        employee = username_matches[0]
        if employee.is_bot_blocked:
            return InboundAccess(employee, "blocked", False)
        newly_linked = _sync_employee_after_inbound(db, employee, chat_user_id, username)
        return InboundAccess(employee, "ok", newly_linked)
    return InboundAccess(None, "unknown", False)


def get_or_create_employee_by_chat(db: Session, chat_user_id: str, username: Optional[str]) -> tuple[Optional[Employee], bool]:
    access = resolve_start_access(db, chat_user_id, username)
    return access.employee, access.created


async def send_access_state_message(
    messenger: MessengerClient,
    chat_user_id: str,
    state: Literal["unknown", "blocked", "conflict"],
) -> None:
    if state == "blocked":
        await messenger.send_text(chat_id=chat_user_id, text=BLOCKED_USER_TEXT)
        return
    await messenger.send_text(chat_id=chat_user_id, text=UNKNOWN_USER_TEXT)


async def handle_start_command(messenger: MessengerClient, db: Session, chat_user_id: str, username: Optional[str]) -> None:
    access = resolve_start_access(db, chat_user_id, username)
    if access.state != "ok" or access.employee is None:
        await send_access_state_message(messenger, chat_user_id, access.state)
        return

    employee = access.employee
    if access.newly_linked and _candidate_registration_allowed(employee):
        scenario = _registration_scenario(db, employee)
        if scenario and await start_scenario(messenger, db, employee, scenario.scenario_key):
            return
    await show_main_menu(messenger, db, employee, "Меню обновлено. Выберите действие.")


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
) -> tuple[Optional[Employee], Optional[EmployeeFile], Literal["saved", "unknown", "blocked", "conflict"]]:
    access = resolve_inbound_access(db, chat_user_id, username)
    if access.state != "ok" or access.employee is None:
        return None, None, access.state
    employee = access.employee
    progress = get_waiting_progress(db, employee.id)
    context_employee = db.get(Employee, progress.employee_id) if progress and progress.employee_id else employee

    db_file = EmployeeFile(
        employee_id=context_employee.id,
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
    return context_employee, db_file, "saved"


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
    if text.strip() == SCENARIO_BACK_BUTTON_TEXT:
        if await handle_back_response(messenger, db, employee):
            return "handled"
    handled = await handle_text_response(messenger, db, employee, type("MessageStub", (), {"text": text})())
    if handled:
        return "handled"
    if await handle_menu_navigation(messenger, db, employee, text):
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


async def handle_date_event(
    messenger: MessengerClient,
    db: Session,
    chat_user_id: str,
    username: Optional[str],
    callback_data: str,
) -> tuple[Literal["handled", "ignored", "unknown", "blocked"], object | None]:
    access = resolve_inbound_access(db, chat_user_id, username)
    if access.state != "ok" or access.employee is None:
        return access.state, None
    if not callback_data.startswith(DATE_CALLBACK_PREFIX):
        return "ignored", None
    parts = callback_data.split(":", 4)
    if len(parts) != 5:
        return "ignored", None
    _, _, step_id_raw, action, value = parts
    if not step_id_raw.isdigit():
        return "ignored", None
    result = await handle_date_response_by_step_id(
        messenger,
        db,
        access.employee,
        int(step_id_raw),
        action,
        value,
    )
    return ("handled" if result.handled else "ignored"), result


async def handle_back_event(
    messenger: MessengerClient,
    db: Session,
    chat_user_id: str,
    username: Optional[str],
) -> Literal["handled", "ignored", "unknown", "blocked"]:
    access = resolve_inbound_access(db, chat_user_id, username)
    if access.state != "ok" or access.employee is None:
        return access.state
    handled = await handle_back_response(messenger, db, access.employee)
    return "handled" if handled else "ignored"
