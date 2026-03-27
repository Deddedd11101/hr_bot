from __future__ import annotations

import hashlib
import hmac
import os
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from .config import settings
from .database import SessionLocal
from .models import AdminAccount


ROLE_LABELS = {
    "admin": "Администратор",
    "hr": "HR",
}


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
            account.updated_at = datetime.utcnow()
        return
    now = datetime.utcnow()
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
