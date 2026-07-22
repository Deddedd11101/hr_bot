from datetime import datetime
from typing import Optional

from fastapi import HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..mass_targeting import (
    MASS_TARGET_NONE,
    build_legacy_target_statuses,
    mass_target_employee_query,
    normalize_mass_target_candidate_stages,
    normalize_mass_target_employee_stages,
    resolve_target_groups,
    serialize_target_values,
)
from ..models import Employee, MassMessageAction, MassScenarioAction, ScenarioTemplate
from ..positions import ROLE_SCOPE_ALL, build_role_scope_labels, resolve_scope_slug
from ..scenario_engine import format_message
from .employees import (
    OFFER_DOCUMENT_TITLE,
    _all_employee_options,
    _employee_display_name,
    _scenario_matches_employee_role,
)

LEGACY_MASS_TARGET_OPTIONS = [
    (MASS_TARGET_NONE, "Не указан"),
    ("candidate", "Кандидат"),
    ("adaptation", "Адаптация"),
    ("ipr", "ИПР"),
    ("staff", "В штате"),
]
MASS_TARGET_EMPLOYEE_STAGE_OPTIONS = [
    (MASS_TARGET_NONE, "Не указан"),
    ("adaptation", "Адаптация"),
    ("ipr", "ИПР"),
    ("staff", "В штате"),
]
MASS_TARGET_CANDIDATE_STAGE_OPTIONS = [
    (MASS_TARGET_NONE, "Не указан"),
    ("testing", "Тестирование"),
    ("offer", "Оффер"),
    ("candidate_decline", "Отказ кандидата"),
    ("company_decline", "Наш отказ"),
    ("preonboarding", "Преонбординг"),
    ("contract", "Заключение договора"),
]


def _mass_actions_redirect(flash_message: Optional[str] = None, flash_type: str = "success") -> RedirectResponse:
    url = "/bulk-actions"
    if flash_message:
        from urllib.parse import urlencode

        url = f"{url}?{urlencode({'flash_message': flash_message, 'flash_type': flash_type})}"
    return RedirectResponse(url=url, status_code=status.HTTP_303_SEE_OTHER)


def _recipient_scope_label(
    db: Session,
    target_all: bool,
    target_statuses: Optional[str],
    target_employee_id: Optional[int] = None,
    target_role_scope: Optional[str] = None,
    target_employee_stages: Optional[str] = None,
    target_candidate_stages: Optional[str] = None,
) -> str:
    if target_employee_id:
        employee = db.get(Employee, target_employee_id)
        if employee:
            return _employee_display_name(employee)
        return f"Сотрудник #{target_employee_id}"
    role_scope = (target_role_scope or "").strip()
    employee_stage_labels = dict(MASS_TARGET_EMPLOYEE_STAGE_OPTIONS)
    candidate_stage_labels = dict(MASS_TARGET_CANDIDATE_STAGE_OPTIONS)
    parts: list[str] = []
    if role_scope == "all" and target_all:
        return "Все"
    role_scope_labels = build_role_scope_labels(db, include_inactive=True)
    if role_scope and role_scope in role_scope_labels and role_scope != ROLE_SCOPE_ALL:
        parts.append(role_scope_labels[role_scope])
    employee_stages, candidate_stages, include_all_candidates = resolve_target_groups(
        legacy_target_statuses=target_statuses,
        target_employee_stages=target_employee_stages,
        target_candidate_stages=target_candidate_stages,
    )
    if employee_stages:
        parts.append("Сотрудники: " + ", ".join(employee_stage_labels.get(value, value) for value in employee_stages))
    if candidate_stages:
        parts.append("Кандидаты: " + ", ".join(candidate_stage_labels.get(value, value) for value in candidate_stages))
    elif include_all_candidates:
        parts.append("Кандидаты: все этапы")
    if target_all and not parts:
        return "Все"
    if not parts:
        return "Не выбраны"
    return "; ".join(parts)


def _mass_target_employees(
    db: Session,
    target_all: bool,
    target_employee_stages: list[str],
    target_candidate_stages: list[str],
    target_employee_id: Optional[int] = None,
    target_role_scope: Optional[str] = None,
    legacy_target_statuses: Optional[list[str]] = None,
) -> list[Employee]:
    return (
        mass_target_employee_query(
            db,
            target_all=target_all,
            target_employee_stages=target_employee_stages,
            target_candidate_stages=target_candidate_stages,
            target_employee_id=target_employee_id,
            target_role_scope=target_role_scope,
            legacy_target_statuses=legacy_target_statuses,
        )
        .order_by(Employee.id.asc())
        .all()
    )


def _bulk_scenario_options(db: Session, kind: str) -> list[ScenarioTemplate]:
    return (
        db.query(ScenarioTemplate)
        .filter(ScenarioTemplate.scenario_kind == kind)
        .order_by(ScenarioTemplate.title, ScenarioTemplate.id)
        .all()
    )


def _serialize_bulk_scenario(scenario: ScenarioTemplate) -> dict:
    return {
        "id": scenario.id,
        "scenario_key": scenario.scenario_key,
        "title": scenario.title,
        "scenario_kind": scenario.scenario_kind,
    }


def _format_dt(value: Optional[datetime]) -> str:
    return value.strftime("%d.%m.%Y %H:%M") if value else "—"


def _serialize_mass_scenario_action(db: Session, action: MassScenarioAction, scenario_by_key: dict[str, ScenarioTemplate]) -> dict:
    scenario = scenario_by_key.get(action.flow_key)
    return {
        "id": action.id,
        "flow_key": action.flow_key,
        "title": scenario.title if scenario else action.flow_key,
        "scenario_kind": action.scenario_kind,
        "launch_type": action.launch_type,
        "requested_at": action.requested_at.isoformat() if action.requested_at else "",
        "requested_at_label": _format_dt(action.requested_at),
        "processed_at": action.processed_at.isoformat() if action.processed_at else "",
        "processed_at_label": _format_dt(action.processed_at),
        "recipient_count": action.recipient_count,
        "recipient_scope": _recipient_scope_label(
            db,
            action.target_all,
            action.target_statuses,
            action.target_employee_id,
            action.target_role_scope,
            action.target_employee_stages,
            action.target_candidate_stages,
        ),
    }


def _serialize_mass_message_action(db: Session, action: MassMessageAction) -> dict:
    return {
        "id": action.id,
        "message_text": action.message_text,
        "launch_type": action.launch_type,
        "requested_at": action.requested_at.isoformat() if action.requested_at else "",
        "requested_at_label": _format_dt(action.requested_at),
        "processed_at": action.processed_at.isoformat() if action.processed_at else "",
        "processed_at_label": _format_dt(action.processed_at),
        "recipient_count": action.recipient_count,
        "recipient_scope": _recipient_scope_label(
            db,
            action.target_all,
            action.target_statuses,
            action.target_employee_id,
            action.target_role_scope,
            action.target_employee_stages,
            action.target_candidate_stages,
        ),
    }


def _bulk_workspace_payload(db: Session) -> dict:
    scenarios = _bulk_scenario_options(db, "scenario")
    surveys = _bulk_scenario_options(db, "survey")
    all_templates = scenarios + surveys
    scenario_by_key = {scenario.scenario_key: scenario for scenario in all_templates}
    scheduled_scenario_actions = (
        db.query(MassScenarioAction)
        .filter(
            MassScenarioAction.scenario_kind == "scenario",
            MassScenarioAction.launch_type == "scheduled",
            MassScenarioAction.processed_at.is_(None),
        )
        .order_by(MassScenarioAction.requested_at.asc(), MassScenarioAction.id.asc())
        .all()
    )
    manual_scenario_history = (
        db.query(MassScenarioAction)
        .filter(
            MassScenarioAction.scenario_kind == "scenario",
            MassScenarioAction.launch_type == "manual",
            MassScenarioAction.processed_at.is_not(None),
        )
        .order_by(MassScenarioAction.processed_at.desc(), MassScenarioAction.id.desc())
        .limit(20)
        .all()
    )
    scheduled_survey_actions = (
        db.query(MassScenarioAction)
        .filter(
            MassScenarioAction.scenario_kind == "survey",
            MassScenarioAction.launch_type == "scheduled",
            MassScenarioAction.processed_at.is_(None),
        )
        .order_by(MassScenarioAction.requested_at.asc(), MassScenarioAction.id.asc())
        .all()
    )
    manual_survey_history = (
        db.query(MassScenarioAction)
        .filter(
            MassScenarioAction.scenario_kind == "survey",
            MassScenarioAction.launch_type == "manual",
            MassScenarioAction.processed_at.is_not(None),
        )
        .order_by(MassScenarioAction.processed_at.desc(), MassScenarioAction.id.desc())
        .limit(20)
        .all()
    )
    scheduled_message_actions = (
        db.query(MassMessageAction)
        .filter(MassMessageAction.launch_type == "scheduled", MassMessageAction.processed_at.is_(None))
        .order_by(MassMessageAction.requested_at.asc(), MassMessageAction.id.asc())
        .all()
    )
    manual_message_history = (
        db.query(MassMessageAction)
        .filter(MassMessageAction.launch_type == "manual", MassMessageAction.processed_at.is_not(None))
        .order_by(MassMessageAction.processed_at.desc(), MassMessageAction.id.desc())
        .limit(20)
        .all()
    )
    role_scope_labels = build_role_scope_labels(db)
    return {
        "scenarios": [_serialize_bulk_scenario(scenario) for scenario in scenarios],
        "surveys": [_serialize_bulk_scenario(survey) for survey in surveys],
        "employee_options": _all_employee_options(db),
        "role_scope_options": [{"value": value, "label": label} for value, label in role_scope_labels.items()],
        "employee_stage_options": [{"value": value, "label": label} for value, label in MASS_TARGET_EMPLOYEE_STAGE_OPTIONS],
        "candidate_stage_options": [{"value": value, "label": label} for value, label in MASS_TARGET_CANDIDATE_STAGE_OPTIONS],
        "document_tag_titles": [OFFER_DOCUMENT_TITLE],
        "scheduled_scenario_actions": [_serialize_mass_scenario_action(db, action, scenario_by_key) for action in scheduled_scenario_actions],
        "manual_scenario_history": [_serialize_mass_scenario_action(db, action, scenario_by_key) for action in manual_scenario_history],
        "scheduled_survey_actions": [_serialize_mass_scenario_action(db, action, scenario_by_key) for action in scheduled_survey_actions],
        "manual_survey_history": [_serialize_mass_scenario_action(db, action, scenario_by_key) for action in manual_survey_history],
        "scheduled_message_actions": [_serialize_mass_message_action(db, action) for action in scheduled_message_actions],
        "manual_message_history": [_serialize_mass_message_action(db, action) for action in manual_message_history],
    }


def _parse_mass_target_payload(payload: dict) -> tuple[bool, list[str], list[str], Optional[int], Optional[str]]:
    target_employee_stages = normalize_mass_target_employee_stages([str(value) for value in payload.get("target_employee_stages") or []])
    target_candidate_stages = normalize_mass_target_candidate_stages([str(value) for value in payload.get("target_candidate_stages") or []])
    target_employee_id_value = str(payload.get("target_employee_id") or "").strip()
    target_employee_id = int(target_employee_id_value) if target_employee_id_value.isdigit() else None
    target_role_scope = resolve_scope_slug(str(payload.get("target_role_scope") or "").strip())
    normalized_role_scope = target_role_scope if target_role_scope != ROLE_SCOPE_ALL else None
    target_all = not any([target_employee_stages, target_candidate_stages, target_employee_id, normalized_role_scope])
    return target_all, target_employee_stages, target_candidate_stages, target_employee_id, normalized_role_scope


def _bulk_target_recipients(db: Session, payload: dict) -> tuple[bool, list[str], list[str], Optional[int], Optional[str], list[Employee]]:
    target_all, target_employee_stages, target_candidate_stages, target_employee_id, target_role_scope = _parse_mass_target_payload(payload)
    recipients = _mass_target_employees(
        db,
        target_all,
        target_employee_stages,
        target_candidate_stages,
        target_employee_id,
        target_role_scope,
    )
    return target_all, target_employee_stages, target_candidate_stages, target_employee_id, target_role_scope, recipients


def _parse_bulk_run_at(value: str, label: str) -> datetime:
    if not (value or "").strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Укажите дату и время {label}.")
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%dT%H:%M")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неверный формат даты и времени.") from exc


def _ensure_confirmed(payload: dict) -> None:
    if payload.get("confirmed") is not True:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нужно подтвердить массовое действие.")


async def _send_mass_message(db: Session, messenger, employee: Employee, message_text: str) -> bool:
    if employee.is_bot_blocked:
        return False
    chat_id = employee.telegram_user_id
    if not chat_id:
        from ..messaging.identity import get_primary_chat_id

        chat_id = get_primary_chat_id(employee, db=db)
    if not chat_id:
        return False
    rendered_text = format_message(
        db,
        message_text,
        employee,
        datetime.now().date(),
        datetime.now().strftime("%H:%M"),
    ).strip()
    if not rendered_text:
        return False
    await messenger.send_text(chat_id=chat_id, text=rendered_text)
    return True


async def _parse_mass_action_targets(request: Request) -> tuple[bool, list[str], list[str], Optional[int], Optional[str]]:
    form = await request.form()
    target_employee_stages = normalize_mass_target_employee_stages(form.getlist("target_employee_stages"))
    target_candidate_stages = normalize_mass_target_candidate_stages(form.getlist("target_candidate_stages"))
    target_employee_id_value = str(form.get("target_employee_id", "") or "").strip()
    target_employee_id = int(target_employee_id_value) if target_employee_id_value.isdigit() else None
    target_role_scope = resolve_scope_slug(str(form.get("target_role_scope", "") or "").strip())
    normalized_role_scope = target_role_scope if target_role_scope != ROLE_SCOPE_ALL else None
    target_all = not any([target_employee_stages, target_candidate_stages, target_employee_id, normalized_role_scope])
    return target_all, target_employee_stages, target_candidate_stages, target_employee_id, normalized_role_scope
