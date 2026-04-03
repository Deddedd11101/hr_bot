from __future__ import annotations

from pathlib import Path
from typing import Any

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BufferedInputFile, FSInputFile


class TelegramMessenger:
    def __init__(self, bot: Any) -> None:
        self.bot = bot

    async def send_text(self, chat_id: str, text: str, reply_markup: Any | None = None) -> None:
        await self.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)

    async def send_photo_path(self, chat_id: str, path: str | Path, filename: str | None = None) -> None:
        file_path = Path(path)
        await self.bot.send_photo(
            chat_id=chat_id,
            photo=FSInputFile(str(file_path), filename=filename or file_path.name),
        )

    async def send_photo_bytes(self, chat_id: str, data: bytes, filename: str) -> None:
        await self.bot.send_photo(
            chat_id=chat_id,
            photo=BufferedInputFile(data, filename=filename),
        )

    async def send_document_path(self, chat_id: str, path: str | Path, filename: str | None = None) -> None:
        file_path = Path(path)
        await self.bot.send_document(
            chat_id=chat_id,
            document=FSInputFile(str(file_path), filename=filename or file_path.name),
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
