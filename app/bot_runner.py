import asyncio
import logging
import re
from typing import Optional

from aiohttp import ClientError
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .config import settings
from .database import SessionLocal, init_db
from .file_storage import build_employee_file_path
from .messaging import create_telegram_messenger
from .messaging.telegram import AnswerWidgetQuery, TelegramMessenger
from .messaging.service import (
    BLOCKED_USER_TEXT,
    DATE_CALLBACK_PREFIX,
    UNKNOWN_USER_TEXT,
    STAFF_EMAIL_VERIFICATION_TEXT,
    detect_category_from_caption,
    handle_back_event,
    handle_button_event,
    handle_choice_confirmation_event,
    handle_menu_callback,
    handle_date_event,
    handle_saved_document,
    handle_start_command,
    handle_text_event,
    resolve_inbound_access,
    save_incoming_file,
)
from .models import FlowStepTemplate
from .scenario_engine import CALLBACK_PREFIX, CHOICE_CONFIRM_CALLBACK_PREFIX, get_waiting_progress, grade_widget_skill_page, handle_back_response
from .scheduler import schedule_all_employees


logger = logging.getLogger(__name__)
TELEGRAM_DOWNLOAD_LIMIT = 20 * 1024 * 1024
OVERSIZED_FILE_TEXT = (
    "Этот файл слишком большой: бот может загрузить файл до 20 МБ. "
    "Для ответа на тестовое отправьте одну ссылку на файл в облачном хранилище "
    "с доступом для просмотра или уменьшите файл. Ответ пока не сохранён."
)


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
    start_parameter = None
    if message.text:
        parts = message.text.split(maxsplit=1)
        if len(parts) == 2:
            start_parameter = parts[1].strip() or None
    with SessionLocal() as db:
        messenger = create_telegram_messenger(settings.TELEGRAM_BOT_TOKEN)
        await handle_start_command(messenger, db, user_id_str, username, start_parameter, message.message_id)
        await messenger.close()


def _media_original_name(media, fallback_extension: str) -> str:
    file_name = getattr(media, "file_name", None)
    if isinstance(file_name, str) and file_name.strip():
        return file_name.strip()
    file_unique_id = getattr(media, "file_unique_id", None) or getattr(media, "file_id", None) or "telegram_file"
    return f"{file_unique_id}{fallback_extension}"


async def _handle_incoming_file_like(
    message: Message,
    bot: Bot,
    media,
    *,
    original_name: str,
    mime_type: Optional[str],
    file_size: Optional[int],
    category_caption: Optional[str],
) -> None:
    user = message.from_user
    if not media or not user:
        return

    with SessionLocal() as db:
        messenger = create_telegram_messenger(settings.TELEGRAM_BOT_TOKEN)
        username = _telegram_username(user)
        access = resolve_inbound_access(db, str(user.id), username)
        if access.state == "unknown":
            await messenger.send_text(chat_id=str(user.id), text=UNKNOWN_USER_TEXT)
            await messenger.close()
            return
        if access.state == "blocked":
            await messenger.send_text(chat_id=str(user.id), text=BLOCKED_USER_TEXT)
            await messenger.close()
            return
        if access.state != "ok":
            await messenger.send_text(chat_id=str(user.id), text=STAFF_EMAIL_VERIFICATION_TEXT if access.state == "verification_required" else UNKNOWN_USER_TEXT)
            await messenger.close()
            return
        employee = access.employee
        if employee is None:
            await messenger.close()
            return
        if file_size is not None and file_size > TELEGRAM_DOWNLOAD_LIMIT:
            await messenger.send_text(chat_id=str(user.id), text=OVERSIZED_FILE_TEXT)
            await messenger.close()
            return
        destination = None
        try:
            file_info = await bot.get_file(media.file_id)
            destination = build_employee_file_path(employee.id, original_name)
            await bot.download_file(file_info.file_path, destination=destination)
        except Exception as exc:
            if destination is not None:
                try:
                    destination.unlink(missing_ok=True)
                except OSError:
                    logger.warning("Could not remove partial inbound download", exc_info=True)
            logger.exception(
                "Telegram inbound media download failed: chat_user_id=%s file_id=%s filename=%s",
                user.id,
                getattr(media, "file_id", None),
                original_name,
            )
            await messenger.send_text(
                chat_id=str(user.id),
                text=(OVERSIZED_FILE_TEXT if isinstance(exc, TelegramBadRequest) and "file is too big" in str(exc).lower()
                      else "Не удалось загрузить файл. Ответ пока не сохранён. Попробуйте отправить его еще раз."),
            )
            await messenger.close()
            return
        employee, db_file, save_state = await save_incoming_file(
            db,
            str(user.id),
            username,
            original_name=original_name,
            stored_path=str(destination),
            category=detect_category_from_caption(category_caption),
            mime_type=mime_type,
            file_size=file_size,
            external_file_id=media.file_id,
            external_unique_id=getattr(media, "file_unique_id", None),
        )
        if save_state != "saved" or employee is None or db_file is None:
            await messenger.close()
            return
        if not await handle_saved_document(messenger, db, employee, db_file):
            logger.warning(
                "Inbound media was saved but not accepted by a scenario step: employee_id=%s file_id=%s",
                employee.id,
                db_file.id,
            )
            if get_waiting_progress(db, employee.id):
                await messenger.send_text(
                    chat_id=str(user.id),
                    text="Файл получен, но текущий шаг его не принял. Ответ пока не засчитан. Уточните ожидаемый формат ответа или обратитесь к HR.",
                )
        await messenger.close()


async def on_document(message: Message, bot: Bot) -> None:
    document = message.document
    if not document:
        return

    await _handle_incoming_file_like(
        message,
        bot,
        document,
        original_name=_media_original_name(document, ".bin"),
        mime_type=document.mime_type,
        file_size=document.file_size,
        category_caption=message.caption,
    )


async def on_photo(message: Message, bot: Bot) -> None:
    photos = message.photo or []
    if not photos:
        return

    photo = photos[-1]
    await _handle_incoming_file_like(
        message,
        bot,
        photo,
        original_name=_media_original_name(photo, ".jpg"),
        mime_type="image/jpeg",
        file_size=photo.file_size,
        category_caption=message.caption,
    )


async def on_video(message: Message, bot: Bot) -> None:
    video = message.video
    if not video:
        return

    await _handle_incoming_file_like(
        message,
        bot,
        video,
        original_name=_media_original_name(video, ".mp4"),
        mime_type=video.mime_type or "video/mp4",
        file_size=video.file_size,
        category_caption=message.caption,
    )


async def on_video_note(message: Message, bot: Bot) -> None:
    video_note = message.video_note
    if not video_note:
        return

    await _handle_incoming_file_like(
        message,
        bot,
        video_note,
        original_name=_media_original_name(video_note, ".mp4"),
        mime_type="video/mp4",
        file_size=video_note.file_size,
        category_caption=None,
    )


async def on_animation(message: Message, bot: Bot) -> None:
    animation = message.animation
    if not animation:
        return

    mime_type = animation.mime_type or "video/mp4"
    await _handle_incoming_file_like(
        message,
        bot,
        animation,
        original_name=_media_original_name(animation, ".gif" if mime_type == "image/gif" else ".mp4"),
        mime_type=mime_type,
        file_size=animation.file_size,
        category_caption=message.caption,
    )


async def on_candidate_text(message: Message) -> None:
    user = message.from_user
    if not user or not message.text:
        return

    with SessionLocal() as db:
        messenger = create_telegram_messenger(settings.TELEGRAM_BOT_TOKEN)
        username = _telegram_username(user)
        handled = await handle_text_event(messenger, db, str(user.id), username, message.text, message.message_id)
        await messenger.close()
        if handled == "handled":
            return
        if handled == "unknown":
            await message.answer(UNKNOWN_USER_TEXT)
            return
        if handled == "blocked":
            await message.answer(BLOCKED_USER_TEXT)
            return
        if handled == "verification_required":
            await message.answer(STAFF_EMAIL_VERIFICATION_TEXT)
            return


async def on_widget_update(handler, update, data):
    # aiogram 3.13 preserves new update types as extras before event routing.
    query = (update.model_extra or {}).get("widget_query")
    if query is None:
        return await handler(update, data)
    result = "error"
    match = re.fullmatch(r"g:([rakpqhb]):([0-9]{1,12}):([0-9]{1,6})", query.get("data") or "")
    sender, chat = query.get("from") or {}, query.get("chat") or {}
    message_id = query.get("message_id")
    if match and message_id and chat.get("type") == "private" and sender.get("id") == chat.get("id"):
        action, step_id, index = match.groups()
        step_id, index = int(step_id), int(index)
        chat_id = str(chat["id"])
        with SessionLocal() as db:
            access = resolve_inbound_access(db, chat_id, sender.get("username"))
            if access.state == "ok" and access.employee:
                step = db.get(FlowStepTemplate, step_id)
                screen = grade_widget_skill_page(db, access.employee, step, message_id, index if action == "r" else 0, chat_id=chat_id)
                if screen and screen[0]:
                    if action == "r":
                        result = screen[0]
                    elif action in {"p", "q", "h"}:
                        if (action, index) in {("p", 1), ("h", 0)}:
                            try:
                                await data["bot"].edit_message_reply_markup(chat_id=chat_id, message_id=message_id, reply_markup=None)
                            except TelegramBadRequest:
                                pass
                        if action in {"p", "q"}:
                            following = grade_widget_skill_page(db, access.employee, step, message_id, index,
                                chat_id=chat_id, prefetch=True)
                            if following and following[0]:
                                result = following[0]
                        else:
                            result = "ok"
                    elif action == "b" and index == 0:
                        if await handle_back_response(TelegramMessenger(data["bot"]), db, access.employee,
                                                      widget_step=step, widget_message_id=message_id):
                            result = "ok"
                    elif action == "k" and index == 0:
                        buttons = [InlineKeyboardButton(text="Обычные кнопки", callback_data=f"scenario:grade_keys:{step_id}")]
                        buttons.extend(button for row in screen[1].inline_keyboard for button in row
                                       if button.callback_data == f"{CALLBACK_PREFIX}back")
                        try:
                            await data["bot"].edit_message_reply_markup(chat_id=chat_id, message_id=message_id,
                                reply_markup=InlineKeyboardMarkup(inline_keyboard=[buttons]))
                        except TelegramBadRequest as exc:
                            if "not modified" in str(exc).casefold():
                                result = "ok"
                        else:
                            result = "ok"
                    elif action == "a" and index <= 4 and (step.button_options or "").splitlines()[:4] == ["1", "2", "3", "4"]:
                        status = await handle_button_event(TelegramMessenger(data["bot"]),
                            db, chat_id, sender.get("username"), step_id, index, message_id)
                        if status == "handled":
                            result = "ok"
    await data["bot"](AnswerWidgetQuery(widget_query_id=query["id"], data=result))


async def on_scenario_button(callback: CallbackQuery) -> None:
    user = callback.from_user
    if not user or not callback.data or not callback.data.startswith(CALLBACK_PREFIX):
        return

    with SessionLocal() as db:
        messenger = create_telegram_messenger(settings.TELEGRAM_BOT_TOKEN)
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
        elif callback.data.startswith(CHOICE_CONFIRM_CALLBACK_PREFIX):
            handled = await handle_choice_confirmation_event(
                messenger,
                db,
                str(user.id),
                _telegram_username(user),
                callback.data,
                callback.message.message_id if callback.message else None,
            )
            date_result = None
        elif callback.data.startswith(f"{CALLBACK_PREFIX}grade_keys:"):
            handled, date_result = "ignored", None
            match = re.fullmatch(r"scenario:grade_keys:([0-9]{1,12})", callback.data)
            if match and callback.message and callback.message.chat.id == user.id:
                access = resolve_inbound_access(db, str(user.id), _telegram_username(user))
                if access.state == "ok" and access.employee:
                    screen = grade_widget_skill_page(db, access.employee, db.get(FlowStepTemplate, int(match[1])),
                        callback.message.message_id, 0, chat_id=str(user.id))
                    if screen:
                        await callback.message.edit_reply_markup(reply_markup=screen[1])
                        handled = "handled"
        else:
            _, step_id, option_index = callback.data.split(":", 2)
            handled = await handle_button_event(
                messenger,
                db,
                str(user.id),
                _telegram_username(user),
                int(step_id),
                int(option_index),
                callback.message.message_id if callback.message else None,
            )
            date_result = None
        await messenger.close()
        if handled == "unknown":
            await callback.answer(UNKNOWN_USER_TEXT, show_alert=True)
            return
        if handled == "blocked":
            await callback.answer(BLOCKED_USER_TEXT, show_alert=True)
            return
        if handled == "verification_required":
            await callback.answer(STAFF_EMAIL_VERIFICATION_TEXT, show_alert=True)
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


async def on_menu_button(callback: CallbackQuery) -> None:
    user = callback.from_user
    if not user or not callback.data or not callback.data.startswith("menu:"):
        return
    with SessionLocal() as db:
        messenger = create_telegram_messenger(settings.TELEGRAM_BOT_TOKEN)
        handled = await handle_menu_callback(
            messenger,
            db,
            str(user.id),
            _telegram_username(user),
            callback.data,
            callback.message.message_id if callback.message else None,
        )
        await messenger.close()
    if handled == "unknown":
        await callback.answer(UNKNOWN_USER_TEXT, show_alert=True)
    elif handled == "blocked":
        await callback.answer(BLOCKED_USER_TEXT, show_alert=True)
    elif handled == "verification_required":
        await callback.answer(STAFF_EMAIL_VERIFICATION_TEXT, show_alert=True)
    elif handled == "handled":
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
    dp.update.outer_middleware(on_widget_update)

    dp.message.register(on_start, CommandStart())
    dp.callback_query.register(
        on_scenario_button,
        lambda callback: callback.data is not None and callback.data.startswith(CALLBACK_PREFIX),
    )
    dp.callback_query.register(
        on_menu_button,
        lambda callback: callback.data is not None and callback.data.startswith("menu:"),
    )
    dp.message.register(
        on_candidate_text,
        lambda message: message.text is not None and not message.text.startswith("/"),
    )
    dp.message.register(on_document, lambda message: message.document is not None)
    dp.message.register(on_photo, lambda message: bool(message.photo))
    dp.message.register(on_video, lambda message: message.video is not None)
    dp.message.register(on_video_note, lambda message: message.video_note is not None)
    dp.message.register(on_animation, lambda message: message.animation is not None)

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
                await dp.start_polling(bot, allowed_updates=[*dp.resolve_used_update_types(), "widget_query"])
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
