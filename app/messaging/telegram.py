from __future__ import annotations

from pathlib import Path
from typing import Any

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import (
    BufferedInputFile,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)


class TelegramMessenger:
    def __init__(self, bot: Any) -> None:
        self.bot = bot

    async def send_text(self, chat_id: str, text: str, reply_markup: Any | None = None) -> None:
        await self.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)

    async def edit_text(self, chat_id: str, message_id: int, text: str, reply_markup: Any | None = None) -> None:
        await self.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=reply_markup,
        )

    async def send_menu(self, chat_id: str, text: str, buttons: list[str]) -> None:
        if not buttons:
            await self.send_text(chat_id=chat_id, text=text)
            return
        keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=button)] for button in buttons if button.strip()],
            resize_keyboard=True,
        )
        await self.bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard)

    @staticmethod
    def _inline_markup(buttons: list[tuple[str, str]]) -> InlineKeyboardMarkup | None:
        rows = [
            [InlineKeyboardButton(text=label, callback_data=callback_data)]
            for label, callback_data in buttons
            if label.strip() and callback_data.strip()
        ]
        return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None

    async def send_inline_menu(self, chat_id: str, text: str, buttons: list[tuple[str, str]]) -> Any:
        # A separate invisible cleanup message removes reply keyboards sent by older versions.
        await self.bot.send_message(chat_id=chat_id, text="\u2063", reply_markup=ReplyKeyboardRemove())
        return await self.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=self._inline_markup(buttons),
        )

    async def edit_inline_menu(
        self, chat_id: str, message_id: int, text: str, buttons: list[tuple[str, str]]
    ) -> Any:
        return await self.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=self._inline_markup(buttons),
        )

    async def send_photo_path(
        self,
        chat_id: str,
        path: str | Path,
        filename: str | None = None,
        reply_markup: Any | None = None,
        caption: str | None = None,
    ) -> None:
        file_path = Path(path)
        await self.bot.send_photo(
            chat_id=chat_id,
            photo=FSInputFile(str(file_path), filename=filename or file_path.name),
            caption=caption,
            reply_markup=reply_markup,
        )

    async def send_photo_bytes(
        self,
        chat_id: str,
        data: bytes,
        filename: str,
        reply_markup: Any | None = None,
        caption: str | None = None,
    ) -> None:
        await self.bot.send_photo(
            chat_id=chat_id,
            photo=BufferedInputFile(data, filename=filename),
            caption=caption,
            reply_markup=reply_markup,
        )

    async def send_document_path(
        self,
        chat_id: str,
        path: str | Path,
        filename: str | None = None,
        reply_markup: Any | None = None,
        caption: str | None = None,
    ) -> None:
        file_path = Path(path)
        await self.bot.send_document(
            chat_id=chat_id,
            document=FSInputFile(str(file_path), filename=filename or file_path.name),
            caption=caption,
            reply_markup=reply_markup,
        )

    async def close(self) -> None:
        session = getattr(self.bot, "session", None)
        if session is not None:
            await session.close()


def create_telegram_messenger(token: str, parse_mode: str | None = "HTML") -> TelegramMessenger:
    default = None
    if parse_mode == "HTML":
        default = DefaultBotProperties(parse_mode=ParseMode.HTML)
    return TelegramMessenger(Bot(token=token, default=default))
