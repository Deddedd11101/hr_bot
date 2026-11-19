"""Exact vacation arithmetic; no database writes or scheduler side effects."""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, localcontext, ROUND_HALF_UP
from enum import Enum
from fractions import Fraction
from typing import Mapping


class LeaveKind(str, Enum):
    ANNUAL = "annual"
    FORCE_MAJEURE = "force_majeure"
    DAY_OFF = "day_off"


class CalendarDayKind(str, Enum):
    WORKDAY = "workday"
    WEEKEND = "weekend"
    HOLIDAY = "holiday"


def exact_amount(value: int | str | Decimal | Fraction) -> Fraction:
    if isinstance(value, bool) or not isinstance(value, (int, str, Decimal, Fraction)):
        raise ValueError("Use an exact number, not a float")
    try:
        return Fraction(value)
    except (ValueError, ZeroDivisionError, OverflowError) as error:
        raise ValueError("Invalid exact amount") from error


def display_amount(value: Fraction) -> str:
    with localcontext() as context:
        context.prec = max(28, len(str(abs(value.numerator))) + len(str(value.denominator)) + 4)
        amount = Decimal(value.numerator) / Decimal(value.denominator)
        return str(amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def annual_accrual(credited_months: int, annual_days: int = 28) -> Fraction:
    if type(credited_months) is not int or credited_months < 0:
        raise ValueError("Credited months must be a non-negative integer")
    if type(annual_days) is not int or annual_days <= 0:
        raise ValueError("Annual allowance must be a positive integer")
    return Fraction(credited_months * annual_days, 12)


def month_is_credited(eligible_calendar_days: int) -> bool:
    """Caller supplies eligible days for one anchored working month."""
    if type(eligible_calendar_days) is not int or not 0 <= eligible_calendar_days <= 31:
        raise ValueError("Eligible days must describe one working month")
    return eligible_calendar_days >= 15


@dataclass(frozen=True)
class LeaveBalance:
    kind: LeaveKind
    opening: Fraction | None
    accrued: Fraction = Fraction(0)
    adjustment: Fraction = Fraction(0)
    used: Fraction = Fraction(0)
    reserved: Fraction = Fraction(0)

    def __post_init__(self):
        if not isinstance(self.kind, LeaveKind):
            raise ValueError("Unknown leave kind")
        for name in ("opening", "accrued", "adjustment", "used", "reserved"):
            value = getattr(self, name)
            if value is None and name == "opening":
                continue
            object.__setattr__(self, name, exact_amount(value))
        if min(self.accrued, self.used, self.reserved) < 0:
            raise ValueError("Accrued, used and reserved must not be negative")

    @property
    def unit(self) -> str:
        return "hours" if self.kind == LeaveKind.DAY_OFF else "days"

    @property
    def balance(self) -> Fraction | None:
        if self.opening is None:
            return None
        return self.opening + self.accrued + self.adjustment - self.used

    @property
    def available(self) -> Fraction | None:
        total = self.balance
        return None if total is None else total - self.reserved


def annual_charge(starts_on: date, ends_on: date,
                  calendar: Mapping[date, CalendarDayKind]) -> int:
    """Inclusive range, excluding holidays only; missing classifications fail closed."""
    span = (ends_on - starts_on).days
    if not 0 <= span <= 365:
        raise ValueError("Choose an ordered range of at most 366 days")
    charged = 0
    for offset in range(span + 1):
        day = starts_on + timedelta(days=offset)
        kind = calendar.get(day)
        if not isinstance(kind, CalendarDayKind):
            raise ValueError(f"Missing calendar day classification: {day.isoformat()}")
        charged += kind != CalendarDayKind.HOLIDAY
    return charged
