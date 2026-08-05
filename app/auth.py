from __future__ import annotations

import hashlib
import hmac
import os
import time
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from .config import settings
from .database import SessionLocal
from .models import AdminAccount
from .time_utils import utc_now


ROLE_LABELS = {
    "admin": "Администратор",
    "hr": "HR",
}

MIN_PASSWORD_LENGTH = 10
WEAK_BOOTSTRAP_PASSWORDS = {"admin123", "hr123", "change-me"}


def hash_password(password: str, salt: Optional[str] = None) -> str:
    salt_value = salt or os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt_value.encode("utf-8"),
        100000,
    ).hex()
    return f"{salt_value}${digest}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        salt_value, stored_digest = password_hash.split("$", 1)
    except ValueError:
        return False
    candidate = hash_password(password, salt_value).split("$", 1)[1]
    return hmac.compare_digest(candidate, stored_digest)


def validate_account_password(password: str) -> str | None:
    stripped = (password or "").strip()
    if len(stripped) < MIN_PASSWORD_LENGTH:
        return f"Пароль должен быть не короче {MIN_PASSWORD_LENGTH} символов"
    if stripped in WEAK_BOOTSTRAP_PASSWORDS:
        return "Нельзя использовать дефолтный или временный пароль"
    return None


def create_admin_session_token(account_id: int, now: int | None = None) -> str:
    issued_at = int(now if now is not None else time.time())
    payload = f"{int(account_id)}.{issued_at}"
    signature = hmac.new(
        settings.ADMIN_SESSION_SECRET.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload}.{signature}"


def verify_admin_session_token(token: str, max_age_seconds: int | None = None, now: int | None = None) -> int | None:
    try:
        account_id_raw, issued_at_raw, signature = (token or "").split(".", 2)
        account_id = int(account_id_raw)
        issued_at = int(issued_at_raw)
    except (TypeError, ValueError):
        return None
    payload = f"{account_id}.{issued_at}"
    expected_signature = hmac.new(
        settings.ADMIN_SESSION_SECRET.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature, expected_signature):
        return None
    current_time = int(now if now is not None else time.time())
    if issued_at > current_time + 60:
        return None
    ttl = settings.ADMIN_SESSION_MAX_AGE_SECONDS if max_age_seconds is None else max_age_seconds
    if ttl > 0 and current_time - issued_at > ttl:
        return None
    return account_id


def authenticate_account(db: Session, login: str, password: str) -> Optional[AdminAccount]:
    account = (
        db.query(AdminAccount)
        .filter(AdminAccount.login == login.strip(), AdminAccount.is_active.is_(True))
        .first()
    )
    if not account:
        return None
    if not verify_password(password, account.password_hash):
        return None
    return account


def seed_admin_accounts() -> None:
    with SessionLocal() as db:
        _ensure_account(
            db,
            login=settings.DEFAULT_ADMIN_LOGIN,
            password=settings.DEFAULT_ADMIN_PASSWORD,
            role="admin",
        )
        _ensure_account(
            db,
            login=settings.DEFAULT_HR_LOGIN,
            password=settings.DEFAULT_HR_PASSWORD,
            role="hr",
        )
        try:
            db.commit()
        except IntegrityError:
            # Возможна гонка при одновременном старте web и bot.
            db.rollback()


def _ensure_account(db: Session, login: str, password: str, role: str) -> None:
    account = db.query(AdminAccount).filter(AdminAccount.login == login).first()
    if account:
        if account.role != role:
            account.role = role
            account.updated_at = utc_now()
        return
    now = utc_now()
    db.add(
        AdminAccount(
            login=login,
            password_hash=hash_password(password),
            role=role,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
    )
