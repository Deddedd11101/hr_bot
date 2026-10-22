"""Employee adaptation plans: explicit, versioned calendar-based scheduling."""

import hashlib
import json
import re
from datetime import date, datetime, time, timedelta

from pytz import timezone
from sqlalchemy.orm import Session

from .config import settings
from .models import AdaptationPlanTemplate, Employee, EmployeeAdaptationPlanItem, FlowLaunchRequest, ProductionCalendarVersion, ProductionCalendarYear, ScenarioProgress, ScenarioTemplate
from .positions import position_matches_scope
from .scenario_engine import matches_role_scope


def default_entries() -> list[dict]:
    rows = [
        ("organization", "scenario_6c14bc1720c2", "all", "first", 0, "workday"),
        ("first_day", "scenario_e77a50f331d4", "all", "first", 0, "workday"),
        ("week", "custom_scenario_bf4b01738d2c", "all", "first", 5, "workday"),
        ("test1", "custom_scenario_6d5d6d7e5738", "pm", "first", 9, "workday"),
        ("pulse1", "scenario_aae666a4c5bc", "all", "test1", 5, "workday"),
        ("middle", "custom_scenario_26921655a2b4", "all", "first", 45, "calendar"),
        ("test2", "scenario_3cca280ab7ec", "pm", "end", -14, "calendar"),
        ("pulse2", "scenario_aae666a4c5bc", "all", "test2", 5, "workday"),
        ("end_pm", "custom_scenario_042d1408d238", "pm", "end", -3, "workday"),
        ("end_other", "custom_scenario_e52d98379e63", "other", "end", -3, "workday"),
    ]
    return [{"key": key, "scenario_key": scenario, "group": group, "anchor": anchor, "offset": offset, "unit": unit, "time": "10:00"}
            for key, scenario, group, anchor, offset, unit in rows]


def template_data(db: Session) -> tuple[list[dict], int]:
    row = db.get(AdaptationPlanTemplate, 1)
    return (json.loads(row.entries_json), row.revision) if row else (default_entries(), 0)


def validate_entries(db: Session, entries) -> list[dict]:
    if not isinstance(entries, list) or not 1 <= len(entries) <= 40:
        raise ValueError("Нужно от 1 до 40 этапов")
    keys = [str(entry.get("key", "")) for entry in entries if isinstance(entry, dict)]
    if len(keys) != len(entries) or len(set(keys)) != len(keys) or any(not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", key) or key in {"first", "end"} for key in keys):
        raise ValueError("Нужны уникальные ключи этапов")
    output = []
    for entry in entries:
        scenario = db.query(ScenarioTemplate).filter_by(scenario_key=entry.get("scenario_key"), scenario_kind="scenario").first()
        if not scenario:
            raise ValueError("Сценарий этапа не найден")
        if entry.get("group") not in {"all", "pm", "other"} or entry.get("unit") not in {"workday", "calendar"}:
            raise ValueError("Неизвестная группа или единица интервала")
        anchor = str(entry.get("anchor", ""))
        if anchor not in {"first", "end", *keys}:
            raise ValueError("Неизвестная опорная дата")
        offset = entry.get("offset")
        if type(offset) is not int or not -365 <= offset <= 365:
            raise ValueError("Интервал должен быть целым числом от -365 до 365")
        clock = str(entry.get("time", ""))
        if not re.fullmatch(r"\d{2}:\d{2}", clock):
            raise ValueError("Укажите время ЧЧ:ММ")
        time.fromisoformat(clock)
        output.append({"key": entry["key"], "scenario_key": scenario.scenario_key, "group": entry["group"], "anchor": anchor,
                       "offset": offset, "unit": entry["unit"], "time": clock})
    by_key = {entry["key"]: entry for entry in output}
    for key in keys:
        seen = set()
        while key not in {"first", "end"}:
            if key in seen:
                raise ValueError("Циклическая зависимость этапов")
            seen.add(key)
            key = by_key[key]["anchor"]
    return output


class CalendarDates:
    def __init__(self, db: Session):
        self.db = db
        self.days = {}
        self.versions = {}

    def working(self, day: date) -> bool:
        if day.year not in self.versions:
            year = self.db.get(ProductionCalendarYear, day.year)
            version = self.db.get(ProductionCalendarVersion, year.current_version_id) if year and year.current_version_id else None
            if not version:
                raise ValueError(f"Не загружен производственный календарь {day.year}")
            self.versions[day.year] = version.id
            self.days.update({date.fromisoformat(row["date"]): row["is_workday"] for row in json.loads(version.days_json)})
        if day not in self.days:
            raise ValueError(f"В календаре нет даты {day}")
        return self.days[day]

    def shift(self, day: date, offset: int, unit: str) -> date:
        if unit == "calendar":
            day += timedelta(days=offset)
        else:
            for _ in range(abs(offset)):
                day += timedelta(days=1 if offset >= 0 else -1)
                while not self.working(day):
                    day += timedelta(days=1 if offset >= 0 else -1)
        for _ in range(370):
            if self.working(day):
                return day
            day += timedelta(days=1)
        raise ValueError("Не найден рабочий день")


def local_now() -> datetime:
    return datetime.now(timezone(settings.TIMEZONE)).replace(tzinfo=None)


def build_preview(db: Session, employee: Employee) -> dict:
    entries, revision = template_data(db)
    calendar = CalendarDates(db)
    by_key = {entry["key"]: entry for entry in entries}
    is_pm = position_matches_scope(employee.desired_position, "project_manager,rukovoditel_proektov,rukovoditel_proekta")
    scenarios = {row.scenario_key: row for row in db.query(ScenarioTemplate)}
    items = {row.entry_key: row for row in db.query(EmployeeAdaptationPlanItem).filter_by(employee_id=employee.id)}
    cache = {}
    def calculate(key, seen=()):
        if key in {"first", "end"}:
            value = employee.first_workday if key == "first" else employee.adaptation_end
            if not value:
                raise ValueError("Укажите первый рабочий день" if key == "first" else "Укажите дату окончания адаптации")
            return value
        if key in seen or key not in by_key:
            raise ValueError("Некорректная зависимость этапов")
        if key not in cache:
            entry = by_key[key]
            cache[key] = calendar.shift(calculate(entry["anchor"], (*seen, key)), entry["offset"], entry["unit"])
        return cache[key]
    rows = []
    occupied_times = set()
    visible_keys = set()
    for entry in entries:
        if entry["group"] not in {"all", "pm" if is_pm else "other"}:
            continue
        visible_keys.add(entry["key"])
        scenario = scenarios.get(entry["scenario_key"])
        item = items.get(entry["key"])
        error = ""
        planned = None
        try:
            if not scenario or not matches_role_scope(employee, scenario):
                raise ValueError("Сценарий недоступен для должности или статуса сотрудника")
            planned = datetime.combine(calculate(entry["key"]), time.fromisoformat(entry["time"]))
            while planned in occupied_times:
                planned += timedelta(minutes=10)
                planned = datetime.combine(calendar.shift(planned.date(), 0, "calendar"), planned.time())
            occupied_times.add(planned)
        except ValueError as exc:
            error = str(exc)
        pending = db.query(FlowLaunchRequest).filter_by(employee_id=employee.id, flow_key=entry["scenario_key"], processed_at=None).all()
        conflicts = [row.id for row in pending if not any(item.launch_request_id == row.id for item in items.values())]
        progress = db.query(ScenarioProgress).filter_by(employee_id=employee.id, scenario_key=entry["scenario_key"]).first()
        previous_completed = bool(progress and progress.is_completed)
        request = db.get(FlowLaunchRequest, item.launch_request_id) if item and item.launch_request_id else None
        item_status = "cancelled" if item and item.status in {"planned", "blocked"} and not request else item.status if item else None
        anchor_entry = by_key.get(entry["anchor"])
        anchor_scenario = scenarios.get(anchor_entry["scenario_key"]) if anchor_entry else None
        anchor_label = "первый рабочий день" if entry["anchor"] == "first" else "конец адаптации" if entry["anchor"] == "end" else anchor_scenario.title if anchor_scenario else entry["anchor"]
        unit_label = "раб. дн." if entry["unit"] == "workday" else "кал. дн."
        rows.append({"key": entry["key"], "scenario_key": entry["scenario_key"], "title": scenario.title if scenario else entry["scenario_key"],
                     "rule": entry, "rule_label": f"{entry['offset']:+d} {unit_label} · {anchor_label}", "proposed_at": planned.isoformat(timespec="minutes") if planned else "", "error": error,
                     "past": bool(planned and planned <= local_now()), "conflict_ids": conflicts, "previous_completed": previous_completed,
                     "item_id": item.id if item else None, "status": item_status or ("previously_completed" if previous_completed else "not_planned"),
                     "requested_at": item.requested_at.isoformat(timespec="minutes") if item else "", "manual_date": item.manual_date if item else False,
                     "last_error": item.last_error if item else None})
    for key, item in items.items():
        if key not in visible_keys:
            rows.append({"key": key, "scenario_key": item.flow_key, "title": item.title, "rule": None,
                         "proposed_at": "", "error": "Этап удалён из шаблона или изменена группа. Сохранённое расписание не изменено.",
                         "past": False, "conflict_ids": [], "previous_completed": False, "item_id": item.id,
                         "status": item.status, "requested_at": item.requested_at.isoformat(timespec="minutes"),
                         "manual_date": item.manual_date, "last_error": item.last_error})
    fingerprint = hashlib.sha256(json.dumps({"revision": revision, "first": str(employee.first_workday), "end": str(employee.adaptation_end),
                     "position": employee.desired_position, "blocked": employee.is_bot_blocked, "rows": rows, "calendars": calendar.versions}, sort_keys=True).encode()).hexdigest()
    return {"revision": revision, "fingerprint": fingerprint, "rows": rows, "calendar_versions": calendar.versions,
            "group": "PM" if is_pm else "Не PM", "timezone": settings.TIMEZONE}
