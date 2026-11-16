from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

from .config import settings
from .models import Employee, EmployeeVacationBalance, EmployeeVacationRequest
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


class VacationDecision(BaseModel):
    approved: bool = Field(strict=True)


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
                workdays=row.workdays, status=row.status, manager_notice=row.manager_notice, hr_notice=row.hr_notice)


def requests_for(db, employee_id, *, for_hr=False):
    return [(hr_request_payload(db, row) if for_hr else request_payload(row))
            for row in db.query(EmployeeVacationRequest).filter_by(employee_id=employee_id)
            .order_by(EmployeeVacationRequest.id.desc()).limit(50)]


def hr_request_payload(db, row):
    from .vacation_delivery import manager_contact

    payload = request_payload(row)
    if row.status != "pending":
        return payload
    employee = db.get(Employee, row.employee_id)
    _, issue = manager_contact(db, employee, row.manager_id)
    return dict(payload, manager_issue=issue, can_route=(
        row.manager_id != employee.manager_employee_id or row.manager_notice == "unavailable"
    ) if employee and employee.manager_employee_id else False)


def submit(db, employee_id, period):
    from .web.grades import _lock_employee

    _lock_employee(db, employee_id)
    overlaps = db.query(EmployeeVacationRequest).filter(
        EmployeeVacationRequest.employee_id == employee_id, EmployeeVacationRequest.status.in_(("pending", "pending_hr", "approved")),
        EmployeeVacationRequest.starts_on <= period.ends_on, EmployeeVacationRequest.ends_on >= period.starts_on,
    )
    same = overlaps.filter_by(starts_on=period.starts_on, ends_on=period.ends_on).first()
    if same:
        return request_payload(same)
    if overlaps.first():
        raise ValueError("На эти даты уже есть заявка на отпуск")
    days = preview(db, period)
    employee = db.get(Employee, employee_id)
    row = EmployeeVacationRequest(employee_id=employee_id, starts_on=period.starts_on, ends_on=period.ends_on,
                                  workdays=days["workdays"], status="pending", created_at=utc_now(),
                                  manager_id=employee.manager_employee_id)
    db.add(row)
    db.flush()
    return request_payload(row)


def _locked_request(db, row_id, employee_id):
    from .web.grades import _lock_employee

    row = db.get(EmployeeVacationRequest, row_id)
    if not row or (employee_id is not None and row.employee_id != employee_id):
        raise LookupError("Заявка не найдена")
    _lock_employee(db, row.employee_id)
    db.refresh(row)
    return row


def route_to_current_manager(db, employee_id, row_id):
    from .vacation_delivery import manager_contact

    row = _locked_request(db, row_id, employee_id)
    employee = db.get(Employee, employee_id, populate_existing=True)
    if row.status != "pending":
        raise ValueError("Заявка уже не на этапе согласования руководителем")
    current_manager = employee.manager_employee_id
    if current_manager == row.manager_id and row.manager_notice != "unavailable":
        raise ValueError("Повторная отправка текущему руководителю недоступна")
    chat, issue = manager_contact(db, employee, current_manager)
    if not chat:
        raise ValueError(issue)
    row.manager_id = current_manager
    row.manager_revision += 1
    row.manager_notice = "pending"
    db.flush()
    return hr_request_payload(db, row)


def decide(db, row_id, *, approved, employee_id=None, hr_account_id=None, telegram_id=None, manager_revision=None):
    from .vacation_delivery import manager_chat

    row = _locked_request(db, row_id, employee_id)
    if hr_account_id is not None:
        if row.status != "pending_hr" and (approved or row.status != "pending"):
            raise ValueError("Заявку нельзя согласовать или отклонить на этом этапе")
        row.hr_account_id, row.hr_decided_at = hr_account_id, utc_now()
        row.status = "approved" if approved else "rejected"
    else:
        if manager_revision != row.manager_revision:
            raise ValueError("Кнопка устарела: заявка была перенаправлена")
        if not telegram_id or manager_chat(db, row) != telegram_id:
            raise PermissionError("Решение может принять только назначенный руководитель")
        if row.status != "pending":
            raise ValueError("Решение по заявке уже принято")
        row.manager_decided_at = utc_now()
        row.status = "pending_hr" if approved else "rejected"
    db.flush()
    return request_payload(row)
