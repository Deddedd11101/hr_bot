from __future__ import annotations

from aiogram import Bot

from .database import SessionLocal
from .models import Employee, HrSettings

FINAL_STAGE_KEYS = {
    # Recruitment flow terminal states
    "recruitment_salary_received",
    "recruitment_consent_no",
    # First day flow
    "feedback_form_18",
    # Probation flows
    "first_week_meeting",
    "mid_meeting",
    "end_meeting",
    # Manual single-step flows
    "mid_feedback",
    "end_feedback",
    "end_summary",
}


def _employee_label(employee: Employee) -> str:
    name = (employee.full_name or "").strip()
    if name:
        return f"{name} (ID {employee.id})"
    return f"ФИО не указано (ID {employee.id})"


async def notify_hr(bot: Bot, text: str) -> None:
    with SessionLocal() as db:
        settings = db.get(HrSettings, 1)
        hr_chat_id = settings.telegram_user_id if settings else None
    if not hr_chat_id:
        return
    await bot.send_message(chat_id=hr_chat_id, text=text)


async def notify_hr_new_employee(bot: Bot, employee: Employee) -> None:
    await notify_hr(
        bot,
        f"Новый сотрудник зарегистрирован в боте: {_employee_label(employee)}.",
    )


async def notify_hr_stage(bot: Bot, employee: Employee, stage_key: str) -> None:
    if stage_key not in FINAL_STAGE_KEYS:
        return
    await notify_hr(
        bot,
        f"Сотрудник {_employee_label(employee)} прошёл этап: {stage_key}.",
    )
