from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import secrets
from datetime import timedelta
from typing import Literal

from sqlalchemy import func, or_, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import settings
from ..mail import MailDeliveryError, send_staff_code
from ..models import Employee, StaffTelegramChallenge
from ..time_utils import utc_now
from .identity import EmployeeIdentityConflictError, get_primary_chat_id, set_primary_chat_id, set_public_chat_handle

logger = logging.getLogger(__name__)
CODE_TTL = timedelta(minutes=10)
RESEND_COOLDOWN = timedelta(seconds=60)
SEND_WINDOW = timedelta(days=1)
MAX_SENDS = 5
MAX_ATTEMPTS = 5


def is_staff(employee: Employee) -> bool:
    return (employee.employee_stage or "").strip() != "candidate"


def is_staff_verified(employee: Employee, chat_id: str) -> bool:
    return bool(employee.telegram_verified_at and employee.telegram_verified_user_id == chat_id)


def _normalized_email(value: str | None) -> str:
    return (value or "").strip().lower()


def _hash_code(chat_id: str, employee_id: int, code: str) -> str:
    data = f"staff-telegram:{chat_id}:{employee_id}:{code}".encode("utf-8")
    return hmac.new(settings.ADMIN_SESSION_SECRET.encode("utf-8"), data, hashlib.sha256).hexdigest()


def _email_is_unique(db: Session, employee: Employee) -> bool:
    email = _normalized_email(employee.work_email)
    if not email or "@" not in email:
        return False
    matches = db.query(Employee.id).filter(
        or_(Employee.employee_stage.is_(None), Employee.employee_stage != "candidate"),
        func.lower(func.trim(Employee.work_email)) == email,
    ).all()
    return len(matches) == 1 and matches[0][0] == employee.id


def get_challenge(db: Session, chat_id: str) -> StaffTelegramChallenge | None:
    return db.get(StaffTelegramChallenge, chat_id)


async def request_staff_code(
    db: Session, employee: Employee, chat_id: str,
) -> Literal["sent", "cooldown", "limit", "unavailable", "conflict", "missing_email"]:
    if not _email_is_unique(db, employee):
        return "missing_email"
    old_chat_id = get_primary_chat_id(employee, db=db, include_unverified=True)
    if old_chat_id and old_chat_id != chat_id:
        return "conflict"
    if employee.telegram_verified_user_id and employee.telegram_verified_user_id != chat_id:
        return "conflict"
    if not all((settings.SMTP_HOST, settings.SMTP_USERNAME, settings.SMTP_PASSWORD, settings.SMTP_FROM_EMAIL)):
        return "unavailable"

    now = utc_now()
    challenge = get_challenge(db, chat_id)
    if challenge and challenge.employee_id != employee.id:
        return "conflict"
    if challenge is None:
        challenge = StaffTelegramChallenge(
            telegram_user_id=chat_id,
            employee_id=employee.id,
            email_snapshot=_normalized_email(employee.work_email),
            attempts_left=0,
            sends_in_window=0,
        )
        db.add(challenge)
    if challenge.last_sent_at and now - challenge.last_sent_at < RESEND_COOLDOWN:
        return "cooldown"
    if not challenge.send_window_started_at or now - challenge.send_window_started_at >= SEND_WINDOW:
        challenge.send_window_started_at = now
        challenge.sends_in_window = 0
    if challenge.sends_in_window >= MAX_SENDS:
        return "limit"
    employee_sends = db.query(func.sum(StaffTelegramChallenge.sends_in_window)).filter(
        StaffTelegramChallenge.employee_id == employee.id,
        StaffTelegramChallenge.send_window_started_at >= now - SEND_WINDOW,
    ).scalar() or 0
    if employee_sends >= MAX_SENDS:
        return "limit"

    code = f"{secrets.randbelow(100_000_000):08d}"
    challenge.email_snapshot = _normalized_email(employee.work_email)
    challenge.code_hash = _hash_code(chat_id, employee.id, code)
    challenge.expires_at = now + CODE_TTL
    challenge.attempts_left = MAX_ATTEMPTS
    challenge.last_sent_at = now
    challenge.sends_in_window += 1
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return "cooldown"
    try:
        await asyncio.to_thread(send_staff_code, challenge.email_snapshot, code)
    except MailDeliveryError:
        logger.exception("Staff OTP mail delivery failed for employee_id=%s", employee.id)
        challenge.code_hash = None
        challenge.expires_at = None
        challenge.last_sent_at = None
        db.commit()
        return "unavailable"
    return "sent"


def verify_staff_code(
    db: Session, chat_id: str, username: str | None, code: str,
) -> tuple[Literal["verified", "invalid", "expired", "conflict"], Employee | None]:
    challenge = get_challenge(db, chat_id)
    if challenge is None or not challenge.code_hash:
        return "expired", None
    employee = db.get(Employee, challenge.employee_id)
    if (
        employee is None or employee.is_bot_blocked or not is_staff(employee)
        or not _email_is_unique(db, employee)
        or _normalized_email(employee.work_email) != challenge.email_snapshot
    ):
        return "conflict", None
    if challenge.expires_at is None or utc_now() >= challenge.expires_at or challenge.attempts_left <= 0:
        challenge.code_hash = None
        db.commit()
        return "expired", None
    if len(code) != 8 or not code.isascii() or not code.isdigit() or not hmac.compare_digest(
        challenge.code_hash, _hash_code(chat_id, employee.id, code)
    ):
        challenge.attempts_left -= 1
        if challenge.attempts_left <= 0:
            challenge.code_hash = None
        db.commit()
        return "invalid", None
    old_chat_id = get_primary_chat_id(employee, db=db, include_unverified=True)
    if old_chat_id and old_chat_id != chat_id:
        return "conflict", None
    if employee.telegram_verified_user_id and employee.telegram_verified_user_id != chat_id:
        return "conflict", None
    try:
        claimed = db.execute(
            update(StaffTelegramChallenge).where(
                StaffTelegramChallenge.telegram_user_id == chat_id,
                StaffTelegramChallenge.employee_id == employee.id,
                StaffTelegramChallenge.code_hash == challenge.code_hash,
                StaffTelegramChallenge.attempts_left > 0,
            ).values(code_hash=None, attempts_left=0)
        )
        if claimed.rowcount != 1:
            db.rollback()
            return "expired", None
        linked = db.execute(
            update(Employee).where(
                Employee.id == employee.id,
                or_(Employee.telegram_verified_user_id.is_(None), Employee.telegram_verified_user_id == chat_id),
            ).values(telegram_verified_user_id=chat_id, telegram_verified_at=utc_now())
        )
        if linked.rowcount != 1:
            db.rollback()
            return "conflict", None
        db.refresh(employee)
        set_public_chat_handle(employee, username, db=db)
        set_primary_chat_id(employee, chat_id, db=db)
        db.delete(challenge)
        db.commit()
    except EmployeeIdentityConflictError:
        db.rollback()
        return "conflict", None
    return "verified", employee
