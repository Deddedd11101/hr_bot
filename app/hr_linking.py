from __future__ import annotations

import hashlib
from datetime import datetime

from sqlalchemy import and_, or_, update
from sqlalchemy.orm import Session

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


def consume_hr_link_token(
    db: Session,
    token: str,
    chat_user_id: str,
    username: str | None,
    now: datetime,
) -> bool:
    """Atomically claim a live HR link without replacing another connection."""
    normalized_chat_id = (chat_user_id or "").strip()
    token_hash = hash_hr_link_token(token) if token else ""
    if not normalized_chat_id or not token_hash:
        return False

    result = db.execute(
        update(HrSettings)
        .where(
            and_(
                HrSettings.id == 1,
                HrSettings.telegram_link_token_hash == token_hash,
                HrSettings.telegram_link_expires_at.is_not(None),
                HrSettings.telegram_link_expires_at > now,
                or_(
                    HrSettings.telegram_user_id.is_(None),
                    HrSettings.telegram_user_id == normalized_chat_id,
                ),
            )
        )
        .values(
            telegram_user_id=normalized_chat_id,
            telegram_username=normalize_telegram_username(username),
            telegram_link_token_hash=None,
            telegram_link_expires_at=None,
            updated_at=now,
        )
    )
    if result.rowcount != 1:
        db.rollback()
        return False
    db.commit()
    return True
