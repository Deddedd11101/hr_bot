import json
from datetime import datetime

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from sqlalchemy import update
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..adaptation_planning import CalendarDates, build_preview, local_now, template_data, validate_entries
from ..database import get_session
from ..models import AdaptationPlanTemplate, Employee, EmployeeAdaptationPlanItem, FlowLaunchRequest, ScenarioTemplate
from ..time_utils import utc_now
from .support import require_api_auth

router = APIRouter()


def get_db():
    with get_session() as db:
        yield db


def _subject(db, employee_id):
    employee = db.get(Employee, employee_id)
    if not employee or employee.employee_stage == "candidate":
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    return employee


def _lock_subject(db, employee):
    db.execute(update(Employee).where(Employee.id == employee.id).values(id=Employee.id))
    db.refresh(employee)


def _timestamp(value):
    try:
        parsed = datetime.fromisoformat(str(value))
        if parsed.tzinfo is not None or parsed.second or parsed.microsecond or parsed <= local_now():
            raise ValueError()
        return parsed
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="Нужна будущая дата и время с точностью до минуты в часовом поясе приложения")


@router.get("/api/adaptation-plan/template")
def template_api(request: Request, db: Session = Depends(get_db)):
    require_api_auth(request)
    entries, revision = template_data(db)
    return {"entries": entries, "revision": revision, "scenario_options": [
        {"value": row.scenario_key, "label": row.title} for row in db.query(ScenarioTemplate).filter_by(scenario_kind="scenario").order_by(ScenarioTemplate.title)
    ]}


@router.post("/api/adaptation-plan/template")
def save_template(request: Request, payload: dict = Body(...), db: Session = Depends(get_db)):
    require_api_auth(request)
    try:
        entries = validate_entries(db, payload.get("entries"))
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    expected = payload.get("revision")
    db.execute(insert(AdaptationPlanTemplate).values(id=1, revision=0, entries_json="[]", updated_at=utc_now()).on_conflict_do_nothing(index_elements=["id"]))
    result = db.execute(update(AdaptationPlanTemplate).where(AdaptationPlanTemplate.id == 1, AdaptationPlanTemplate.revision == expected)
                        .values(revision=AdaptationPlanTemplate.revision + 1, entries_json=json.dumps(entries), updated_at=utc_now()))
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="Порядок изменён другим пользователем. Обновите страницу.")
    db.commit()
    return template_api(request, db)


@router.get("/api/employees/{employee_id}/adaptation-plan")
def plan_api(request: Request, employee_id: int, db: Session = Depends(get_db)):
    require_api_auth(request)
    return build_preview(db, _subject(db, employee_id))


@router.get("/api/adaptation-plan/working-days/{year}")
def working_days(request: Request, year: int, db: Session = Depends(get_db)):
    require_api_auth(request)
    from datetime import date, timedelta
    if not 2000 <= year <= 2100:
        raise HTTPException(status_code=422, detail="Некорректный год")
    calendar = CalendarDates(db)
    result = []
    day = date(year, 1, 1)
    try:
        while day.year == year:
            if calendar.working(day):
                result.append(day.isoformat())
            day += timedelta(days=1)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"year": year, "working_days": result}


@router.post("/api/employees/{employee_id}/adaptation-plan")
def apply_plan(request: Request, employee_id: int, payload: dict = Body(...), db: Session = Depends(get_db)):
    require_api_auth(request)
    employee = _subject(db, employee_id)
    _lock_subject(db, employee)
    preview = build_preview(db, employee)
    if payload.get("fingerprint") != preview["fingerprint"]:
        raise HTTPException(status_code=409, detail="Даты, календарь или план изменились. Обновите предпросмотр.")
    if payload.get("rules_confirmed") is not True:
        raise HTTPException(status_code=422, detail="Подтвердите правила расчёта и выбранные даты")
    if employee.is_bot_blocked:
        raise HTTPException(status_code=409, detail="Доступ сотрудника к боту заблокирован")
    selected = payload.get("rows")
    if not isinstance(selected, list) or not 1 <= len(selected) <= 40:
        raise HTTPException(status_code=422, detail="Выберите этапы для планирования")
    if any(not isinstance(choice, dict) or not isinstance(choice.get("key"), str) for choice in selected):
        raise HTTPException(status_code=422, detail="Некорректный состав этапов")
    rows = {row["key"]: row for row in preview["rows"]}
    if payload.get("full_plan") is True:
        expected = {key for key, row in rows.items() if not row["item_id"]}
        if {choice.get("key") for choice in selected if isinstance(choice, dict)} != expected:
            raise HTTPException(status_code=422, detail="Нужно запланировать все этапы плана")
    seen = set()
    try:
        for choice in selected:
            key = choice.get("key") if isinstance(choice, dict) else None
            row = rows.get(key)
            if not row or key in seen or row["item_id"] or row["error"] or row["conflict_ids"]:
                raise HTTPException(status_code=409, detail="Этап уже запланирован, недоступен или имеет конфликт расписания")
            seen.add(key)
            requested_at = _timestamp(choice.get("requested_at"))
            if not CalendarDates(db).working(requested_at.date()):
                raise ValueError("Выберите рабочий день для запуска")
            launch = FlowLaunchRequest(employee_id=employee.id, flow_key=row["scenario_key"], requested_at=requested_at, launch_type="adaptation_plan")
            db.add(launch)
            db.flush()
            db.add(EmployeeAdaptationPlanItem(employee_id=employee.id, entry_key=key, flow_key=row["scenario_key"], title=row["title"],
                   requested_at=requested_at, launch_request_id=launch.id, status="planned", manual_date=choice.get("requested_at") != row["proposed_at"],
                   calculation_json=json.dumps({"revision": preview["revision"], "rule": row["rule"], "calendar_versions": preview["calendar_versions"],
                   "first_workday": str(employee.first_workday), "adaptation_end": preview["adaptation_end"], "adaptation_midpoint": preview["adaptation_midpoint"], "proposed_at": row["proposed_at"]})))
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="План уже изменён. Обновите страницу.") from exc
    except HTTPException:
        db.rollback()
        raise
    return build_preview(db, employee)


@router.post("/api/employees/{employee_id}/adaptation-plan/replan")
def replan(request: Request, employee_id: int, payload: dict = Body(...), db: Session = Depends(get_db)):
    require_api_auth(request)
    employee = _subject(db, employee_id)
    _lock_subject(db, employee)
    preview = build_preview(db, employee)
    if payload.get("fingerprint") != preview["fingerprint"] or payload.get("rules_confirmed") is not True:
        raise HTTPException(status_code=409, detail="План изменился. Повторите расчёт и подтвердите даты.")
    if employee.is_bot_blocked:
        raise HTTPException(status_code=409, detail="Доступ сотрудника к боту заблокирован")
    remaining = [row for row in preview["rows"] if row["item_id"] and row["status"] in {"planned", "blocked"}]
    choices = payload.get("rows")
    if not isinstance(choices, list) or not remaining or len(choices) != len(remaining) or any(not isinstance(row, dict) or not isinstance(row.get("key"), str) for row in choices):
        raise HTTPException(status_code=422, detail="Нужны все оставшиеся запланированные этапы")
    dates = {row.get("key"): row.get("requested_at") for row in choices}
    if set(dates) != {row["key"] for row in remaining}:
        raise HTTPException(status_code=422, detail="Состав оставшихся этапов изменился")
    try:
        changes = []
        for row in remaining:
            if row["error"] or row["conflict_ids"]:
                raise HTTPException(status_code=409, detail=f"{row['title']}: {row['error'] or 'конфликт расписания'}")
            item = db.get(EmployeeAdaptationPlanItem, row["item_id"])
            launch = db.get(FlowLaunchRequest, item.launch_request_id) if item.launch_request_id else None
            if item.status not in {"planned", "blocked"} or not launch or launch.processed_at is not None:
                raise HTTPException(status_code=409, detail="Один из этапов уже обрабатывается")
            value = _timestamp(dates[row["key"]])
            if not CalendarDates(db).working(value.date()):
                raise ValueError("Выберите рабочий день для запуска")
            changes.append((item, launch, value, row))
        for item, launch, value, row in changes:
            item.requested_at = launch.requested_at = value
            item.manual_date = dates[row["key"]] != row["proposed_at"]
            item.calculation_json = json.dumps({"revision": preview["revision"], "rule": row["rule"], "calendar_versions": preview["calendar_versions"], "proposed_at": row["proposed_at"], "first_workday": str(employee.first_workday), "adaptation_end": preview["adaptation_end"]})
        db.commit()
    except (HTTPException, ValueError) as exc:
        db.rollback()
        if isinstance(exc, ValueError):
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        raise
    return build_preview(db, employee)


@router.patch("/api/employees/{employee_id}/adaptation-plan/{item_id}")
def edit_item(request: Request, employee_id: int, item_id: int, payload: dict = Body(...), db: Session = Depends(get_db)):
    require_api_auth(request)
    employee = _subject(db, employee_id)
    _lock_subject(db, employee)
    item = db.query(EmployeeAdaptationPlanItem).filter_by(id=item_id, employee_id=employee_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Этап не найден")
    if item.status not in {"planned", "blocked", "failed", "cancelled"} or item.requested_at.isoformat(timespec="minutes") != payload.get("expected_at"):
        raise HTTPException(status_code=409, detail="Этап уже запущен или изменён. Обновите страницу.")
    launch = db.get(FlowLaunchRequest, item.launch_request_id) if item.launch_request_id else None
    if launch and launch.processed_at is not None and item.status in {"planned", "blocked"}:
        raise HTTPException(status_code=409, detail="Запуск уже обрабатывается")
    if payload.get("action") == "cancel":
        if launch and launch.processed_at is None:
            db.delete(launch)
        item.launch_request_id = None
        item.status = "cancelled"
    else:
        value = _timestamp(payload.get("requested_at"))
        try:
            if not CalendarDates(db).working(value.date()):
                raise ValueError("Выберите рабочий день для запуска")
        except ValueError as exc:
            db.rollback()
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if not launch or launch.processed_at:
            launch = FlowLaunchRequest(employee_id=employee.id, flow_key=item.flow_key, launch_type="adaptation_plan", requested_at=value)
            db.add(launch)
            db.flush()
            item.launch_request_id = launch.id
        launch.requested_at = value
        item.requested_at = value
        item.manual_date = True
        item.status = "planned"
        item.last_error = None
    db.commit()
    return build_preview(db, employee)
