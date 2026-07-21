from __future__ import annotations

import asyncio
import hashlib
import hmac
import secrets
from datetime import timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import settings
from ..mail import send_email
from ..models import Employee, EmployeeLinkSession
from ..time_utils import utc_now

LINK_STATE_CHOOSE_AUDIENCE = "choose_audience"
LINK_STATE_USERNAME_MATCH = "username_match"
LINK_STATE_AWAITING_EMAIL = "awaiting_email"
LINK_STATE_AWAITING_OTP = "awaiting_otp"
LINK_STATE_CANDIDATE_HELP = "candidate_help"


def normalize_email(value: Optional[str]) -> str:
    return (value or "").strip().lower()


def mask_email(value: Optional[str]) -> str:
    email = normalize_email(value)
    if "@" not in email:
        return "скрытый адрес"
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        masked_local = local[:1] + "***"
    else:
        masked_local = local[:2] + "***"
    return f"{masked_local}@{domain}"


def get_link_session(db: Session, *, channel: str, external_user_id: str) -> Optional[EmployeeLinkSession]:
    return (
        db.query(EmployeeLinkSession)
        .filter(
            EmployeeLinkSession.channel == channel,
            EmployeeLinkSession.external_user_id == external_user_id,
        )
        .first()
    )


def ensure_link_session(
    db: Session,
    *,
    channel: str,
    external_user_id: str,
    external_username: Optional[str],
) -> EmployeeLinkSession:
    session = get_link_session(db, channel=channel, external_user_id=external_user_id)
    now = utc_now()
    if session is None:
        session = EmployeeLinkSession(
            channel=channel,
            external_user_id=external_user_id,
            external_username=(external_username or "").strip() or None,
            state=LINK_STATE_CHOOSE_AUDIENCE,
            created_at=now,
            updated_at=now,
        )
        db.add(session)
        db.flush()
        return session

    session.external_username = (external_username or "").strip() or None
    session.updated_at = now
    db.flush()
    return session


def reset_link_session(
    db: Session,
    *,
    channel: str,
    external_user_id: str,
    external_username: Optional[str],
) -> EmployeeLinkSession:
    session = ensure_link_session(
        db,
        channel=channel,
        external_user_id=external_user_id,
        external_username=external_username,
    )
    session.employee_id = None
    session.state = LINK_STATE_CHOOSE_AUDIENCE
    session.pending_email = None
    session.otp_code_hash = None
    session.otp_expires_at = None
    session.otp_attempts_left = 0
    session.last_code_sent_at = None
    session.updated_at = utc_now()
    db.flush()
    return session


def clear_link_session(db: Session, *, channel: str, external_user_id: str) -> None:
    session = get_link_session(db, channel=channel, external_user_id=external_user_id)
    if session is not None:
        db.delete(session)
        db.flush()


def find_staff_by_work_email(db: Session, raw_email: Optional[str]) -> Optional[Employee]:
    normalized_email = normalize_email(raw_email)
    if not normalized_email:
        return None
    employees = (
        db.query(Employee)
        .filter(
            Employee.employee_stage.is_not(None),
            Employee.employee_stage != "candidate",
            func.lower(func.trim(Employee.work_email)) == normalized_email,
        )
        .order_by(Employee.id.asc())
        .all()
    )
    if len(employees) != 1:
        return None
    return employees[0]


def staff_requires_email_verification(employee: Employee) -> bool:
    return (employee.employee_stage or "").strip() != "candidate"


def mark_employee_telegram_verified(employee: Employee, method: str) -> None:
    employee.telegram_verified_at = utc_now()
    employee.telegram_link_method = method


def note_employee_telegram_link_method(employee: Employee, method: str) -> None:
    if employee.telegram_link_method:
        return
    employee.telegram_link_method = method


def build_otp_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _code_hash(code: str) -> str:
    return hmac.new(
        settings.ADMIN_SESSION_SECRET.encode("utf-8"),
        code.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def can_resend_otp(session: EmployeeLinkSession) -> bool:
    if session.last_code_sent_at is None:
        return True
    return utc_now() >= session.last_code_sent_at + timedelta(seconds=settings.TELEGRAM_LINK_OTP_RESEND_COOLDOWN_SECONDS)


async def issue_email_otp(
    db: Session,
    *,
    session: EmployeeLinkSession,
    employee: Employee,
    email: str,
    code: Optional[str] = None,
) -> str:
    otp_code = code or build_otp_code()
    session.employee_id = employee.id
    session.state = LINK_STATE_AWAITING_OTP
    session.pending_email = normalize_email(email)
    session.otp_code_hash = _code_hash(otp_code)
    session.otp_expires_at = utc_now() + timedelta(minutes=settings.TELEGRAM_LINK_OTP_TTL_MINUTES)
    session.otp_attempts_left = settings.TELEGRAM_LINK_OTP_MAX_ATTEMPTS
    session.last_code_sent_at = utc_now()
    session.updated_at = utc_now()
    db.flush()

    subject = "Код подтверждения для HR-бота"
    full_name = (employee.full_name or "").strip() or "сотрудник"
    text = (
        f"{full_name},\n\n"
        f"Ваш код подтверждения для привязки Telegram к HR-боту: {otp_code}\n\n"
        f"Код действует {settings.TELEGRAM_LINK_OTP_TTL_MINUTES} минут.\n"
        "Если вы не запрашивали привязку, просто проигнорируйте это письмо."
    )
    await asyncio.to_thread(send_email, to_email=session.pending_email, subject=subject, text=text)
    return otp_code


def verify_otp_code(session: EmployeeLinkSession, raw_code: str) -> bool:
    code = (raw_code or "").strip()
    if not code or session.otp_code_hash is None or session.otp_expires_at is None:
        return False
    if utc_now() > session.otp_expires_at:
        return False
    return hmac.compare_digest(session.otp_code_hash, _code_hash(code))
