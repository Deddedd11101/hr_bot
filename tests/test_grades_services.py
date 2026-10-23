"""Service contracts on fresh SQLite; no application startup or live DB access."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, Thread
import unittest

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "ci-dummy-token")
os.environ.setdefault("ADMIN_SESSION_SECRET", "ci-admin-session-secret")
os.environ.setdefault("DATABASE_URL", "sqlite://")

from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import Session
from fastapi import HTTPException
from unittest.mock import patch

from app.database import Base
from app.models import (AdminAccount, Employee, EmployeeGradeProfile, Grade,
                        GradeAssessment, GradeAssessmentValue, GradeSkill,
                        GradeSkillImportance, GradeSkillExpectation, Position)
from app.time_utils import utc_now
from app.web import grades as service


class GradeServicesTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.engine = create_engine("sqlite:///" + str(Path(self.temp.name) / "grades.db"),
                                    connect_args={"check_same_thread": False, "timeout": 10})
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine, autoflush=False)
        now = utc_now()
        self.db.add_all([Employee(id=1, full_name="Test employee", created_at=now,
                                 desired_position="designer"),
                         AdminAccount(id=1, login="test", password_hash="unused", role="hr",
                                      created_at=now, updated_at=now),
                         Position(id=1, title="Designer", slug="designer", created_at=now)])
        service.seed_grades(self.db)
        self.spec = service.save_catalog_item(self.db, "specializations",
                                              {"name": "Services", "position_slug": "designer"})
        self.cat = service.save_catalog_item(self.db, "categories", {"name": "Research"})
        self.skill = service.save_catalog_item(self.db, "skills", {"name": "Interview", "category_id": self.cat["id"]})
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        self.temp.cleanup()

    def profile(self, **extra):
        return service.update_employee_grade(self.db, 1, dict(specialization_id=self.spec["id"],
                                                             current_grade_id=1, **extra))

    def draft(self, **extra):
        self.profile(**extra)
        return service.create_assessment(self.db, 1, 1)

    def review_request(self, **extra):
        from uuid import uuid4
        preview = service.preview_review(self.db, 1, self.spec["id"], 1)
        return dict(request_id=str(uuid4()), specialization_id=self.spec["id"], current_grade_id=1,
                    matrix_version=preview["matrix_version"], comment="First review",
                    values=[{"skill_id": self.skill["id"], "level": 0}], **extra)

    def test_single_save_is_final_and_idempotent_with_explicit_zero(self):
        payload = self.review_request()
        self.assertIsNone(service._profile(self.db, 1))
        self.assertEqual(self.db.query(GradeAssessment).count(), 0)
        result = service.save_review(self.db, 1, 1, payload)
        self.assertEqual(result["status"], "final")
        self.assertTrue(result["scores"][0]["assessed"])
        self.assertEqual(result["review_comment"], "First review")
        self.assertEqual(service.save_review(self.db, 1, 1, payload), result)
        self.assertEqual(self.db.query(GradeAssessment).count(), 1)

    def test_single_save_rejects_stale_template_and_foreign_draft(self):
        payload = self.review_request()
        service.save_catalog_item(self.db, "skills", {"name": "Changed"}, self.skill["id"])
        with self.assertRaises(ValueError):
            service.save_review(self.db, 1, 1, payload)
        self.assertIsNone(service._profile(self.db, 1))
        old = self.draft()
        payload = self.review_request(draft_id=old.id)
        payload["current_grade_id"] = 3
        final = service.save_review(self.db, 1, 1, payload)
        self.assertEqual(final["id"], old.id)
        self.assertEqual(final["current_grade_id"], 3)
        self.assertEqual(service._profile(self.db, 1).current_grade_id, 3)

    def test_purge_verifies_backup_and_keeps_selected_review(self):
        import sqlite3
        from contextlib import closing
        old = self.draft()
        service.finalize_assessment(self.db, old.id)
        keep = service.create_assessment(self.db, 1, 1)
        self.db.commit()
        result = service.purge_other_reviews(self.db, 1, {"keep_id": keep.id, "expected_ids": [old.id]})
        self.db.commit()
        self.assertEqual(result["deleted_count"], 1)
        with closing(sqlite3.connect(Path(self.temp.name) / "backups" / result["backup"])) as backup:
            self.assertEqual(backup.execute("SELECT count(*) FROM grade_assessments").fetchone()[0], 2)
        self.assertEqual(self.db.query(GradeAssessment).count(), 1)
        self.assertEqual(service.assessment_payload(self.db, keep.id)["status"], "draft")

    def test_purge_fails_closed_before_deletion(self):
        old = self.draft()
        service.finalize_assessment(self.db, old.id)
        keep = service.create_assessment(self.db, 1, 1)
        self.db.commit()
        with self.assertRaises(ValueError):
            service.purge_other_reviews(self.db, 1, {"keep_id": keep.id, "expected_ids": []})
        with patch.object(service, "_backup_before_grade_purge", side_effect=ValueError("Backup failed")):
            with self.assertRaises(ValueError):
                service.purge_other_reviews(self.db, 1, {"keep_id": keep.id, "expected_ids": [old.id]})
        self.assertEqual(self.db.query(GradeAssessment).count(), 2)

    def test_archive_draft_preserves_values_and_allows_new_review(self):
        old = self.draft()
        service.update_assessment(self.db, old.id, {"values": [{"skill_id": self.skill["id"], "level": 3}]})
        archived = service.archive_assessment(self.db, old.id)
        self.assertEqual(archived["status"], "archived")
        self.assertIsNone(archived["finalized_at"])
        self.assertEqual(archived["scores"][0]["currentLevel"], 3)
        self.assertEqual(service.archive_assessment(self.db, old.id), archived)
        new = service.create_assessment(self.db, 1, 1)
        self.assertNotEqual(new.id, old.id)
        self.assertFalse(service.assessment_payload(self.db, new.id)["scores"][0]["assessed"])
        for mutation in (service.update_assessment,):
            with self.assertRaises(service.GradeConflictError):
                mutation(self.db, old.id, {"values": []})
        with self.assertRaises(service.GradeConflictError):
            service.finalize_assessment(self.db, old.id)
        self.assertEqual(service.assessment_payload(self.db, old.id), archived)

    def test_final_cannot_be_archived(self):
        old = self.draft()
        final = service.finalize_assessment(self.db, old.id)
        with self.assertRaises(service.GradeConflictError):
            service.archive_assessment(self.db, old.id)
        self.assertEqual(service.assessment_payload(self.db, old.id), final)

    def matrix(self, **extra):
        entry = dict(skill_id=self.skill["id"], importance=3, levels={"junior": 1, "middle": 4})
        entry.update(extra)
        return {"specialization_id": self.spec["id"], "rows": [entry]}

    def import_request(self, dry=True):
        return {"dryRun": dry, "mode": "create-specialization", "catalog": {
            "specialization": {"name": "Services"}, "categories": [{"name": "Research", "skills": [
                {"name": "Interview", "importance": "critical", "complexity": 2,
                 "levels": {"junior": "none", "middle": "2", "senior": 3, "lead": 4}}]}]}}

    def test_workspace_defaults_and_seed_preserve_existing(self):
        service.save_matrix(self.db, self.matrix())
        grade = self.db.get(Grade, 1)
        grade.name, grade.active = "Renamed", False
        self.db.flush()
        service.seed_grades(self.db)
        service.ensure_defaults(self.db)
        payload = service.workspace_payload(self.db)
        self.assertEqual(set(payload), {"grades", "specializations", "categories", "skills", "importances", "expectations", "positions"})
        self.assertEqual(len(payload["expectations"]), 4)
        self.assertEqual(payload["importances"][0]["importance"], 3)
        self.assertEqual(grade.name, "Renamed")
        self.assertFalse(grade.active)
        self.assertTrue(all(type(item["id"]) is int for item in payload["grades"]))

    def test_employee_delete_removes_grade_draft_and_values(self):
        from app.web.employees import _delete_employee_record
        draft = self.draft()
        self.db.add(GradeAssessmentValue(assessment_id=draft.id, skill_id=self.skill["id"], level=2))
        self.db.commit()
        with patch("app.web.employees.settings.FILE_STORAGE_DIR", self.temp.name):
            _delete_employee_record(self.db, self.db.get(Employee, 1))
        self.db.expire_all()
        for model in (Employee, EmployeeGradeProfile, GradeAssessment, GradeAssessmentValue):
            self.assertIsNone(self.db.scalar(select(model)))

    def test_employee_delete_preserves_final_grade_and_files(self):
        from app.web.employees import _delete_employee_record
        draft = self.draft()
        service.finalize_assessment(self.db, draft.id)
        self.db.commit()
        snapshot = draft.catalog_snapshot
        directory = Path(self.temp.name) / "1"
        directory.mkdir()
        evidence = directory / "evidence.txt"
        evidence.write_text("keep", encoding="utf-8")
        with patch("app.web.employees.settings.FILE_STORAGE_DIR", self.temp.name):
            with self.assertRaises(HTTPException) as caught:
                _delete_employee_record(self.db, self.db.get(Employee, 1))
        self.assertEqual(caught.exception.status_code, 409)
        self.db.rollback()
        self.assertIsNotNone(self.db.get(Employee, 1))
        self.assertIsNotNone(self.db.scalar(select(EmployeeGradeProfile)))
        self.assertEqual(self.db.get(GradeAssessment, draft.id).catalog_snapshot, snapshot)
        self.assertEqual(evidence.read_text(encoding="utf-8"), "keep")

    def test_catalog_uniqueness_and_archival(self):
        with self.assertRaises(ValueError):
            service.save_catalog_item(self.db, "categories", {"name": " research "})
        with self.assertRaises(ValueError):
            service.save_catalog_item(self.db, "grades", {"name": "Other", "rank": 1})
        with self.assertRaises(ValueError):
            service.save_catalog_item(self.db, "specializations", {"name": "Other", "position_slug": "missing"})
        service.archive_catalog_item(self.db, "categories", self.cat["id"])
        self.assertEqual(len(service.workspace_payload(self.db)["skills"]), 1)
        with self.assertRaises(ValueError):
            service.save_matrix(self.db, self.matrix())

    def test_seed_does_not_recreate_renamed_grade(self):
        grade = self.db.get(Grade, 1)
        grade.slug = "entry"
        self.db.flush()
        service.seed_grades(self.db)
        self.assertEqual(len(service.workspace_payload(self.db)["grades"]), 4)
        self.assertEqual(grade.slug, "entry")

    def test_finalize_does_not_depend_on_archived_legacy_goal(self):
        draft = self.draft(target_grade_id=2)
        service.archive_catalog_item(self.db, "grades", 2)
        final = service.finalize_assessment(self.db, draft.id)
        self.assertEqual(final["status"], "final")
        self.assertIsNone(final["target_grade_id"])

    def test_matrix_validates_all_rows_before_mutation(self):
        for bad in (True, 1.5, "2", -1, 5, None):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                service.save_matrix(self.db, self.matrix(levels={"middle": bad}))
        with self.assertRaises(ValueError):
            service.save_matrix(self.db, self.matrix(importance=4))
        with self.assertRaises(ValueError):
            service.save_matrix(self.db, self.matrix(levels={"nonexistent": 2}))
        payload = self.matrix()
        payload["rows"].append({"skill_id": 999, "importance": 2, "levels": {"middle": 3}})
        with self.assertRaises(ValueError):
            service.save_matrix(self.db, payload)
        self.assertEqual(self.db.scalar(select(GradeSkillImportance)).importance, 1)

    def test_import_preview_is_read_only_even_with_autoflush(self):
        self.db.autoflush = True
        grade = self.db.get(Grade, 1)
        grade.name = "Pending unrelated edit"
        writes = []

        def observe(conn, cursor, statement, parameters, context, executemany):
            if statement.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")):
                writes.append(statement)

        event.listen(self.engine, "before_cursor_execute", observe)
        try:
            preview = service.import_catalog(self.db, self.import_request())
        finally:
            event.remove(self.engine, "before_cursor_execute", observe)
        self.assertEqual(writes, [])
        self.assertEqual(preview["counts"]["updateSkills"], 1)
        self.db.rollback()

    def test_import_aliases_merge_restore_and_caller_rollback(self):
        request = self.import_request(False)
        service.archive_catalog_item(self.db, "skills", self.skill["id"])
        service.archive_catalog_item(self.db, "specializations", self.spec["id"])
        service.archive_catalog_item(self.db, "categories", self.cat["id"])
        self.db.commit()
        request["expectedFingerprint"] = service.import_catalog(self.db, {**request, "dryRun": True})["fingerprint"]
        preview = service.import_catalog(self.db, request)
        self.assertEqual(preview["counts"]["createSkills"], 1)
        self.assertEqual(preview["specialization"]["id"], self.spec["id"])
        self.assertEqual(self.db.get(GradeSkill, self.skill["id"]).complexity, 1)
        self.assertTrue(self.db.get(GradeSkill, self.skill["id"]).active)
        self.assertEqual(self.db.scalar(select(GradeSkillImportance)).importance, 3)
        self.db.rollback()
        self.assertFalse(self.db.get(GradeSkill, self.skill["id"]).active)
        self.assertEqual(self.db.scalar(select(GradeSkillImportance)).importance, 1)

    def test_import_validation_and_current_grade_slugs(self):
        request = self.import_request()
        request["catalog"]["categories"] *= 2
        with self.assertRaises(ValueError):
            service.import_catalog(self.db, request)
        request = self.import_request()
        request.update(mode="update-specialization", targetSpecializationId=999)
        with self.assertRaises(LookupError):
            service.import_catalog(self.db, request)
        grade = self.db.get(Grade, 1)
        grade.slug = "starter"
        self.db.flush()
        with self.assertRaises(ValueError):
            service.import_catalog(self.db, self.import_request())
        request = self.import_request()
        request["catalog"]["categories"][0]["skills"][0]["levels"]["starter"] = "\u043d\u0435\u0442"
        self.assertEqual(service.import_catalog(self.db, request)["errors"], [])

    def test_position_suggestion_no_get_writes_or_name_guess(self):
        payload = service.employee_grade_payload(self.db, 1)
        self.assertIsNone(payload["profile"])
        self.assertEqual(payload["suggested_specialization_id"], self.spec["id"])
        self.assertIsNone(self.db.scalar(select(EmployeeGradeProfile)))
        self.db.get(Employee, 1).desired_position = "Services"
        self.db.flush()
        self.assertIsNone(service.employee_grade_payload(self.db, 1)["suggested_specialization_id"])

    def test_profile_no_goal_and_explicit_null(self):
        self.assertIsNone(self.profile()["target_grade_id"])
        other = service.save_catalog_item(self.db, "specializations", {"name": "Concepts"})
        self.profile(target_grade_id=2, target_specialization_id=other["id"])
        profile = service.update_employee_grade(self.db, 1, {"target_grade_id": None})
        self.assertIsNone(profile["target_grade_id"])
        self.assertIsNone(profile["target_specialization_id"])
        service.update_employee_grade(self.db, 1, {"current_grade_id": None})
        with self.assertRaises(ValueError):
            service.create_assessment(self.db, 1, 1)

    def test_assessment_reference_values_idempotency_and_no_promotion(self):
        assessment = self.draft(target_grade_id=2)
        self.assertEqual(service.create_assessment(self.db, 1, 1).id, assessment.id)
        service.update_assessment(self.db, assessment.id, {"values": [{"skill_id": self.skill["id"], "level": 3}]})
        service.finalize_assessment(self.db, assessment.id)
        next_assessment = service.create_assessment(self.db, 1, 1)
        self.assertNotEqual(next_assessment.id, assessment.id)
        self.assertFalse(service.assessment_payload(self.db, next_assessment.id)["scores"][0]["assessed"])
        self.assertEqual(self.db.scalar(select(EmployeeGradeProfile)).current_grade_id, 1)

    def test_target_specialization_uses_its_matrix(self):
        other = service.save_catalog_item(self.db, "specializations", {"name": "Concepts"})
        service.save_matrix(self.db, self.matrix())
        matrix = self.matrix(importance=1, levels={"middle": 2})
        matrix["specialization_id"] = other["id"]
        service.save_matrix(self.db, matrix)
        assessment = self.draft(target_grade_id=2, target_specialization_id=other["id"])
        payload = service.update_assessment(self.db, assessment.id,
                                             {"values": [{"skill_id": self.skill["id"], "level": 1}]})
        self.assertEqual(payload["catalog"]["specialization_id"], self.spec["id"])
        self.assertEqual(payload["scores"][0]["importance"], 3)
        self.assertEqual(payload["scores"][0]["targetLevel"], 0)
        self.assertIsNone(payload["progress"])
        self.assertEqual(payload["categories"][0]["categoryName"], "Research")

    def test_full_final_snapshot_is_frozen_and_read_without_catalog_queries(self):
        assessment = self.draft(target_grade_id=2)
        service.save_matrix(self.db, self.matrix())
        frozen = service.finalize_assessment(self.db, assessment.id)
        service.save_catalog_item(self.db, "skills", {"name": "Renamed"}, self.skill["id"])
        service.archive_catalog_item(self.db, "specializations", self.spec["id"])
        self.db.commit()
        queries = []

        def observe(conn, cursor, statement, parameters, context, executemany):
            queries.append(statement)

        event.listen(self.engine, "before_cursor_execute", observe)
        try:
            result = service.assessment_payload(self.db, frozen["id"])
        finally:
            event.remove(self.engine, "before_cursor_execute", observe)
        self.assertEqual(result, frozen)
        self.assertEqual(len(queries), 1)
        self.assertEqual(service.finalize_assessment(self.db, frozen["id"]), frozen)
        self.assertEqual(service.employee_grade_payload(self.db, 1)["latest_final"], frozen)
        with self.assertRaises(service.GradeConflictError):
            service.update_assessment(self.db, frozen["id"], {"values": []})

    def test_patch_rejects_unknown_archived_and_invalid_values(self):
        assessment = self.draft()
        for value in (True, -1, 5, 1.5, "2"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                service.update_assessment(self.db, assessment.id, {"values": [{"skill_id": self.skill["id"], "level": value}]})
        with self.assertRaises(ValueError):
            service.update_assessment(self.db, assessment.id, {"values": [{"skill_id": 999, "level": 1}]})
        service.archive_catalog_item(self.db, "skills", self.skill["id"])
        payload = service.update_assessment(self.db, assessment.id, {"values": [{"skill_id": self.skill["id"], "level": 1}]})
        self.assertEqual(payload["scores"][0]["currentLevel"], 1)

    def test_finalize_patch_race_and_stale_identity_map(self):
        assessment = self.draft()
        assessment_id = assessment.id
        self.db.commit()
        ready, done = Event(), Event()
        outcome = []

        def patch():
            with Session(self.engine) as db:
                stale = db.get(GradeAssessment, assessment_id)
                self.assertEqual(stale.status, "draft")
                ready.set()
                done.wait(5)
                try:
                    service.update_assessment(db, assessment_id, {"values": [{"skill_id": self.skill["id"], "level": 4}]})
                    db.commit()
                    outcome.append("incorrectly updated")
                except service.GradeConflictError:
                    db.rollback()
                    outcome.append("conflict")

        thread = Thread(target=patch)
        thread.start()
        self.assertTrue(ready.wait(5))
        frozen = service.finalize_assessment(self.db, assessment_id)
        done.set()
        self.db.commit()
        thread.join(10)
        self.assertFalse(thread.is_alive())
        self.assertEqual(outcome, ["conflict"])
        self.assertEqual(service.assessment_payload(self.db, assessment_id), frozen)
        self.assertIsNone(self.db.scalar(select(GradeAssessmentValue)))

    def test_no_commit_and_caller_rollback(self):
        assessment = self.draft()
        assessment_id = assessment.id
        service.finalize_assessment(self.db, assessment_id)
        self.db.rollback()
        self.assertIsNone(self.db.get(GradeAssessment, assessment_id))
        self.assertIsNone(self.db.scalar(select(EmployeeGradeProfile)))

    def test_sample_exact_seed_count_and_idempotent_import(self):
        path = Path(__file__).resolve().parents[1] / "tools/data/grade-design-catalog.json"
        catalog = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(len(catalog["categories"]), 6)
        # a360e50 contains 26 skills; the task's 27 is an off-by-one.
        self.assertEqual(sum(len(c["skills"]) for c in catalog["categories"]), 26)
        request = {"dryRun": False, "mode": "create-specialization", "catalog": catalog}
        request["expectedFingerprint"] = service.import_catalog(self.db, {**request, "dryRun": True})["fingerprint"]
        first = service.import_catalog(self.db, request)
        request["expectedFingerprint"] = service.import_catalog(self.db, {**request, "dryRun": True})["fingerprint"]
        second = service.import_catalog(self.db, request)
        self.assertEqual(first["specialization"]["id"], second["specialization"]["id"])
        self.assertEqual(second["counts"]["createSkills"], 0)
        self.assertEqual(second["counts"]["updateSkills"], 26)

    def test_review_freezes_draft_and_distinguishes_missing_from_zero(self):
        assessment = self.draft()
        original = service.assessment_payload(self.db, assessment.id)
        self.assertFalse(original["scores"][0]["assessed"])
        service.save_catalog_item(self.db, "skills", {"name": "Changed meaning"}, self.skill["id"])
        self.assertEqual(service.assessment_payload(self.db, assessment.id)["scores"][0]["skillName"], "Interview")
        zero = service.update_assessment(self.db, assessment.id, {"values": [{"skill_id": self.skill["id"], "level": 0}]})
        self.assertTrue(zero["scores"][0]["assessed"])
        cleared = service.update_assessment(self.db, assessment.id, {"values": [{"skill_id": self.skill["id"], "level": None}]})
        self.assertFalse(cleared["scores"][0]["assessed"])

    def test_compare_semantic_change_and_unchanged_grade(self):
        from app.grades.history import compare_reviews
        from app.models import EmployeeGradeDecision
        first = self.draft()
        service.update_assessment(self.db, first.id, {"values": [{"skill_id": self.skill["id"], "level": 2}]})
        frozen = service.finalize_assessment(self.db, first.id)
        second = service.create_assessment(self.db, 1, 1)
        service.update_assessment(self.db, second.id, {"values": [{"skill_id": self.skill["id"], "level": 3}]})
        newer = service.finalize_assessment(self.db, second.id)
        self.assertEqual(compare_reviews(frozen, newer)["rows"][0]["delta"], 1)
        self.assertEqual(self.db.scalar(select(EmployeeGradeProfile)).current_grade_id, 1)
        service.update_employee_grade(self.db, 1, {"comment": "Grade unchanged after review"}, actor_id=1)
        self.assertEqual(self.db.scalars(select(EmployeeGradeDecision)).all()[-1].grade_id, 1)
        service.save_catalog_item(self.db, "skills", {"description": "New evaluation criteria"}, self.skill["id"])
        third = service.create_assessment(self.db, 1, 1)
        service.update_assessment(self.db, third.id, {"values": [{"skill_id": self.skill["id"], "level": 4}]})
        changed = compare_reviews(newer, service.finalize_assessment(self.db, third.id))["rows"][0]
        self.assertEqual(changed["state"], "changed")
        self.assertIsNone(changed["delta"])
        foreign = dict(newer, employee_id=999)
        with self.assertRaises(ValueError):
            compare_reviews(frozen, foreign)

    def test_import_stale_guard_scope_and_stable_ids(self):
        request = self.import_request(False)
        request["expectedFingerprint"] = service.import_catalog(self.db, dict(request, dryRun=True))["fingerprint"]
        service.save_catalog_item(self.db, "skills", {"name": "Different"}, self.skill["id"])
        with self.assertRaises(ValueError):
            service.import_catalog(self.db, request)
        incoming = request["catalog"]["categories"][0]["skills"][0]
        incoming.update(id=self.skill["id"], name="Renamed only", change_kind="editorial")
        revision = self.db.get(GradeSkill, self.skill["id"]).revision
        request["expectedFingerprint"] = service.import_catalog(self.db, dict(request, dryRun=True))["fingerprint"]
        service.import_catalog(self.db, request)
        self.assertEqual(self.db.get(GradeSkill, self.skill["id"]).revision, revision)
        service.save_catalog_item(self.db, "skills", {"name": "Not part of the imported template", "category_id": self.cat["id"]})
        draft = self.draft()
        self.assertEqual([score["skillId"] for score in service.assessment_payload(self.db, draft.id)["scores"]], [self.skill["id"]])

    def test_payload_queries_are_bounded(self):
        assessment = self.draft()
        request = self.import_request(False)
        request["catalog"]["categories"][0]["skills"] = [dict(
            request["catalog"]["categories"][0]["skills"][0], name=f"Skill {index}") for index in range(40)]
        request["expectedFingerprint"] = service.import_catalog(self.db, {**request, "dryRun": True})["fingerprint"]
        service.import_catalog(self.db, request)
        queries = []

        def observe(conn, cursor, statement, parameters, context, executemany):
            queries.append(statement)

        event.listen(self.engine, "before_cursor_execute", observe)
        try:
            payload = service.assessment_payload(self.db, assessment.id)
        finally:
            event.remove(self.engine, "before_cursor_execute", observe)
        self.assertEqual(len(payload["scores"]), 1)
        self.assertLessEqual(len(queries), 9)


if __name__ == "__main__":
    unittest.main()
