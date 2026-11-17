import asyncio
import time
from collections import OrderedDict

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession

from .config import settings

MAX_BYTES = 128 * 1024
_cache = OrderedDict()
_downloads = asyncio.Semaphore(4)


async def _download(chat_id):
    async with asyncio.timeout(7), Bot(
        token=settings.TELEGRAM_BOT_TOKEN, session=AiohttpSession(timeout=4),
    ).context() as bot:
        photos = await bot.get_user_profile_photos(int(chat_id), limit=1)
        if not photos.photos:
            return None
        photo = min(photos.photos[0], key=lambda size: size.width * size.height)
        if photo.file_size is None or photo.file_size > MAX_BYTES:
            return None
        result = await bot.download(photo.file_id, timeout=4)
        data = result.read(MAX_BYTES + 1) if result else b""
        return data if len(data) <= MAX_BYTES and data.startswith(b"\xff\xd8\xff") else None


async def telegram_avatar(chat_id):
    async with _downloads:
        cached = _cache.get(chat_id)
        if cached and cached[0] > time.monotonic():
            _cache.move_to_end(chat_id)
            return cached[1]
        try:
            data = await _download(chat_id)
            ttl = 600 if data else 180
        except Exception:
            # Telegram download exceptions may include the bot token in the URL.
            data, ttl = None, 45
        _cache[chat_id] = (time.monotonic() + ttl, data)
        _cache.move_to_end(chat_id)
        if len(_cache) > 128:
            _cache.popitem(last=False)
        return data
