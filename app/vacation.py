from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

from .config import settings
from .models import EmployeeVacationBalance, EmployeeVacationRequest
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


class VacationPeriod(BaseModel):
    starts_on: date
    ends_on: date


def preview(db, period):
    from .adaptation_planning import CalendarDates

    span = (period.ends_on - period.starts_on).days
    today = datetime.now(ZoneInfo(settings.TIMEZONE)).date()
    if period.starts_on < today or not 0 <= span <= 365:
        raise ValueError("Выберите будущий период не длиннее 366 календарных дней")
    calendar = CalendarDates(db)
    workdays = sum(calendar.working(period.starts_on + timedelta(days=i)) for i in range(span + 1))
    return dict(calendar_days=span + 1, workdays=workdays, non_workdays=span + 1 - workdays)


def request_payload(row):
    return dict(id=row.id, starts_on=row.starts_on.isoformat(), ends_on=row.ends_on.isoformat(),
                workdays=row.workdays, status=row.status)


def requests_for(db, employee_id):
    return [request_payload(row) for row in db.query(EmployeeVacationRequest).filter_by(employee_id=employee_id)
            .order_by(EmployeeVacationRequest.id.desc()).limit(50)]


def submit(db, employee_id, period):
    from .web.grades import _lock_employee

    _lock_employee(db, employee_id)
    overlaps = db.query(EmployeeVacationRequest).filter(
        EmployeeVacationRequest.employee_id == employee_id, EmployeeVacationRequest.status.in_(("pending", "approved")),
        EmployeeVacationRequest.starts_on <= period.ends_on, EmployeeVacationRequest.ends_on >= period.starts_on,
    )
    same = overlaps.filter_by(starts_on=period.starts_on, ends_on=period.ends_on).first()
    if same:
        return request_payload(same)
    if overlaps.first():
        raise ValueError("На эти даты уже есть заявка на отпуск")
    days = preview(db, period)
    row = EmployeeVacationRequest(employee_id=employee_id, starts_on=period.starts_on, ends_on=period.ends_on,
                                  workdays=days["workdays"], status="pending", created_at=utc_now())
    db.add(row)
    db.flush()
    return request_payload(row)
