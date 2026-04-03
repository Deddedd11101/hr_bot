import asyncio
from typing import Optional

from aiohttp import ClientError
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramNetworkError
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .config import settings
from .database import SessionLocal, init_db
from .file_storage import build_employee_file_path
from .messaging import create_telegram_messenger
from .messaging.service import (
    detect_category_from_caption,
    ensure_employee_for_chat,
    handle_button_event,
    handle_saved_document,
    handle_start_command,
    handle_text_event,
    save_incoming_document,
)
from .scenario_engine import CALLBACK_PREFIX
from .scheduler import schedule_all_employees


def _telegram_username(user) -> Optional[str]:
    username = getattr(user, "username", None)
    return username.strip() if isinstance(username, str) and username.strip() else None


async def on_start(message: Message) -> None:
    user = message.from_user
    if not user:
        await message.answer("Не удалось определить ваш Telegram ID. Попробуйте ещё раз.")
        return

    user_id_str = str(user.id)
    username = _telegram_username(user)
    with SessionLocal() as db:
        messenger = create_telegram_messenger(settings.TELEGRAM_BOT_TOKEN)
        await handle_start_command(messenger, db, user_id_str, username)
        await messenger.close()


async def on_document(message: Message, bot: Bot) -> None:
    document = message.document
    user = message.from_user
    if not document or not user:
        return

    with SessionLocal() as db:
        messenger = create_telegram_messenger(settings.TELEGRAM_BOT_TOKEN)
        username = _telegram_username(user)
        employee, _ = await ensure_employee_for_chat(messenger, db, str(user.id), username)
        file_info = await bot.get_file(document.file_id)
        original_name = document.file_name or f"{document.file_unique_id}.bin"
        destination = build_employee_file_path(employee.id, original_name)
        await bot.download_file(file_info.file_path, destination=destination)
        employee, db_file, _ = await save_incoming_document(
            db,
            messenger,
            str(user.id),
            username,
            original_name=original_name,
            stored_path=str(destination),
            category=detect_category_from_caption(message.caption),
            mime_type=document.mime_type,
            file_size=document.file_size,
            external_file_id=document.file_id,
            external_unique_id=document.file_unique_id,
        )
        handled = await handle_saved_document(messenger, db, employee, db_file)
        await messenger.close()
        if handled:
            return

    await message.answer("Файл получен и сохранен в вашей карточке.")


async def on_candidate_text(message: Message) -> None:
    user = message.from_user
    if not user or not message.text:
        return

    with SessionLocal() as db:
        messenger = create_telegram_messenger(settings.TELEGRAM_BOT_TOKEN)
        username = _telegram_username(user)
        handled = await handle_text_event(messenger, db, str(user.id), username, message.text)
        await messenger.close()
        if handled:
            return
    await message.answer("Сообщение получено. Если это ответ на шаг сценария, HR обработает его в админке.")


async def on_scenario_button(callback: CallbackQuery) -> None:
    user = callback.from_user
    if not user or not callback.data or not callback.data.startswith(CALLBACK_PREFIX):
        return

    _, step_id, option_index = callback.data.split(":", 2)
    with SessionLocal() as db:
        messenger = create_telegram_messenger(settings.TELEGRAM_BOT_TOKEN)
        handled = await handle_button_event(
            messenger,
            db,
            str(user.id),
            _telegram_username(user),
            int(step_id),
            int(option_index),
        )
        await messenger.close()
        if handled is None:
            await callback.answer("Карточка сотрудника не найдена.", show_alert=True)
            return
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
