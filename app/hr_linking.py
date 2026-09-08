from __future__ import annotations

import hashlib
import hmac
from datetime import datetime

from .models import HrSettings


def normalize_telegram_username(value: str | None) -> str | None:
    normalized = (value or "").strip().lstrip("@").strip()
    return normalized or None


def is_numeric_telegram_id(value: str | None) -> bool:
    normalized = (value or "").strip()
    return bool(normalized) and normalized.isdigit()


def hash_hr_link_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hr_connection_state(settings: HrSettings | None, now: datetime) -> str:
    if settings and settings.telegram_link_expires_at and settings.telegram_link_expires_at > now:
        return "pending"
    if settings and is_numeric_telegram_id(settings.telegram_user_id):
        return "connected"
    return "disconnected"


def consume_hr_link_token(settings: HrSettings, token: str, now: datetime) -> bool:
    if not token or not settings.telegram_link_token_hash:
        return False
    expires_at = settings.telegram_link_expires_at
    if not expires_at or expires_at <= now:
        return False
    return hmac.compare_digest(settings.telegram_link_token_hash, hash_hr_link_token(token))
