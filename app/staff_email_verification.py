from __future__ import annotations

import hashlib
import hmac
import secrets
import smtplib
import ssl
from datetime import timedelta
from email.message import EmailMessage

from sqlalchemy import func, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .config import settings
from .models import Employee, EmployeeTelegramEmailVerification
from .time_utils import utc_now


CODE_TTL = timedelta(minutes=10)
RESEND_COOLDOWN = timedelta(seconds=60)
MAX_ATTEMPTS = 5


def verification_required(employee: Employee) -> bool:
    return settings.STAFF_EMAIL_OTP_ENABLED and (employee.employee_stage or "").strip() != "candidate"


def normalized_work_email(employee: Employee) -> str | None:
    address = (employee.work_email or "").strip().lower()
    domain = settings.STAFF_EMAIL_DOMAIN.strip().lower().lstrip("@")
    if not domain or address.count("@") != 1 or not address.endswith(f"@{domain}"):
        return None
    return address


def has_unique_work_email(db: Session, employee: Employee) -> bool:
    address = normalized_work_email(employee)
    if not address:
        return False
    return db.query(Employee.id).filter(
        func.lower(func.trim(Employee.work_email)) == address,
    ).count() == 1


def is_verified(db: Session, employee: Employee, telegram_user_id: str) -> bool:
    if not verification_required(employee):
        return True
    current_work_email = normalized_work_email(employee)
    row = db.get(EmployeeTelegramEmailVerification, employee.id)
    return bool(
        current_work_email
        and has_unique_work_email(db, employee)
        and row
        and row.verified_at
        and row.verified_telegram_user_id == telegram_user_id
        and row.verified_work_email == current_work_email
    )


def chat_id_allowed(db: Session, telegram_user_id: str) -> bool:
    from .messaging.identity import find_employees_by_channel_user_id, get_primary_chat_id

    employees = find_employees_by_channel_user_id(db, channel="telegram", external_user_id=telegram_user_id)
    if not employees:
        return True
    return len(employees) == 1 and get_primary_chat_id(employees[0], db=db) == telegram_user_id


def _code_hash(employee_id: int, telegram_user_id: str, code: str) -> str:
    secret = settings.ADMIN_SESSION_SECRET.encode("utf-8")
    message = f"staff-email:{employee_id}:{telegram_user_id}:{code}".encode("utf-8")
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def prepare_challenge(db: Session, employee: Employee, telegram_user_id: str) -> tuple[str, str] | None:
    if not settings.STAFF_EMAIL_SMTP_PASSWORD or not settings.STAFF_EMAIL_SMTP_USERNAME or not settings.STAFF_EMAIL_FROM:
        return None
    if settings.ADMIN_SESSION_SECRET == "change-me-admin-session-secret":
        return None
    if not has_unique_work_email(db, employee):
        return None
    address = normalized_work_email(employee)
    row = db.get(EmployeeTelegramEmailVerification, employee.id)
    now = utc_now()
    if row and row.last_sent_at and now - row.last_sent_at < RESEND_COOLDOWN:
        return "", address
    code = f"{secrets.randbelow(1_000_000):06d}"
    if row is None:
        row = EmployeeTelegramEmailVerification(employee_id=employee.id)
        db.add(row)
    row.pending_telegram_user_id = telegram_user_id
    row.pending_work_email = address
    row.code_hash = _code_hash(employee.id, telegram_user_id, code)
    row.expires_at = now + CODE_TTL
    row.last_sent_at = now
    row.attempts = 0
    try:
        db.commit()
    except IntegrityError:
        # Another /start may have inserted the single row concurrently. The
        # winner's cooldown makes this request a no-op instead of surfacing a
        # raw UNIQUE/PK error to the bot.
        db.rollback()
        existing_row = db.get(EmployeeTelegramEmailVerification, employee.id)
        if existing_row and existing_row.last_sent_at and utc_now() - existing_row.last_sent_at < RESEND_COOLDOWN:
            return "", address
        raise
    return code, address


def _invalidate_pending_challenge(row: EmployeeTelegramEmailVerification) -> None:
    row.pending_telegram_user_id = None
    row.pending_work_email = None
    row.code_hash = None
    row.expires_at = None
    row.last_sent_at = None
    row.attempts = 0


def clear_failed_challenge(db: Session, employee_id: int, telegram_user_id: str, code: str) -> None:
    row = db.get(EmployeeTelegramEmailVerification, employee_id)
    if row and row.pending_telegram_user_id == telegram_user_id and row.code_hash == _code_hash(employee_id, telegram_user_id, code):
        row.code_hash = None
        row.expires_at = None
        row.last_sent_at = None
        db.commit()


def send_code_email(address: str, code: str, telegram_user_id: str) -> None:
    message = EmailMessage()
    message["From"] = settings.STAFF_EMAIL_FROM
    message["To"] = address
    message["Subject"] = "Код входа в HR-бот"
    message.set_content(
        f"Код для подключения Telegram к HR-боту: {code}\n"
        f"Код действует 10 минут. Запрос пришёл из Telegram ID {telegram_user_id}.\n"
        "Если вы не запрашивали код, не сообщайте его никому и обратитесь в HR.\n"
    )
    with smtplib.SMTP_SSL(
        settings.STAFF_EMAIL_SMTP_HOST,
        settings.STAFF_EMAIL_SMTP_PORT,
        timeout=10,
        context=ssl.create_default_context(),
    ) as client:
        client.login(settings.STAFF_EMAIL_SMTP_USERNAME, settings.STAFF_EMAIL_SMTP_PASSWORD)
        client.send_message(message)


def confirm_code(db: Session, employee: Employee, telegram_user_id: str, code: str) -> bool:
    row = db.get(EmployeeTelegramEmailVerification, employee.id)
    now = utc_now()
    if not row or not row.code_hash or row.pending_telegram_user_id != telegram_user_id:
        return False
    if not row.expires_at or row.expires_at < now or row.attempts >= MAX_ATTEMPTS:
        _invalidate_pending_challenge(row)
        db.commit()
        return False
    attempts_before = row.attempts
    if not hmac.compare_digest(row.code_hash, _code_hash(employee.id, telegram_user_id, code.strip())):
        if attempts_before + 1 >= MAX_ATTEMPTS:
            _invalidate_pending_challenge(row)
        else:
            row.attempts = attempts_before + 1
        db.commit()
        return False

    current_work_email = normalized_work_email(employee)
    if not current_work_email or not has_unique_work_email(db, employee) or row.pending_work_email != current_work_email:
        _invalidate_pending_challenge(row)
        db.commit()
        return False
    from .messaging.identity import get_primary_chat_id, set_primary_chat_id

    existing_chat_id = get_primary_chat_id(employee, db=db, include_unverified=True)
    if existing_chat_id and existing_chat_id != telegram_user_id:
        return False

    claimed = db.execute(
        update(EmployeeTelegramEmailVerification)
        .where(
            EmployeeTelegramEmailVerification.employee_id == employee.id,
            EmployeeTelegramEmailVerification.pending_telegram_user_id == telegram_user_id,
            EmployeeTelegramEmailVerification.pending_work_email == current_work_email,
            EmployeeTelegramEmailVerification.code_hash == row.code_hash,
            EmployeeTelegramEmailVerification.expires_at >= now,
            EmployeeTelegramEmailVerification.attempts == attempts_before,
            EmployeeTelegramEmailVerification.attempts < MAX_ATTEMPTS,
        )
        .values(
            verified_telegram_user_id=telegram_user_id,
            verified_work_email=current_work_email,
            verified_at=now,
            pending_telegram_user_id=None,
            pending_work_email=None,
            code_hash=None,
            expires_at=None,
            attempts=attempts_before + 1,
        )
    )
    if claimed.rowcount != 1:
        db.rollback()
        return False

    try:
        set_primary_chat_id(employee, telegram_user_id, db=db)
        db.commit()
    except (IntegrityError, ValueError):
        # Roll back the conditional claim together with the identity change;
        # a concurrent identity owner must never leave a verified row behind.
        db.rollback()
        return False
    return True
