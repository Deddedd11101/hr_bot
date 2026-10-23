"""Grade sidecar services; all mutations flush, never commit.

Routes own a write transaction (BEGIN IMMEDIATE on SQLite). Conditional writes
also serialize draft mutation/finalization when these helpers are called directly.
Profiles without an explicit target have no goal; no implicit grade promotion.
"""
from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime

from sqlalchemy import select, update, delete

from app.grades.catalog import (
    archive_catalog_item, ensure_defaults, import_catalog, save_catalog_item,
    save_matrix, seed_grades, workspace_payload, integer, items, record, require, row,
)
from app.models import (
    AdminAccount, Employee, EmployeeGradeProfile, Grade, GradeSpecialization,
    GradeAssessment, GradeAssessmentValue, EmployeeGradeDecision,
)
from app.positions import normalize_position_slug
from app.time_utils import utc_now


class GradeConflictError(ValueError):
    """A finalized assessment cannot be mutated (route may map to 409)."""


def _serialized(item):
    result = {key: value.isoformat() if isinstance(value, datetime) else value
            for key, value in row(item).items() if key != "catalog_snapshot"}
    if isinstance(item, GradeAssessment) and item.archived_at is not None:
        result["status"] = "archived"
    return result


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
            GradeAssessment.id == assessment_id, GradeAssessment.status == "draft", GradeAssessment.archived_at.is_(None)
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
            "decisions": [_serialized(item) for item in db.scalars(select(EmployeeGradeDecision).where(EmployeeGradeDecision.employee_id == employee_id).order_by(EmployeeGradeDecision.created_at.desc(), EmployeeGradeDecision.id.desc()))],
            "latest_final": _snapshot(latest_final) if latest_final else None}


def update_employee_grade(db, employee_id, payload, actor_id=None):
    payload = record(payload)
    if set(payload) - {"specialization_id", "current_grade_id", "target_grade_id", "target_specialization_id", "comment"}:
        raise ValueError("Unknown profile fields")
    _lock_employee(db, employee_id)
    profile = _profile(db, employee_id)
    if profile is None:
        profile = EmployeeGradeProfile(employee_id=employee_id)
    previous_grade = profile.current_grade_id
    previous_spec = profile.specialization_id
    data = _goal_fields(db, profile, payload, profile=True)
    comment = payload.get("comment", "")
    if not isinstance(comment, str) or len(comment) > 4000:
        raise ValueError("Comment must contain at most 4000 characters")
    if previous_grade != data["current_grade_id"] or previous_spec != data["specialization_id"] or comment.strip():
        labels = {"grade": db.get(Grade, data["current_grade_id"]).name if data["current_grade_id"] else None,
                  "previous_grade": db.get(Grade, previous_grade).name if previous_grade else None,
                  "specialization": db.get(GradeSpecialization, data["specialization_id"]).name if data["specialization_id"] else None}
        db.add(EmployeeGradeDecision(employee_id=employee_id, actor_id=actor_id, previous_grade_id=previous_grade,
               grade_id=data["current_grade_id"], specialization_id=data["specialization_id"], comment=comment.strip() or None,
               labels_json=json.dumps(labels, ensure_ascii=False)))
    for field, value in data.items():
        setattr(profile, field, value)
    db.add(profile)
    db.flush()
    return row(profile)


def create_assessment(db, employee_id, assessor_id):
    _lock_employee(db, employee_id)
    draft = db.scalar(select(GradeAssessment).where(GradeAssessment.employee_id == employee_id,
                                                   GradeAssessment.status == "draft", GradeAssessment.archived_at.is_(None))
                      .execution_options(populate_existing=True))
    if draft is not None:
        return draft
    assessor = require(db, AdminAccount, assessor_id)
    if not assessor.is_active:
        raise ValueError("Inactive assessor")
    profile = _profile(db, employee_id)
    if profile is None or profile.specialization_id is None or profile.current_grade_id is None:
        raise ValueError("Select a specialization and current grade before assessment")
    require(db, GradeSpecialization, profile.specialization_id, active=True)
    require(db, Grade, profile.current_grade_id, active=True)
    data = {"specialization_id": profile.specialization_id, "current_grade_id": profile.current_grade_id,
            "target_grade_id": None, "target_specialization_id": None}
    assessment = GradeAssessment(employee_id=employee_id, assessor_admin_account_id=assessor_id,
                                 status="draft", **data)
    db.add(assessment)
    db.flush()
    catalog = _review_catalog(db, profile.specialization_id)
    assessment.catalog_snapshot = json.dumps({"draft_catalog": catalog, "review_mode": "historical"}, ensure_ascii=False)
    db.flush()
    return assessment


def _review_catalog(db, specialization_id):
    catalog = workspace_payload(db)
    spec = require(db, GradeSpecialization, specialization_id, active=True)
    allowed = set(json.loads(spec.skill_ids_json)) if spec.skill_ids_json is not None else None
    for key in ("grades", "specializations", "categories", "skills"):
        catalog[key] = [item for item in catalog[key] if item["active"]]
    category_ids = {item["id"] for item in catalog["categories"]}
    catalog["skills"] = [item for item in catalog["skills"] if item["category_id"] in category_ids and (allowed is None or item["id"] in allowed)]
    skill_ids = {item["id"] for item in catalog["skills"]}
    used_categories = {item["category_id"] for item in catalog["skills"]}
    catalog["categories"] = [item for item in catalog["categories"] if item["id"] in used_categories]
    catalog["specializations"] = [item for item in catalog["specializations"] if item["id"] == spec.id]
    catalog["importances"] = [item for item in catalog["importances"] if item["specialization_id"] == spec.id and item["skill_id"] in skill_ids]
    catalog["expectations"] = [item for item in catalog["expectations"] if item["specialization_id"] == spec.id and item["skill_id"] in skill_ids]
    catalog["specialization_id"] = spec.id
    return catalog


def preview_review(db, employee_id, specialization_id, grade_id):
    require(db, Employee, employee_id)
    require(db, Grade, grade_id, active=True)
    catalog = _review_catalog(db, specialization_id)
    assessment = GradeAssessment(id=-1, employee_id=employee_id, specialization_id=specialization_id,
                                 current_grade_id=grade_id, status="draft", created_at=utc_now(),
                                 catalog_snapshot=json.dumps({"draft_catalog": catalog, "review_mode": "historical"}))
    return _draft_payload(db, assessment)


def save_review(db, employee_id, actor_id, payload):
    from uuid import UUID
    payload = record(payload)
    if set(payload) - {"request_id", "draft_id", "specialization_id", "current_grade_id", "comment", "values", "matrix_version"}:
        raise ValueError("Unknown review fields")
    if not isinstance(payload.get("request_id"), str):
        raise ValueError("request_id must be a UUID")
    request_id = str(UUID(payload["request_id"]))
    _lock_employee(db, employee_id)
    for previous in db.scalars(select(GradeAssessment).where(GradeAssessment.employee_id == employee_id, GradeAssessment.status == "final")):
        if json.loads(previous.catalog_snapshot or "{}").get("review_request_id") == request_id:
            return assessment_payload(db, previous.id)
    draft_id = payload.get("draft_id")
    if draft_id is not None:
        assessment = lock_assessment(db, draft_id)
        if assessment.employee_id != employee_id:
            raise LookupError("Assessment not found")
        if assessment.specialization_id != payload.get("specialization_id"):
            raise ValueError("Archive the draft before changing its template")
        view = _draft_payload(db, assessment)
    else:
        active = db.scalar(select(GradeAssessment.id).where(GradeAssessment.employee_id == employee_id, GradeAssessment.status == "draft", GradeAssessment.archived_at.is_(None)))
        if active:
            raise ValueError("Continue or archive the existing draft")
        view = preview_review(db, employee_id, payload.get("specialization_id"), payload.get("current_grade_id"))
    if view["matrix_version"] != payload.get("matrix_version"):
        raise ValueError("Template changed. Reload the review form")
    if not any(item.get("level") is not None for item in items(payload.get("values", []), "values")):
        raise ValueError("Assess at least one skill")
    update_employee_grade(db, employee_id, {"specialization_id": payload.get("specialization_id"),
        "current_grade_id": payload.get("current_grade_id"), "target_grade_id": None,
        "target_specialization_id": None, "comment": payload.get("comment", "")}, actor_id=actor_id)
    if draft_id is None:
        assessment = create_assessment(db, employee_id, actor_id)
    assessment.current_grade_id = payload["current_grade_id"]
    db.flush()
    update_assessment(db, assessment.id, {"values": payload["values"], "target_grade_id": None, "target_specialization_id": None})
    result = finalize_assessment(db, assessment.id)
    result.update(review_comment=payload.get("comment", ""), review_request_id=request_id)
    assessment.catalog_snapshot = json.dumps(result, ensure_ascii=False, allow_nan=False)
    db.flush()
    return result


def _backup_before_grade_purge(db):
    import os
    import sqlite3
    from contextlib import closing
    from pathlib import Path
    from uuid import uuid4
    if db.bind.dialect.name != "sqlite" or not db.bind.url.database or db.bind.url.database == ":memory:":
        raise ValueError("Verified SQLite backup is required before deleting reviews")
    source_path = Path(db.bind.url.database).resolve(strict=True)
    directory = source_path.parent / "backups"
    directory.mkdir(exist_ok=True)
    target = directory / f"hr_bot.before-grade-purge.{uuid4().hex}.db"
    fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    with closing(sqlite3.connect(source_path.as_uri() + "?mode=ro", uri=True)) as source, closing(sqlite3.connect(target)) as backup:
        source.backup(backup)
        if backup.execute("PRAGMA quick_check").fetchone() != ("ok",):
            raise ValueError("Backup integrity check failed; reviews were not deleted")
    return target.name


def purge_other_reviews(db, employee_id, payload):
    payload = record(payload)
    if set(payload) != {"keep_id", "expected_ids"}:
        raise ValueError("keep_id and expected_ids are required")
    _lock_employee(db, employee_id)
    keep_id = integer(payload["keep_id"], 1, 2**63 - 1, "keep_id")
    keep = _assessment(db, keep_id)
    if keep.employee_id != employee_id or keep.archived_at is not None:
        raise ValueError("Keep an active review belonging to this employee")
    actual = sorted(db.scalars(select(GradeAssessment.id).where(GradeAssessment.employee_id == employee_id, GradeAssessment.id != keep_id)))
    expected = [integer(item, 1, 2**63 - 1, "expected_ids") for item in items(payload["expected_ids"], "expected_ids")]
    if sorted(expected) != actual or not actual:
        raise ValueError("Review history changed. Reload before deleting")
    backup = _backup_before_grade_purge(db)
    db.execute(delete(GradeAssessmentValue).where(GradeAssessmentValue.assessment_id.in_(actual)))
    db.execute(delete(GradeAssessment).where(GradeAssessment.employee_id == employee_id, GradeAssessment.id.in_(actual)))
    db.flush()
    return {"deleted_count": len(actual), "kept_id": keep_id, "backup": backup}


def _snapshot(assessment):
    # Fail closed: never silently recalculate a corrupt/missing final snapshot.
    try:
        payload = json.loads(assessment.catalog_snapshot or "")
    except (ValueError, TypeError) as exc:
        raise GradeConflictError("Final assessment snapshot is missing or invalid") from exc
    expected_status = "archived" if assessment.archived_at is not None else "final"
    if not isinstance(payload, dict) or payload.get("status") != expected_status or payload.get("id") != assessment.id:
        raise GradeConflictError("Final assessment snapshot is invalid")
    return deepcopy(payload)


def assessment_payload(db, assessment_id):
    assessment = _assessment(db, assessment_id)
    if assessment.status == "final" or assessment.archived_at is not None:
        return _snapshot(assessment)
    return _draft_payload(db, assessment)


def _draft_payload(db, assessment):
    from app.grades.calculations import category_averages, next_grade_progress, gap_list
    from app.grades.goals import build_goal_options, normalize_goal

    frozen = json.loads(assessment.catalog_snapshot or "{}")
    historical = frozen.get("review_mode") == "historical"
    catalog = deepcopy(frozen["draft_catalog"]) if historical else workspace_payload(db)
    for key in ("grades", "specializations", "categories", "skills"):
        catalog[key] = [item for item in catalog[key] if item["active"]]
    specs = {s["id"]: s for s in catalog["specializations"]}
    grades = {g["id"]: g for g in catalog["grades"]}
    goal = normalize_goal({"targetGradeId": assessment.target_grade_id if not historical and assessment.target_grade_id in grades else None,
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
               "assessed": s["id"] in values if historical else True,
               "currentLevel": values.get(s["id"], 0),
               "targetLevel": expectations.get((s["id"], goal["targetGradeId"]), 0)} for s in catalog["skills"]]
    result = _serialized(assessment)
    category_values = {item["categoryId"]: item for item in category_averages([score for score in scores if score["assessed"]])}
    category_rows = [{"categoryId": key, "categoryName": item["name"], "current": 0, "target": 0,
                      **category_values.get(key, {}), "assessed_count": sum(score["assessed"] for score in scores if score["categoryId"] == key)}
                     for key, item in categories.items() if any(score["categoryId"] == key for score in scores)]
    from app.grades.history import matrix_version
    result.update(catalog=catalog, scores=scores, categories=category_rows,
                  review_mode="historical" if historical else "legacy", scale_version="levels-0-4-v1", matrix_version=matrix_version(catalog),
                  import_source=frozen.get("import_source"),
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
    frozen = json.loads(assessment.catalog_snapshot or "{}")
    historical = frozen.get("review_mode") == "historical"
    if historical and any(payload.get(key) is not None for key in ("target_grade_id", "target_specialization_id")):
        raise ValueError("Review records actual skills, not a target grade")
    data = _goal_fields(db, assessment, payload)
    require(db, GradeSpecialization, assessment.specialization_id, active=not historical)
    require(db, Grade, assessment.current_grade_id, active=not historical)
    catalog = frozen["draft_catalog"] if historical else workspace_payload(db)
    categories = {c["id"] for c in catalog["categories"] if c["active"]}
    skills = {s["id"] for s in catalog["skills"] if s["active"] and s["category_id"] in categories}
    validated = {}
    for entry in items(payload.get("values", []), "values"):
        entry = record(entry)
        skill_id = integer(entry.get("skill_id"), 1, 2**63 - 1, "skill_id")
        if skill_id not in skills or skill_id in validated:
            raise ValueError("Unknown, archived or duplicate skill")
        validated[skill_id] = None if entry.get("level") is None and historical else integer(entry.get("level"), 0, 4, "level")
    existing = {v.skill_id: v for v in db.scalars(select(GradeAssessmentValue)
                 .where(GradeAssessmentValue.assessment_id == assessment.id))}
    for field, value in data.items():
        setattr(assessment, field, value)
    for skill_id, level in validated.items():
        value = existing.get(skill_id)
        if level is None:
            if value is not None:
                db.delete(value)
            continue
        if value is None:
            value = GradeAssessmentValue(assessment_id=assessment.id, skill_id=skill_id)
            db.add(value)
        value.level = level
    assessment.updated_at = utc_now()
    db.flush()
    return assessment_payload(db, assessment.id)


def archive_assessment(db, assessment_id):
    existing = _assessment(db, assessment_id)
    if existing.archived_at is not None:
        return _snapshot(existing)
    assessment = lock_assessment(db, assessment_id)
    payload = _draft_payload(db, assessment)
    now = utc_now()
    payload.update(status="archived", archived_at=now.isoformat(), updated_at=now.isoformat(), snapshot_version=2)
    assessment.archived_at = now
    assessment.updated_at = now
    assessment.catalog_snapshot = json.dumps(payload, ensure_ascii=False, allow_nan=False)
    db.flush()
    return payload


def finalize_assessment(db, assessment_id):
    assessment = lock_assessment(db, assessment_id, allow_final=True)
    if assessment.status == "final":
        return _snapshot(assessment)
    if json.loads(assessment.catalog_snapshot or "{}").get("review_mode") != "historical":
        _goal_fields(db, assessment, {}, profile=True)
    payload = _draft_payload(db, assessment)
    now = utc_now()
    payload.update(status="final", finalized_at=now.isoformat(), updated_at=now.isoformat(), snapshot_version=2)
    assessment.status = "final"
    assessment.finalized_at = assessment.updated_at = now
    assessment.catalog_snapshot = json.dumps(payload, ensure_ascii=False, allow_nan=False)
    db.flush()
    return deepcopy(payload)
