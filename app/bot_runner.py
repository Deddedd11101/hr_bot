import asyncio
from datetime import datetime
from typing import Optional

from aiohttp import ClientError
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramNetworkError
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, KeyboardButton, Message, ReplyKeyboardMarkup
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .config import settings
from .database import SessionLocal, init_db
from .file_storage import build_employee_file_path
from .models import BotMenuButton, BotMenuSet, Employee, EmployeeFile, HrSettings, ScenarioTemplate
from .notifications import notify_hr_new_employee, notify_hr_test_task_received
from .scenario_engine import CALLBACK_PREFIX, handle_button_response_by_step_id, handle_file_response, handle_text_response, start_scenario
from .scheduler import schedule_all_employees


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


async def _start_registration_scenarios(bot: Bot, db, employee: Employee) -> None:
    scenarios = (
        db.query(ScenarioTemplate)
        .filter(ScenarioTemplate.trigger_mode == "bot_registration")
        .order_by(ScenarioTemplate.id)
        .all()
    )
    for scenario in scenarios:
        await start_scenario(bot, db, employee, scenario.scenario_key)


def _telegram_username(user) -> Optional[str]:
    username = getattr(user, "username", None)
    return username.strip() if isinstance(username, str) and username.strip() else None


def _default_menu_set(db) -> Optional[BotMenuSet]:
    hr_settings = db.get(HrSettings, 1)
    if hr_settings and hr_settings.default_menu_set_id:
        return db.get(BotMenuSet, hr_settings.default_menu_set_id)
    return (
        db.query(BotMenuSet)
        .order_by(BotMenuSet.sort_order, BotMenuSet.id)
        .first()
    )


def _current_menu_set(db, employee: Employee) -> Optional[BotMenuSet]:
    if employee.current_menu_set_id:
        current_set = db.get(BotMenuSet, employee.current_menu_set_id)
        if current_set:
            return current_set
    default_set = _default_menu_set(db)
    if default_set:
        employee.current_menu_set_id = default_set.id
        db.commit()
    return default_set


def _menu_buttons(db, menu_set_id: int) -> list[BotMenuButton]:
    return (
        db.query(BotMenuButton)
        .filter(BotMenuButton.menu_set_id == menu_set_id)
        .order_by(BotMenuButton.sort_order, BotMenuButton.id)
        .all()
    )


def _menu_keyboard(db, employee: Employee) -> Optional[ReplyKeyboardMarkup]:
    menu_set = _current_menu_set(db, employee)
    if not menu_set:
        return None
    buttons = [button for button in _menu_buttons(db, menu_set.id) if button.label.strip()]
    if not buttons:
        return None
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=button.label)] for button in buttons],
        resize_keyboard=True,
    )


async def _send_menu_keyboard(bot: Bot, db, employee: Employee, text: str) -> None:
    if not employee.telegram_user_id:
        return
    keyboard = _menu_keyboard(db, employee)
    if not keyboard:
        return
    await bot.send_message(chat_id=employee.telegram_user_id, text=text, reply_markup=keyboard)


async def _handle_menu_button(bot: Bot, db, employee: Employee, text: str) -> bool:
    menu_set = _current_menu_set(db, employee)
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
        scenario = (
            db.query(ScenarioTemplate)
            .filter(ScenarioTemplate.scenario_key == button.scenario_key)
            .first()
        )
        if not scenario:
            await _send_menu_keyboard(bot, db, employee, "Этот сценарий сейчас недоступен.")
            return True
        started = await start_scenario(bot, db, employee, scenario.scenario_key)
        if not started:
            await _send_menu_keyboard(bot, db, employee, "Не удалось запустить этот сценарий.")
        return True

    if button.action_type == "open_set" and button.target_menu_set_id:
        target_set = db.get(BotMenuSet, button.target_menu_set_id)
        if not target_set:
            await _send_menu_keyboard(bot, db, employee, "Этот раздел меню сейчас недоступен.")
            return True
        employee.current_menu_set_id = target_set.id
        db.commit()
        await _send_menu_keyboard(bot, db, employee, target_set.description or f"Открыт раздел «{target_set.title}».")
        return True

    await _send_menu_keyboard(bot, db, employee, "Эта кнопка пока неактивна.")
    return True


async def on_start(message: Message) -> None:
    user = message.from_user
    if not user:
        await message.answer("Не удалось определить ваш Telegram ID. Попробуйте ещё раз.")
        return

    user_id_str = str(user.id)
    username = _telegram_username(user)
    with SessionLocal() as db:
        employee = db.query(Employee).filter(Employee.telegram_user_id == user_id_str).first()
        if employee:
            employee.telegram_user_id = user_id_str
            employee.telegram_username = username
            employee.is_flow_scheduled = False
            db.commit()
            await message.answer("Привет! Я HR-бот.\nЯ обновил привязку вашего Telegram и перепланировал уведомления.")
            await _send_menu_keyboard(message.bot, db, employee, "Меню обновлено. Выберите действие.")
            return

        employee = Employee(
            full_name=None,
            telegram_user_id=user_id_str,
            telegram_username=username,
            first_workday=None,
            created_at=datetime.utcnow(),
            is_flow_scheduled=False,
            candidate_status="new",
        )
        db.add(employee)
        db.commit()
        db.refresh(employee)
        try:
            await notify_hr_new_employee(message.bot, employee)
        except Exception:
            pass
        await _start_registration_scenarios(message.bot, db, employee)
        await _send_menu_keyboard(message.bot, db, employee, "Меню готово. Выберите действие.")


async def on_document(message: Message, bot: Bot) -> None:
    document = message.document
    user = message.from_user
    if not document or not user:
        return

    with SessionLocal() as db:
        username = _telegram_username(user)
        employee = db.query(Employee).filter(Employee.telegram_user_id == str(user.id)).first()
        if not employee:
            employee = Employee(
                full_name=None,
                telegram_user_id=str(user.id),
                telegram_username=username,
                first_workday=None,
                created_at=datetime.utcnow(),
                is_flow_scheduled=False,
                candidate_status="new",
            )
            db.add(employee)
            db.commit()
            db.refresh(employee)
            try:
                await notify_hr_new_employee(bot, employee)
            except Exception:
                pass
            await _start_registration_scenarios(bot, db, employee)
        elif employee.telegram_username != username:
            employee.telegram_username = username
            db.commit()

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
        db.commit()
        db.refresh(db_file)

        if db_file.category == "test_result":
            try:
                await notify_hr_test_task_received(bot, employee, db_file.original_filename)
            except Exception:
                pass

        handled = await handle_file_response(bot, db, employee, db_file)
        if handled:
            return

    await message.answer("Файл получен и сохранен в вашей карточке.")


async def on_candidate_text(message: Message) -> None:
    user = message.from_user
    if not user or not message.text:
        return

    with SessionLocal() as db:
        employee = db.query(Employee).filter(Employee.telegram_user_id == str(user.id)).first()
        if not employee:
            return
        username = _telegram_username(user)
        if employee.telegram_username != username:
            employee.telegram_username = username
            db.commit()
        handled = await handle_text_response(message.bot, db, employee, message)
        if handled:
            return
        menu_handled = await _handle_menu_button(message.bot, db, employee, message.text)
    if not menu_handled:
        await message.answer("Сообщение получено. Если это ответ на шаг сценария, HR обработает его в админке.")


async def on_scenario_button(callback: CallbackQuery) -> None:
    user = callback.from_user
    if not user or not callback.data or not callback.data.startswith(CALLBACK_PREFIX):
        return

    _, step_id, option_index = callback.data.split(":", 2)
    with SessionLocal() as db:
        employee = db.query(Employee).filter(Employee.telegram_user_id == str(user.id)).first()
        if not employee:
            await callback.answer("Карточка сотрудника не найдена.", show_alert=True)
            return
        username = _telegram_username(user)
        if employee.telegram_username != username:
            employee.telegram_username = username
            db.commit()
        handled = await handle_button_response_by_step_id(
            callback.bot,
            db,
            employee,
            int(step_id),
            int(option_index),
        )
    if handled:
        await callback.answer("Принято")
    else:
        await callback.answer()


async def main() -> None:
    if not settings.TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN не задан. Укажите его в .env")

    init_db()

    bot = Bot(
        token=settings.TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    dp.message.register(on_start, CommandStart())
    dp.callback_query.register(
        on_scenario_button,
        lambda callback: callback.data is not None and callback.data.startswith(CALLBACK_PREFIX),
    )
    dp.message.register(
        on_candidate_text,
        lambda message: message.text is not None and not message.text.startswith("/"),
    )
    dp.message.register(on_document, lambda message: message.document is not None)

    scheduler = AsyncIOScheduler(timezone=settings.TIMEZONE)
    scheduler.start()

    scheduler.add_job(
        schedule_all_employees,
        "interval",
        seconds=10 if settings.DEMO_MODE else 60,
        args=[scheduler, bot],
        id="scan_employees",
        replace_existing=True,
    )

    print("HR Telegram bot is running. Press Ctrl+C to stop.")

    try:
        reconnect_delay_seconds = 5
        while True:
            try:
                await dp.start_polling(bot)
                break
            except (TelegramNetworkError, ClientError, asyncio.TimeoutError, OSError) as exc:
                print(
                    f"Telegram connection error: {exc}. "
                    f"Retrying in {reconnect_delay_seconds} seconds..."
                )
                await asyncio.sleep(reconnect_delay_seconds)
    finally:
        if scheduler.running:
            scheduler.shutdown(wait=False)
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
