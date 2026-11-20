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


def manager_contact(db, employee, manager_id):
    if not employee or not employee.manager_employee_id:
        return None, "Руководитель не назначен в карточке сотрудника"
    if employee.manager_employee_id != manager_id:
        return None, "Руководитель изменился после подачи заявки"
    manager = db.get(Employee, manager_id)
    if not manager or manager.id == employee.id or manager.employee_stage not in {"staff", "adaptation", "ipr"}:
        return None, "Назначенный руководитель недоступен"
    if manager.is_bot_blocked:
        return None, "У руководителя заблокирован доступ к боту"
    chat = get_primary_chat_id(manager, db=db, channel="telegram")
    if not chat or not chat.isdecimal() or chat.startswith("0"):
        return None, "У руководителя нет подтверждённой привязки Telegram"
    owners = find_employees_by_channel_user_id(db, channel="telegram", external_user_id=chat)
    if [owner.id for owner in owners] != [manager.id]:
        return None, "Telegram руководителя нельзя однозначно сопоставить с его карточкой"
    return chat, None


def manager_chat(db, row):
    return manager_contact(db, db.get(Employee, row.employee_id), row.manager_id)[0]


async def deliver_pending(bot):
    from .vacation import LEAVE_LABELS
    for status, column in (("pending", "manager_notice"), ("pending_hr", "hr_notice")):
        flag = getattr(EmployeeVacationRequest, column)
        with SessionLocal() as db:
            rows = db.query(EmployeeVacationRequest.id, EmployeeVacationRequest.manager_revision)
            jobs = rows.filter(EmployeeVacationRequest.status == status, flag == "pending").order_by(
                EmployeeVacationRequest.id).limit(25).all()
        for row_id, revision in jobs:
            with SessionLocal() as db:
                result = db.execute(update(EmployeeVacationRequest).where(
                    EmployeeVacationRequest.id == row_id, EmployeeVacationRequest.status == status,
                    flag == "pending", EmployeeVacationRequest.manager_revision == revision,
                ).values({column: "sending"}))
                db.commit()
                if not result.rowcount:
                    continue
                row = db.get(EmployeeVacationRequest, row_id)
                if not row or row.status != status or row.manager_revision != revision:
                    continue
                keyboard = None
                if status == "pending":
                    chat = manager_chat(db, row)
                    employee = db.get(Employee, row.employee_id)
                    name = escape(employee.full_name or f"Карточка №{row.employee_id}") if employee else ""
                    message = (
                        f"Заявка: {LEAVE_LABELS.get(row.kind, row.kind)} — {name}\n"
                        f"{row.starts_on:%d.%m.%Y} – {row.ends_on:%d.%m.%Y} · рабочих дней: {row.workdays}"
                    )
                    if row.employee_comment:
                        message += f"\nКомментарий сотрудника: {escape(row.employee_comment)}"
                    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(text="Согласовать", callback_data=f"vacation:{row_id}:{revision}:yes"),
                        InlineKeyboardButton(text="Отклонить", callback_data=f"vacation:{row_id}:{revision}:no"),
                    ]])
                else:
                    hr = db.get(HrSettings, 1)
                    chat = (hr.telegram_user_id or "").strip() if hr else ""
                    if not chat.isdecimal() or chat.startswith("0") or not chat_id_allowed(db, chat):
                        chat = None
                    message = f"Заявка ({LEAVE_LABELS.get(row.kind, row.kind)}) ожидает решения HR. Откройте вкладку «Отпуск» в карточке №{row.employee_id}."
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
                    EmployeeVacationRequest.manager_revision == revision,
                ).values({column: outcome}))
                db.commit()


async def vacation_decision_callback(callback: CallbackQuery):
    from .vacation import decide

    match = re.fullmatch(r"vacation:([0-9]{1,18}):([0-9]{1,18}):(yes|no)", callback.data or "")
    if not match or not callback.message or callback.message.chat.type != ChatType.PRIVATE:
        return await callback.answer("Заявка недоступна", show_alert=True)
    if callback.message.chat.id != callback.from_user.id:
        return await callback.answer("Заявка недоступна", show_alert=True)
    with SessionLocal() as db:
        try:
            decide(db, int(match[1]), approved=match[3] == "yes", telegram_id=str(callback.from_user.id),
                   manager_revision=int(match[2]))
            db.commit()
        except LookupError:
            return await callback.answer("Заявка не найдена", show_alert=True)
        except (PermissionError, ValueError) as exc:
            return await callback.answer(str(exc), show_alert=True)
    await callback.answer("Решение сохранено", show_alert=True)
