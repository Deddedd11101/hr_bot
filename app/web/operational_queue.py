"""Read-only cross-card queue projection; does not claim or dispatch work."""

from datetime import UTC
from zoneinfo import ZoneInfo
from collections import Counter

from ..config import settings
from ..models import (Employee, EmployeeAdaptationPlanItem, EmployeeFeedbackRecipient,
    EmployeeFeedbackRun, FlowLaunchRequest, FlowStepTemplate, MassScenarioAction, ScenarioProgress, ScenarioTemplate)
from ..scenario_engine import resolve_scenario_recipient, INTERACTIVE_RESPONSE_TYPES
from ..scenario_watchdog import progress_health
from ..time_utils import utc_now

STATES = {"all", "attention", "blocked", "waiting", "scheduled", "queued", "active"}
LIMIT = 500


def scenario_href(scenario):
    if not scenario:
        return None
    return f"/app/{'surveys/workspace' if scenario.scenario_kind == 'survey' else 'flows/workspace-v2'}?scenario_id={scenario.id}"


def request_utc(row):
    value = row.requested_at
    if row.launch_type in {"scheduled", "adaptation_plan"} and not getattr(row, "skip_step_key", None):
        return value.replace(tzinfo=ZoneInfo(settings.TIMEZONE)).astimezone(UTC).replace(tzinfo=None)
    return value


def queue_rows(db):
    now = utc_now()
    people = {p.id: p for p in db.query(Employee).all()}
    scenarios = {s.scenario_key: s for s in db.query(ScenarioTemplate).all()}
    interactive = {r[0] for r in db.query(FlowStepTemplate.flow_key).filter(FlowStepTemplate.response_type.in_(INTERACTIVE_RESPONSE_TYPES)).distinct()}
    rows = []
    truncated = False

    def bounded(query):
        nonlocal truncated
        result = query.limit(LIMIT + 1).all()
        truncated |= len(result) > LIMIT
        return result[:LIMIT]

    def add(key, person_id, flow_key, state, reason, at, source, recipient_id=None, title=None):
        person, recipient, scenario = people.get(person_id), people.get(recipient_id), scenarios.get(flow_key)
        rows.append({"id": key, "employee_id": person_id, "employee_name": (person.full_name or f"Карточка №{person_id}") if person else "Группа сотрудников" if person_id is None else "Карточка недоступна",
            "employee_href": f"/app/employees/{person_id}" if person else None,
            "title": title or (scenario.title if scenario else "Удалённый сценарий"), "scenario_href": scenario_href(scenario),
            "state": state, "reason": reason, "at": at.replace(tzinfo=UTC).isoformat(), "source": source,
            "recipient_name": recipient.full_name if recipient else None})

    active = bounded(db.query(ScenarioProgress).filter_by(is_completed=False, interrupted_at=None).order_by(ScenarioProgress.updated_at))
    busy = {}
    for p in active:
        rid = p.recipient_employee_id or p.employee_id
        busy.setdefault(rid, p)
        health = progress_health(db, p, now=now)
        state = "attention" if health["alert_due"] else {"waiting_human": "waiting", "scheduled": "scheduled"}.get(health["state"], "active")
        add(f"progress:{p.id}", p.employee_id, p.scenario_key, state,
            f"{health['reason']}. Без изменений: {health['idle_seconds'] // 60} мин",
            p.updated_at, "Активный диалог", rid)

    pending = bounded(db.query(FlowLaunchRequest).filter_by(processed_at=None).order_by(FlowLaunchRequest.requested_at))
    for r in pending:
        person, scenario, at = people.get(r.employee_id), scenarios.get(r.flow_key), request_utc(r)
        resolution = resolve_scenario_recipient(db, person, scenario, requires_response=r.flow_key in interactive) if person and scenario else None
        rid = resolution.employee_id if resolution else None
        blocker = busy.get(rid)
        error = resolution.error if resolution else "Сотрудник или сценарий недоступен"
        if person and person.is_bot_blocked:
            error = "Доступ сотрудника к боту заблокирован"
        if at > now:
            state, reason = "scheduled", "Ожидает планового времени" + (f". {error}" if error else "")
        elif error:
            state, reason = "attention", error
        elif blocker and not (r.skip_step_key and blocker.scenario_key == r.flow_key):
            title = scenarios.get(blocker.scenario_key)
            state, reason = "blocked", f"Ожидает завершения диалога: {title.title if title else 'Удалённый сценарий'} (№{blocker.id})"
        else:
            state, reason = "queued", "Ожидает обработки планировщиком"
        source = {"adaptation_plan": "План адаптации", "scheduled": "По расписанию", "manual": "Ручной запуск"}.get(r.launch_type, "Автоматический запуск")
        add(f"request:{r.id}", r.employee_id, r.flow_key, state, reason, at, source, rid)

    for item in bounded(db.query(EmployeeAdaptationPlanItem).filter(EmployeeAdaptationPlanItem.status.in_(["failed", "blocked"])).order_by(EmployeeAdaptationPlanItem.requested_at)):
        if any(r["id"] == f"request:{item.launch_request_id}" for r in rows):
            continue
        person, scenario = people.get(item.employee_id), scenarios.get(item.flow_key)
        resolution = resolve_scenario_recipient(db, person, scenario, requires_response=item.flow_key in interactive) if person and scenario else None
        error = resolution.error if resolution else None
        add(f"plan:{item.id}", item.employee_id, item.flow_key, "attention", error or item.last_error or "Этап адаптации не запущен",
            item.requested_at.replace(tzinfo=ZoneInfo(settings.TIMEZONE)).astimezone(UTC).replace(tzinfo=None), "План адаптации", title=item.title)

    feedback = bounded(db.query(EmployeeFeedbackRecipient, EmployeeFeedbackRun).join(EmployeeFeedbackRun,
        EmployeeFeedbackRun.id == EmployeeFeedbackRecipient.run_id).filter(EmployeeFeedbackRecipient.delivery_status == "pending").order_by(EmployeeFeedbackRun.created_at))
    for recipient, run in feedback:
        blocker = busy.get(recipient.respondent_employee_id)
        add(f"feedback:{recipient.id}", run.subject_employee_id, run.scenario_key,
            "blocked" if blocker else "queued", f"Оценивающий занят диалогом №{blocker.id}" if blocker else "Ожидает отправки опрашиваемому",
            run.created_at, "Сбор оценок / обратной связи", recipient.respondent_employee_id, run.scenario_title)

    for action in bounded(db.query(MassScenarioAction).filter_by(processed_at=None).order_by(MassScenarioAction.requested_at)):
        at = request_utc(action)
        add(f"mass:{action.id}", action.target_employee_id, action.flow_key,
            "scheduled" if at > now else "queued", f"Массовый запуск · получателей: {action.recipient_count}", at,
            "Массовый запуск")
    priority = {"attention": 0, "blocked": 1, "queued": 2, "active": 3, "waiting": 4, "scheduled": 5}
    rows.sort(key=lambda r: (priority[r["state"]], r["at"], r["id"]))
    return rows, truncated


def queue_payload(db, *, state="all", search="", page=1, page_size=20):
    rows, truncated = queue_rows(db)
    counts = dict(Counter(r["state"] for r in rows))
    needle = search.strip().casefold()
    filtered = [r for r in rows if (state == "all" or r["state"] == state) and
        (not needle or needle in f"{r['employee_name']} {r['title']} {r['recipient_name'] or ''}".casefold())]
    start = (page - 1) * page_size
    return {"items": filtered[start:start + page_size], "total": len(filtered), "counts": counts,
        "page": page, "pages": max(1, (len(filtered) + page_size - 1) // page_size), "truncated": truncated,
        "generated_at": utc_now().replace(tzinfo=UTC).isoformat()}
