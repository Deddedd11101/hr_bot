from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from ..models import Employee, EmployeeMessengerAccount


class EmployeeIdentityConflictError(ValueError):
    def __init__(
        self,
        *,
        channel: str,
        external_user_id: str,
        conflicting_employee_id: int,
        conflicting_employee_name: str | None = None,
    ) -> None:
        self.channel = channel
        self.external_user_id = external_user_id
        self.conflicting_employee_id = conflicting_employee_id
        self.conflicting_employee_name = conflicting_employee_name
        label = conflicting_employee_name or f"#{conflicting_employee_id}"
        super().__init__(
            f"Идентификатор {external_user_id} уже привязан к сотруднику {label} (id={conflicting_employee_id})."
        )


def _normalized(value: Optional[str]) -> Optional[str]:
    text = (value or "").strip()
    return text or None


def _looks_like_numeric_chat_id(value: Optional[str]) -> bool:
    normalized = _normalized(value)
    return bool(normalized) and (normalized.isdigit() or (normalized.startswith("-") and normalized[1:].isdigit()))


def get_primary_account(
    employee: Employee,
    db: Session | None = None,
    channel: str | None = None,
) -> Optional[EmployeeMessengerAccount]:
    if db is None or employee.id is None:
        return None

    query = db.query(EmployeeMessengerAccount).filter(
        EmployeeMessengerAccount.employee_id == employee.id,
        EmployeeMessengerAccount.is_active.is_(True),
    )
    if channel:
        query = query.filter(EmployeeMessengerAccount.channel == channel)

    account = (
        query.filter(EmployeeMessengerAccount.is_primary.is_(True))
        .order_by(EmployeeMessengerAccount.id.asc())
        .first()
    )
    if account:
        return account

    return query.order_by(EmployeeMessengerAccount.id.asc()).first()


def find_employee_by_channel_user_id(
    db: Session,
    *,
    channel: str,
    external_user_id: Optional[str],
) -> Optional[Employee]:
    normalized_user_id = _normalized(external_user_id)
    if not normalized_user_id:
        return None

    account = (
        db.query(EmployeeMessengerAccount)
        .filter(
            EmployeeMessengerAccount.channel == channel,
            EmployeeMessengerAccount.external_user_id == normalized_user_id,
            EmployeeMessengerAccount.is_active.is_(True),
        )
        .order_by(EmployeeMessengerAccount.is_primary.desc(), EmployeeMessengerAccount.id.asc())
        .first()
    )
    if account:
        return db.get(Employee, account.employee_id)

    if channel == "telegram":
        return db.query(Employee).filter(Employee.telegram_user_id == normalized_user_id).first()
    return None


def get_primary_chat_id(
    employee: Employee,
    db: Session | None = None,
    channel: str | None = None,
) -> Optional[str]:
    if db is not None and employee.id is not None:
        numeric_account = (
            db.query(EmployeeMessengerAccount)
            .filter(
                EmployeeMessengerAccount.employee_id == employee.id,
                EmployeeMessengerAccount.is_active.is_(True),
            )
            .order_by(EmployeeMessengerAccount.is_primary.desc(), EmployeeMessengerAccount.id.asc())
            .all()
        )
        for account in numeric_account:
            if channel and account.channel != channel:
                continue
            if _looks_like_numeric_chat_id(account.external_user_id):
                return _normalized(account.external_user_id)

    legacy_user_id = _normalized(employee.telegram_user_id)
    if _looks_like_numeric_chat_id(legacy_user_id):
        return legacy_user_id
    return None


def set_primary_chat_id(
    employee: Employee,
    value: Optional[str],
    db: Session | None = None,
    channel: str = "telegram",
) -> None:
    normalized = _normalized(value)
    employee.telegram_user_id = normalized
    if db is not None and employee.id is not None:
        upsert_employee_channel_account(
            db,
            employee,
            channel=channel,
            external_user_id=normalized,
            external_username=_normalized(employee.telegram_username),
            make_primary=(channel == "telegram"),
        )


def get_public_chat_handle(
    employee: Employee,
    db: Session | None = None,
    channel: str = "telegram",
) -> Optional[str]:
    account = get_primary_account(employee, db=db, channel=channel)
    if account and _normalized(account.external_username):
        return _normalized(account.external_username)
    public_handle = _normalized(employee.telegram_username)
    if public_handle:
        return public_handle
    legacy_user_id = _normalized(employee.telegram_user_id)
    if legacy_user_id and not _looks_like_numeric_chat_id(legacy_user_id):
        return legacy_user_id
    return None


def set_public_chat_handle(
    employee: Employee,
    value: Optional[str],
    db: Session | None = None,
    channel: str = "telegram",
) -> None:
    normalized = _normalized(value)
    employee.telegram_username = normalized
    if db is not None and employee.id is not None and _looks_like_numeric_chat_id(employee.telegram_user_id):
        upsert_employee_channel_account(
            db,
            employee,
            channel=channel,
            external_user_id=_normalized(employee.telegram_user_id),
            external_username=normalized,
            make_primary=(channel == "telegram"),
        )


def upsert_employee_channel_account(
    db: Session,
    employee: Employee,
    *,
    channel: str,
    external_user_id: Optional[str],
    external_username: Optional[str] = None,
    make_primary: bool = False,
) -> Optional[EmployeeMessengerAccount]:
    normalized_user_id = _normalized(external_user_id)
    if employee.id is None or not normalized_user_id:
        return None

    conflicting_account = (
        db.query(EmployeeMessengerAccount)
        .filter(
            EmployeeMessengerAccount.channel == channel,
            EmployeeMessengerAccount.external_user_id == normalized_user_id,
            EmployeeMessengerAccount.employee_id != employee.id,
        )
        .first()
    )
    if conflicting_account:
        conflicting_employee = db.get(Employee, conflicting_account.employee_id)
        raise EmployeeIdentityConflictError(
            channel=channel,
            external_user_id=normalized_user_id,
            conflicting_employee_id=conflicting_account.employee_id,
            conflicting_employee_name=(getattr(conflicting_employee, "full_name", None) or "").strip() or None,
        )

    account = (
        db.query(EmployeeMessengerAccount)
        .filter(
            EmployeeMessengerAccount.employee_id == employee.id,
            EmployeeMessengerAccount.channel == channel,
            EmployeeMessengerAccount.external_user_id == normalized_user_id,
        )
        .first()
    )
    now = datetime.utcnow()
    if not account:
        account = EmployeeMessengerAccount(
            employee_id=employee.id,
            channel=channel,
            external_user_id=normalized_user_id,
            external_username=_normalized(external_username),
            is_primary=bool(make_primary),
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        db.add(account)
    else:
        account.external_username = _normalized(external_username)
        account.is_active = True
        if make_primary:
            account.is_primary = True
        account.updated_at = now

    if make_primary:
        primary_reset_query = db.query(EmployeeMessengerAccount).filter(
            EmployeeMessengerAccount.employee_id == employee.id,
        )
        if account.id is not None:
            primary_reset_query = primary_reset_query.filter(EmployeeMessengerAccount.id != account.id)
        primary_reset_query.update({"is_primary": False}, synchronize_session=False)
        account.is_primary = True

    return account


def sync_legacy_telegram_account(db: Session, employee: Employee) -> Optional[EmployeeMessengerAccount]:
    if not _looks_like_numeric_chat_id(employee.telegram_user_id):
        return None
    return upsert_employee_channel_account(
        db,
        employee,
        channel="telegram",
        external_user_id=_normalized(employee.telegram_user_id),
        external_username=_normalized(employee.telegram_username),
        make_primary=True,
    )


def get_manager_chat_id(employee: Employee) -> Optional[str]:
    return _normalized(employee.manager_telegram_id)


def get_mentor_adaptation_chat_id(employee: Employee) -> Optional[str]:
    return _normalized(employee.mentor_adaptation_telegram_id)


def get_mentor_ipr_chat_id(employee: Employee) -> Optional[str]:
    return _normalized(employee.mentor_ipr_telegram_id)
