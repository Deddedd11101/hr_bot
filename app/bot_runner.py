import asyncio
from datetime import datetime
from typing import Optional

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .config import settings
from .database import init_db, SessionLocal
from .flow_templates import get_step_text
from .file_storage import build_employee_file_path
from .models import Employee, EmployeeFile
from .notifications import notify_hr_new_employee, notify_hr_stage
from .recruitment_flow import (
    ASK_FULL_NAME_MESSAGE,
    CALLBACK_CONSENT_NO,
    CALLBACK_CONSENT_YES,
    CALLBACK_ROLE_ANALYST,
    CALLBACK_ROLE_DESIGNER,
    CALLBACK_ROLE_PM,
    CONSENT_DECLINED_MESSAGE,
    CONSENT_MESSAGE,
    STATUS_DECLINED,
    STATUS_WAIT_FULL_NAME,
    STATUS_PRIMARY_DONE,
    STATUS_WAIT_POSITION,
    STATUS_WAIT_RESUME,
    STATUS_WAIT_SALARY,
    STATUS_WAIT_CONSENT,
    recruitment_consent_keyboard,
    recruitment_role_keyboard,
)
from .scheduler import schedule_all_employees


async def on_start(message: Message) -> None:
    """
    Привязка Telegram‑пользователя к сотруднику + перезапуск флоу.

    Логика:
    - берём Telegram user_id из message.from_user.id;
    - если сотрудник уже есть — перепривязываем и перепланируем флоу;
    - если сотрудника нет — создаём черновик карточки в админке;
    - сбрасываем флаг is_flow_scheduled = False, чтобы флоу был
      заново запланирован планировщиком.
    """
    user = message.from_user
    if not user:
        await message.answer("Не удалось определить ваш Telegram ID. Попробуйте ещё раз.")
        return

    user_id_str = str(user.id)

    with SessionLocal() as db:
        employee = db.query(Employee).filter(Employee.telegram_user_id == user_id_str).first()

        if employee:
            employee.telegram_user_id = user_id_str
            employee.is_flow_scheduled = False  # важно: дать планировщику повод перепланировать флоу
            db.commit()
            await message.answer(
                "Привет! Я HR‑бот.\n"
                "Я обновил привязку вашего Telegram и перепланировал уведомления.",
            )
            return

        new_employee = Employee(
            full_name=None,
            telegram_user_id=user_id_str,
            first_workday=None,
            created_at=datetime.utcnow(),
            is_flow_scheduled=False,
            candidate_status=STATUS_WAIT_CONSENT,
        )
        db.add(new_employee)
        db.commit()
        db.refresh(new_employee)
        try:
            await notify_hr_new_employee(message.bot, new_employee)
        except Exception:
            pass

    await message.answer(
        get_step_text("recruitment_consent_request", CONSENT_MESSAGE),
        reply_markup=recruitment_consent_keyboard(),
    )


def _detect_category_from_caption(caption: Optional[str]) -> str:
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


async def on_document(message: Message, bot: Bot) -> None:
    document = message.document
    user = message.from_user
    if not document or not user:
        return

    user_id_str = str(user.id)
    with SessionLocal() as db:
        employee = db.query(Employee).filter(Employee.telegram_user_id == user_id_str).first()
        if not employee:
            employee = Employee(
                full_name=None,
                telegram_user_id=user_id_str,
                first_workday=None,
                created_at=datetime.utcnow(),
                is_flow_scheduled=False,
                candidate_status=STATUS_WAIT_CONSENT,
            )
            db.add(employee)
            db.flush()
            try:
                await notify_hr_new_employee(bot, employee)
            except Exception:
                pass
            await bot.send_message(
                chat_id=user_id_str,
                text=get_step_text("recruitment_consent_request", CONSENT_MESSAGE),
                reply_markup=recruitment_consent_keyboard(),
            )

        file_info = await bot.get_file(document.file_id)
        original_name = document.file_name or f"{document.file_unique_id}.bin"
        destination = build_employee_file_path(employee.id, original_name)
        await bot.download_file(file_info.file_path, destination=destination)

        db_file = EmployeeFile(
            employee_id=employee.id,
            direction="inbound",
            category=_detect_category_from_caption(message.caption),
            telegram_file_id=document.file_id,
            telegram_file_unique_id=document.file_unique_id,
            original_filename=original_name,
            stored_path=str(destination),
            mime_type=document.mime_type,
            file_size=document.file_size,
            created_at=datetime.utcnow(),
        )
        db.add(db_file)

        if employee.candidate_status == STATUS_WAIT_RESUME:
            if db_file.category == "candidate_file":
                db_file.category = "resume"
            employee.candidate_status = STATUS_WAIT_SALARY
            db.commit()
            await message.answer(get_step_text("recruitment_ask_salary", "Какой уровень дохода для тебя комфортен? Можешь указать диапазон."))
            return

        if db_file.category == "resume" and not employee.candidate_status:
            employee.candidate_status = STATUS_WAIT_SALARY

        db.commit()

    await message.answer(
        "Файл получен и сохранён в вашей карточке. Если нужно, отправьте следующий документ.",
    )


async def on_recruitment_consent(callback: CallbackQuery) -> None:
    user = callback.from_user
    if not user:
        return

    with SessionLocal() as db:
        employee = db.query(Employee).filter(Employee.telegram_user_id == str(user.id)).first()
        if not employee:
            await callback.answer("Карточка сотрудника не найдена.", show_alert=True)
            return

        if callback.data == CALLBACK_CONSENT_YES:
            employee.personal_data_consent = True
            employee.candidate_status = STATUS_WAIT_FULL_NAME
            db.commit()
            await callback.message.answer(
                get_step_text("recruitment_ask_full_name", ASK_FULL_NAME_MESSAGE)
            )
            await callback.answer("Согласие принято")
            return

        if callback.data == CALLBACK_CONSENT_NO:
            employee.personal_data_consent = False
            employee.candidate_status = STATUS_DECLINED
            db.commit()
            await callback.message.answer(CONSENT_DECLINED_MESSAGE)
            try:
                await notify_hr_stage(callback.bot, employee, "recruitment_consent_no")
            except Exception:
                pass
            await callback.answer("Принято")
            return

    await callback.answer()


async def on_recruitment_role(callback: CallbackQuery) -> None:
    user = callback.from_user
    if not user:
        return

    role_map = {
        CALLBACK_ROLE_DESIGNER: "Дизайнер",
        CALLBACK_ROLE_PM: "РМ",
        CALLBACK_ROLE_ANALYST: "Аналитик",
    }
    selected_role = role_map.get(callback.data or "")
    if not selected_role:
        await callback.answer()
        return

    with SessionLocal() as db:
        employee = db.query(Employee).filter(Employee.telegram_user_id == str(user.id)).first()
        if not employee:
            await callback.answer("Карточка сотрудника не найдена.", show_alert=True)
            return

        if employee.candidate_status != STATUS_WAIT_POSITION:
            await callback.answer()
            return

        employee.desired_position = selected_role
        employee.candidate_status = STATUS_WAIT_RESUME
        db.commit()

    await callback.message.answer(
        get_step_text("recruitment_ask_resume", "Пришли, пожалуйста, своё резюме файлом (PDF / DOC / DOCX).")
    )
    await callback.answer()


async def on_candidate_text(message: Message) -> None:
    user = message.from_user
    if not user or not message.text:
        return

    with SessionLocal() as db:
        employee = db.query(Employee).filter(Employee.telegram_user_id == str(user.id)).first()
        if not employee:
            return

        text = message.text.strip()
        if employee.candidate_status == STATUS_WAIT_FULL_NAME:
            employee.full_name = text
            employee.candidate_status = STATUS_WAIT_POSITION
            db.commit()
            await message.answer(
                get_step_text("recruitment_ask_position", "На какую должность ты рассматриваешься?"),
                reply_markup=recruitment_role_keyboard(),
            )
            return

        if employee.candidate_status == STATUS_WAIT_SALARY:
            employee.salary_expectation = text
            employee.candidate_status = STATUS_PRIMARY_DONE
            db.commit()
            await message.answer(
                get_step_text(
                    "recruitment_primary_done",
                    "Спасибо! Мы получили первичные данные.\nДальше HR проверит информацию и вернётся к тебе со следующим шагом.",
                )
            )
            try:
                await notify_hr_stage(message.bot, employee, "recruitment_salary_received")
            except Exception:
                pass
            return


async def main() -> None:
    if not settings.TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN не задан. Укажите его в .env")

    # Инициализируем базу
    init_db()

    bot = Bot(
        token=settings.TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    # Хэндлер /start
    dp.message.register(on_start, CommandStart())
    dp.callback_query.register(
        on_recruitment_consent,
        lambda callback: callback.data in {CALLBACK_CONSENT_YES, CALLBACK_CONSENT_NO},
    )
    dp.callback_query.register(
        on_recruitment_role,
        lambda callback: callback.data
        in {CALLBACK_ROLE_DESIGNER, CALLBACK_ROLE_PM, CALLBACK_ROLE_ANALYST},
    )
    dp.message.register(
        on_candidate_text,
        lambda message: message.text is not None and not message.text.startswith("/"),
    )
    dp.message.register(on_document, lambda message: message.document is not None)

    # Планировщик
    scheduler = AsyncIOScheduler(timezone=settings.TIMEZONE)
    scheduler.start()

    # Периодически проверяем БД на наличие новых сотрудников без флоу
    if settings.DEMO_MODE:
        scheduler.add_job(
            schedule_all_employees,
            "interval",
            seconds=10,
            args=[scheduler, bot],
            id="scan_employees",
            replace_existing=True,
        )
    else:
        scheduler.add_job(
            schedule_all_employees,
            "interval",
            minutes=1,
            args=[scheduler, bot],
            id="scan_employees",
            replace_existing=True,
        )

    print("HR Telegram bot is running. Press Ctrl+C to stop.")

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
