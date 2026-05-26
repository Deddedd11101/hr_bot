from __future__ import annotations

from typing import Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from .models import Employee


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
ROLE_SCOPE_TO_POSITION = {
    "designer": "Дизайнер",
    "project_manager": "Project manager",
    "analyst": "Аналитик",
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
):
    query = db.query(Employee)
    if not include_blocked:
        query = query.filter(Employee.is_bot_blocked.is_(False))

    if target_employee_id:
        return query.filter(Employee.id == target_employee_id)

    normalized_role_scope = (target_role_scope or "").strip()
    if normalized_role_scope and normalized_role_scope != "all":
        target_position = ROLE_SCOPE_TO_POSITION.get(normalized_role_scope)
        if not target_position:
            return query.filter(Employee.id == -1)
        query = query.filter(Employee.desired_position == target_position)

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

    if not stage_conditions:
        return query.filter(Employee.id == -1)

    return query.filter(or_(*stage_conditions))
