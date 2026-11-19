import hashlib
import hmac
import json
import re
import time
from datetime import UTC
from pathlib import Path
from urllib.parse import parse_qsl
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from sqlalchemy import and_

from ..config import settings
from ..database import get_session
from ..messaging.identity import find_employees_by_channel_user_id, get_primary_chat_id
from ..models import (
    BotMenuSet, CatalogGroup, CatalogMembership, Employee, EmployeeAdaptationPlanItem, EmployeeFile,
    Grade, GradeAssessment, GradeDevelopmentCycle, GradeDevelopmentMilestone, HrSettings,
)
from ..staff_email_verification import is_verified, verification_required
from ..vacation import VacationPeriod, calendar_month, preview as preview_vacation, requests_for, submit as submit_vacation

router = APIRouter(prefix="/employee-cabinet")
PILOT_EMPLOYEE_IDS = {70, 80, 84}
STAFF_STAGES = ("staff", "adaptation", "ipr")
PRIVATE_HEADERS = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}


def signed_telegram_id(raw, token, now, *, max_age=1800):
    if not raw or len(raw) > 8192 or not token:
        return None
    try:
        pairs = parse_qsl(raw, keep_blank_values=True, strict_parsing=True, max_num_fields=32)
        fields = dict(pairs)
        if len(pairs) != len(fields):
            return None
        signature = fields.pop("hash")
        secret = hmac.digest(b"WebAppData", token.encode(), hashlib.sha256)
        check = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
        if not hmac.compare_digest(hmac.new(secret, check.encode(), hashlib.sha256).hexdigest(), signature):
            return None
        if not -30 <= now - int(fields["auth_date"]) <= max_age:
            return None
        user_id = json.loads(fields["user"])["id"]
        return str(user_id) if type(user_id) is int and 0 < user_id < 2**52 else None
    except (KeyError, ValueError, TypeError):
        return None


def pilot_employee(db, telegram_id):
    if not telegram_id or not settings.EMPLOYEE_CABINET_URL:
        return None
    matches = find_employees_by_channel_user_id(db, channel="telegram", external_user_id=telegram_id)
    if len(matches) != 1:
        return None
    person = matches[0]
    if (person.id in PILOT_EMPLOYEE_IDS and person.employee_stage in STAFF_STAGES
            and not person.is_bot_blocked and verification_required(person)
            and is_verified(db, person, telegram_id) and get_primary_chat_id(person, db=db) == telegram_id):
        return person
    return None


def authorize(db, request):
    telegram_id = signed_telegram_id(request.headers.get("X-Telegram-Init-Data"), settings.TELEGRAM_BOT_TOKEN, time.time())
    employee = pilot_employee(db, telegram_id)
    if not employee:
        raise HTTPException(403, "Кабинет доступен только через Telegram пилота.", headers=PRIVATE_HEADERS)
    return employee


def own_files(db, employee):
    return db.query(EmployeeFile).filter_by(employee_id=employee.id, direction="inbound")


def development(db, employee):
    from .grades import GradeConflictError, assessment_payload

    def local_date(value):
        return value.replace(tzinfo=UTC).astimezone(ZoneInfo(settings.TIMEZONE)).date().isoformat()

    adaptation = db.query(EmployeeAdaptationPlanItem).filter_by(employee_id=employee.id).filter(
        EmployeeAdaptationPlanItem.status.not_in(("cancelled", "archived")),
    ).order_by(EmployeeAdaptationPlanItem.requested_at).all()
    cycle = db.query(GradeDevelopmentCycle).filter_by(employee_id=employee.id).one_or_none()
    milestones = db.query(GradeDevelopmentMilestone).filter_by(employee_id=employee.id,
        assessment_id=cycle.assessment_id).order_by(GradeDevelopmentMilestone.due_at).all() if cycle else []
    latest = db.query(GradeAssessment).filter_by(employee_id=employee.id, status="final", archived_at=None).order_by(
        GradeAssessment.finalized_at.desc(), GradeAssessment.id.desc(),
    ).first()
    grade = None
    if latest:
        level = db.get(Grade, latest.current_grade_id) if latest.current_grade_id else None
        try:
            assessment = assessment_payload(db, latest.id)
        except GradeConflictError:
            assessment = None
        if assessment:
            grade = {"label": level.name if level else None, "date": local_date(latest.finalized_at) if latest.finalized_at else None,
                     "categories": [{"name": row["categoryName"], "percent": round(25 * row["current"])}
                                    for row in assessment.get("categories", []) if row.get("assessed_count", 1)]}
    names = {"ipr6": "Промежуточная встреча", "ipr12": "Итоговая встреча", "review12": "Годовое ревью"}
    adapting = employee.employee_stage == "adaptation"
    rows = (
        [{"title": item.title, "date": local_date(item.requested_at), "status": item.status} for item in adaptation]
        if adapting else
        [{"title": names[item.kind], "date": item.due_at.date().isoformat(),
          "status": "paused" if not cycle.enabled and item.status in {"planned", "blocked"} else item.status}
         for item in milestones if item.kind in names and item.status != "cancelled"]
    )
    active_states = {"starting", "started", "in_progress", "running"}
    current = next((row for row in reversed(rows) if row["status"] in active_states), None)
    upcoming = next((row for row in rows if row["status"] in {"planned", "scheduled", "blocked", "paused"}), None)
    return {
        "active": "adaptation" if adapting else "development",
        "current": current,
        "upcoming": upcoming,
        "grade": grade,
    }


@router.get("", include_in_schema=False)
def cabinet_page():
    return FileResponse(Path(__file__).resolve().parents[1] / "static" / "employee-cabinet.html", headers=PRIVATE_HEADERS)


@router.get("/profile")
def profile(request: Request):
    from ..vacation import balance

    with get_session() as db:
        employee = authorize(db, request)

        def contact(employee_id):
            related = db.get(Employee, employee_id) if employee_id else None
            if not related:
                return None
            username = (related.telegram_username or "").strip().lstrip("@")
            return {"name": related.full_name, "username": username if re.fullmatch(r"[A-Za-z0-9_]{5,32}", username) else None}

        return JSONResponse({
            "name": employee.full_name, "position": employee.desired_position,
            "email": employee.work_email, "hours": employee.work_hours,
            "birthday": employee.birth_date.strftime("%d.%m") if employee.birth_date else None,
            "vacation": balance(db, employee.id),
            "first_workday": employee.first_workday.isoformat() if employee.first_workday else None,
            "manager": contact(employee.manager_employee_id), "adaptation_mentor": contact(employee.mentor_adaptation_employee_id),
            "development_mentor": contact(employee.mentor_ipr_employee_id), "development": development(db, employee),
            "files": [{"id": item.id, "name": item.original_filename, "size": item.file_size,
                       "material": {"ipr": "ipr", "probation_plan": "adaptation"}.get(item.category)}
                      for item in own_files(db, employee).order_by(EmployeeFile.id.desc())],
        }, headers=PRIVATE_HEADERS)


@router.get("/vacation/requests")
def vacation_requests(request: Request):
    with get_session() as db:
        employee = authorize(db, request)
        return JSONResponse(requests_for(db, employee.id), headers=PRIVATE_HEADERS)


@router.get("/vacation/team-schedule")
def vacation_team_schedule(request: Request,
    month: str | None = Query(None, pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$"),
    year: int | None = Query(None, ge=1900, le=2100),
    search: str = Query("", max_length=200), group_id: int | None = Query(None, ge=0),
    page: int = Query(1, ge=1, le=10000)):
    from ..vacation_schedule import schedule
    with get_session() as db:
        authorize(db, request)
        try:
            return JSONResponse(schedule(db, month=month, year=year, search=search, group_id=group_id, page=page), headers=PRIVATE_HEADERS)
        except ValueError as exc:
            raise HTTPException(422, str(exc), headers=PRIVATE_HEADERS) from exc


def directory_entries(db, viewer_id):
    rows = db.query(Employee, CatalogGroup.id, CatalogGroup.name).outerjoin(
        CatalogMembership, and_(CatalogMembership.scope == "people", CatalogMembership.object_id == Employee.id),
    ).outerjoin(
        CatalogGroup, and_(CatalogGroup.scope == "people", CatalogGroup.id == CatalogMembership.group_id),
    ).filter(Employee.employee_stage.in_(STAFF_STAGES), Employee.id != viewer_id)
    entries = []
    for person, group_id, group_name in rows:
        name = (person.full_name or "").strip()
        if not name:
            continue
        chat_id = directory_chat(db, person)
        username = (person.telegram_username or "").strip().removeprefix("@")
        if not re.fullmatch(r"[A-Za-z0-9_]{5,32}", username) or not chat_id:
            username = None
        entries.append({"name": name, "position": person.desired_position, "username": username,
                        "avatar_id": person.id if chat_id else None,
                        "group_id": group_id, "group_name": group_name})
    return entries


def directory_chat(db, person):
    if not person or person.is_bot_blocked or person.employee_stage not in STAFF_STAGES:
        return None
    chat_id = get_primary_chat_id(person, db=db, channel="telegram")
    if not chat_id or not re.fullmatch(r"[1-9][0-9]{0,15}", chat_id):
        return None
    owners = find_employees_by_channel_user_id(db, channel="telegram", external_user_id=chat_id)
    return chat_id if [owner.id for owner in owners] == [person.id] else None


@router.get("/colleagues")
def colleagues(request: Request):
    with get_session() as db:
        employee = authorize(db, request)
        return JSONResponse(directory_entries(db, employee.id), headers=PRIVATE_HEADERS)


@router.get("/colleagues/{employee_id}/avatar")
async def colleague_avatar(request: Request, employee_id: int):
    from starlette.concurrency import run_in_threadpool

    from ..cabinet_avatars import telegram_avatar

    def resolve_chat():
        with get_session() as db:
            viewer = authorize(db, request)
            if viewer.id == employee_id or not 0 < employee_id < 2**63:
                return None
            return directory_chat(db, db.get(Employee, employee_id))

    chat_id = await run_in_threadpool(resolve_chat)
    data = await telegram_avatar(chat_id) if chat_id else None
    if data is None:
        raise HTTPException(404, headers=PRIVATE_HEADERS)
    return Response(data, media_type="image/jpeg", headers=PRIVATE_HEADERS)


def knowledge_links(db, employee, root_id):
    from ..messaging.service import _menu_button_rows, menu_set_matches_employee

    seen = set()

    def walk(menu_id, depth):
        if not menu_id or menu_id in seen or depth > 8 or len(seen) >= 64:
            return []
        seen.add(menu_id)
        menu = db.get(BotMenuSet, menu_id)
        if not menu or menu.employee_scope == "candidates" or not menu_set_matches_employee(employee, menu):
            return []
        stages = {value.strip() for value in (menu.target_employee_stages or "").split(",") if value.strip()}
        if stages and employee.employee_stage not in stages:
            return []
        items = []
        for row in _menu_button_rows(db, menu):
            for button in row:
                label = button.label.strip()
                if not label:
                    continue
                if button.action_type == "open_url":
                    items.append({"label": label, "url": button.url})
                elif button.action_type == "open_set":
                    children = walk(button.target_menu_set_id, depth + 1)
                    if children:
                        items.append({"label": label, "children": children})
        return items

    return walk(root_id, 0)


@router.get("/knowledge")
def knowledge(request: Request):
    with get_session() as db:
        employee = authorize(db, request)
        hr = db.get(HrSettings, 1)
        return JSONResponse(knowledge_links(db, employee, hr.cabinet_knowledge_menu_set_id if hr else None),
                            headers=PRIVATE_HEADERS)


@router.post("/vacation/preview")
def vacation_preview(request: Request, period: VacationPeriod):
    with get_session() as db:
        authorize(db, request)
        try:
            return JSONResponse(preview_vacation(db, period), headers=PRIVATE_HEADERS)
        except ValueError as exc:
            raise HTTPException(422, str(exc), headers=PRIVATE_HEADERS) from exc


@router.get("/vacation/calendar")
def vacation_calendar(request: Request, month: str | None = Query(None, pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$")):
    with get_session() as db:
        authorize(db, request)
        try:
            return JSONResponse(calendar_month(db, month), headers=PRIVATE_HEADERS)
        except ValueError as exc:
            raise HTTPException(422, str(exc), headers=PRIVATE_HEADERS) from exc


@router.post("/vacation/requests")
def vacation_submit(request: Request, period: VacationPeriod):
    with get_session() as db:
        employee = authorize(db, request)
        try:
            result = submit_vacation(db, employee.id, period)
        except ValueError as exc:
            raise HTTPException(422, str(exc), headers=PRIVATE_HEADERS) from exc
        db.commit()
        return JSONResponse(result, headers=PRIVATE_HEADERS)


@router.get("/files/{file_id}")
def download(file_id: int, request: Request):
    with get_session() as db:
        employee = authorize(db, request)
        item = own_files(db, employee).filter_by(id=file_id).first()
        if not item:
            raise HTTPException(404, headers=PRIVATE_HEADERS)
        root = Path(settings.FILE_STORAGE_DIR).expanduser().resolve() / str(employee.id)
        path = Path(item.stored_path).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise HTTPException(404, headers=PRIVATE_HEADERS)
        return FileResponse(path, filename=item.original_filename, media_type="application/octet-stream", headers=PRIVATE_HEADERS)
