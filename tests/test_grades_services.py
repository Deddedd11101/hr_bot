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

    def test_finalize_rejects_archived_goal_without_closing_draft(self):
        draft = self.draft(target_grade_id=2)
        service.archive_catalog_item(self.db, "grades", 2)
        with self.assertRaises(ValueError):
            service.finalize_assessment(self.db, draft.id)
        self.assertEqual(draft.status, "draft")
        self.assertIsNone(draft.catalog_snapshot)

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
        self.assertEqual(service.assessment_payload(self.db, next_assessment.id)["scores"][0]["currentLevel"], 3)
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
        self.assertEqual(payload["catalog"]["specialization_id"], other["id"])
        self.assertEqual(payload["scores"][0]["importance"], 1)
        self.assertEqual(payload["scores"][0]["targetLevel"], 2)
        self.assertEqual(payload["progress"], 0.5)
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
        with self.assertRaises(ValueError):
            service.update_assessment(self.db, assessment.id, {"values": [{"skill_id": self.skill["id"], "level": 1}]})

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
        first = service.import_catalog(self.db, request)
        second = service.import_catalog(self.db, request)
        self.assertEqual(first["specialization"]["id"], second["specialization"]["id"])
        self.assertEqual(second["counts"]["createSkills"], 0)
        self.assertEqual(second["counts"]["updateSkills"], 26)

    def test_payload_queries_are_bounded(self):
        assessment = self.draft()
        request = self.import_request(False)
        request["catalog"]["categories"][0]["skills"] = [dict(
            request["catalog"]["categories"][0]["skills"][0], name=f"Skill {index}") for index in range(40)]
        service.import_catalog(self.db, request)
        queries = []

        def observe(conn, cursor, statement, parameters, context, executemany):
            queries.append(statement)

        event.listen(self.engine, "before_cursor_execute", observe)
        try:
            payload = service.assessment_payload(self.db, assessment.id)
        finally:
            event.remove(self.engine, "before_cursor_execute", observe)
        self.assertEqual(len(payload["scores"]), 41)
        self.assertLessEqual(len(queries), 9)


if __name__ == "__main__":
    unittest.main()
