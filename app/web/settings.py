from sqlalchemy.orm import Session

from ..auth import ROLE_LABELS
from ..flow_templates import EMPLOYEE_SCOPE_LABELS, ROLE_SCOPE_LABELS
from ..models import AdminAccount, BotMenuButton, BotMenuSet, DocumentLibraryItem, Employee, HrSettings, ScenarioTemplate
from ..time_utils import utc_now
from .employees import CANDIDATE_WORK_STAGE_VALUES, EMPLOYEE_STAGE_VALUES
from .documents import _document_option


def _get_or_create_hr_settings(db: Session) -> HrSettings:
    settings_row = db.get(HrSettings, 1)
    if settings_row:
        return settings_row
    now = utc_now()
    settings_row = HrSettings(
        id=1,
        hr_name=None,
        telegram_user_id=None,
        notification_recipient_ids=None,
        notify_scenario_completed=True,
        notify_test_task_received=True,
        notify_user_actions=True,
        default_menu_set_id=None,
        created_at=now,
        updated_at=now,
    )
    db.add(settings_row)
    db.commit()
    db.refresh(settings_row)
    return settings_row


def _serialize_hr_settings(settings_row: HrSettings) -> dict:
    return {
        "id": settings_row.id,
        "hr_name": settings_row.hr_name or "",
        "telegram_user_id": settings_row.telegram_user_id or "",
        "notification_recipient_ids": settings_row.notification_recipient_ids or "",
        "notify_scenario_completed": bool(settings_row.notify_scenario_completed),
        "notify_test_task_received": bool(settings_row.notify_test_task_received),
        "notify_user_actions": bool(settings_row.notify_user_actions),
        "default_menu_set_id": settings_row.default_menu_set_id,
    }


def _serialize_menu_button(button: BotMenuButton) -> dict:
    return {
        "id": button.id,
        "menu_set_id": button.menu_set_id,
        "label": button.label,
        "sort_order": button.sort_order,
        "action_type": button.action_type,
        "scenario_key": button.scenario_key or "",
        "target_menu_set_id": button.target_menu_set_id,
        "document_item_id": button.document_item_id,
    }


def _serialize_menu_set(menu_set: BotMenuSet, buttons: list[BotMenuButton]) -> dict:
    return {
        "id": menu_set.id,
        "title": menu_set.title,
        "description": menu_set.description or "",
        "sort_order": menu_set.sort_order,
        "role_scope": menu_set.role_scope or "all",
        "employee_scope": menu_set.employee_scope or "all",
        "target_employee_ids": _deserialize_menu_target_employee_ids(menu_set),
        "system_tag": menu_set.system_tag or "",
        "buttons": [_serialize_menu_button(button) for button in buttons],
    }


def _serialize_admin_account(account: AdminAccount) -> dict:
    return {
        "id": account.id,
        "login": account.login,
        "role": account.role,
        "role_label": ROLE_LABELS.get(account.role, account.role),
        "is_active": bool(account.is_active),
    }


def _menu_sets(db: Session) -> list[BotMenuSet]:
    return db.query(BotMenuSet).order_by(BotMenuSet.sort_order, BotMenuSet.id).all()


def _menu_buttons_by_set(db: Session) -> dict[int, list[BotMenuButton]]:
    result: dict[int, list[BotMenuButton]] = {}
    buttons = db.query(BotMenuButton).order_by(BotMenuButton.menu_set_id, BotMenuButton.sort_order, BotMenuButton.id).all()
    for button in buttons:
        result.setdefault(button.menu_set_id, []).append(button)
    return result


def _employee_options(db: Session) -> list[dict]:
    employees = db.query(Employee).order_by(Employee.full_name.asc(), Employee.id.asc()).all()
    result: list[dict] = []
    for employee in employees:
        is_candidate = (employee.employee_stage or "").strip() == "candidate"
        display_name = (employee.full_name or "").strip() or f"Сотрудник #{employee.id}"
        stage = (
            CANDIDATE_WORK_STAGE_VALUES.get((employee.candidate_work_stage or "").strip(), "Без этапа")
            if is_candidate
            else EMPLOYEE_STAGE_VALUES.get((employee.employee_stage or "").strip(), "Без статуса")
        )
        result.append(
            {
                "id": employee.id,
                "label": f"{display_name} · {stage}",
                "audience": "candidate" if is_candidate else "employee",
            }
        )
    return result


def _normalize_menu_role_scope(value: str) -> str:
    normalized = (value or "").strip()
    return normalized if normalized in ROLE_SCOPE_LABELS else "all"


def _normalize_menu_employee_scope(value: str) -> str:
    normalized = (value or "").strip()
    return normalized if normalized in EMPLOYEE_SCOPE_LABELS else "all"


def _normalize_menu_target_employee_ids(values: list[object]) -> list[int]:
    normalized: list[int] = []
    for raw_value in values:
        if not str(raw_value or "").isdigit():
            continue
        employee_id = int(str(raw_value))
        if employee_id not in normalized:
            normalized.append(employee_id)
    return normalized


def _serialize_menu_target_employee_ids(values: list[int]) -> str | None:
    return ",".join(str(value) for value in values) if values else None


def _deserialize_menu_target_employee_ids(menu_set: BotMenuSet) -> list[int]:
    raw_value = (menu_set.target_employee_ids or "").strip()
    values = _normalize_menu_target_employee_ids(raw_value.split(",")) if raw_value else []
    if values:
        return values
    if menu_set.target_employee_id:
        return [menu_set.target_employee_id]
    return []


def _menu_target_conflicts(db: Session, menu_set_id: int | None, target_employee_ids: list[int]) -> dict[int, str]:
    if not target_employee_ids:
        return {}
    conflicts: dict[int, str] = {}
    other_sets = db.query(BotMenuSet).order_by(BotMenuSet.sort_order, BotMenuSet.id).all()
    for other_set in other_sets:
        if menu_set_id and other_set.id == menu_set_id:
            continue
        other_ids = set(_deserialize_menu_target_employee_ids(other_set))
        overlap = other_ids.intersection(target_employee_ids)
        for employee_id in overlap:
            conflicts[employee_id] = other_set.title
    return conflicts


def _apply_menu_set_payload(menu_set: BotMenuSet, payload: dict) -> list[int]:
    title = str(payload.get("title") or "").strip()
    description = str(payload.get("description") or "").strip()
    target_employee_ids = _normalize_menu_target_employee_ids(
        [str(value) for value in payload.get("target_employee_ids") or []]
    )

    menu_set.title = title or menu_set.title
    menu_set.description = description or None
    menu_set.role_scope = _normalize_menu_role_scope(str(payload.get("role_scope") or "all"))
    menu_set.employee_scope = _normalize_menu_employee_scope(str(payload.get("employee_scope") or "all"))
    menu_set.target_employee_id = None
    menu_set.target_employee_ids = _serialize_menu_target_employee_ids(target_employee_ids)
    menu_set.target_employee_stages = None
    menu_set.target_candidate_stages = None
    return target_employee_ids


def _settings_workspace_payload(db: Session, current_user: AdminAccount) -> dict:
    hr_settings = _get_or_create_hr_settings(db)
    menu_sets = _menu_sets(db)
    menu_buttons = _menu_buttons_by_set(db)
    scenarios = db.query(ScenarioTemplate).order_by(ScenarioTemplate.title, ScenarioTemplate.id).all()
    document_items = (
        db.query(DocumentLibraryItem)
        .filter(DocumentLibraryItem.is_active.is_(True))
        .order_by(DocumentLibraryItem.sort_order, DocumentLibraryItem.id)
        .all()
    )
    accounts = db.query(AdminAccount).order_by(AdminAccount.id).all() if current_user.role == "admin" else []
    return {
        "current_user": _serialize_admin_account(current_user),
        "role_labels": ROLE_LABELS,
        "menu_role_scope_labels": ROLE_SCOPE_LABELS,
        "menu_employee_scope_labels": EMPLOYEE_SCOPE_LABELS,
        "hr_settings": _serialize_hr_settings(hr_settings),
        "menu_sets": [_serialize_menu_set(menu_set, menu_buttons.get(menu_set.id, [])) for menu_set in menu_sets],
        "available_scenarios": [
            {
                "id": scenario.id,
                "scenario_key": scenario.scenario_key,
                "title": scenario.title,
                "scenario_kind": scenario.scenario_kind,
            }
            for scenario in scenarios
        ],
        "document_options": [_document_option(item) for item in document_items],
        "employee_options": _employee_options(db),
        "accounts": [_serialize_admin_account(account) for account in accounts],
    }


def _normalize_menu_action(action_type: str) -> str:
    return action_type if action_type in {"inactive", "launch_scenario", "open_set", "send_document"} else "inactive"


def _apply_menu_button_payload(button: BotMenuButton, payload: dict) -> None:
    normalized_action = _normalize_menu_action(str(payload.get("action_type") or "inactive"))
    button.label = str(payload.get("label") or "").strip() or button.label
    button.action_type = normalized_action
    scenario_key = str(payload.get("scenario_key") or "").strip()
    target_menu_set_id = payload.get("target_menu_set_id")
    document_item_id = payload.get("document_item_id")
    button.scenario_key = scenario_key if normalized_action == "launch_scenario" and scenario_key else None
    button.target_menu_set_id = (
        int(target_menu_set_id)
        if normalized_action == "open_set" and str(target_menu_set_id or "").isdigit()
        else None
    )
    button.document_item_id = (
        int(document_item_id)
        if normalized_action == "send_document" and str(document_item_id or "").isdigit()
        else None
    )


def _validate_menu_button_payload_refs(db: Session, button: BotMenuButton) -> str | None:
    if button.action_type == "open_set" and button.target_menu_set_id:
        if db.get(BotMenuSet, button.target_menu_set_id) is None:
            return "Целевой набор меню не найден"
    if button.action_type == "send_document" and button.document_item_id:
        document_item = db.get(DocumentLibraryItem, button.document_item_id)
        if document_item is None or not document_item.is_active:
            return "Выбранный документ недоступен"
    return None


def _delete_menu_set_relations(db: Session, menu_set_id: int) -> None:
    db.query(BotMenuButton).filter(BotMenuButton.menu_set_id == menu_set_id).delete(synchronize_session=False)
    db.query(BotMenuButton).filter(BotMenuButton.target_menu_set_id == menu_set_id).update(
        {
            BotMenuButton.action_type: "inactive",
            BotMenuButton.target_menu_set_id: None,
        },
        synchronize_session=False,
    )
    db.query(Employee).filter(Employee.current_menu_set_id == menu_set_id).update(
        {Employee.current_menu_set_id: None},
        synchronize_session=False,
    )
