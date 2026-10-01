from __future__ import annotations

import json
from typing import Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from .models import Employee
from .positions import parse_role_scopes, position_titles_for_scope, resolve_scope_slug


MASS_TARGET_NONE = "__none__"
LEGACY_MASS_TARGET_OPTIONS = {
    MASS_TARGET_NONE,
    "candidate",
    "adaptation",
    "ipr",
    "staff",
}
MASS_TARGET_EMPLOYEE_STAGE_OPTIONS = {
    MASS_TARGET_NONE,
    "adaptation",
    "ipr",
    "staff",
}
MASS_TARGET_CANDIDATE_STAGE_OPTIONS = {
    MASS_TARGET_NONE,
    "testing",
    "offer",
    "candidate_decline",
    "company_decline",
    "preonboarding",
    "contract",
}
def _normalize_values(values: list[str], allowed: set[str]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        key = (value or "").strip()
        if key and key in allowed and key not in normalized:
            normalized.append(key)
    return normalized


def normalize_legacy_target_statuses(values: list[str]) -> list[str]:
    return _normalize_values(values, LEGACY_MASS_TARGET_OPTIONS)


def normalize_mass_target_employee_stages(values: list[str]) -> list[str]:
    return _normalize_values(values, MASS_TARGET_EMPLOYEE_STAGE_OPTIONS)


def normalize_mass_target_candidate_stages(values: list[str]) -> list[str]:
    return _normalize_values(values, MASS_TARGET_CANDIDATE_STAGE_OPTIONS)


def serialize_target_values(values: list[str]) -> Optional[str]:
    normalized = [item for item in values if (item or "").strip()]
    return ",".join(normalized) if normalized else None


def serialize_target_selection(values: list[str] | list[int] | None) -> Optional[str]:
    return json.dumps(values, separators=(",", ":")) if values is not None else None


def deserialize_target_selection(value: Optional[str], *, kind: str) -> list[str] | list[int] | None:
    if value is None:
        return None
    try:
        items = json.loads(value)
    except (TypeError, ValueError):
        return []
    if not isinstance(items, list):
        return []
    if kind == "role":
        return parse_role_scopes([item for item in items if isinstance(item, str)])
    return list(dict.fromkeys(item for item in items if type(item) is int and item > 0))


def deserialize_target_values(value: Optional[str], *, kind: str) -> list[str]:
    if not value:
        return []
    items = [item.strip() for item in value.split(",")]
    if kind == "legacy":
        return normalize_legacy_target_statuses(items)
    if kind == "employee":
        return normalize_mass_target_employee_stages(items)
    return normalize_mass_target_candidate_stages(items)


def build_legacy_target_statuses(
    target_employee_stages: list[str],
    target_candidate_stages: list[str],
) -> list[str]:
    values = normalize_mass_target_employee_stages(target_employee_stages)
    if normalize_mass_target_candidate_stages(target_candidate_stages):
        values.append("candidate")
    return normalize_legacy_target_statuses(values)


def resolve_target_groups(
    *,
    legacy_target_statuses: Optional[str] = None,
    target_employee_stages: Optional[str] = None,
    target_candidate_stages: Optional[str] = None,
) -> tuple[list[str], list[str], bool]:
    employee_stages = deserialize_target_values(target_employee_stages, kind="employee")
    candidate_stages = deserialize_target_values(target_candidate_stages, kind="candidate")
    legacy_statuses = deserialize_target_values(legacy_target_statuses, kind="legacy")
    include_all_candidates = "candidate" in legacy_statuses and not candidate_stages
    if not employee_stages:
        employee_stages = [value for value in legacy_statuses if value != "candidate"]
    return employee_stages, candidate_stages, include_all_candidates


def mass_target_employee_query(
    db: Session,
    *,
    target_all: bool,
    target_employee_stages: list[str],
    target_candidate_stages: list[str],
    target_employee_id: Optional[int] = None,
    target_role_scope: Optional[str] = None,
    legacy_target_statuses: Optional[list[str]] = None,
    include_blocked: bool = False,
    target_role_scopes: Optional[list[str]] = None,
    target_employee_ids: Optional[list[int]] = None,
):
    query = db.query(Employee)
    if not include_blocked:
        query = query.filter(Employee.is_bot_blocked.is_(False))

    multi_target = target_role_scopes is not None or target_employee_ids is not None
    if target_employee_id and not multi_target:
        return query.filter(Employee.id == target_employee_id)

    normalized_role_scope = (target_role_scope or "").strip()
    if normalized_role_scope and normalized_role_scope != "all" and not multi_target:
        normalized_scope = resolve_scope_slug(normalized_role_scope)
        target_titles = position_titles_for_scope(db, normalized_scope)
        if not target_titles:
            return query.filter(Employee.id == -1)
        query = query.filter(Employee.desired_position.in_(target_titles))

    normalized_employee_stages = normalize_mass_target_employee_stages(target_employee_stages)
    normalized_candidate_stages = normalize_mass_target_candidate_stages(target_candidate_stages)
    legacy_statuses = normalize_legacy_target_statuses(legacy_target_statuses or [])
    include_all_candidates = "candidate" in legacy_statuses and not normalized_candidate_stages

    if target_all:
        return query

    stage_conditions = []
    if normalized_employee_stages:
        employee_conditions = []
        for value in normalized_employee_stages:
            if value == MASS_TARGET_NONE:
                employee_conditions.append(Employee.employee_stage.is_(None))
                employee_conditions.append(Employee.employee_stage == "")
            else:
                employee_conditions.append(Employee.employee_stage == value)
        if employee_conditions:
            stage_conditions.append(or_(*employee_conditions))

    if normalized_candidate_stages or include_all_candidates:
        candidate_conditions = [Employee.employee_stage == "candidate"]
        if normalized_candidate_stages:
            candidate_stage_conditions = []
            for value in normalized_candidate_stages:
                if value == MASS_TARGET_NONE:
                    candidate_stage_conditions.append(Employee.candidate_work_stage.is_(None))
                    candidate_stage_conditions.append(Employee.candidate_work_stage == "")
                else:
                    candidate_stage_conditions.append(Employee.candidate_work_stage == value)
            candidate_conditions.append(or_(*candidate_stage_conditions))
        stage_conditions.append(and_(*candidate_conditions))

    if legacy_statuses and not normalized_employee_stages:
        legacy_employee_conditions = []
        for value in legacy_statuses:
            if value in {"candidate"}:
                continue
            if value == MASS_TARGET_NONE:
                legacy_employee_conditions.append(Employee.employee_stage.is_(None))
                legacy_employee_conditions.append(Employee.employee_stage == "")
            else:
                legacy_employee_conditions.append(Employee.employee_stage == value)
        if legacy_employee_conditions:
            stage_conditions.append(or_(*legacy_employee_conditions))

    if multi_target:
        audience_conditions = []
        group_conditions = []
        scopes = parse_role_scopes(target_role_scopes or [])
        if scopes:
            titles = position_titles_for_scope(db, ",".join(scopes))
            group_conditions.append(Employee.desired_position.in_(titles) if titles else Employee.id == -1)
        if stage_conditions:
            group_conditions.append(or_(*stage_conditions))
        if group_conditions:
            audience_conditions.append(and_(*group_conditions))
        ids = [item for item in (target_employee_ids or []) if type(item) is int and item > 0]
        if ids:
            audience_conditions.append(Employee.id.in_(ids))
        return query.filter(or_(*audience_conditions)) if audience_conditions else query.filter(Employee.id == -1)

    if not stage_conditions:
        return query.filter(Employee.id == -1)

    return query.filter(or_(*stage_conditions))
