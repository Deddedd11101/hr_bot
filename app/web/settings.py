from datetime import datetime

from sqlalchemy.orm import Session

from ..auth import ROLE_LABELS
from ..models import AdminAccount, BotMenuButton, BotMenuSet, Employee, HrSettings, ScenarioTemplate


def _get_or_create_hr_settings(db: Session) -> HrSettings:
    settings_row = db.get(HrSettings, 1)
    if settings_row:
        return settings_row
    now = datetime.utcnow()
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
    }


def _serialize_menu_set(menu_set: BotMenuSet, buttons: list[BotMenuButton]) -> dict:
    return {
        "id": menu_set.id,
        "title": menu_set.title,
        "description": menu_set.description or "",
        "sort_order": menu_set.sort_order,
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


def _settings_workspace_payload(db: Session, current_user: AdminAccount) -> dict:
    hr_settings = _get_or_create_hr_settings(db)
    menu_sets = _menu_sets(db)
    menu_buttons = _menu_buttons_by_set(db)
    scenarios = db.query(ScenarioTemplate).order_by(ScenarioTemplate.title, ScenarioTemplate.id).all()
    accounts = db.query(AdminAccount).order_by(AdminAccount.id).all() if current_user.role == "admin" else []
    return {
        "current_user": _serialize_admin_account(current_user),
        "role_labels": ROLE_LABELS,
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
        "accounts": [_serialize_admin_account(account) for account in accounts],
    }


def _normalize_menu_action(action_type: str) -> str:
    return action_type if action_type in {"inactive", "launch_scenario", "open_set"} else "inactive"


def _apply_menu_button_payload(button: BotMenuButton, payload: dict) -> None:
    normalized_action = _normalize_menu_action(str(payload.get("action_type") or "inactive"))
    button.label = str(payload.get("label") or "").strip() or button.label
    button.action_type = normalized_action
    scenario_key = str(payload.get("scenario_key") or "").strip()
    target_menu_set_id = payload.get("target_menu_set_id")
    button.scenario_key = scenario_key if normalized_action == "launch_scenario" and scenario_key else None
    button.target_menu_set_id = (
        int(target_menu_set_id)
        if normalized_action == "open_set" and str(target_menu_set_id or "").isdigit()
        else None
    )


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
