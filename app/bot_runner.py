import asyncio
from typing import Optional

from aiohttp import ClientError
from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramNetworkError
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .config import settings
from .database import SessionLocal, init_db
from .file_storage import build_employee_file_path
from .messaging import TelegramMessenger, create_telegram_bot
from .messaging.service import (
    BLOCKED_USER_TEXT,
    DATE_CALLBACK_PREFIX,
    UNKNOWN_USER_TEXT,
    detect_category_from_caption,
    handle_back_event,
    handle_button_event,
    handle_date_event,
    handle_saved_document,
    handle_start_command,
    handle_text_event,
    resolve_inbound_access,
    save_incoming_file,
)
from .scenario_engine import CALLBACK_PREFIX
from .scheduler import schedule_all_employees


def _telegram_username(user) -> Optional[str]:
    username = getattr(user, "username", None)
    return username.strip() if isinstance(username, str) and username.strip() else None


async def on_start(message: Message, bot: Bot) -> None:
    user = message.from_user
    if not user:
        await message.answer("Не удалось определить ваш Telegram ID. Попробуйте ещё раз.")
        return

    user_id_str = str(user.id)
    username = _telegram_username(user)
    with SessionLocal() as db:
        messenger = TelegramMessenger(bot)
        await handle_start_command(messenger, db, user_id_str, username)


async def on_document(message: Message, bot: Bot) -> None:
    document = message.document
    user = message.from_user
    if not document or not user:
        return

    with SessionLocal() as db:
        messenger = TelegramMessenger(bot)
        username = _telegram_username(user)
        access = resolve_inbound_access(db, str(user.id), username)
        if access.state == "unknown":
            await messenger.send_text(chat_id=str(user.id), text=UNKNOWN_USER_TEXT)
            return
        if access.state == "blocked":
            await messenger.send_text(chat_id=str(user.id), text=BLOCKED_USER_TEXT)
            return
        employee = access.employee
        if employee is None:
            return
        file_info = await bot.get_file(document.file_id)
        original_name = document.file_name or f"{document.file_unique_id}.bin"
        destination = build_employee_file_path(employee.id, original_name)
        await bot.download_file(file_info.file_path, destination=destination)
        employee, db_file, save_state = await save_incoming_file(
            db,
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
        if save_state != "saved" or employee is None or db_file is None:
            return
        handled = await handle_saved_document(messenger, db, employee, db_file)
        if handled:
            return


async def on_photo(message: Message, bot: Bot) -> None:
    photos = message.photo or []
    user = message.from_user
    if not photos or not user:
        return

    with SessionLocal() as db:
        messenger = TelegramMessenger(bot)
        username = _telegram_username(user)
        access = resolve_inbound_access(db, str(user.id), username)
        if access.state == "unknown":
            await messenger.send_text(chat_id=str(user.id), text=UNKNOWN_USER_TEXT)
            return
        if access.state == "blocked":
            await messenger.send_text(chat_id=str(user.id), text=BLOCKED_USER_TEXT)
            return
        employee = access.employee
        if employee is None:
            return
        photo = photos[-1]
        file_info = await bot.get_file(photo.file_id)
        original_name = f"{photo.file_unique_id}.jpg"
        destination = build_employee_file_path(employee.id, original_name)
        await bot.download_file(file_info.file_path, destination=destination)
        employee, db_file, save_state = await save_incoming_file(
            db,
            str(user.id),
            username,
            original_name=original_name,
            stored_path=str(destination),
            category=detect_category_from_caption(message.caption),
            mime_type="image/jpeg",
            file_size=photo.file_size,
            external_file_id=photo.file_id,
            external_unique_id=photo.file_unique_id,
        )
        if save_state != "saved" or employee is None or db_file is None:
            return
        await handle_saved_document(messenger, db, employee, db_file)


async def on_candidate_text(message: Message, bot: Bot) -> None:
    user = message.from_user
    if not user or not message.text:
        return

    with SessionLocal() as db:
        messenger = TelegramMessenger(bot)
        username = _telegram_username(user)
        handled = await handle_text_event(messenger, db, str(user.id), username, message.text)
        if handled == "handled":
            return
        if handled == "unknown":
            await message.answer(UNKNOWN_USER_TEXT)
            return
        if handled == "blocked":
            await message.answer(BLOCKED_USER_TEXT)
            return


async def on_scenario_button(callback: CallbackQuery, bot: Bot) -> None:
    user = callback.from_user
    if not user or not callback.data or not callback.data.startswith(CALLBACK_PREFIX):
        return

    with SessionLocal() as db:
        messenger = TelegramMessenger(bot)
        if callback.data == f"{CALLBACK_PREFIX}back":
            handled = await handle_back_event(
                messenger,
                db,
                str(user.id),
                _telegram_username(user),
            )
            date_result = None
        elif callback.data.startswith(DATE_CALLBACK_PREFIX):
            handled, date_result = await handle_date_event(
                messenger,
                db,
                str(user.id),
                _telegram_username(user),
                callback.data,
            )
        else:
            _, step_id, option_index = callback.data.split(":", 2)
            handled = await handle_button_event(
                messenger,
                db,
                str(user.id),
                _telegram_username(user),
                int(step_id),
                int(option_index),
            )
            date_result = None
        if handled == "unknown":
            await callback.answer(UNKNOWN_USER_TEXT, show_alert=True)
            return
        if handled == "blocked":
            await callback.answer(BLOCKED_USER_TEXT, show_alert=True)
            return
        if handled == "handled" and date_result is not None and callback.message:
            if getattr(date_result, "action", None) == "updated" and getattr(date_result, "reply_markup", None) is not None:
                await callback.message.edit_reply_markup(reply_markup=date_result.reply_markup)
            elif getattr(date_result, "action", None) == "selected":
                await callback.message.edit_reply_markup(reply_markup=None)
    if handled == "handled":
        await callback.answer("Принято" if date_result is None or getattr(date_result, "action", None) == "selected" else "")
    else:
        await callback.answer()


async def main() -> None:
    if not settings.TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN не задан. Укажите его в .env")

    init_db()

    bot = create_telegram_bot(settings.TELEGRAM_BOT_TOKEN)
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
    dp.message.register(on_photo, lambda message: bool(message.photo))

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
