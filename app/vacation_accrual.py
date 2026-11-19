"""Explicitly invoked annual accrual; not registered with the worker scheduler."""

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum
from fractions import Fraction

from sqlalchemy import select, update

from .models import Employee, EmployeeLeaveOperation
from .vacation_accounting import LeaveKind, annual_accrual
from .vacation_ledger import append_operation


class MonthEndPolicy(str, Enum):
    CLAMP_TO_LAST_DAY = "clamp_to_last_day"


@dataclass(frozen=True)
class AccrualItem:
    month_start: date
    earned_on: date
    amount: Fraction

    @property
    def operation_key(self):
        return f"annual-month:{self.month_start.isoformat()}"


def _anchor(hired_on, offset, policy):
    month_index = hired_on.year * 12 + hired_on.month - 1 + offset
    year, zero_month = divmod(month_index, 12)
    month = zero_month + 1
    last = monthrange(year, month)[1]
    if hired_on.day > last and policy is None:
        raise ValueError("Confirm month-end policy for this employment date")
    return date(year, month, min(hired_on.day, last))


def preview_accrual(*, hired_on, through, opening_through,
                    no_exclusions_confirmed, month_end_policy=None):
    """Opening includes all accrual earned on/before opening_through."""
    if any(type(day) is not date for day in (hired_on, through, opening_through)):
        raise ValueError("Explicit employment, snapshot and calculation dates are required")
    if no_exclusions_confirmed is not True:
        raise ValueError("HR must review periods excluded from accrual")
    if month_end_policy is not None and not isinstance(month_end_policy, MonthEndPolicy):
        raise ValueError("Unknown month-end policy")
    if hired_on > through or opening_through < hired_on or opening_through > through:
        raise ValueError("Invalid employment/snapshot/calculation range")
    # Long backfills are intentionally bounded; migration supplies a confirmed opening.
    if (through - opening_through).days > 3660:
        raise ValueError("Accrual window exceeds ten years; use a confirmed opening")
    offset = max(0, (opening_through.year - hired_on.year) * 12
                 + opening_through.month - hired_on.month - 1)
    items = []
    while True:
        start = _anchor(hired_on, offset, month_end_policy)
        if start > through:
            break
        earned_on = start + timedelta(days=14)
        if opening_through < earned_on <= through:
            items.append(AccrualItem(start, earned_on, annual_accrual(1)))
        offset += 1
    return items


def accrue_annual(db, *, employee_id, contract_key, hired_on, through,
                  no_exclusions_confirmed, month_end_policy=None):
    """Caller must authorize, verify employment data, and commit or roll back atomically."""
    if type(employee_id) is not int or employee_id <= 0:
        raise ValueError("Invalid employee id")
    if not db.execute(update(Employee).where(Employee.id == employee_id).values(id=Employee.id)
                      .execution_options(synchronize_session=False)).rowcount:
        raise LookupError("Employee not found")
    rows = db.scalars(select(EmployeeLeaveOperation).where(
        EmployeeLeaveOperation.employee_id == employee_id,
        EmployeeLeaveOperation.contract_key == contract_key,
        EmployeeLeaveOperation.kind == LeaveKind.ANNUAL.value,
    )).all()
    opening = next((row for row in rows if row.operation == "opening"), None)
    if opening is None:
        raise ValueError("Confirm opening balance and its inclusive snapshot date first")
    plan = preview_accrual(hired_on=hired_on, through=through,
                           opening_through=opening.effective_on,
                           no_exclusions_confirmed=no_exclusions_confirmed,
                           month_end_policy=month_end_policy)
    policy = month_end_policy.value if month_end_policy else "regular"
    reason = f"Annual accrual v1; hired={hired_on.isoformat()}; month-end={policy}"
    previous = [row for row in rows if row.operation_key.startswith("annual-month:")]
    if any(row.reason != reason for row in previous):
        raise ValueError("Employment date or policy changed; HR reconciliation required")
    if previous and max(row.effective_on for row in previous) > through:
        raise ValueError("Calculation date precedes an already posted accrual")
    previous_keys = {row.operation_key for row in previous}
    if not previous_keys.issubset({item.operation_key for item in plan}):
        raise ValueError("Accrual history does not match the confirmed snapshot")
    for item in plan:
        append_operation(db, employee_id=employee_id, contract_key=contract_key,
            kind=LeaveKind.ANNUAL, operation="accrual", operation_key=item.operation_key,
            amount=item.amount, effective_on=item.earned_on, actor="system:annual-accrual",
            reason=reason)
    return [item for item in plan if item.operation_key not in previous_keys]
