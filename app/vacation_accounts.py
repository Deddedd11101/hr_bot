"""HR-confirmed employment settings, independent of adaptation first_workday."""

from datetime import date, datetime
from fractions import Fraction
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select, update

from .config import settings
from .models import Employee, EmployeeLeaveAccount, EmployeeLeaveOperation
from .time_utils import utc_now
from .vacation_accounting import LeaveKind, display_amount
from .vacation_accrual import MonthEndPolicy, preview_accrual
from .vacation_ledger import read_balance


def today():
    return datetime.now(ZoneInfo(settings.TIMEZONE)).date()


class AccountInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    contract_key: str = Field(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_-]+$")
    employed_on: date
    reviewed_through: date | None = None
    month_end_policy: MonthEndPolicy | None = None
    revision: int = Field(strict=True, ge=0)
    reason: str = Field(min_length=1, max_length=1024)


class AccrualPreviewInput(BaseModel):
    contract_key: str = Field(min_length=1, max_length=128)
    through: date


def list_accounts(db, employee_id):
    rows = db.scalars(select(EmployeeLeaveAccount).where(
        EmployeeLeaveAccount.employee_id == employee_id).order_by(EmployeeLeaveAccount.id)).all()
    result = []
    for row in rows:
        balances = []
        for kind in LeaveKind:
            balance = read_balance(db, employee_id, row.contract_key, kind)
            balances.append(dict(kind=kind.value, unit=balance.unit,
                available=display_amount(balance.available) if balance.available is not None else None,
                reserved=display_amount(balance.reserved), used=display_amount(balance.used)))
        result.append(dict(contract_key=row.contract_key, employed_on=row.employed_on.isoformat(),
            reviewed_through=row.reviewed_through.isoformat() if row.reviewed_through else None,
            month_end_policy=row.month_end_policy, revision=row.revision, balances=balances))
    return result


def save_account(db, employee_id, actor_id, values):
    if not values.reason.strip():
        raise ValueError("Укажите основание изменения")
    if values.employed_on < date(1900, 1, 1) or values.employed_on > today():
        raise ValueError("Укажите фактическую дату трудоустройства, не будущую")
    if values.reviewed_through and not values.employed_on <= values.reviewed_through <= today():
        raise ValueError("Дата проверки периодов должна быть между трудоустройством и сегодня")
    if not db.execute(update(Employee).where(Employee.id == employee_id).values(id=Employee.id)
                      .execution_options(synchronize_session=False)).rowcount:
        raise LookupError("Сотрудник не найден")
    row = db.scalar(select(EmployeeLeaveAccount).where(
        EmployeeLeaveAccount.employee_id == employee_id,
        EmployeeLeaveAccount.contract_key == values.contract_key))
    policy = values.month_end_policy.value if values.month_end_policy else None
    if row is None:
        if db.scalar(select(EmployeeLeaveAccount.id).where(EmployeeLeaveAccount.employee_id == employee_id).limit(1)) is not None:
            raise ValueError("Для сотрудника уже настроен отпускной учёт. Второй счёт сейчас не поддерживается.")
        if values.revision != 0:
            raise ValueError("Настройки изменились, обновите вкладку")
        row = EmployeeLeaveAccount(employee_id=employee_id, contract_key=values.contract_key, revision=1)
        db.add(row)
    else:
        if row.revision != values.revision:
            raise ValueError("Настройки изменились, обновите вкладку")
        has_operations = db.scalar(select(EmployeeLeaveOperation.id).where(
            EmployeeLeaveOperation.employee_id == employee_id,
            EmployeeLeaveOperation.contract_key == values.contract_key).limit(1)) is not None
        if has_operations and (row.employed_on != values.employed_on or row.month_end_policy != policy):
            raise ValueError("По договору есть операции: смена даты или политики требует сверки HR")
        row.revision += 1
    row.employed_on = values.employed_on
    row.month_end_policy = policy
    row.reviewed_through = values.reviewed_through
    row.reason = values.reason.strip()
    row.updated_by_account_id = actor_id
    row.updated_at = utc_now()
    db.flush()


def account_preview(db, employee_id, values):
    row = db.scalar(select(EmployeeLeaveAccount).where(
        EmployeeLeaveAccount.employee_id == employee_id,
        EmployeeLeaveAccount.contract_key == values.contract_key))
    if row is None:
        raise LookupError("Сначала сохраните настройки договора")
    if values.through > today():
        raise ValueError("Предпросмотр начислений доступен только по текущую дату")
    if row.reviewed_through is None or row.reviewed_through < values.through:
        raise ValueError("Подтвердите отсутствие исключаемых периодов по дату расчёта")
    operations = db.scalars(select(EmployeeLeaveOperation).where(
        EmployeeLeaveOperation.employee_id == employee_id,
        EmployeeLeaveOperation.contract_key == row.contract_key,
        EmployeeLeaveOperation.kind == LeaveKind.ANNUAL.value)).all()
    opening = next((entry for entry in operations if entry.operation == "opening"), None)
    if opening is None:
        raise ValueError("Не подтверждён входящий остаток и дата его среза. Начислений не будет.")
    plan = preview_accrual(hired_on=row.employed_on, through=values.through,
        opening_through=opening.effective_on, no_exclusions_confirmed=True,
        month_end_policy=MonthEndPolicy(row.month_end_policy) if row.month_end_policy else None)
    existing = {entry.operation_key for entry in operations}
    return dict(items=[dict(month_start=item.month_start.isoformat(), earned_on=item.earned_on.isoformat(),
        amount=display_amount(item.amount), posted=item.operation_key in existing) for item in plan],
        new_total=display_amount(sum((item.amount for item in plan if item.operation_key not in existing), Fraction(0))),
        opening_through=opening.effective_on.isoformat())
