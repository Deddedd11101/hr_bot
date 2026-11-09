"""Bounded merge of persisted sending facts and processed launch requests."""

from datetime import UTC, datetime

from ..models import (AdminAccount, Employee, EmployeeManualBotMessage, FlowLaunchRequest,
    FlowStepTemplate, OnboardingEvent, ScenarioTemplate)
from .dashboard import _sent_history
from .operational_queue import scenario_href

KINDS = {"all", "steps", "surveys", "messages", "launches"}


def history_payload(db, *, kind="all", page=1, page_size=20):
    take = page * page_size + 1
    events = []
    people = {p.id: p.full_name or f"Карточка №{p.id}" for p in db.query(Employee).all()}
    scenarios = {s.scenario_key: s for s in db.query(ScenarioTemplate).all()}
    accounts = {a.id: a.login for a in db.query(AdminAccount).all()}
    steps = {}
    for step in db.query(FlowStepTemplate).all():
        steps.setdefault(step.step_key, []).append(step)

    def add(key, at, event_kind, title, person_id=None, scenario=None, detail=None, source=None, actor=None, href=None):
        events.append({"id": key, "at": at.replace(tzinfo=UTC).isoformat(), "kind": event_kind, "title": title,
            "employee_name": people.get(person_id), "employee_href": f"/app/employees/{person_id}" if person_id in people else None,
            "scenario_href": scenario_href(scenario), "detail": detail, "source": source, "actor": actor, "href": href})

    if kind in {"all", "steps", "surveys"}:
        # Classify survey events by unambiguous existing step ownership only.
        survey_keys = {key for key, candidates in steps.items() if len(candidates) == 1 and
            scenarios.get(candidates[0].flow_key) and scenarios[candidates[0].flow_key].scenario_kind == "survey"}
        query = db.query(OnboardingEvent).filter(OnboardingEvent.sent_at.isnot(None), OnboardingEvent.event_key != "scenario_queue_action")
        if kind == "surveys":
            query = query.filter(OnboardingEvent.event_key.in_(survey_keys))
        elif kind == "steps":
            query = query.filter(OnboardingEvent.event_key.notin_(survey_keys))
        for event in query.order_by(OnboardingEvent.sent_at.desc(), OnboardingEvent.id.desc()).limit(take):
            candidates = steps.get(event.event_key, [])
            step = candidates[0] if len(candidates) == 1 else None
            scenario = scenarios.get(step.flow_key) if step else None
            event_kind = "surveys" if event.event_key in survey_keys else "steps"
            title = event.scenario_title or (scenario.title if scenario else "Название сценария не сохранено")
            step_title = event.step_title or (step.step_title if step else None)
            add(f"event:{event.id}", event.sent_at, event_kind, title, event.employee_id, scenario,
                f"{step_title + ': ' if step_title else ''}{event.message}",
                "Отправлено ботом · способ запуска не сохранён", "Бот")
            if step and scenario:
                events[-1]["scenario_href"] += f"&step_id={step.id}"
    if kind in {"all", "messages"}:
        for message in db.query(EmployeeManualBotMessage).filter(EmployeeManualBotMessage.sent_at.isnot(None),
            EmployeeManualBotMessage.status == "sent", EmployeeManualBotMessage.deleted_at.is_(None)).order_by(
                EmployeeManualBotMessage.sent_at.desc(), EmployeeManualBotMessage.id.desc()).limit(take):
            add(f"message:{message.id}", message.sent_at, "messages", "Ручное сообщение отправлено", message.employee_id,
                detail=message.message_text, source="Вручную", actor=accounts.get(message.sender_account_id, "Инициатор не сохранён"))
    if kind in {"all", "launches"}:
        for launch in db.query(FlowLaunchRequest).filter(FlowLaunchRequest.processed_at.isnot(None)).order_by(
            FlowLaunchRequest.processed_at.desc(), FlowLaunchRequest.id.desc()).limit(take):
            scenario = scenarios.get(launch.flow_key)
            source = {"manual": "Вручную", "scheduled": "По расписанию", "adaptation_plan": "План адаптации"}.get(launch.launch_type, "Автоматически")
            add(f"launch:{launch.id}", launch.processed_at, "launches", scenario.title if scenario else "Сценарий удалён",
                launch.employee_id, scenario, "Запрос обработан · не является подтверждением доставки", source,
                accounts.get(launch.requested_by_account_id, "Инициатор не сохранён") if source != "Автоматически" else "Система")
        for event in _sent_history(db, limit=take):
            add(event["id"], datetime.fromisoformat(event["processed_at"]), "launches",
                event["title"], detail=f"{event['kind_label']} · {event['subtitle']} · запрос обработан, доставка не подтверждена",
                source=f"Массовое задание · {event['launch_source']}", actor="Инициатор не сохранён", href=event["href"])
    events.sort(key=lambda e: (e["at"], e["id"]), reverse=True)
    start = (page - 1) * page_size
    return {"items": events[start:start + page_size], "page": page, "has_more": len(events) > start + page_size}
