"""Privacy-minimal read model of agreed absences, shared by admin and cabinet."""

from calendar import monthrange
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import and_, select

from .config import settings
from .models import CatalogGroup, CatalogMembership, Employee, EmployeeVacationRequest


def schedule(db, *, month=None, search="", group_id=None, page=1, page_size=30):
    try:
        first = date.fromisoformat(f"{month}-01") if month else datetime.now(
            ZoneInfo(settings.TIMEZONE)).date().replace(day=1)
    except ValueError as exc:
        raise ValueError("Укажите месяц в формате ГГГГ-ММ") from exc
    if not 1900 <= first.year <= 2100 or not 1 <= page <= 10000 or not 1 <= page_size <= 100:
        raise ValueError("Недопустимый период или страница")
    last = first.replace(day=monthrange(first.year, first.month)[1])
    query = select(EmployeeVacationRequest, Employee, CatalogGroup).join(
        Employee, Employee.id == EmployeeVacationRequest.employee_id).outerjoin(
        CatalogMembership, and_(CatalogMembership.scope == "people", CatalogMembership.object_id == Employee.id)
    ).outerjoin(CatalogGroup, and_(CatalogGroup.scope == "people", CatalogGroup.id == CatalogMembership.group_id)).where(
        Employee.employee_stage.in_(("staff", "adaptation", "ipr")),
        EmployeeVacationRequest.status == "approved",
        EmployeeVacationRequest.starts_on <= last, EmployeeVacationRequest.ends_on >= first,
    ).order_by(EmployeeVacationRequest.starts_on, Employee.id, EmployeeVacationRequest.id)
    if group_id == 0:
        query = query.where(CatalogMembership.group_id.is_(None))
    elif group_id is not None:
        query = query.where(CatalogMembership.group_id == group_id)
    term = search.strip().casefold()
    items = []
    for leave, employee, group in db.execute(query):
        name = (employee.full_name or "").strip()
        group_name = group.name if group else "Без группы"
        if not name or term and term not in f"{name} {group_name}".casefold():
            continue
        # Explicit allowlist: no comments, reasons, contacts, balances or HR metadata.
        items.append(dict(employee_id=employee.id, name=name, group_id=group.id if group else None,
            group_name=group_name, starts_on=leave.starts_on.isoformat(), ends_on=leave.ends_on.isoformat()))
    groups = db.scalars(select(CatalogGroup).where(CatalogGroup.scope == "people").order_by(CatalogGroup.name)).all()
    return dict(month=first.isoformat()[:7], days_in_month=last.day, total=len(items), page=page,
        page_size=page_size, groups=[dict(id=row.id, name=row.name) for row in groups],
        items=items[(page - 1) * page_size:page * page_size])
