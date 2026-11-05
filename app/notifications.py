from __future__ import annotations

import logging

from .database import SessionLocal
from .hr_linking import is_numeric_telegram_id
from .messaging import as_messenger
from .models import Employee, HrSettings
from .staff_email_verification import chat_id_allowed


logger = logging.getLogger(__name__)

NOTIFY_SCENARIO_COMPLETED = "scenario_completed"
NOTIFY_TEST_TASK_RECEIVED = "test_task_received"
NOTIFY_USER_ACTIONS = "user_actions"

def _employee_label(employee: Employee) -> str:
    name = (employee.full_name or "").strip()
    if name:
        return f"{name} (ID {employee.id})"
    return f"ФИО не указано (ID {employee.id})"


async def notify_hr(messenger_or_bot, text: str) -> None:
    messenger = as_messenger(messenger_or_bot)
    with SessionLocal() as db:
        settings = db.get(HrSettings, 1)
        recipients = _notification_recipients(settings, db=db)
    if not recipients:
        return
    for chat_id in recipients:
        try:
            await messenger.send_text(chat_id=chat_id, text=text)
        except Exception:
            continue


def _notification_recipients(settings: HrSettings | None, *, db=None, observers_only=False) -> list[str]:
    if not settings:
        return []
    raw_values = []
    if not observers_only and is_numeric_telegram_id(settings.telegram_user_id):
        raw_values.append(settings.telegram_user_id)
    if settings.notification_recipient_ids:
        raw_values.extend(
            chunk.strip()
            for chunk in settings.notification_recipient_ids.replace("\n", ",").split(",")
        )
    recipients: list[str] = []
    for value in raw_values:
        normalized = (value or "").strip()
        observer = normalized.startswith("observer:")
        if observers_only and not observer:
            continue
        if observer:
            normalized = normalized.removeprefix("observer:")
        if normalized.startswith("employee:"):
            employee_id = normalized.removeprefix("employee:")
            person = db.get(Employee, int(employee_id)) if db is not None and employee_id.isdigit() else None
            if not person or person.is_bot_blocked or person.employee_stage not in {"staff", "adaptation", "ipr"}:
                continue
            from .messaging.identity import get_primary_chat_id
            normalized = get_primary_chat_id(person, db=db)
        if (is_numeric_telegram_id(normalized) and normalized not in recipients
                and (db is None or chat_id_allowed(db, normalized))):
            recipients.append(normalized)
    return recipients


def _is_notification_enabled(settings: HrSettings | None, kind: str) -> bool:
    if not settings:
        return False
    if kind == NOTIFY_SCENARIO_COMPLETED:
        return bool(settings.notify_scenario_completed)
    if kind == NOTIFY_TEST_TASK_RECEIVED:
        return bool(settings.notify_test_task_received)
    if kind == NOTIFY_USER_ACTIONS:
        return bool(settings.notify_user_actions)
    return True


async def notify_hr_by_kind(messenger_or_bot, text: str, kind: str) -> None:
    messenger = as_messenger(messenger_or_bot)
    with SessionLocal() as db:
        settings = db.get(HrSettings, 1)
        if not _is_notification_enabled(settings, kind):
            return
        recipients = _notification_recipients(settings, db=db)
    if not recipients:
        return
    for chat_id in recipients:
        try:
            await messenger.send_text(chat_id=chat_id, text=text)
        except Exception:
            continue


async def notify_hr_new_employee(messenger_or_bot, employee: Employee) -> None:
    await notify_hr_by_kind(
        messenger_or_bot,
        f"Новый сотрудник зарегистрирован в боте: {_employee_label(employee)}.",
        NOTIFY_USER_ACTIONS,
    )


async def notify_hr_stage(messenger_or_bot, employee: Employee, stage_key: str) -> None:
    logger.info(
        "Suppressed legacy scenario stage notification: employee_id=%s stage_key=%s",
        employee.id,
        stage_key,
    )


async def notify_hr_test_task_received(messenger_or_bot, employee: Employee, filename: str) -> None:
    await notify_hr_by_kind(
        messenger_or_bot,
        f"Кандидат {_employee_label(employee)} отправил тестовое задание: {filename}.",
        NOTIFY_TEST_TASK_RECEIVED,
    )
