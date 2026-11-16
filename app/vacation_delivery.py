import logging
import re
from html import escape

from aiogram.enums import ChatType
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import update

from .database import SessionLocal
from .messaging.identity import find_employees_by_channel_user_id, get_primary_chat_id
from .models import Employee, EmployeeVacationRequest, HrSettings
from .staff_email_verification import chat_id_allowed

logger = logging.getLogger(__name__)


def manager_chat(db, row):
    employee = db.get(Employee, row.employee_id)
    manager = db.get(Employee, row.manager_id) if row.manager_id else None
    if (not employee or not manager or manager.id == employee.id
            or employee.manager_employee_id != manager.id or manager.is_bot_blocked
            or manager.employee_stage not in {"staff", "adaptation", "ipr"}):
        return None
    chat = get_primary_chat_id(manager, db=db, channel="telegram")
    if not chat or not chat.isdecimal() or chat.startswith("0"):
        return None
    owners = find_employees_by_channel_user_id(db, channel="telegram", external_user_id=chat)
    return chat if [owner.id for owner in owners] == [manager.id] else None


async def deliver_pending(bot):
    for status, column in (("pending", "manager_notice"), ("pending_hr", "hr_notice")):
        flag = getattr(EmployeeVacationRequest, column)
        with SessionLocal() as db:
            ids = [r.id for r in db.query(EmployeeVacationRequest.id)
                   .filter(EmployeeVacationRequest.status == status, flag == "pending")
                   .order_by(EmployeeVacationRequest.id).limit(25)]
        for row_id in ids:
            with SessionLocal() as db:
                result = db.execute(update(EmployeeVacationRequest).where(
                    EmployeeVacationRequest.id == row_id, EmployeeVacationRequest.status == status,
                    flag == "pending",
                ).values({column: "sending"}))
                db.commit()
                if not result.rowcount:
                    continue
                row = db.get(EmployeeVacationRequest, row_id)
                if not row or row.status != status:
                    continue
                keyboard = None
                if status == "pending":
                    chat = manager_chat(db, row)
                    employee = db.get(Employee, row.employee_id)
                    name = escape(employee.full_name or f"Карточка №{row.employee_id}") if employee else ""
                    message = (
                        f"Заявка на отпуск: {name}\n"
                        f"{row.starts_on:%d.%m.%Y} – {row.ends_on:%d.%m.%Y} · рабочих дней: {row.workdays}"
                    )
                    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(text="Согласовать", callback_data=f"vacation:{row_id}:yes"),
                        InlineKeyboardButton(text="Отклонить", callback_data=f"vacation:{row_id}:no"),
                    ]])
                else:
                    hr = db.get(HrSettings, 1)
                    chat = (hr.telegram_user_id or "").strip() if hr else ""
                    if not chat.isdecimal() or chat.startswith("0") or not chat_id_allowed(db, chat):
                        chat = None
                    message = f"Заявка на отпуск ожидает решения HR. Откройте вкладку «Отпуск» в карточке №{row.employee_id}."
            outcome = "unavailable"
            if chat:
                try:
                    await bot.send_message(int(chat), message, reply_markup=keyboard)
                    outcome = "sent"
                except Exception as exc:
                    logger.warning("Vacation notice failed: request=%s error=%s", row_id, type(exc).__name__)
                    outcome = "failed"
            with SessionLocal() as db:
                db.execute(update(EmployeeVacationRequest).where(
                    EmployeeVacationRequest.id == row_id, flag == "sending",
                ).values({column: outcome}))
                db.commit()


async def vacation_decision_callback(callback: CallbackQuery):
    from .vacation import decide

    match = re.fullmatch(r"vacation:([0-9]{1,18}):(yes|no)", callback.data or "")
    if not match or not callback.message or callback.message.chat.type != ChatType.PRIVATE:
        return await callback.answer("Заявка недоступна", show_alert=True)
    if callback.message.chat.id != callback.from_user.id:
        return await callback.answer("Заявка недоступна", show_alert=True)
    with SessionLocal() as db:
        try:
            decide(db, int(match[1]), approved=match[2] == "yes", telegram_id=str(callback.from_user.id))
            db.commit()
        except LookupError:
            return await callback.answer("Заявка не найдена", show_alert=True)
        except (PermissionError, ValueError) as exc:
            return await callback.answer(str(exc), show_alert=True)
    await callback.answer("Решение сохранено", show_alert=True)
