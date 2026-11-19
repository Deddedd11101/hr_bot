"""Append-only exact leave journal. Callers own authorization and commit/rollback."""

from datetime import date
from fractions import Fraction

from sqlalchemy import select, update

from .models import Employee, EmployeeLeaveOperation
from .vacation_accounting import LeaveBalance, LeaveKind, exact_amount


def _text(value, limit, label):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"Invalid {label}")
    return value.strip()


def _rows(db, employee_id, contract_key, kind):
    return db.scalars(select(EmployeeLeaveOperation).where(
        EmployeeLeaveOperation.employee_id == employee_id,
        EmployeeLeaveOperation.contract_key == contract_key,
        EmployeeLeaveOperation.kind == kind.value,
    ).order_by(EmployeeLeaveOperation.id)).all()


def _scope(employee_id, contract_key, kind):
    if type(employee_id) is not int or employee_id <= 0:
        raise ValueError("Invalid employee id")
    if not isinstance(kind, LeaveKind):
        raise ValueError("Unknown leave kind")
    return _text(contract_key, 128, "contract key")


def _balance(rows, kind):
    opening = None
    accrued = adjustment = used = reserved = Fraction(0)
    for row in rows:
        amount = Fraction(row.amount_exact)
        if row.operation == "opening":
            opening = amount
        elif row.operation == "accrual":
            accrued += amount
        elif row.operation == "adjustment":
            adjustment += amount
        elif row.operation == "reserve":
            reserved += amount
        elif row.operation == "release":
            reserved -= amount
        elif row.operation == "consume":
            reserved -= amount
            used += amount
    return LeaveBalance(kind, opening, accrued, adjustment, used, reserved)


def read_balance(db, employee_id, contract_key, kind):
    contract_key = _scope(employee_id, contract_key, kind)
    return _balance(_rows(db, employee_id, contract_key, kind), kind)


def append_operation(db, *, employee_id, contract_key, kind, operation,
                     operation_key, amount, effective_on, actor, reason,
                     reservation_key=None):
    """Serialize on employee before reading; duplicate keys must have identical payloads."""
    contract_key = _scope(employee_id, contract_key, kind)
    operation_key = _text(operation_key, 128, "operation key")
    reason = _text(reason, 1024, "reason")
    actor = _text(actor, 128, "actor")
    if type(effective_on) is not date:
        raise ValueError("An explicit effective date is required")
    if operation not in {"opening", "accrual", "adjustment", "reserve", "release", "consume"}:
        raise ValueError("Unknown operation")
    if (operation == "opening") != (operation_key == "opening"):
        raise ValueError("Opening uses the reserved key 'opening'")
    amount = exact_amount(amount)
    if len(str(amount)) > 256:
        raise ValueError("Amount is too large")
    if operation not in {"opening", "adjustment"} and amount <= 0:
        raise ValueError("This operation requires a positive amount")
    if operation in {"reserve", "release", "consume"}:
        reservation_key = _text(reservation_key, 128, "reservation key")
    elif reservation_key is not None:
        raise ValueError("Only reservation operations accept a reservation key")

    # Same lock pattern as employee/grade writes; no implicit commits or Telegram I/O.
    if not db.execute(update(Employee).where(Employee.id == employee_id).values(id=Employee.id)
                      .execution_options(synchronize_session=False)).rowcount:
        raise LookupError("Employee not found")
    rows = _rows(db, employee_id, contract_key, kind)
    payload = dict(operation=operation, amount_exact=str(amount), effective_on=effective_on,
                   actor=actor, reason=reason, reservation_key=reservation_key)
    existing = next((row for row in rows if row.operation_key == operation_key), None)
    if existing is not None:
        if any(getattr(existing, key) != value for key, value in payload.items()):
            raise ValueError("Operation key already used with different data")
        return existing
    if operation != "opening" and not any(row.operation == "opening" for row in rows):
        raise ValueError("Confirm opening balance before recording operations")
    if operation in {"release", "consume"}:
        outstanding = sum((Fraction(row.amount_exact) * (1 if row.operation == "reserve" else -1)
                           for row in rows if row.reservation_key == reservation_key), Fraction(0))
        if amount > outstanding:
            raise ValueError("Operation exceeds this reservation")
    if operation == "reserve" and kind != LeaveKind.ANNUAL:
        available = _balance(rows, kind).available
        if available is None or amount > available:
            raise ValueError("Insufficient balance for reservation")
    row = EmployeeLeaveOperation(employee_id=employee_id, contract_key=contract_key,
                                 kind=kind.value, operation_key=operation_key, **payload)
    db.add(row)
    db.flush()
    return row
