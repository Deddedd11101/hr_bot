import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..file_storage import build_step_attachment_path
from ..flow_templates import (
    CANDIDATE_WORK_STAGE_LABELS,
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
    StepSendNotification,
    SurveyAnswer,
)
from ..scenario_engine import resolve_followup_step
from .employees import OFFER_DOCUMENT_TITLE, _all_employee_options


def _scenario_timestamp_columns(db: Session) -> set[str]:
    rows = db.execute(text("PRAGMA table_info(scenario_templates)")).fetchall()
    return {str(row[1]) for row in rows}


def _load_scenario_timestamps(db: Session, scenario_ids: list[int]) -> dict[int, dict[str, Optional[str]]]:
    if not scenario_ids:
        return {}
    scenario_columns = _scenario_timestamp_columns(db)
    has_created_at = "created_at" in scenario_columns
    has_updated_at = "updated_at" in scenario_columns
    if not has_created_at and not has_updated_at:
        return {}

    select_parts = ["id"]
    if has_created_at:
        select_parts.append("created_at")
    if has_updated_at:
        select_parts.append("updated_at")
    rows = db.execute(
        text(f"SELECT {', '.join(select_parts)} FROM scenario_templates WHERE id IN ({', '.join(str(int(item)) for item in scenario_ids)})")
    ).fetchall()

    timestamps: dict[int, dict[str, Optional[str]]] = {}
    for row in rows:
        row_map = dict(row._mapping)
        created_at = row_map.get("created_at")
        updated_at = row_map.get("updated_at")
        timestamps[int(row_map["id"])] = {
            "created_at": created_at.isoformat() if isinstance(created_at, datetime) else None,
            "updated_at": updated_at.isoformat() if isinstance(updated_at, datetime) else None,
        }
    return timestamps


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
        .order_by(
            StepButtonNotification.step_id,
            StepButtonNotification.option_index,
            StepButtonNotification.rule_index,
            StepButtonNotification.id,
        )
        .all()
    )
    button_notifications_by_step: dict[int, dict[int, list[StepButtonNotification]]] = defaultdict(lambda: defaultdict(list))
    for notification in button_notifications:
        button_notifications_by_step[notification.step_id][notification.option_index].append(notification)
    step_send_notifications = (
        db.query(StepSendNotification)
        .filter(StepSendNotification.flow_key == scenario.scenario_key)
        .order_by(
            StepSendNotification.step_id,
            StepSendNotification.rule_index,
            StepSendNotification.id,
        )
        .all()
    )
    step_send_notifications_by_step: dict[int, list[StepSendNotification]] = defaultdict(list)
    for notification in step_send_notifications:
        step_send_notifications_by_step[notification.step_id].append(notification)
    available_scenarios = db.query(ScenarioTemplate).order_by(ScenarioTemplate.title, ScenarioTemplate.id).all()
    employee_options = _all_employee_options(db)
    return {
        "steps": steps,
        "branch_steps_by_parent": dict(branch_steps_by_parent),
        "chain_steps_by_parent": dict(chain_steps_by_parent),
        "button_notifications_by_step": {
            step_id: {option_index: list(items) for option_index, items in option_map.items()}
            for step_id, option_map in button_notifications_by_step.items()
        },
        "step_send_notifications_by_step": {
            step_id: list(items) for step_id, items in step_send_notifications_by_step.items()
        },
        "available_scenarios": available_scenarios,
        "employee_options": employee_options,
        "document_tag_titles": [OFFER_DOCUMENT_TITLE],
    }


def _workspace_response_label(step: FlowStepTemplate, scenario_kind: str = "scenario") -> str:
    response_type = (step.response_type or "").strip()
    if scenario_kind == "survey" and response_type == "text" and (step.button_options or "").strip():
        return "Варианты ответа"
    extra_labels = {
        "chain": "Цепочка шагов",
        "launch_scenario": "Переход к сценарию",
    }
    return RESPONSE_TYPE_LABELS.get(response_type, extra_labels.get(response_type, response_type or "none"))


def _workspace_response_type_labels() -> dict[str, str]:
    labels = dict(RESPONSE_TYPE_LABELS)
    labels["launch_scenario"] = "Переход к сценарию"
    labels["chain"] = "Цепочка шагов"
    return labels


def _resolve_branch_return_to_step_key(db: Session, step: FlowStepTemplate, raw_value: str) -> Optional[str]:
    if step.parent_step_id is None or step.branch_option_index is None:
        return None
    normalized = (raw_value or "").strip()
    if not normalized:
        return None
    target_step = (
        db.query(FlowStepTemplate)
        .filter(
            FlowStepTemplate.flow_key == step.flow_key,
            FlowStepTemplate.step_key == normalized,
            FlowStepTemplate.parent_step_id.is_(None),
        )
        .first()
    )
    if not target_step:
        return None
    current = step
    while current.parent_step_id is not None:
        parent_step = db.get(FlowStepTemplate, current.parent_step_id)
        if not parent_step:
            break
        current = parent_step
    if current.step_key == target_step.step_key:
        return None
    return target_step.step_key


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


def _workspace_graph_node_id(step_id: int) -> str:
    return f"step:{step_id}"


def _workspace_graph_launch_node_id(source_step_id: int, scenario_key: str) -> str:
    return f"launch:{source_step_id}:{scenario_key}"


def _workspace_graph_branch_slot_node_id(parent_step_id: int, option_index: int) -> str:
    return f"branch-slot:{parent_step_id}:{option_index}"


def _workspace_graph_waits_for_response(response_type: str) -> bool:
    return response_type in {"text", "file", "buttons", "branching"}


def _flatten_workspace_graph_steps(root_steps: list[dict[str, Any]]) -> tuple[dict[int, dict[str, Any]], list[dict[str, Any]]]:
    steps_by_id: dict[int, dict[str, Any]] = {}
    empty_branch_slots: list[dict[str, Any]] = []

    def visit_step(step_payload: dict[str, Any]) -> None:
        step_id = int(step_payload["id"])
        steps_by_id[step_id] = step_payload
        for branch_item in step_payload.get("branch_items", []):
            branch_step = branch_item.get("step")
            if branch_step:
                visit_step(branch_step)
            else:
                empty_branch_slots.append(
                    {
                        "parent_step_id": step_id,
                        "option_index": int(branch_item["option_index"]),
                        "label": branch_item.get("label", ""),
                    }
                )
        for child_step in step_payload.get("chain_steps", []):
            visit_step(child_step)

    for root_step in root_steps:
        visit_step(root_step)
    return steps_by_id, empty_branch_slots


def _workspace_graph_branch_ancestor(db: Session, step: FlowStepTemplate) -> FlowStepTemplate | None:
    current = step
    while current.parent_step_id is not None:
        parent_step = db.get(FlowStepTemplate, current.parent_step_id)
        if not parent_step:
            return None
        if parent_step.branch_option_index is not None:
            return parent_step
        current = parent_step
    return None


def _workspace_graph_follow_edge_kind(
    db: Session,
    step: FlowStepTemplate,
    followup_step: FlowStepTemplate,
) -> str:
    if followup_step.parent_step_id == step.id and followup_step.branch_option_index is None:
        return "chain"
    branch_ancestor = step if step.branch_option_index is not None else _workspace_graph_branch_ancestor(db, step)
    if branch_ancestor and (branch_ancestor.return_to_step_key or "").strip() == followup_step.step_key:
        return "return_to_root"
    return "next"


def _workspace_graph_node_from_step(
    step_payload: dict[str, Any],
    actual_step: FlowStepTemplate,
) -> dict[str, Any]:
    has_button_rules = any(item.get("rules") for item in step_payload.get("button_notifications", []))
    return {
        "id": _workspace_graph_node_id(actual_step.id),
        "step_id": actual_step.id,
        "step_key": actual_step.step_key,
        "kind": "root_step" if actual_step.parent_step_id is None else ("branch_step" if actual_step.branch_option_index is not None else "chain_step"),
        "title": step_payload.get("title", "") or "Без названия",
        "text_preview": step_payload.get("text_preview", "") or "",
        "response_type": step_payload.get("response_type", "none") or "none",
        "response_label": step_payload.get("response_label", "") or "",
        "has_attachment": bool(step_payload.get("has_attachment")),
        "has_notifications": bool(step_payload.get("notify_on_send")) or has_button_rules,
        "waits_for_response": _workspace_graph_waits_for_response(str(step_payload.get("response_type") or "none")),
        "send_mode": step_payload.get("send_mode", "immediate") or "immediate",
        "launch_scenario_key": step_payload.get("launch_scenario_key", "") or "",
        "is_placeholder": False,
        "is_terminal": False,
    }


def _workspace_graph_slot_node(
    parent_step_id: int,
    option_index: int,
    label: str,
) -> dict[str, Any]:
    return {
        "id": _workspace_graph_branch_slot_node_id(parent_step_id, option_index),
        "step_id": None,
        "step_key": "",
        "kind": "branch_slot",
        "title": label or f"Ветка {option_index + 1}",
        "text_preview": "Ветка ещё не создана.",
        "response_type": "none",
        "response_label": "Пустая ветка",
        "has_attachment": False,
        "has_notifications": False,
        "waits_for_response": False,
        "send_mode": "immediate",
        "launch_scenario_key": "",
        "is_placeholder": True,
        "is_terminal": False,
    }


def _workspace_graph_launch_node(
    source_step_id: int,
    scenario_key: str,
    available_titles: dict[str, str],
) -> dict[str, Any]:
    return {
        "id": _workspace_graph_launch_node_id(source_step_id, scenario_key),
        "step_id": None,
        "step_key": scenario_key,
        "kind": "launch_target",
        "title": available_titles.get(scenario_key, scenario_key or "Целевой сценарий"),
        "text_preview": "Переход к другому сценарию.",
        "response_type": "launch_scenario",
        "response_label": "Переход к сценарию",
        "has_attachment": False,
        "has_notifications": False,
        "waits_for_response": False,
        "send_mode": "immediate",
        "launch_scenario_key": scenario_key,
        "is_placeholder": True,
        "is_terminal": True,
    }


def _build_workspace_graph(
    db: Session,
    scenario: ScenarioTemplate,
    root_steps: list[dict[str, Any]],
    editor_data: dict[str, Any],
) -> dict[str, Any]:
    serialized_by_id, empty_branch_slots = _flatten_workspace_graph_steps(root_steps)
    raw_steps_by_id: dict[int, FlowStepTemplate] = {}
    for root_step in editor_data["steps"]:
        raw_steps_by_id[root_step.id] = root_step
    for child_steps in editor_data["branch_steps_by_parent"].values():
        for child_step in child_steps:
            raw_steps_by_id[child_step.id] = child_step
    for child_steps in editor_data["chain_steps_by_parent"].values():
        for child_step in child_steps:
            raw_steps_by_id[child_step.id] = child_step

    available_titles = {item.scenario_key: item.title for item in editor_data["available_scenarios"]}
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    outgoing_edges: defaultdict[str, int] = defaultdict(int)
    added_node_ids: set[str] = set()
    added_edge_ids: set[str] = set()

    def add_node(node: dict[str, Any]) -> None:
        node_id = str(node["id"])
        if node_id in added_node_ids:
            return
        added_node_ids.add(node_id)
        nodes.append(node)

    def add_edge(source: str, target: str, kind: str, label: str = "") -> None:
        edge_id = f"{kind}:{source}:{target}:{label}"
        if edge_id in added_edge_ids:
            return
        added_edge_ids.add(edge_id)
        edges.append(
            {
                "id": edge_id,
                "source": source,
                "target": target,
                "kind": kind,
                "label": label,
            }
        )
        outgoing_edges[source] += 1

    for step_id, actual_step in raw_steps_by_id.items():
        serialized_step = serialized_by_id.get(step_id)
        if not serialized_step:
            continue
        add_node(_workspace_graph_node_from_step(serialized_step, actual_step))

    for slot in empty_branch_slots:
        add_node(
            _workspace_graph_slot_node(
                slot["parent_step_id"],
                slot["option_index"],
                slot["label"],
            )
        )

    for step_id, actual_step in raw_steps_by_id.items():
        serialized_step = serialized_by_id.get(step_id)
        if not serialized_step:
            continue
        source_id = _workspace_graph_node_id(step_id)
        if actual_step.response_type == "branching":
            existing_branch_steps = {
                child.branch_option_index: child
                for child in editor_data["branch_steps_by_parent"].get(actual_step.id, [])
                if child.branch_option_index is not None
            }
            for option_index, label in enumerate(serialized_step.get("button_options", [])):
                branch_step = existing_branch_steps.get(option_index)
                if branch_step is not None:
                    add_edge(
                        source_id,
                        _workspace_graph_node_id(branch_step.id),
                        "branch_option",
                        label,
                    )
                else:
                    slot_id = _workspace_graph_branch_slot_node_id(actual_step.id, option_index)
                    add_edge(source_id, slot_id, "branch_option", label)
                    fallback_step = resolve_followup_step(db, scenario.scenario_key, actual_step)
                    if fallback_step:
                        add_edge(slot_id, _workspace_graph_node_id(fallback_step.id), "next")
            continue

        if actual_step.response_type == "launch_scenario" and (actual_step.launch_scenario_key or "").strip():
            launch_key = actual_step.launch_scenario_key.strip()
            launch_node = _workspace_graph_launch_node(actual_step.id, launch_key, available_titles)
            add_node(launch_node)
            add_edge(source_id, launch_node["id"], "launch_scenario", launch_node["title"])
            continue

        followup_step = resolve_followup_step(db, scenario.scenario_key, actual_step)
        if not followup_step:
            continue
        add_edge(
            source_id,
            _workspace_graph_node_id(followup_step.id),
            _workspace_graph_follow_edge_kind(db, actual_step, followup_step),
        )

    for node in nodes:
        node["is_terminal"] = bool(node.get("is_terminal")) or outgoing_edges.get(str(node["id"]), 0) == 0

    return {
        "nodes": nodes,
        "edges": edges,
        "meta": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "has_branching": any(edge["kind"] == "branch_option" for edge in edges),
            "has_return_edges": any(edge["kind"] == "return_to_root" for edge in edges),
            "has_launch_edges": any(edge["kind"] == "launch_scenario" for edge in edges),
            "has_placeholders": any(node["is_placeholder"] for node in nodes),
        },
    }


def _serialize_workspace_step(
    step: FlowStepTemplate,
    scenario_kind: str,
    branch_steps_by_parent: dict[int, list[FlowStepTemplate]],
    chain_steps_by_parent: dict[int, list[FlowStepTemplate]],
    button_notifications_by_step: dict[int, dict[int, list[StepButtonNotification]]],
    step_send_notifications_by_step: dict[int, list[StepSendNotification]],
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
                    "step": _serialize_workspace_step(
                        branch_step,
                        scenario_kind,
                        branch_steps_by_parent,
                        chain_steps_by_parent,
                        button_notifications_by_step,
                        step_send_notifications_by_step,
                    ) if branch_step else None,
                }
            )

    chain_steps = []
    if step.response_type == "chain":
        chain_steps = [
            _serialize_workspace_step(
                child,
                scenario_kind,
                branch_steps_by_parent,
                chain_steps_by_parent,
                button_notifications_by_step,
                step_send_notifications_by_step,
            )
            for child in chain_steps_by_parent.get(step.id, [])
        ]

    step_button_notifications = button_notifications_by_step.get(step.id, {})
    step_send_rules = [
        {
            "rule_index": notification.rule_index,
            "message_text": notification.message_text or "",
            "recipient_ids": notification.recipient_ids or "",
            "recipient_scope": notification.recipient_scope or "",
        }
        for notification in step_send_notifications_by_step.get(step.id, [])
    ]
    button_notifications = [
        {
            "option_index": option_index,
            "option_label": label,
            "message_text": getattr((step_button_notifications.get(option_index) or [None])[0], "message_text", None) or "",
            "recipient_ids": getattr((step_button_notifications.get(option_index) or [None])[0], "recipient_ids", None) or "",
            "recipient_scope": getattr((step_button_notifications.get(option_index) or [None])[0], "recipient_scope", None) or "",
            "rules": [
                {
                    "rule_index": notification.rule_index,
                    "message_text": notification.message_text or "",
                    "recipient_ids": notification.recipient_ids or "",
                    "recipient_scope": notification.recipient_scope or "",
                }
                for notification in (step_button_notifications.get(option_index) or [])
            ],
        }
        for option_index, label in enumerate(button_options)
    ]

    return {
        "id": step.id,
        "step_key": step.step_key,
        "kind": _workspace_node_kind(step),
        "title": step.step_title,
        "text": (step.custom_text or "").strip() if (step.custom_text or "").strip() else (step.default_text or ""),
        "text_preview": _workspace_text_preview(step),
        "response_type": step.response_type or "none",
        "response_label": _workspace_response_label(step, scenario_kind),
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
        "return_to_step_key": getattr(step, "return_to_step_key", None) or "",
        "notify_on_send": bool(
            step_send_rules
            or
            (getattr(step, "notify_on_send_text", None) or "").strip()
            or (getattr(step, "notify_on_send_recipient_ids", None) or "").strip()
            or (getattr(step, "notify_on_send_recipient_scope", None) or "").strip()
        ),
        "notify_on_send_text": getattr(step, "notify_on_send_text", None) or "",
        "notify_on_send_recipient_ids": getattr(step, "notify_on_send_recipient_ids", None) or "",
        "notify_on_send_recipient_scope": getattr(step, "notify_on_send_recipient_scope", None) or "",
        "step_send_notifications": step_send_rules,
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

    scenario_timestamps = _load_scenario_timestamps(db, [scenario.id for scenario in scenarios])
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
                "employee_scope": getattr(scenario, "employee_scope", "all"),
                "created_at": scenario_timestamps.get(scenario.id, {}).get("created_at"),
                "updated_at": scenario_timestamps.get(scenario.id, {}).get("updated_at"),
                "candidate_work_stage_trigger": getattr(scenario, "candidate_work_stage_trigger", None) or "",
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
                selected_scenario.scenario_kind,
                editor_data["branch_steps_by_parent"],
                editor_data["chain_steps_by_parent"],
                editor_data["button_notifications_by_step"],
                editor_data["step_send_notifications_by_step"],
            )
            for step in editor_data["steps"]
        ]
        workspace_graph = _build_workspace_graph(db, selected_scenario, root_steps, editor_data)
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
                "candidate_work_stage_trigger": getattr(selected_scenario, "candidate_work_stage_trigger", None) or "",
                "trigger_mode_label": TRIGGER_MODE_LABELS.get(selected_scenario.trigger_mode, selected_scenario.trigger_mode),
                "target_employee_id": getattr(selected_scenario, "target_employee_id", None),
                "classic_url": f"{_workspace_collection_path(kind)}/{selected_scenario.id}",
                "scenario_kind": kind,
            },
            "root_steps": root_steps,
            "graph": workspace_graph,
            "stats": {
                "steps_count": len(root_steps),
            },
            "response_type_labels": _workspace_response_type_labels(),
            "role_scope_labels": ROLE_SCOPE_LABELS,
            "employee_scope_labels": EMPLOYEE_SCOPE_LABELS,
            "trigger_mode_labels": TRIGGER_MODE_LABELS,
            "candidate_work_stage_labels": CANDIDATE_WORK_STAGE_LABELS,
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


def _apply_workspace_step_update(db: Session, step: FlowStepTemplate, payload: dict, scenario_kind: str = "scenario"):
    if scenario_kind == "survey":
        question = (
            str(payload.get("text") or "").strip()
            or str(payload.get("title") or "").strip()
            or step.step_title
            or (step.custom_text or "").strip()
            or (step.default_text or "").strip()
            or "Без вопроса"
        )
        button_options = str(payload.get("button_options") or "").strip()
        step.step_title = question
        step.custom_text = question
        step.default_text = question
        step.response_type = "text"
        step.button_options = button_options or None
        step.send_mode = "immediate"
        step.send_time = None
        step.target_field = None
        step.launch_scenario_key = None
        step.return_to_step_key = None
        step.send_employee_card = False
        step.notify_on_send_text = None
        step.notify_on_send_recipient_ids = None
        step.notify_on_send_recipient_scope = None
        return step

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
    step.return_to_step_key = _resolve_branch_return_to_step_key(
        db,
        step,
        str(payload.get("return_to_step_key") or ""),
    )
    step.send_employee_card = str(payload.get("send_employee_card") or "").strip().lower() in {"1", "true", "yes", "on"}
    step.notify_on_send_text = str(payload.get("notify_on_send_text") or "").strip() or None
    step.notify_on_send_recipient_ids = str(payload.get("notify_on_send_recipient_ids") or "").strip() or None
    step.notify_on_send_recipient_scope = _normalize_notification_scope(str(payload.get("notify_on_send_recipient_scope") or ""))

    if step.response_type not in {"buttons", "branching"}:
        step.button_options = None
    if step.response_type == "chain":
        step.target_field = None

    return step


def _sync_workspace_button_notifications(db: Session, step: FlowStepTemplate, payload: dict, scenario_kind: str = "scenario") -> None:
    if scenario_kind == "survey" or step.response_type not in {"buttons", "branching"}:
        db.query(StepButtonNotification).filter(StepButtonNotification.step_id == step.id).delete()
        return

    button_options = [item.strip() for item in (step.button_options or "").splitlines() if item.strip()]
    submitted_notifications = payload.get("button_notifications") or []
    submitted_by_index: dict[int, list[dict]] = {}
    if isinstance(submitted_notifications, list):
        for item in submitted_notifications:
            if not isinstance(item, dict):
                continue
            raw_index = item.get("option_index")
            if raw_index is None or not str(raw_index).strip().isdigit():
                continue
            option_index = int(str(raw_index).strip())
            raw_rules = item.get("rules")
            normalized_rules: list[dict] = []
            if isinstance(raw_rules, list):
                for rule_index, rule in enumerate(raw_rules):
                    if not isinstance(rule, dict):
                        continue
                    normalized_rules.append(
                        {
                            "rule_index": int(str(rule.get("rule_index") or rule_index).strip() or rule_index),
                            "message_text": str(rule.get("message_text") or ""),
                            "recipient_ids": str(rule.get("recipient_ids") or ""),
                            "recipient_scope": str(rule.get("recipient_scope") or ""),
                        }
                    )
            else:
                normalized_rules.append(
                    {
                        "rule_index": 0,
                        "message_text": str(item.get("message_text") or ""),
                        "recipient_ids": str(item.get("recipient_ids") or ""),
                        "recipient_scope": str(item.get("recipient_scope") or ""),
                    }
                )
            submitted_by_index[option_index] = normalized_rules

    db.query(StepButtonNotification).filter(StepButtonNotification.step_id == step.id).delete()
    for option_index, _label in enumerate(button_options):
        for fallback_rule_index, notification_payload in enumerate(submitted_by_index.get(option_index, [])):
            _sync_button_notification(
                db,
                step,
                option_index,
                str(notification_payload.get("message_text") or ""),
                str(notification_payload.get("recipient_ids") or ""),
                str(notification_payload.get("recipient_scope") or ""),
                int(notification_payload.get("rule_index") or fallback_rule_index),
            )


def _sync_workspace_step_send_notifications(db: Session, step: FlowStepTemplate, payload: dict, scenario_kind: str = "scenario") -> None:
    if scenario_kind == "survey":
        db.query(StepSendNotification).filter(StepSendNotification.step_id == step.id).delete()
        step.notify_on_send_text = None
        step.notify_on_send_recipient_ids = None
        step.notify_on_send_recipient_scope = None
        return

    submitted_rules = payload.get("step_send_notifications") or []
    normalized_rules: list[dict] = []
    if isinstance(submitted_rules, list):
        for fallback_rule_index, item in enumerate(submitted_rules):
            if not isinstance(item, dict):
                continue
            normalized_rules.append(
                {
                    "rule_index": int(str(item.get("rule_index") or fallback_rule_index).strip() or fallback_rule_index),
                    "message_text": str(item.get("message_text") or ""),
                    "recipient_ids": str(item.get("recipient_ids") or ""),
                    "recipient_scope": str(item.get("recipient_scope") or ""),
                }
            )
    elif any(
        str(payload.get(field) or "").strip()
        for field in ("notify_on_send_text", "notify_on_send_recipient_ids", "notify_on_send_recipient_scope")
    ):
        normalized_rules.append(
            {
                "rule_index": 0,
                "message_text": str(payload.get("notify_on_send_text") or ""),
                "recipient_ids": str(payload.get("notify_on_send_recipient_ids") or ""),
                "recipient_scope": str(payload.get("notify_on_send_recipient_scope") or ""),
            }
        )

    db.query(StepSendNotification).filter(StepSendNotification.step_id == step.id).delete()
    for fallback_rule_index, notification_payload in enumerate(normalized_rules):
        normalized_text = str(notification_payload.get("message_text") or "").strip() or None
        normalized_recipient_ids = str(notification_payload.get("recipient_ids") or "").strip() or None
        normalized_scope = _normalize_notification_scope(str(notification_payload.get("recipient_scope") or ""))
        if not normalized_text and not normalized_recipient_ids and not normalized_scope:
            continue
        db.add(
            StepSendNotification(
                flow_key=step.flow_key,
                step_id=step.id,
                rule_index=int(notification_payload.get("rule_index") or fallback_rule_index),
                message_text=normalized_text,
                recipient_ids=normalized_recipient_ids,
                recipient_scope=normalized_scope,
            )
        )

    first_rule = next(
        (
            rule
            for rule in sorted(normalized_rules, key=lambda item: int(item.get("rule_index") or 0))
            if str(rule.get("message_text") or "").strip()
            or str(rule.get("recipient_ids") or "").strip()
            or _normalize_notification_scope(str(rule.get("recipient_scope") or ""))
        ),
        None,
    )
    step.notify_on_send_text = str(first_rule.get("message_text") or "").strip() or None if first_rule else None
    step.notify_on_send_recipient_ids = str(first_rule.get("recipient_ids") or "").strip() or None if first_rule else None
    step.notify_on_send_recipient_scope = (
        _normalize_notification_scope(str(first_rule.get("recipient_scope") or "")) if first_rule else None
    )


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
    db.query(StepSendNotification).filter(StepSendNotification.step_id == step.id).delete()
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
    rule_index: int = 0,
) -> None:
    notification = (
        db.query(StepButtonNotification)
        .filter(
            StepButtonNotification.step_id == step.id,
            StepButtonNotification.option_index == option_index,
            StepButtonNotification.rule_index == rule_index,
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
            rule_index=rule_index,
        )
        db.add(notification)
    notification.flow_key = step.flow_key
    notification.step_id = step.id
    notification.option_index = option_index
    notification.rule_index = rule_index
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
    db.query(StepSendNotification).filter(StepSendNotification.step_id == step.id).delete()
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
        .order_by(
            StepButtonNotification.step_id.asc(),
            StepButtonNotification.option_index.asc(),
            StepButtonNotification.rule_index.asc(),
            StepButtonNotification.id.asc(),
        )
        .all()
    )
    original_step_send_notifications = (
        db.query(StepSendNotification)
        .filter(StepSendNotification.flow_key == scenario.scenario_key)
        .order_by(
            StepSendNotification.step_id.asc(),
            StepSendNotification.rule_index.asc(),
            StepSendNotification.id.asc(),
        )
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
            return_to_step_key=getattr(original_step, "return_to_step_key", None),
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
                rule_index=original_notification.rule_index,
                message_text=original_notification.message_text,
                recipient_ids=original_notification.recipient_ids,
                recipient_scope=original_notification.recipient_scope,
            )
        )

    for original_notification in original_step_send_notifications:
        copied_parent_step = step_id_map.get(original_notification.step_id)
        if not copied_parent_step:
            continue
        db.add(
            StepSendNotification(
                flow_key=scenario_copy.scenario_key,
                step_id=copied_parent_step.id,
                rule_index=original_notification.rule_index,
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
    db.query(StepSendNotification).filter(StepSendNotification.flow_key == scenario.scenario_key).delete()
    db.query(FlowStepTemplate).filter(FlowStepTemplate.flow_key == scenario.scenario_key).delete()
    db.query(ScenarioProgress).filter(ScenarioProgress.scenario_key == scenario.scenario_key).delete()
    db.query(SurveyAnswer).filter(SurveyAnswer.scenario_key == scenario.scenario_key).delete()
    db.query(FlowLaunchRequest).filter(FlowLaunchRequest.flow_key == scenario.scenario_key).delete()
    db.delete(scenario)
