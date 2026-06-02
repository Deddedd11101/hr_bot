import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy.orm import Session

from ..file_storage import build_step_attachment_path
from ..flow_templates import (
    EMPLOYEE_SCOPE_LABELS,
    NOTIFICATION_RECIPIENT_SCOPE_LABELS,
    RESPONSE_TYPE_LABELS,
    ROLE_SCOPE_LABELS,
    SEND_MODE_LABELS,
    TARGET_FIELD_LABELS,
    TRIGGER_MODE_LABELS,
)
from ..models import (
    FlowLaunchRequest,
    FlowStepTemplate,
    ScenarioProgress,
    ScenarioTemplate,
    StepButtonNotification,
    SurveyAnswer,
)
from .employees import OFFER_DOCUMENT_TITLE, _all_employee_options


def _load_scenario_editor_data(db: Session, scenario: ScenarioTemplate):
    steps = (
        db.query(FlowStepTemplate)
        .filter(
            FlowStepTemplate.flow_key == scenario.scenario_key,
            FlowStepTemplate.parent_step_id.is_(None),
        )
        .order_by(FlowStepTemplate.sort_order)
        .all()
    )
    branch_steps = (
        db.query(FlowStepTemplate)
        .filter(
            FlowStepTemplate.flow_key == scenario.scenario_key,
            FlowStepTemplate.parent_step_id.is_not(None),
            FlowStepTemplate.branch_option_index.is_not(None),
        )
        .order_by(FlowStepTemplate.parent_step_id, FlowStepTemplate.branch_option_index, FlowStepTemplate.id)
        .all()
    )
    chain_steps = (
        db.query(FlowStepTemplate)
        .filter(
            FlowStepTemplate.flow_key == scenario.scenario_key,
            FlowStepTemplate.parent_step_id.is_not(None),
            FlowStepTemplate.branch_option_index.is_(None),
        )
        .order_by(FlowStepTemplate.parent_step_id, FlowStepTemplate.sort_order, FlowStepTemplate.id)
        .all()
    )
    branch_steps_by_parent = defaultdict(list)
    for branch_step in branch_steps:
        branch_steps_by_parent[branch_step.parent_step_id].append(branch_step)
    chain_steps_by_parent = defaultdict(list)
    for chain_step in chain_steps:
        chain_steps_by_parent[chain_step.parent_step_id].append(chain_step)
    button_notifications = (
        db.query(StepButtonNotification)
        .filter(StepButtonNotification.flow_key == scenario.scenario_key)
        .order_by(StepButtonNotification.step_id, StepButtonNotification.option_index, StepButtonNotification.id)
        .all()
    )
    button_notifications_by_step: dict[int, dict[int, StepButtonNotification]] = defaultdict(dict)
    for notification in button_notifications:
        button_notifications_by_step[notification.step_id][notification.option_index] = notification
    available_scenarios = db.query(ScenarioTemplate).order_by(ScenarioTemplate.title, ScenarioTemplate.id).all()
    employee_options = _all_employee_options(db)
    return {
        "steps": steps,
        "branch_steps_by_parent": dict(branch_steps_by_parent),
        "chain_steps_by_parent": dict(chain_steps_by_parent),
        "button_notifications_by_step": {step_id: dict(option_map) for step_id, option_map in button_notifications_by_step.items()},
        "available_scenarios": available_scenarios,
        "employee_options": employee_options,
        "document_tag_titles": [OFFER_DOCUMENT_TITLE],
    }


def _workspace_response_label(step: FlowStepTemplate) -> str:
    response_type = (step.response_type or "").strip()
    if response_type == "buttons":
        response_type = "branching"
    extra_labels = {
        "chain": "Цепочка шагов",
        "launch_scenario": "Переход к сценарию",
    }
    return RESPONSE_TYPE_LABELS.get(response_type, extra_labels.get(response_type, response_type or "none"))


def _workspace_response_type_labels() -> dict[str, str]:
    labels = {key: value for key, value in RESPONSE_TYPE_LABELS.items() if key != "buttons"}
    labels["launch_scenario"] = "Переход к сценарию"
    labels["chain"] = "Цепочка шагов"
    return labels


def _generate_workspace_scenario_key(kind: str = "scenario") -> str:
    return f"{kind}_{uuid4().hex[:12]}"


def _normalize_workspace_kind(kind: Optional[str]) -> str:
    return "survey" if (kind or "").strip() == "survey" else "scenario"


def _workspace_collection_path(kind: str) -> str:
    return "/surveys" if kind == "survey" else "/flows"


def _workspace_app_path(kind: str) -> str:
    return "/app/surveys/workspace" if kind == "survey" else "/app/flows/workspace-v2"


def _workspace_item_label(kind: str) -> str:
    return "опрос" if kind == "survey" else "сценарий"


def _get_workspace_scenario_by_flow_key(db: Session, flow_key: str) -> Optional[ScenarioTemplate]:
    return (
        db.query(ScenarioTemplate)
        .filter(
            ScenarioTemplate.scenario_key == flow_key,
            ScenarioTemplate.scenario_kind.in_(["scenario", "survey"]),
        )
        .first()
    )


def _workspace_node_kind(step: FlowStepTemplate) -> str:
    if step.parent_step_id is None:
        return "step"
    if step.branch_option_index is None:
        return "chain_step"
    return "branch_step"


def _workspace_text_preview(step: FlowStepTemplate) -> str:
    raw = (step.custom_text or step.default_text or "").strip()
    if len(raw) <= 180:
        return raw
    return f"{raw[:177].rstrip()}..."


def _serialize_workspace_step(
    step: FlowStepTemplate,
    branch_steps_by_parent: dict[int, list[FlowStepTemplate]],
    chain_steps_by_parent: dict[int, list[FlowStepTemplate]],
    button_notifications_by_step: dict[int, dict[int, StepButtonNotification]],
):
    button_options = [item.strip() for item in (step.button_options or "").splitlines() if item.strip()]
    branch_items = []
    if step.response_type == "branching":
        existing_branch_steps = {
            child.branch_option_index: child
            for child in branch_steps_by_parent.get(step.id, [])
            if child.branch_option_index is not None
        }
        for option_index, label in enumerate(button_options):
            branch_step = existing_branch_steps.get(option_index)
            branch_items.append(
                {
                    "id": f"branch-slot-{step.id}-{option_index}",
                    "kind": "branch_slot",
                    "option_index": option_index,
                    "label": label,
                    "has_step": branch_step is not None,
                    "step": _serialize_workspace_step(branch_step, branch_steps_by_parent, chain_steps_by_parent, button_notifications_by_step) if branch_step else None,
                }
            )

    chain_steps = []
    if step.response_type == "chain":
        chain_steps = [
            _serialize_workspace_step(child, branch_steps_by_parent, chain_steps_by_parent, button_notifications_by_step)
            for child in chain_steps_by_parent.get(step.id, [])
        ]

    step_button_notifications = button_notifications_by_step.get(step.id, {})
    button_notifications = [
        {
            "option_index": option_index,
            "option_label": label,
            "message_text": getattr(step_button_notifications.get(option_index), "message_text", None) or "",
            "recipient_ids": getattr(step_button_notifications.get(option_index), "recipient_ids", None) or "",
            "recipient_scope": getattr(step_button_notifications.get(option_index), "recipient_scope", None) or "",
        }
        for option_index, label in enumerate(button_options)
    ]

    return {
        "id": step.id,
        "kind": _workspace_node_kind(step),
        "title": step.step_title,
        "text": (step.custom_text or "").strip() if (step.custom_text or "").strip() else (step.default_text or ""),
        "text_preview": _workspace_text_preview(step),
        "response_type": step.response_type or "none",
        "response_label": _workspace_response_label(step),
        "button_options": button_options,
        "has_attachment": bool(step.attachment_filename),
        "attachment_filename": step.attachment_filename or "",
        "send_employee_card": bool(getattr(step, "send_employee_card", False)),
        "send_mode": step.send_mode or "immediate",
        "send_mode_label": SEND_MODE_LABELS.get(step.send_mode or "immediate", step.send_mode or "immediate"),
        "send_time": step.send_time or "",
        "day_offset_workdays": step.day_offset_workdays or 0,
        "target_field": step.target_field or "",
        "target_field_label": TARGET_FIELD_LABELS.get(step.target_field or "", "Не сохранять"),
        "launch_scenario_key": step.launch_scenario_key or "",
        "notify_on_send": bool(
            (getattr(step, "notify_on_send_text", None) or "").strip()
            or (getattr(step, "notify_on_send_recipient_ids", None) or "").strip()
            or (getattr(step, "notify_on_send_recipient_scope", None) or "").strip()
        ),
        "notify_on_send_text": getattr(step, "notify_on_send_text", None) or "",
        "notify_on_send_recipient_ids": getattr(step, "notify_on_send_recipient_ids", None) or "",
        "notify_on_send_recipient_scope": getattr(step, "notify_on_send_recipient_scope", None) or "",
        "button_notifications": button_notifications,
        "branch_items": branch_items,
        "chain_steps": chain_steps,
    }


def _build_scenario_workspace_payload(
    db: Session,
    selected_scenario_id: Optional[int] = None,
    kind: str = "scenario",
):
    kind = _normalize_workspace_kind(kind)
    scenarios = (
        db.query(ScenarioTemplate)
        .filter(ScenarioTemplate.scenario_kind == kind)
        .order_by(ScenarioTemplate.sort_order, ScenarioTemplate.id)
        .all()
    )

    selected_scenario = None
    if selected_scenario_id:
        selected_scenario = next((item for item in scenarios if item.id == selected_scenario_id), None)
    if selected_scenario is None and scenarios:
        selected_scenario = scenarios[0]

    scenario_items = []
    for scenario in scenarios:
        steps_count = (
            db.query(FlowStepTemplate)
            .filter(
                FlowStepTemplate.flow_key == scenario.scenario_key,
                FlowStepTemplate.parent_step_id.is_(None),
            )
            .count()
        )
        scenario_items.append(
            {
                "id": scenario.id,
                "title": scenario.title,
                "description": scenario.description or "",
                "role_scope_label": ROLE_SCOPE_LABELS.get(scenario.role_scope, scenario.role_scope),
                "employee_scope_label": EMPLOYEE_SCOPE_LABELS.get(
                    getattr(scenario, "employee_scope", "all"),
                    getattr(scenario, "employee_scope", "all"),
                ),
                "trigger_mode_label": TRIGGER_MODE_LABELS.get(scenario.trigger_mode, scenario.trigger_mode),
                "steps_count": steps_count,
                "classic_url": f"{_workspace_collection_path(kind)}/{scenario.id}",
                "workspace_url": f"{_workspace_app_path(kind)}?scenario_id={scenario.id}",
            }
        )

    workspace = None
    if selected_scenario is not None:
        editor_data = _load_scenario_editor_data(db, selected_scenario)
        root_steps = [
            _serialize_workspace_step(
                step,
                editor_data["branch_steps_by_parent"],
                editor_data["chain_steps_by_parent"],
                editor_data["button_notifications_by_step"],
            )
            for step in editor_data["steps"]
        ]
        workspace = {
            "scenario": {
                "id": selected_scenario.id,
                "title": selected_scenario.title,
                "description": selected_scenario.description or "",
                "role_scope": selected_scenario.role_scope,
                "role_scope_label": ROLE_SCOPE_LABELS.get(selected_scenario.role_scope, selected_scenario.role_scope),
                "employee_scope": getattr(selected_scenario, "employee_scope", "all"),
                "employee_scope_label": EMPLOYEE_SCOPE_LABELS.get(
                    getattr(selected_scenario, "employee_scope", "all"),
                    getattr(selected_scenario, "employee_scope", "all"),
                ),
                "trigger_mode": selected_scenario.trigger_mode,
                "trigger_mode_label": TRIGGER_MODE_LABELS.get(selected_scenario.trigger_mode, selected_scenario.trigger_mode),
                "target_employee_id": getattr(selected_scenario, "target_employee_id", None),
                "classic_url": f"{_workspace_collection_path(kind)}/{selected_scenario.id}",
                "scenario_kind": kind,
            },
            "root_steps": root_steps,
            "stats": {
                "steps_count": len(root_steps),
            },
            "response_type_labels": _workspace_response_type_labels(),
            "role_scope_labels": ROLE_SCOPE_LABELS,
            "employee_scope_labels": EMPLOYEE_SCOPE_LABELS,
            "trigger_mode_labels": TRIGGER_MODE_LABELS,
            "target_field_labels": TARGET_FIELD_LABELS,
            "send_mode_labels": SEND_MODE_LABELS,
            "notification_recipient_scope_labels": NOTIFICATION_RECIPIENT_SCOPE_LABELS,
            "document_tag_titles": editor_data["document_tag_titles"],
            "employee_options": editor_data["employee_options"],
            "available_scenarios": [
                {
                    "value": item.scenario_key,
                    "label": item.title,
                }
                for item in editor_data["available_scenarios"]
            ],
        }

    return {
        "kind": kind,
        "item_label": _workspace_item_label(kind),
        "scenarios": scenario_items,
        "selected_scenario_id": selected_scenario.id if selected_scenario else None,
        "workspace": workspace,
    }


def _normalize_workspace_response_type(value: str, step: FlowStepTemplate) -> str:
    normalized = (value or "").strip()
    allowed = {"none", "text", "file", "buttons", "branching", "launch_scenario"}
    if step.parent_step_id is not None and step.branch_option_index is not None:
        allowed.add("chain")
    return normalized if normalized in allowed else (step.response_type or "none")


def _apply_workspace_step_update(step: FlowStepTemplate, payload: dict):
    step.step_title = str(payload.get("title") or "").strip() or step.step_title or "Без названия"
    step.custom_text = str(payload.get("text") or "").strip()
    step.response_type = _normalize_workspace_response_type(str(payload.get("response_type") or ""), step)
    button_options = str(payload.get("button_options") or "").strip()
    step.button_options = button_options or None

    send_mode = str(payload.get("send_mode") or "").strip() or "immediate"
    step.send_mode = send_mode if send_mode in SEND_MODE_LABELS else "immediate"
    step.send_time = (str(payload.get("send_time") or "").strip() or None) if step.send_mode == "specific_time" else None

    target_field = str(payload.get("target_field") or "").strip()
    step.target_field = target_field if target_field in TARGET_FIELD_LABELS else None
    step.launch_scenario_key = (
        str(payload.get("launch_scenario_key") or "").strip() or None
        if step.response_type == "launch_scenario"
        else None
    )
    step.send_employee_card = str(payload.get("send_employee_card") or "").strip().lower() in {"1", "true", "yes", "on"}
    step.notify_on_send_text = str(payload.get("notify_on_send_text") or "").strip() or None
    step.notify_on_send_recipient_ids = str(payload.get("notify_on_send_recipient_ids") or "").strip() or None
    step.notify_on_send_recipient_scope = _normalize_notification_scope(str(payload.get("notify_on_send_recipient_scope") or ""))

    if step.response_type not in {"buttons", "branching"}:
        step.button_options = None
    if step.response_type in {"branching", "chain"}:
        step.target_field = None

    return step


def _sync_workspace_button_notifications(db: Session, step: FlowStepTemplate, payload: dict) -> None:
    if step.response_type not in {"buttons", "branching"}:
        db.query(StepButtonNotification).filter(StepButtonNotification.step_id == step.id).delete()
        return

    button_options = [item.strip() for item in (step.button_options or "").splitlines() if item.strip()]
    submitted_notifications = payload.get("button_notifications") or []
    submitted_by_index = {}
    if isinstance(submitted_notifications, list):
        for item in submitted_notifications:
            if not isinstance(item, dict):
                continue
            raw_index = item.get("option_index")
            if raw_index is None or not str(raw_index).strip().isdigit():
                continue
            submitted_by_index[int(str(raw_index).strip())] = item

    for option_index, _label in enumerate(button_options):
        notification_payload = submitted_by_index.get(option_index, {})
        _sync_button_notification(
            db,
            step,
            option_index,
            str(notification_payload.get("message_text") or ""),
            str(notification_payload.get("recipient_ids") or ""),
            str(notification_payload.get("recipient_scope") or ""),
        )

    for notification in db.query(StepButtonNotification).filter(StepButtonNotification.step_id == step.id).all():
        if notification.option_index >= len(button_options):
            db.delete(notification)


def _delete_step_attachment_file(step: FlowStepTemplate) -> None:
    attachment_path = (getattr(step, "attachment_path", None) or "").strip()
    if attachment_path:
        path = Path(attachment_path)
        if path.exists():
            path.unlink()
    setattr(step, "attachment_path", None)
    setattr(step, "attachment_filename", None)


def _delete_step_subtree(db: Session, step: FlowStepTemplate) -> None:
    child_steps = (
        db.query(FlowStepTemplate)
        .filter(FlowStepTemplate.parent_step_id == step.id)
        .order_by(FlowStepTemplate.id.asc())
        .all()
    )
    for child_step in child_steps:
        _delete_step_subtree(db, child_step)
    _delete_step_attachment_file(step)
    db.query(StepButtonNotification).filter(StepButtonNotification.step_id == step.id).delete()
    db.delete(step)


def _normalize_notification_scope(value: Optional[str]) -> Optional[str]:
    normalized = ",".join(
        chunk.strip()
        for chunk in (value or "").replace("\n", ",").split(",")
        if chunk.strip()
    )
    return normalized if normalized in NOTIFICATION_RECIPIENT_SCOPE_LABELS else None


def _sync_button_notification(
    db: Session,
    step: FlowStepTemplate,
    option_index: int,
    message_text: str,
    recipient_ids: str,
    recipient_scope: str,
) -> None:
    notification = (
        db.query(StepButtonNotification)
        .filter(
            StepButtonNotification.step_id == step.id,
            StepButtonNotification.option_index == option_index,
        )
        .order_by(StepButtonNotification.id.asc())
        .first()
    )
    normalized_text = message_text.strip() or None
    normalized_recipient_ids = recipient_ids.strip() or None
    normalized_scope = _normalize_notification_scope(recipient_scope)
    if not normalized_text and not normalized_recipient_ids and not normalized_scope:
        if notification:
            db.delete(notification)
        return
    if not notification:
        notification = StepButtonNotification(
            flow_key=step.flow_key,
            step_id=step.id,
            option_index=option_index,
        )
        db.add(notification)
    notification.flow_key = step.flow_key
    notification.step_id = step.id
    notification.option_index = option_index
    notification.message_text = normalized_text
    notification.recipient_ids = normalized_recipient_ids
    notification.recipient_scope = normalized_scope


def _copy_step_attachment_file(source_step: FlowStepTemplate, target_step: FlowStepTemplate) -> None:
    source_path = (getattr(source_step, "attachment_path", None) or "").strip()
    source_name = (getattr(source_step, "attachment_filename", None) or "").strip()
    if not source_path or not source_name:
        return
    source = Path(source_path)
    if not source.exists():
        return
    destination = build_step_attachment_path(target_step.flow_key, target_step.step_key, source_name)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    target_step.attachment_path = str(destination)
    target_step.attachment_filename = source_name


async def _save_step_attachment(step: FlowStepTemplate, upload: UploadFile) -> None:
    filename = (upload.filename or "").strip()
    if not filename:
        return
    destination = build_step_attachment_path(step.flow_key, step.step_key, filename)
    content = await upload.read()
    destination.write_bytes(content)
    _delete_step_attachment_file(step)
    step.attachment_path = str(destination)
    step.attachment_filename = filename


def _delete_step_tree(db: Session, step: FlowStepTemplate) -> None:
    db.query(StepButtonNotification).filter(StepButtonNotification.step_id == step.id).delete()
    children = db.query(FlowStepTemplate).filter(FlowStepTemplate.parent_step_id == step.id).all()
    for child in children:
        _delete_step_tree(db, child)
    _delete_step_attachment_file(step)
    db.delete(step)


def _copy_template_entity(db: Session, scenario: ScenarioTemplate) -> ScenarioTemplate:
    last_scenario = (
        db.query(ScenarioTemplate)
        .filter(ScenarioTemplate.scenario_kind == scenario.scenario_kind)
        .order_by(ScenarioTemplate.sort_order.desc(), ScenarioTemplate.id.desc())
        .first()
    )
    scenario_copy = ScenarioTemplate(
        scenario_key=_generate_workspace_scenario_key(f"custom_{scenario.scenario_kind}"),
        title=f"{scenario.title} (копия)",
        sort_order=(last_scenario.sort_order + 10) if last_scenario else 10,
        scenario_kind=scenario.scenario_kind,
        role_scope=scenario.role_scope,
        employee_scope=getattr(scenario, "employee_scope", "all"),
        target_employee_id=getattr(scenario, "target_employee_id", None),
        trigger_mode=scenario.trigger_mode,
        description=scenario.description,
    )
    db.add(scenario_copy)
    db.flush()

    original_steps = (
        db.query(FlowStepTemplate)
        .filter(FlowStepTemplate.flow_key == scenario.scenario_key)
        .order_by(FlowStepTemplate.id.asc())
        .all()
    )
    original_button_notifications = (
        db.query(StepButtonNotification)
        .filter(StepButtonNotification.flow_key == scenario.scenario_key)
        .order_by(StepButtonNotification.step_id.asc(), StepButtonNotification.option_index.asc(), StepButtonNotification.id.asc())
        .all()
    )
    step_id_map: dict[int, FlowStepTemplate] = {}
    for index, original_step in enumerate(original_steps, start=1):
        copied_step = FlowStepTemplate(
            flow_key=scenario_copy.scenario_key,
            step_key=f"{original_step.step_key}_copy_{scenario_copy.id}_{index}",
            parent_step_id=step_id_map.get(original_step.parent_step_id).id if original_step.parent_step_id in step_id_map else None,
            branch_option_index=original_step.branch_option_index,
            step_title=original_step.step_title,
            sort_order=original_step.sort_order,
            default_text=original_step.default_text,
            custom_text=original_step.custom_text,
            response_type=original_step.response_type,
            button_options=original_step.button_options,
            send_mode=original_step.send_mode,
            send_time=original_step.send_time,
            day_offset_workdays=original_step.day_offset_workdays,
            target_field=original_step.target_field,
            launch_scenario_key=original_step.launch_scenario_key,
            send_employee_card=getattr(original_step, "send_employee_card", False),
            notify_on_send_text=getattr(original_step, "notify_on_send_text", None),
            notify_on_send_recipient_ids=getattr(original_step, "notify_on_send_recipient_ids", None),
            notify_on_send_recipient_scope=getattr(original_step, "notify_on_send_recipient_scope", None),
        )
        db.add(copied_step)
        db.flush()
        _copy_step_attachment_file(original_step, copied_step)
        step_id_map[original_step.id] = copied_step

    for original_notification in original_button_notifications:
        copied_parent_step = step_id_map.get(original_notification.step_id)
        if not copied_parent_step:
            continue
        db.add(
            StepButtonNotification(
                flow_key=scenario_copy.scenario_key,
                step_id=copied_parent_step.id,
                option_index=original_notification.option_index,
                message_text=original_notification.message_text,
                recipient_ids=original_notification.recipient_ids,
                recipient_scope=original_notification.recipient_scope,
            )
        )

    db.commit()
    db.refresh(scenario_copy)
    return scenario_copy


def _delete_template_entity(db: Session, scenario: ScenarioTemplate) -> None:
    for step in db.query(FlowStepTemplate).filter(FlowStepTemplate.flow_key == scenario.scenario_key).all():
        _delete_step_attachment_file(step)
    db.query(StepButtonNotification).filter(StepButtonNotification.flow_key == scenario.scenario_key).delete()
    db.query(FlowStepTemplate).filter(FlowStepTemplate.flow_key == scenario.scenario_key).delete()
    db.query(ScenarioProgress).filter(ScenarioProgress.scenario_key == scenario.scenario_key).delete()
    db.query(SurveyAnswer).filter(SurveyAnswer.scenario_key == scenario.scenario_key).delete()
    db.query(FlowLaunchRequest).filter(FlowLaunchRequest.flow_key == scenario.scenario_key).delete()
    db.delete(scenario)
