"""Explicit amendments of final reviews; generic PATCH/finalize stay immutable."""
import json
from uuid import UUID

from sqlalchemy import select, update

from app.grades.catalog import integer, items, record, require
from app.grades.history import matrix_version
from app.models import AdminAccount, GradeAssessment, GradeAssessmentRevision, GradeAssessmentValue
from app.time_utils import utc_now
from app.web import grades


def view(db, assessment_id):
    payload = grades.assessment_payload(db, assessment_id)
    if payload['status'] == 'final':
        payload['edit_token'] = matrix_version(payload)
    return payload


def history(db, assessment_id):
    assessment = grades._assessment(db, assessment_id)
    return [dict(id=r.id, actor_id=r.actor_id, reason=r.reason, created_at=r.created_at.isoformat(),
                 previous=json.loads(r.previous_snapshot))
            for r in db.scalars(select(GradeAssessmentRevision).where(
                GradeAssessmentRevision.assessment_id == assessment.id).order_by(GradeAssessmentRevision.id.desc()))]


def correct(db, assessment_id, actor_id, payload):
    payload = record(payload)
    if set(payload) != {'request_id', 'expected_token', 'reason', 'values'}:
        raise ValueError('request_id, expected_token, reason and values are required')
    if not isinstance(payload['request_id'], str):
        raise ValueError('request_id must be a UUID')
    request_id = str(UUID(payload['request_id']))
    reason = payload['reason']
    if not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 4000:
        raise ValueError('Explain the correction (1..4000 characters)')
    actor = require(db, AdminAccount, actor_id)
    if not actor.is_active:
        raise ValueError('Inactive assessor')
    changed = db.execute(update(GradeAssessment).where(
        GradeAssessment.id == assessment_id, GradeAssessment.status == 'final',
        GradeAssessment.archived_at.is_(None)).values(updated_at=GradeAssessment.updated_at)
        .execution_options(synchronize_session=False)).rowcount
    if not changed:
        raise grades.GradeConflictError('Only active finalized reviews can be corrected')
    assessment = grades._assessment(db, assessment_id)
    request_hash = matrix_version(payload)
    previous = db.scalar(select(GradeAssessmentRevision).where(
        GradeAssessmentRevision.assessment_id == assessment_id, GradeAssessmentRevision.request_id == request_id))
    if previous:
        if previous.request_hash != request_hash:
            raise grades.GradeConflictError('This correction request was already used with different values')
        return view(db, assessment_id)
    before = grades._snapshot(assessment)
    if before.get('review_mode') != 'historical':
        raise ValueError('Legacy reviews need explicit conversion before correction')
    if payload['expected_token'] != matrix_version(before):
        raise grades.GradeConflictError('Review changed. Reload before saving your correction')
    allowed = {s['skillId']: s for s in before['scores']}
    validated = {}
    for entry in items(payload['values'], 'values', nonempty=True):
        entry = record(entry)
        if set(entry) != {'skill_id', 'level'}:
            raise ValueError('Only skill_id and level can be corrected')
        skill_id = integer(entry['skill_id'], 1, 2**63 - 1, 'skill_id')
        if skill_id not in allowed or skill_id in validated:
            raise ValueError('Unknown or duplicate frozen skill')
        validated[skill_id] = None if entry['level'] is None else integer(entry['level'], 0, 4, 'level')
    effective = {key: (score['currentLevel'] if score.get('assessed', True) else None) for key, score in allowed.items()}
    effective.update(validated)
    if not any(v is not None for v in effective.values()):
        raise ValueError('Keep at least one assessed skill')
    if all(effective[key] == (score['currentLevel'] if score.get('assessed', True) else None) for key, score in allowed.items()):
        raise ValueError('No score changes to save')
    db.add(GradeAssessmentRevision(assessment_id=assessment_id, actor_id=actor_id, request_id=request_id,
        request_hash=request_hash, previous_snapshot=assessment.catalog_snapshot, reason=reason.strip()))
    values = {v.skill_id: v for v in db.scalars(select(GradeAssessmentValue).where(GradeAssessmentValue.assessment_id == assessment_id))}
    for skill_id, level in validated.items():
        value = values.get(skill_id)
        if level is None:
            if value is not None:
                db.delete(value)
        elif value is None:
            db.add(GradeAssessmentValue(assessment_id=assessment_id, skill_id=skill_id, level=level))
        else:
            value.level = level
    assessment.updated_at = utc_now()
    db.flush()
    calculated = grades._draft_payload(db, assessment, frozen_override=dict(
        draft_catalog=before['catalog'], review_mode='historical', import_source=before.get('import_source')))
    before.update(scores=calculated['scores'], categories=calculated['categories'],
                  updated_at=assessment.updated_at.isoformat(), correction_count=before.get('correction_count', 0) + 1)
    assessment.catalog_snapshot = json.dumps(before, ensure_ascii=False, allow_nan=False)
    db.flush()
    return view(db, assessment_id)
