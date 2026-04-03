from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class MessengerClient(Protocol):
    async def send_text(self, chat_id: str, text: str, reply_markup: Any | None = None) -> None: ...

    async def send_menu(self, chat_id: str, text: str, buttons: list[str]) -> None: ...

    async def send_photo_path(self, chat_id: str, path: str | Path, filename: str | None = None) -> None: ...

    async def send_photo_bytes(self, chat_id: str, data: bytes, filename: str) -> None: ...

    async def send_document_path(self, chat_id: str, path: str | Path, filename: str | None = None) -> None: ...


def as_messenger(client_or_bot: Any) -> MessengerClient:
    if hasattr(client_or_bot, "send_text") and hasattr(client_or_bot, "send_photo_path"):
        return client_or_bot

    from .telegram import TelegramMessenger

    return TelegramMessenger(client_or_bot)
