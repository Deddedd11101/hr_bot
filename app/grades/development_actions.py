"""Optional, independently claimed actions at each development milestone."""
import json
from uuid import UUID, NAMESPACE_URL, uuid5

from sqlalchemy import select, update

from ..models import (AdminAccount, Employee, EmployeeAdaptationPlanItem, EmployeeFeedbackRecipient,
    EmployeeFeedbackRun, GradeDevelopmentAction as Action, GradeDevelopmentMilestone as Milestone,
    FlowLaunchRequest, ScenarioTemplate)
from ..scenario_engine import (INTERACTIVE_RESPONSE_TYPES, get_scenario_steps, get_waiting_progress,
    matches_role_scope, resolve_scenario_recipient, start_scenario)
from ..time_utils import utc_now
from . import development as dev
from .collections import recipient_ids


def action_payload(row):
    return dict(key=row.action_key, type=row.action_type, scenario_key=row.scenario_key,
        **json.loads(row.settings_json), id=row.id, status=row.status, last_error=row.last_error, result_id=row.result_id)


def validate(db, employee, data):
    if not isinstance(data, dict) or set(data) != set(dev.KINDS):
        raise ValueError("Нужны списки действий для всех трёх этапов")
    clean = {}
    for kind, choices in data.items():
        if not isinstance(choices, list) or len(choices) > 10:
            raise ValueError("В одном этапе допускается до 10 действий")
        rows, keys, scenarios = [], set(), set()
        for choice in choices:
            if not isinstance(choice, dict) or set(choice) - {"key", "type", "scenario_key", "recipient_ids", "specialization_id"}:
                raise ValueError("Некорректные поля действия")
            key = str(UUID(choice["key"]))
            if key in keys:
                raise ValueError("Действие повторяется")
            keys.add(key)
            action_type = choice.get("type")
            if action_type not in {"scenario", "feedback", "review"}:
                raise ValueError("Выберите сценарий, сбор ОС или сбор оценок")
            settings, scenario_key = {}, choice.get("scenario_key")
            if action_type in {"feedback", "review"}:
                settings["recipient_ids"] = recipient_ids(db, choice.get("recipient_ids"))
                if employee.id in settings["recipient_ids"]:
                    raise ValueError("Выберите коллег, а не оцениваемого сотрудника")
            if action_type == "review":
                from ..web.grades import preview_review
                view = preview_review(db, employee.id, choice.get("specialization_id"), None)
                if not view["scores"]:
                    raise ValueError("В шаблоне оценки нет навыков")
                settings["specialization_id"] = choice["specialization_id"]
                scenario_key = None
            else:
                scenario = db.scalar(select(ScenarioTemplate).where(ScenarioTemplate.scenario_key == scenario_key))
                if not scenario or not get_scenario_steps(db, scenario_key):
                    raise ValueError("Сценарий пуст или недоступен")
                if action_type == "scenario" and (scenario.scenario_kind != "scenario" or not matches_role_scope(employee, scenario)):
                    raise ValueError("Сценарий не подходит сотруднику")
                if action_type == "feedback" and (scenario.scenario_kind != "survey" or scenario.recipient_mode != "self"
                        or any(not matches_role_scope(db.get(Employee, i), scenario) for i in settings["recipient_ids"])):
                    raise ValueError("Опрос недоступен выбранным отвечающим")
                if scenario_key in scenarios:
                    raise ValueError("Один сценарий не должен повторяться в одном этапе")
                scenarios.add(scenario_key)
            rows.append(dict(key=key, type=action_type, scenario_key=scenario_key, settings=settings))
        clean[kind] = rows
    return clean


def configure(db, employee_id, actor_id, data):
    from ..web.grades import GradeConflictError
    dev._lock(db, employee_id)
    employee = db.get(Employee, employee_id)
    if not employee:
        raise LookupError("Сотрудник не найден")
    clean = validate(db, employee, data.get("actions"))
    base = {k: v for k, v in data.items() if k != "actions"}
    enabled = base.get("enabled")
    if type(enabled) is not bool:
        raise ValueError("enabled должен быть логическим значением")
    selected = [a["scenario_key"] for values in clean.values() for a in values if a["type"] == "scenario"]
    if enabled and selected:
        pending = db.scalar(select(FlowLaunchRequest.id).where(FlowLaunchRequest.employee_id == employee_id,
            FlowLaunchRequest.flow_key.in_(selected), FlowLaunchRequest.processed_at.is_(None)))
        adaptation = db.scalar(select(EmployeeAdaptationPlanItem.id).where(EmployeeAdaptationPlanItem.employee_id == employee_id,
            EmployeeAdaptationPlanItem.flow_key.in_(selected), EmployeeAdaptationPlanItem.status.in_(["planned", "blocked", "starting", "in_progress"])))
        if pending or adaptation or dev._pending_mass_conflict(db, employee_id, selected):
            raise GradeConflictError("Есть другой запланированный запуск выбранного сценария")
    base.update(enabled=False, **{k + "_scenario_key": None for k in dev.KINDS})
    old_items = list(db.scalars(select(Milestone).where(Milestone.employee_id == employee_id, Milestone.assessment_id == data.get("assessment_id"))))
    for item in old_items:
        if item.status not in dev.EDITABLE:
            old_actions = [r for r in db.scalars(select(Action).where(Action.milestone_id == item.id)) if r.action_type != "reminder"]
            comparable = [dict(key=r.action_key, type=r.action_type, scenario_key=r.scenario_key,
                settings={k: v for k, v in json.loads(r.settings_json).items() if k != "actor_id"}) for r in old_actions]
            if clean[item.kind] != comparable:
                raise GradeConflictError("Нельзя менять действия уже запущенного этапа")
    dev.configure(db, employee_id, base, allow_actions=True)
    cycle = db.scalar(select(dev.Cycle).where(dev.Cycle.employee_id == employee_id))
    for item in db.scalars(select(Milestone).where(Milestone.employee_id == employee_id, Milestone.assessment_id == cycle.assessment_id)):
        if item.status not in dev.EDITABLE:
            continue
        if enabled and item.due_at <= dev.local_now():
            raise ValueError("Укажите будущие даты этапов перед включением цикла")
        previous = {row.action_key: row for row in db.scalars(select(Action).where(Action.milestone_id == item.id))}
        choices = clean[item.kind] or [dict(key=str(uuid5(NAMESPACE_URL, f"reminder:{item.id}")), type="reminder", scenario_key=None, settings={})]
        retained = set()
        for choice in choices:
            retained.add(choice["key"])
            row = previous.get(choice["key"])
            config = dict(choice["settings"], actor_id=actor_id)
            if row and row.status not in dev.EDITABLE:
                if row.action_type != choice["type"] or row.scenario_key != choice["scenario_key"] or json.loads(row.settings_json) != config:
                    raise GradeConflictError("Запущенное действие нельзя изменить")
                continue
            if not row:
                row = Action(milestone_id=item.id, action_key=choice["key"])
                db.add(row)
            row.action_type, row.scenario_key, row.settings_json = choice["type"], choice["scenario_key"], json.dumps(config)
            row.status, row.last_error = "planned", None
        for key, row in previous.items():
            if key not in retained:
                if row.status not in dev.EDITABLE:
                    raise GradeConflictError("Нельзя удалить запущенное действие")
                db.delete(row)
        item.scenario_key = None
    if enabled and not dev._active_staff(employee):
        raise ValueError("Сотрудник недоступен")
    cycle.enabled = enabled
    db.flush()
    return dev.payload(db, employee_id)


async def process_actions(db, bot, employee, item, cycle):
    rows = list(db.scalars(select(Action).where(Action.milestone_id == item.id).order_by(Action.id)))
    if not rows:
        return False
    for row in rows:
        dev._lock(db, employee.id)
        db.refresh(cycle)
        db.refresh(item)
        if not cycle.enabled or cycle.assessment_id != item.assessment_id or item.status not in dev.EDITABLE or item.due_at > dev.local_now():
            db.rollback()
            return True
        db.refresh(employee)
        if not dev._active_staff(employee):
            dev._pause_unavailable(db, employee, cycle, item)
            return True
        if row.status not in dev.EDITABLE:
            continue
        if row.action_type == "reminder":
            row.status = "started"
            db.commit()
            continue
        config = json.loads(row.settings_json)
        try:
            if row.action_type in {"review", "feedback"}:
                recipient_ids(db, config.get("recipient_ids"))
            scenario = db.scalar(select(ScenarioTemplate).where(ScenarioTemplate.scenario_key == row.scenario_key)) if row.scenario_key else None
            if row.action_type == "scenario":
                if not scenario or not matches_role_scope(employee, scenario):
                    raise ValueError("Сценарий недоступен сотруднику")
                recipient = resolve_scenario_recipient(db, employee, scenario, requires_response=any(s.response_type in INTERACTIVE_RESPONSE_TYPES for s in get_scenario_steps(db, scenario.scenario_key)))
                if recipient.error:
                    raise ValueError(recipient.error)
                if recipient.employee_id and get_waiting_progress(db, recipient.employee_id):
                    row.status, row.last_error = "blocked", "Получатель отвечает на другой сценарий"
                    db.commit()
                    continue
                conflict = db.scalar(select(EmployeeAdaptationPlanItem.id).where(EmployeeAdaptationPlanItem.employee_id == employee.id,
                    EmployeeAdaptationPlanItem.flow_key == row.scenario_key, EmployeeAdaptationPlanItem.status.in_(["planned", "blocked", "starting", "in_progress"])))
                pending = db.scalar(select(FlowLaunchRequest.id).where(FlowLaunchRequest.employee_id == employee.id,
                    FlowLaunchRequest.flow_key == row.scenario_key, FlowLaunchRequest.processed_at.is_(None)))
                if conflict or pending or dev._pending_mass_conflict(db, employee.id, [row.scenario_key]):
                    row.status, row.last_error = "blocked", "Есть отдельный запрос запуска или незавершённый план адаптации"
                    db.commit()
                    continue
                changed = db.execute(update(Action).where(Action.id == row.id, Action.status.in_(dev.EDITABLE)).values(status="starting")).rowcount
                db.commit()
                if changed != 1:
                    continue
                row.status = "started" if await start_scenario(bot, db, employee, row.scenario_key) else "failed"
                row.last_error = None if row.status == "started" else "Не удалось запустить сценарий"
            elif row.action_type == "review":
                actor = db.get(AdminAccount, config["actor_id"])
                if not actor or not actor.is_active:
                    raise ValueError("Автор настройки недоступен")
                from .collections import create
                collection = create(db, employee.id, actor.id, dict(request_id=str(uuid5(NAMESPACE_URL, f"review:{item.id}:{row.action_key}")),
                    specialization_id=config["specialization_id"], recipient_ids=config["recipient_ids"]))
                row.result_id, row.status, row.last_error = collection.id, "started", None
            elif row.action_type == "feedback":
                if not scenario or scenario.scenario_kind != "survey" or scenario.recipient_mode != "self":
                    raise ValueError("Опрос недоступен")
                if any(not matches_role_scope(db.get(Employee, i), scenario) for i in config["recipient_ids"]):
                    raise ValueError("Опрос не подходит выбранным отвечающим")
                run = EmployeeFeedbackRun(subject_employee_id=employee.id, scenario_key=row.scenario_key, scenario_title=scenario.title, created_at=utc_now())
                db.add(run)
                db.flush()
                for respondent in config["recipient_ids"]:
                    db.add(EmployeeFeedbackRecipient(run_id=run.id, respondent_employee_id=respondent, delivery_status="pending"))
                row.result_id, row.status, row.last_error = run.id, "started", None
            db.commit()
        except ValueError as exc:
            db.rollback()
            row = db.get(Action, row.id)
            row.status, row.last_error = "failed", str(exc)
            db.commit()
        except Exception:
            db.rollback()
            row = db.get(Action, row.id)
            row.last_error = "Результат запуска неизвестен. Проверьте доставку перед повтором"
            if row.status != "starting":
                row.status = "failed"
            db.commit()
    db.expire_all()
    statuses = [r.status for r in db.scalars(select(Action).where(Action.milestone_id == item.id))]
    item.status = "started" if all(s == "started" for s in statuses) else "blocked" if any(s in dev.EDITABLE for s in statuses) else "failed"
    item.last_error = None if item.status == "started" else "Проверьте статусы отдельных действий этапа"
    db.commit()
    return True
