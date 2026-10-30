"""Explicit operator reset of adaptation only; no sends or record deletion."""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from sqlalchemy import or_, text

from .adaptation_planning import template_data
from .models import Employee, EmployeeAdaptationPlanItem, FlowLaunchRequest, ScenarioAnswerRun, ScenarioProgress
from .time_utils import utc_now


def preview(db, employee_id):
    if db.get(Employee, employee_id) is None:
        raise ValueError("Сотрудник не найден")
    items = db.query(EmployeeAdaptationPlanItem).filter_by(employee_id=employee_id).filter(
        EmployeeAdaptationPlanItem.status != "archived").order_by(EmployeeAdaptationPlanItem.id).all()
    entries, revision = template_data(db)
    keys = {entry["scenario_key"] for entry in entries} | {item.flow_key for item in items}
    active = db.query(ScenarioProgress).filter(
        or_(ScenarioProgress.employee_id == employee_id, ScenarioProgress.recipient_employee_id == employee_id),
        or_(ScenarioProgress.waiting_for_response.is_(True), ScenarioProgress.is_completed.is_(False)),
    ).order_by(ScenarioProgress.id).all()
    selected = [p for p in active if p.employee_id == employee_id and p.scenario_key in keys
                and p.feedback_run_id is None and p.survey_launch_id is None]
    pending = db.query(FlowLaunchRequest).filter(FlowLaunchRequest.employee_id == employee_id,
        FlowLaunchRequest.flow_key.in_(keys), FlowLaunchRequest.processed_at.is_(None)).order_by(FlowLaunchRequest.id).all()
    plan = dict(employee_id=employee_id, revision=revision,
        items=[dict(id=i.id, key=i.entry_key, flow_key=i.flow_key, status=i.status,
                    requested_at=i.requested_at.isoformat(), launch_request_id=i.launch_request_id,
                    calculation_json=i.calculation_json) for i in items],
        progress=[dict(id=p.id, scenario_key=p.scenario_key, step=p.current_step_key,
                       updated_at=p.updated_at.isoformat(), answer_run_id=p.answer_run_id) for p in selected],
        pending_request_ids=[r.id for r in pending],
        request_versions=[(r.id, r.requested_at.isoformat(), r.flow_key) for r in pending],
        blockers=[p.id for p in active if p not in selected],
        in_flight_item_ids=[i.id for i in items if i.status in {"starting", "in_progress"}])
    plan["fingerprint"] = hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest()
    return plan


def apply(db, employee_id, fingerprint):
    if db.bind.dialect.name != "sqlite":
        raise ValueError("Для этого сброса требуется SQLite")
    database = Path(db.bind.url.database).resolve()
    if not database.is_file():
        raise ValueError("База не найдена")
    db.commit()
    backup = database.parent / "backups" / f"hr_bot.before-adaptation-retest.{uuid4().hex}.db"
    backup.parent.mkdir(exist_ok=True)
    backup.touch(mode=0o600, exist_ok=False)
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as source, closing(sqlite3.connect(backup)) as target:
        source.backup(target)
        if target.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError("Резервная копия не прошла проверку")
    try:
        db.execute(text("BEGIN IMMEDIATE"))
        plan = preview(db, employee_id)
        if fingerprint != plan["fingerprint"]:
            raise ValueError("Состояние изменилось; повторите preview")
        if plan["blockers"] or plan["in_flight_item_ids"]:
            raise ValueError("Есть посторонний диалог или отправка в процессе; автоматический сброс запрещён")
        now = utc_now()
        for row in plan["items"]:
            item = db.get(EmployeeAdaptationPlanItem, row["id"])
            snapshot = json.loads(item.calculation_json)
            snapshot["retest_archive"] = {"entry_key": item.entry_key, "status": item.status, "archived_at": now.isoformat()}
            item.calculation_json = json.dumps(snapshot)
            item.entry_key = f"past_{item.id}_{uuid4().hex[:12]}"
            item.status = "archived"
        for progress in plan["progress"]:
            p = db.get(ScenarioProgress, progress["id"])
            p.waiting_for_response, p.is_completed = False, True
            p.completed_at = p.updated_at = now
            p.last_delivery_error = "Прерван HR для повторного теста адаптации; история сохранена"
            p.pending_confirmation_value = p.pending_confirmation_option_index = p.pending_confirmation_message_id = None
            if p.answer_run_id:
                run = db.get(ScenarioAnswerRun, p.answer_run_id)
                if run and run.status == "in_progress":
                    run.status = "interrupted"
        for request_id in plan["pending_request_ids"]:
            db.get(FlowLaunchRequest, request_id).processed_at = now
        db.flush()
        after = preview(db, employee_id)
        if after["items"] or after["progress"] or after["pending_request_ids"]:
            raise ValueError("Проверка сброса не прошла")
        db.commit()
        return dict(archived_item_ids=[i["id"] for i in plan["items"]],
                    interrupted_progress_ids=[p["id"] for p in plan["progress"]], backup=str(backup))
    except Exception:
        db.rollback()
        raise
