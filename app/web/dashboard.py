from datetime import timedelta

from sqlalchemy.orm import Session

from ..messaging.identity import get_primary_chat_id
from ..models import (
    Employee,
    EmployeeFile,
    EmployeeMessengerAccount,
    FlowLaunchRequest,
    MassMessageAction,
    MassScenarioAction,
    ScenarioTemplate,
)
from ..time_utils import utc_now
from .bulk_actions import _recipient_scope_label
from .employees import _candidate_work_stage_label, _employee_display_name, _employee_list_kind, _employee_status_label


RECENT_DAYS = 7
UPCOMING_DAYS = 14
STAT_UPCOMING_DAYS = 7
BLOCK_LIMIT = 8


def _format_dt(value) -> str:
    return value.strftime("%d.%m.%Y %H:%M") if value else "—"


def _format_date(value) -> str:
    return value.strftime("%d.%m.%Y") if value else "—"


def _event_date_label(value) -> str:
    today = utc_now().date()
    if not value:
        return "Без даты"
    event_date = value.date()
    if event_date == today:
        return "Сегодня"
    if event_date == today + timedelta(days=1):
        return "Завтра"
    return _format_date(value)


def _scenario_title_map(db: Session) -> dict[str, ScenarioTemplate]:
    return {scenario.scenario_key: scenario for scenario in db.query(ScenarioTemplate).all()}


def _candidate_rows(db: Session) -> list[Employee]:
    return db.query(Employee).filter(Employee.employee_stage == "candidate").order_by(Employee.id.desc()).all()


def _candidates_without_channel(db: Session, candidates: list[Employee]) -> list[Employee]:
    return [candidate for candidate in candidates if not get_primary_chat_id(candidate, db=db)]


def _recent_telegram_links(db: Session, since) -> list[dict]:
    rows = (
        db.query(EmployeeMessengerAccount, Employee)
        .join(Employee, Employee.id == EmployeeMessengerAccount.employee_id)
        .filter(
            Employee.employee_stage == "candidate",
            EmployeeMessengerAccount.is_active.is_(True),
            EmployeeMessengerAccount.updated_at >= since,
        )
        .order_by(EmployeeMessengerAccount.updated_at.desc(), EmployeeMessengerAccount.id.desc())
        .limit(BLOCK_LIMIT)
        .all()
    )
    return [
        {
            "employee_id": employee.id,
            "full_name": employee.full_name or f"Кандидат #{employee.id}",
            "channel": account.channel,
            "handle_or_id": account.external_username or account.external_user_id,
            "linked_at": account.updated_at.isoformat() if account.updated_at else "",
            "linked_at_label": _format_dt(account.updated_at),
            "href": f"/app/employees/{employee.id}",
        }
        for account, employee in rows
    ]


def _inbound_files(db: Session, since) -> list[dict]:
    rows = (
        db.query(EmployeeFile, Employee)
        .join(Employee, Employee.id == EmployeeFile.employee_id)
        .filter(EmployeeFile.direction == "inbound", EmployeeFile.created_at >= since)
        .order_by(EmployeeFile.created_at.desc(), EmployeeFile.id.desc())
        .limit(BLOCK_LIMIT)
        .all()
    )
    return [
        {
            "id": file_row.id,
            "employee_id": employee.id,
            "full_name": employee.full_name or f"Сотрудник #{employee.id}",
            "filename": file_row.original_filename or "Файл",
            "created_at": file_row.created_at.isoformat() if file_row.created_at else "",
            "created_at_label": _format_dt(file_row.created_at),
            "href": f"/app/employees/{employee.id}",
        }
        for file_row, employee in rows
    ]


def _count_recent_telegram_links(db: Session, since) -> int:
    return (
        db.query(EmployeeMessengerAccount)
        .join(Employee, Employee.id == EmployeeMessengerAccount.employee_id)
        .filter(
            Employee.employee_stage == "candidate",
            EmployeeMessengerAccount.is_active.is_(True),
            EmployeeMessengerAccount.updated_at >= since,
        )
        .count()
    )


def _count_recent_inbound_files(db: Session, since) -> int:
    return db.query(EmployeeFile).filter(EmployeeFile.direction == "inbound", EmployeeFile.created_at >= since).count()


def _serialize_employee_launch_event(
    launch_request: FlowLaunchRequest,
    employee: Employee,
    scenario_by_key: dict[str, ScenarioTemplate],
) -> dict:
    scenario = scenario_by_key.get(launch_request.flow_key)
    return {
        "id": f"employee-launch-{launch_request.id}",
        "kind": "employee_scenario",
        "kind_label": "Сценарий",
        "title": scenario.title if scenario else launch_request.flow_key,
        "subtitle": _employee_display_name(employee),
        "scheduled_at": launch_request.requested_at.isoformat() if launch_request.requested_at else "",
        "scheduled_at_label": _format_dt(launch_request.requested_at),
        "date_label": _event_date_label(launch_request.requested_at),
        "recipient_count": 1,
        "href": f"/app/employees/{employee.id}",
        "action_id": None,
        "deletable": False,
    }


def _serialize_mass_scenario_event(
    db: Session,
    action: MassScenarioAction,
    scenario_by_key: dict[str, ScenarioTemplate],
) -> dict:
    scenario = scenario_by_key.get(action.flow_key)
    kind_label = "Опрос" if action.scenario_kind == "survey" else "Массовый сценарий"
    return {
        "id": f"mass-scenario-{action.id}",
        "kind": "mass_survey" if action.scenario_kind == "survey" else "mass_scenario",
        "kind_label": kind_label,
        "title": scenario.title if scenario else action.flow_key,
        "subtitle": _recipient_scope_label(
            db,
            action.target_all,
            action.target_statuses,
            action.target_employee_id,
            action.target_role_scope,
            action.target_employee_stages,
            action.target_candidate_stages,
        ),
        "scheduled_at": action.requested_at.isoformat() if action.requested_at else "",
        "scheduled_at_label": _format_dt(action.requested_at),
        "date_label": _event_date_label(action.requested_at),
        "recipient_count": action.recipient_count,
        # Событие ведёт в деталь записи: страницы массовых действий больше нет.
        "href": (
            f"/app/surveys/workspace?scenario_id={scenario.id}"
            if scenario and action.scenario_kind == "survey"
            else f"/app/flows/workspace-v2?scenario_id={scenario.id}"
            if scenario
            else "/app/messages"
        ),
        "action_id": action.id,
        "deletable": action.processed_at is None,
    }


def _serialize_mass_message_event(db: Session, action: MassMessageAction) -> dict:
    title = (action.message_text or "").strip().replace("\n", " ")
    if len(title) > 80:
        title = f"{title[:77]}..."
    return {
        "id": f"mass-message-{action.id}",
        "kind": "mass_message",
        "kind_label": "Массовое сообщение",
        "title": title or "Сообщение",
        "subtitle": _recipient_scope_label(
            db,
            action.target_all,
            action.target_statuses,
            action.target_employee_id,
            action.target_role_scope,
            action.target_employee_stages,
            action.target_candidate_stages,
        ),
        "scheduled_at": action.requested_at.isoformat() if action.requested_at else "",
        "scheduled_at_label": _format_dt(action.requested_at),
        "date_label": _event_date_label(action.requested_at),
        "recipient_count": action.recipient_count,
        "href": "/app/messages",
        "action_id": action.id,
        "deletable": action.processed_at is None,
    }


def _upcoming_events(db: Session, now, until) -> list[dict]:
    scenario_by_key = _scenario_title_map(db)
    events: list[dict] = []
    employee_launches = (
        db.query(FlowLaunchRequest, Employee)
        .join(Employee, Employee.id == FlowLaunchRequest.employee_id)
        .filter(
            FlowLaunchRequest.processed_at.is_(None),
            FlowLaunchRequest.launch_type == "scheduled",
            FlowLaunchRequest.requested_at >= now,
            FlowLaunchRequest.requested_at <= until,
        )
        .order_by(FlowLaunchRequest.requested_at.asc(), FlowLaunchRequest.id.asc())
        .limit(20)
        .all()
    )
    events.extend(
        _serialize_employee_launch_event(launch_request, employee, scenario_by_key)
        for launch_request, employee in employee_launches
    )

    mass_scenarios = (
        db.query(MassScenarioAction)
        .filter(
            MassScenarioAction.launch_type == "scheduled",
            MassScenarioAction.processed_at.is_(None),
            MassScenarioAction.requested_at >= now,
            MassScenarioAction.requested_at <= until,
        )
        .order_by(MassScenarioAction.requested_at.asc(), MassScenarioAction.id.asc())
        .limit(20)
        .all()
    )
    events.extend(_serialize_mass_scenario_event(db, action, scenario_by_key) for action in mass_scenarios)

    mass_messages = (
        db.query(MassMessageAction)
        .filter(
            MassMessageAction.launch_type == "scheduled",
            MassMessageAction.processed_at.is_(None),
            MassMessageAction.requested_at >= now,
            MassMessageAction.requested_at <= until,
        )
        .order_by(MassMessageAction.requested_at.asc(), MassMessageAction.id.asc())
        .limit(20)
        .all()
    )
    events.extend(_serialize_mass_message_event(db, action) for action in mass_messages)
    return sorted(events, key=lambda item: item["scheduled_at"])[:12]


def _attention_items(db: Session, candidates_without_channel: list[Employee], now) -> list[dict]:
    items: list[dict] = []
    for candidate in candidates_without_channel[:5]:
        items.append(
            {
                "id": f"candidate-channel-{candidate.id}",
                "kind": "missing_channel",
                "severity": "warning",
                "title": candidate.full_name or f"Кандидат #{candidate.id}",
                "subtitle": "Нет Telegram-привязки",
                "href": f"/app/employees/{candidate.id}",
            }
        )

    overdue_candidates = (
        db.query(Employee)
        .filter(
            Employee.employee_stage == "candidate",
            Employee.test_task_due_at.is_not(None),
            Employee.test_task_due_at < now,
        )
        .order_by(Employee.test_task_due_at.asc(), Employee.id.asc())
        .limit(5)
        .all()
    )
    for candidate in overdue_candidates:
        items.append(
            {
                "id": f"candidate-overdue-{candidate.id}",
                "kind": "overdue_test_task",
                "severity": "danger",
                "title": candidate.full_name or f"Кандидат #{candidate.id}",
                "subtitle": f"Просрочен дедлайн тестового: {_format_dt(candidate.test_task_due_at)}",
                "href": f"/app/employees/{candidate.id}",
            }
        )

    blocked_employees = db.query(Employee).filter(Employee.is_bot_blocked.is_(True)).order_by(Employee.id.desc()).limit(5).all()
    for employee in blocked_employees:
        status_label = _candidate_work_stage_label(employee) if _employee_list_kind(employee) == "candidates" else _employee_status_label(employee)
        items.append(
            {
                "id": f"blocked-bot-{employee.id}",
                "kind": "blocked_bot",
                "severity": "info",
                "title": employee.full_name or f"Сотрудник #{employee.id}",
                "subtitle": f"Бот заблокирован, статус: {status_label}",
                "href": f"/app/employees/{employee.id}",
            }
        )
    return items[:12]


def _sent_history(db: Session, limit: int = 15) -> list[dict]:
    """Последние выполненные массовые отправки, все три типа одной лентой.

    Журнал жил на странице массовых действий; страница сжалась до сообщений,
    и общая история переехала на дашборд — оператору нужен один список,
    а не три, разнесённых по страницам записей.
    """
    scenario_by_key = _scenario_title_map(db)
    entries: list[dict] = []

    scenario_actions = (
        db.query(MassScenarioAction)
        .filter(MassScenarioAction.processed_at.isnot(None))
        .order_by(MassScenarioAction.processed_at.desc(), MassScenarioAction.id.desc())
        .limit(limit)
        .all()
    )
    for action in scenario_actions:
        event = _serialize_mass_scenario_event(db, action, scenario_by_key)
        event["id"] = f"sent-scenario-{action.id}"
        event["processed_at"] = action.processed_at.isoformat() if action.processed_at else ""
        event["processed_at_label"] = _format_dt(action.processed_at)
        entries.append(event)

    message_actions = (
        db.query(MassMessageAction)
        .filter(MassMessageAction.processed_at.isnot(None))
        .order_by(MassMessageAction.processed_at.desc(), MassMessageAction.id.desc())
        .limit(limit)
        .all()
    )
    for action in message_actions:
        event = _serialize_mass_message_event(db, action)
        event["id"] = f"sent-message-{action.id}"
        event["processed_at"] = action.processed_at.isoformat() if action.processed_at else ""
        event["processed_at_label"] = _format_dt(action.processed_at)
        entries.append(event)

    entries.sort(key=lambda item: item["processed_at"], reverse=True)
    return entries[:limit]


def _module_links() -> list[dict]:
    return [
        {
            "key": "employees",
            "title": "Люди",
            "description": "Карточки сотрудников и кандидатов",
            "href": "/app/employees?list_kind=candidates",
        },
        {
            "key": "messages",
            "title": "Сообщения",
            "description": "Массовые сообщения в Telegram",
            "href": "/app/messages",
        },
        {
            "key": "flows",
            "title": "Сценарии",
            "description": "Конструктор сценариев",
            "href": "/app/flows/workspace-v2",
        },
        {
            "key": "surveys",
            "title": "Опросы",
            "description": "Конструктор опросов",
            "href": "/app/surveys/workspace",
        },
        {
            "key": "settings",
            "title": "Настройки",
            "description": "HR, меню бота и аккаунты",
            "href": "/app/settings",
        },
    ]


def _count_scheduled(db: Session, now, until) -> int:
    employee_count = (
        db.query(FlowLaunchRequest)
        .filter(
            FlowLaunchRequest.launch_type == "scheduled",
            FlowLaunchRequest.processed_at.is_(None),
            FlowLaunchRequest.requested_at >= now,
            FlowLaunchRequest.requested_at <= until,
        )
        .count()
    )
    scenario_count = (
        db.query(MassScenarioAction)
        .filter(
            MassScenarioAction.launch_type == "scheduled",
            MassScenarioAction.processed_at.is_(None),
            MassScenarioAction.requested_at >= now,
            MassScenarioAction.requested_at <= until,
        )
        .count()
    )
    message_count = (
        db.query(MassMessageAction)
        .filter(
            MassMessageAction.launch_type == "scheduled",
            MassMessageAction.processed_at.is_(None),
            MassMessageAction.requested_at >= now,
            MassMessageAction.requested_at <= until,
        )
        .count()
    )
    return employee_count + scenario_count + message_count


def dashboard_workspace_payload(db: Session) -> dict:
    now = utc_now()
    recent_since = now - timedelta(days=RECENT_DAYS)
    upcoming_until = now + timedelta(days=UPCOMING_DAYS)
    stat_until = now + timedelta(days=STAT_UPCOMING_DAYS)
    candidates = _candidate_rows(db)
    candidates_without_channel = _candidates_without_channel(db, candidates)
    telegram_links = _recent_telegram_links(db, recent_since)
    inbound_files = _inbound_files(db, recent_since)
    return {
        "meta": {
            "recent_days": RECENT_DAYS,
            "upcoming_days": UPCOMING_DAYS,
            "stat_upcoming_days": STAT_UPCOMING_DAYS,
            "generated_at": now.isoformat(),
        },
        "stats": {
            "candidates_without_channel": len(candidates_without_channel),
            "recent_telegram_links": _count_recent_telegram_links(db, recent_since),
            "recent_inbound_files": _count_recent_inbound_files(db, recent_since),
            "scheduled_next_7_days": _count_scheduled(db, now, stat_until),
        },
        "upcoming_events": _upcoming_events(db, now, upcoming_until),
        "telegram_links": telegram_links,
        "inbound_files": inbound_files,
        "attention_items": _attention_items(db, candidates_without_channel, now),
        "module_links": _module_links(),
        "sent_history": _sent_history(db),
    }
