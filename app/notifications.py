from __future__ import annotations

from aiogram import Bot

from .database import SessionLocal
from .models import Employee, HrSettings


NOTIFY_SCENARIO_COMPLETED = "scenario_completed"
NOTIFY_TEST_TASK_RECEIVED = "test_task_received"
NOTIFY_USER_ACTIONS = "user_actions"

def _employee_label(employee: Employee) -> str:
    name = (employee.full_name or "").strip()
    if name:
        return f"{name} (ID {employee.id})"
    return f"ФИО не указано (ID {employee.id})"


async def notify_hr(bot: Bot, text: str) -> None:
    with SessionLocal() as db:
        settings = db.get(HrSettings, 1)
        recipients = _notification_recipients(settings)
    if not recipients:
        return
    for chat_id in recipients:
        try:
            await bot.send_message(chat_id=chat_id, text=text)
        except Exception:
            continue


def _notification_recipients(settings: HrSettings | None) -> list[str]:
    if not settings:
        return []
    raw_values = []
    if settings.telegram_user_id:
        raw_values.append(settings.telegram_user_id)
    if settings.notification_recipient_ids:
        raw_values.extend(
            chunk.strip()
            for chunk in settings.notification_recipient_ids.replace("\n", ",").split(",")
        )
    recipients: list[str] = []
    for value in raw_values:
        normalized = (value or "").strip()
        if normalized and normalized not in recipients:
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


async def notify_hr_by_kind(bot: Bot, text: str, kind: str) -> None:
    with SessionLocal() as db:
        settings = db.get(HrSettings, 1)
        if not _is_notification_enabled(settings, kind):
            return
        recipients = _notification_recipients(settings)
    if not recipients:
        return
    for chat_id in recipients:
        try:
            await bot.send_message(chat_id=chat_id, text=text)
        except Exception:
            continue


async def notify_hr_new_employee(bot: Bot, employee: Employee) -> None:
    await notify_hr_by_kind(
        bot,
        f"Новый сотрудник зарегистрирован в боте: {_employee_label(employee)}.",
        NOTIFY_USER_ACTIONS,
    )


async def notify_hr_stage(bot: Bot, employee: Employee, stage_key: str) -> None:
    await notify_hr_by_kind(
        bot,
        f"Сотрудник {_employee_label(employee)} прошёл этап: {stage_key}.",
        NOTIFY_SCENARIO_COMPLETED,
    )


async def notify_hr_test_task_received(bot: Bot, employee: Employee, filename: str) -> None:
    await notify_hr_by_kind(
        bot,
        f"Кандидат {_employee_label(employee)} отправил тестовое задание: {filename}.",
        NOTIFY_TEST_TASK_RECEIVED,
    )
