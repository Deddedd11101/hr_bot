from datetime import datetime
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

from .config import settings
from .models import EmployeeVacationBalance
from .time_utils import utc_now


class BalanceInput(BaseModel):
    year: int = Field(strict=True)
    used_days: int | None = Field(strict=True, ge=0, le=9999)
    remaining_days: int | None = Field(strict=True, ge=0, le=9999)


def current_year():
    return datetime.now(ZoneInfo(settings.TIMEZONE)).year


def balance(db, employee_id):
    year = current_year()
    row = db.get(EmployeeVacationBalance, (employee_id, year))
    return dict(year=year, used_days=row.used_days if row else None,
                remaining_days=row.remaining_days if row else None)


def save_balance(db, employee_id, actor_id, values):
    from .web.grades import _lock_employee

    _lock_employee(db, employee_id)
    row = db.get(EmployeeVacationBalance, (employee_id, values.year))
    if row is None:
        row = EmployeeVacationBalance(employee_id=employee_id, year=values.year)
        db.add(row)
    row.used_days, row.remaining_days = values.used_days, values.remaining_days
    row.updated_by_account_id, row.updated_at = actor_id, utc_now()
    db.flush()
