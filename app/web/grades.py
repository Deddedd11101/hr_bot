"""Grade sidecar services; all mutations flush, never commit.

Routes own a write transaction (BEGIN IMMEDIATE on SQLite). Conditional writes
also serialize draft mutation/finalization when these helpers are called directly.
Profiles without an explicit target have no goal; no implicit grade promotion.
"""
from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime

from sqlalchemy import select, update

from app.grades.catalog import (
    archive_catalog_item, ensure_defaults, import_catalog, save_catalog_item,
    save_matrix, seed_grades, workspace_payload, integer, items, record, require, row,
)
from app.models import (
    AdminAccount, Employee, EmployeeGradeProfile, Grade, GradeSpecialization,
    GradeAssessment, GradeAssessmentValue,
)
from app.positions import normalize_position_slug
from app.time_utils import utc_now


class GradeConflictError(ValueError):
    """A finalized assessment cannot be mutated (route may map to 409)."""


def _serialized(item):
    return {key: value.isoformat() if isinstance(value, datetime) else value
            for key, value in row(item).items() if key != "catalog_snapshot"}


def _assessment(db, assessment_id):
    # Populate-existing is essential after another transaction finalized a cached row.
    integer(assessment_id, 1, 2**63 - 1, "assessment_id")
    item = db.scalar(select(GradeAssessment).where(GradeAssessment.id == assessment_id)
                     .execution_options(populate_existing=True))
    if item is None:
        raise LookupError("Assessment not found")
    return item


def lock_assessment(db, assessment_id, *, allow_final=False):
    """Acquire a database write lock held until the caller commits or rolls back.

    This is a conditional no-op UPDATE, not a Python process-local lock. Never
    write AssessmentValue directly outside this guard or the route write lock.
    """
    integer(assessment_id, 1, 2**63 - 1, "assessment_id")
    with db.no_autoflush:
        changed = db.execute(update(GradeAssessment).where(
            GradeAssessment.id == assessment_id, GradeAssessment.status == "draft"
        ).values(updated_at=GradeAssessment.updated_at).execution_options(synchronize_session=False)).rowcount
        item = _assessment(db, assessment_id)
    if not changed and not (allow_final and item.status == "final"):
        raise GradeConflictError("Finalized assessment is immutable")
    return item


def _lock_employee(db, employee_id):
    integer(employee_id, 1, 2**63 - 1, "employee_id")
    changed = db.execute(update(Employee).where(Employee.id == employee_id)
                         .values(id=Employee.id).execution_options(synchronize_session=False)).rowcount
    if not changed:
        raise LookupError("Employee not found")


def _profile(db, employee_id):
    return db.scalar(select(EmployeeGradeProfile).where(EmployeeGradeProfile.employee_id == employee_id)
                     .execution_options(populate_existing=True))


def _goal_fields(db, source, payload, *, profile=False):
    from app.grades.goals import normalize_goal

    fields = {"target_grade_id", "target_specialization_id"}
    if profile:
        fields |= {"specialization_id", "current_grade_id"}
    data = {field: getattr(source, field, None) for field in fields}
    data.update({field: payload[field] for field in fields if field in payload})
    # Validate even references subsequently cleared by normalization.
    for field, value in data.items():
        if value is not None:
            require(db, GradeSpecialization if "specialization" in field else Grade, value, active=True)
    specialization_id = data.get("specialization_id", getattr(source, "specialization_id", None))
    goal = normalize_goal({"targetGradeId": data["target_grade_id"],
                           "targetSpecializationId": data["target_specialization_id"]}, specialization_id)
    data.update(target_grade_id=goal["targetGradeId"], target_specialization_id=goal["targetSpecializationId"])
    return data


def employee_grade_payload(db, employee_id):
    employee = require(db, Employee, employee_id)
    profile = _profile(db, employee_id)
    catalog = workspace_payload(db)
    grades = [g for g in catalog["grades"] if g["active"]]
    specs = [s for s in catalog["specializations"] if s["active"]]
    position_slug = normalize_position_slug(employee.desired_position or "")
    matches = [s["id"] for s in specs if s["position_slug"] and s["position_slug"] == position_slug]
    assessments = list(db.scalars(select(GradeAssessment).where(GradeAssessment.employee_id == employee_id)
                                  .order_by(GradeAssessment.created_at.desc(), GradeAssessment.id.desc())))
    latest_final = next((a for a in assessments if a.status == "final"), None)
    return {"employee_id": employee_id, "profile": row(profile) if profile else None,
            "suggested_specialization_id": matches[0] if len(matches) == 1 and
            (profile is None or profile.specialization_id is None) else None,
            "grades": grades, "specializations": specs,
            "assessments": [_serialized(a) for a in assessments],
            "latest_final": _snapshot(latest_final) if latest_final else None}


def update_employee_grade(db, employee_id, payload):
    payload = record(payload)
    if set(payload) - {"specialization_id", "current_grade_id", "target_grade_id", "target_specialization_id"}:
        raise ValueError("Unknown profile fields")
    _lock_employee(db, employee_id)
    profile = _profile(db, employee_id)
    if profile is None:
        profile = EmployeeGradeProfile(employee_id=employee_id)
    data = _goal_fields(db, profile, payload, profile=True)
    for field, value in data.items():
        setattr(profile, field, value)
    db.add(profile)
    db.flush()
    return row(profile)


def create_assessment(db, employee_id, assessor_id):
    _lock_employee(db, employee_id)
    draft = db.scalar(select(GradeAssessment).where(GradeAssessment.employee_id == employee_id,
                                                   GradeAssessment.status == "draft")
                      .execution_options(populate_existing=True))
    if draft is not None:
        return draft
    assessor = require(db, AdminAccount, assessor_id)
    if not assessor.is_active:
        raise ValueError("Inactive assessor")
    profile = _profile(db, employee_id)
    if profile is None or profile.specialization_id is None or profile.current_grade_id is None:
        raise ValueError("Select a specialization and current grade before assessment")
    data = _goal_fields(db, profile, {}, profile=True)
    previous = db.scalar(select(GradeAssessment).where(GradeAssessment.employee_id == employee_id)
                         .order_by(GradeAssessment.created_at.desc(), GradeAssessment.id.desc()).limit(1))
    assessment = GradeAssessment(employee_id=employee_id, assessor_admin_account_id=assessor_id,
                                 status="draft", **data)
    db.add(assessment)
    db.flush()
    if previous is not None:
        values = db.scalars(select(GradeAssessmentValue).where(GradeAssessmentValue.assessment_id == previous.id))
        for value in values:
            db.add(GradeAssessmentValue(assessment_id=assessment.id, skill_id=value.skill_id, level=value.level))
    db.flush()
    return assessment


def _snapshot(assessment):
    # Fail closed: never silently recalculate a corrupt/missing final snapshot.
    try:
        payload = json.loads(assessment.catalog_snapshot or "")
    except (ValueError, TypeError) as exc:
        raise GradeConflictError("Final assessment snapshot is missing or invalid") from exc
    if not isinstance(payload, dict) or payload.get("status") != "final" or payload.get("id") != assessment.id:
        raise GradeConflictError("Final assessment snapshot is invalid")
    return deepcopy(payload)


def assessment_payload(db, assessment_id):
    assessment = _assessment(db, assessment_id)
    if assessment.status == "final":
        return _snapshot(assessment)
    return _draft_payload(db, assessment)


def _draft_payload(db, assessment):
    from app.grades.calculations import category_averages, next_grade_progress, gap_list
    from app.grades.goals import build_goal_options, normalize_goal

    catalog = workspace_payload(db)
    for key in ("grades", "specializations", "categories", "skills"):
        catalog[key] = [item for item in catalog[key] if item["active"]]
    specs = {s["id"]: s for s in catalog["specializations"]}
    grades = {g["id"]: g for g in catalog["grades"]}
    goal = normalize_goal({"targetGradeId": assessment.target_grade_id if assessment.target_grade_id in grades else None,
                           "targetSpecializationId": assessment.target_specialization_id
                           if assessment.target_specialization_id in specs else None}, assessment.specialization_id)
    spec_id = goal["targetSpecializationId"] or assessment.specialization_id
    categories = {c["id"]: c for c in catalog["categories"]}
    catalog["skills"] = [s for s in catalog["skills"] if s["category_id"] in categories and spec_id in specs]
    skill_ids = {s["id"] for s in catalog["skills"]}
    catalog["importances"] = [i for i in catalog["importances"]
                              if i["specialization_id"] == spec_id and i["skill_id"] in skill_ids]
    catalog["expectations"] = [e for e in catalog["expectations"] if e["specialization_id"] == spec_id
                               and e["skill_id"] in skill_ids and e["grade_id"] in grades]
    catalog["specialization_id"] = spec_id
    values = {v.skill_id: v.level for v in db.scalars(select(GradeAssessmentValue)
              .where(GradeAssessmentValue.assessment_id == assessment.id))}
    importances = {i["skill_id"]: i["importance"] for i in catalog["importances"]}
    expectations = {(e["skill_id"], e["grade_id"]): e["level"] for e in catalog["expectations"]}
    scores = [{"skillId": s["id"], "skillName": s["name"], "categoryId": s["category_id"],
               "categoryName": categories[s["category_id"]]["name"], "importance": importances.get(s["id"], 1),
               "currentLevel": values.get(s["id"], 0),
               "targetLevel": expectations.get((s["id"], goal["targetGradeId"]), 0)} for s in catalog["skills"]]
    result = _serialized(assessment)
    result.update(catalog=catalog, scores=scores, categories=category_averages(scores),
                  progress=next_grade_progress(scores) if goal["targetGradeId"] else None,
                  gaps=gap_list(scores) if goal["targetGradeId"] else [],
                  goal_options=build_goal_options({"grades": catalog["grades"],
                      "specializations": catalog["specializations"], "currentSpecializationId": assessment.specialization_id}))
    return result


def update_assessment(db, assessment_id, payload):
    payload = record(payload)
    if set(payload) - {"values", "target_grade_id", "target_specialization_id"}:
        raise ValueError("Unknown assessment fields")
    assessment = lock_assessment(db, assessment_id)
    data = _goal_fields(db, assessment, payload)
    require(db, GradeSpecialization, assessment.specialization_id, active=True)
    require(db, Grade, assessment.current_grade_id, active=True)
    catalog = workspace_payload(db)
    categories = {c["id"] for c in catalog["categories"] if c["active"]}
    skills = {s["id"] for s in catalog["skills"] if s["active"] and s["category_id"] in categories}
    validated = {}
    for entry in items(payload.get("values", []), "values"):
        entry = record(entry)
        skill_id = integer(entry.get("skill_id"), 1, 2**63 - 1, "skill_id")
        if skill_id not in skills or skill_id in validated:
            raise ValueError("Unknown, archived or duplicate skill")
        validated[skill_id] = integer(entry.get("level"), 0, 4, "level")
    existing = {v.skill_id: v for v in db.scalars(select(GradeAssessmentValue)
                 .where(GradeAssessmentValue.assessment_id == assessment.id))}
    for field, value in data.items():
        setattr(assessment, field, value)
    for skill_id, level in validated.items():
        value = existing.get(skill_id)
        if value is None:
            value = GradeAssessmentValue(assessment_id=assessment.id, skill_id=skill_id)
            db.add(value)
        value.level = level
    assessment.updated_at = utc_now()
    db.flush()
    return assessment_payload(db, assessment.id)


def finalize_assessment(db, assessment_id):
    assessment = lock_assessment(db, assessment_id, allow_final=True)
    if assessment.status == "final":
        return _snapshot(assessment)
    _goal_fields(db, assessment, {}, profile=True)
    payload = _draft_payload(db, assessment)
    now = utc_now()
    payload.update(status="final", finalized_at=now.isoformat(), updated_at=now.isoformat(), snapshot_version=1)
    assessment.status = "final"
    assessment.finalized_at = assessment.updated_at = now
    assessment.catalog_snapshot = json.dumps(payload, ensure_ascii=False, allow_nan=False)
    db.flush()
    return deepcopy(payload)
