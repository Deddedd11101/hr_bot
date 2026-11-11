import json
import unittest
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select

from app.grades.catalog import import_catalog, save_catalog_item
from app.grades.collections import create, report
from app.grades.history import compare_reviews
from app.models import FlowStepTemplate, GradeSpecialization, GradeSkill
from app.web import grades
from tests import test_grade_collections as collection_fixtures
from tests import test_grades_services as service_fixtures


class RubricTests(unittest.TestCase):
    setUp = service_fixtures.GradeServicesTests.setUp
    tearDown = service_fixtures.GradeServicesTests.tearDown
    review_request = service_fixtures.GradeServicesTests.review_request
    def payload(self, text="Observed behavior"):
        return {"dryRun": True, "mode": "update-specialization", "targetSpecializationId": self.spec["id"],
            "catalog": {"specialization": {"name": "Services", "assessment_intro": "Intro",
                "open_questions": ["What works well?"]}, "categories": [{"name": "Research", "skills": [{
                "id": self.skill["id"], "name": "Interview", "importance": 2,
                "levels": {"junior": 1, "middle": 2, "senior": 3, "lead": 4},
                "rubric": {"levels": {str(i): f"{text} {i}" for i in range(1, 5)}, "na": "Cannot assess"}}]}]}}

    def apply(self, payload):
        preview = import_catalog(self.db, payload)
        import_catalog(self.db, {**payload, "dryRun": False, "expectedFingerprint": preview["fingerprint"]})
        self.db.commit()
        return preview

    def test_specialization_scope_and_readonly_preview(self):
        self.apply(self.payload())
        second = save_catalog_item(self.db, "specializations", {"name": "Other"})
        self.db.commit()
        p = self.payload("Other behavior")
        p["targetSpecializationId"] = second["id"]
        p["catalog"]["specialization"]["name"] = "Other"
        self.apply(p)
        first = grades.preview_review(self.db, 1, self.spec["id"], None)
        other = grades.preview_review(self.db, 1, second["id"], None)
        self.assertNotEqual(first["scores"][0]["rubric"], other["scores"][0]["rubric"])
        before = self.db.get(GradeSpecialization, self.spec["id"]).assessment_guidance_json
        import_catalog(self.db, self.payload("Not applied"))
        self.assertEqual(self.db.get(GradeSpecialization, self.spec["id"]).assessment_guidance_json, before)
        self.assertIsNone(self.db.get(GradeSkill, self.skill["id"]).description)

    def test_collection_freezes_rubric_questions_and_legacy(self):
        collection_fixtures.GradeCollectionTests.prepare(self)
        legacy = create(self.db, 1, 1, {"request_id": str(uuid4()), "specialization_id": self.spec["id"], "recipient_ids": [2]})
        self.db.commit()
        self.apply(self.payload())
        run = create(self.db, 1, 1, {"request_id": str(uuid4()), "specialization_id": self.spec["id"], "recipient_ids": [3]})
        self.db.commit()
        old_text = self.db.scalar(select(FlowStepTemplate.default_text).where(FlowStepTemplate.flow_key == legacy.scenario_key))
        step = self.db.scalar(select(FlowStepTemplate).where(FlowStepTemplate.flow_key == run.scenario_key, FlowStepTemplate.step_key == f"skill_{self.skill['id']}"))
        self.assertIn("Observed behavior 1", step.default_text)
        self.assertEqual(step.button_options, "1\n2\n3\n4\nНе могу оценить")
        self.assertEqual(report(self.db, run)["reviewers"][0]["comments"][0]["question"], "What works well?")
        self.apply(self.payload("Changed"))
        self.assertIn("Observed behavior 1", step.default_text)
        self.assertEqual(report(self.db, run)["scores"][0]["rubric"]["levels"]["1"], "Observed behavior 1")
        self.assertEqual(self.db.scalar(select(FlowStepTemplate.default_text).where(FlowStepTemplate.flow_key == legacy.scenario_key)), old_text)

    def test_changed_criteria_not_comparable_and_final_immutable(self):
        self.apply(self.payload())
        before = grades.save_review(self.db, 1, 1, self.review_request())
        self.db.commit()
        self.apply(self.payload("Changed"))
        after = grades.save_review(self.db, 1, 1, self.review_request())
        self.db.commit()
        self.assertEqual(grades.assessment_payload(self.db, before["id"]), before)
        compared = compare_reviews(before, after)
        self.assertEqual(compared["rows"][0]["state"], "changed")
        self.assertIsNone(compared["rows"][0]["delta"])

    def test_approved_payloads_all_validate_and_designer_replacement(self):
        data = json.loads((Path(__file__).parents[1] / "tools/data/grade-rubrics-20261106.json").read_text(encoding="utf-8"))
        self.assertEqual(sum(len(c["skills"]) for p in data["packages"] for c in p["catalog"]["categories"]), 156)
        for package in data["packages"]:
            self.apply({"dryRun": True, "mode": "create-specialization", "catalog": package["catalog"]})
        designer = data["packages"][1]
        self.assertEqual(len(designer["added"]), 5)
        self.assertEqual(len(designer["removed"]), 5)
        analyst = data["packages"][4]["catalog"]["categories"]
        corporate = next(c for c in analyst if c["name"] == "Корпоративные компетенции")
        soft = next(c for c in analyst if c["name"] == "Soft skills")
        duplicates = {"Командная работа", "Системность", "Ответственность"}
        self.assertTrue(duplicates <= {s["name"] for s in corporate["skills"]})
        self.assertFalse(duplicates & {s["name"] for s in soft["skills"]})

    def test_invalid_anchors_rejected(self):
        p = self.payload()
        del p["catalog"]["categories"][0]["skills"][0]["rubric"]["levels"]["2"]
        with self.assertRaises(ValueError):
            import_catalog(self.db, p)

    def test_replacement_changes_only_specialization_scope(self):
        self.apply(self.payload())
        previous = grades.save_review(self.db, 1, 1, self.review_request())
        self.db.commit()
        replacement = self.payload()
        skill = replacement["catalog"]["categories"][0]["skills"][0]
        skill.pop("id")
        skill["name"] = "New competency"
        plan = self.apply(replacement)
        self.assertIn(self.skill["id"], plan["missing_ids"])
        self.assertIsNotNone(self.db.get(GradeSkill, self.skill["id"]))
        self.assertEqual(grades.assessment_payload(self.db, previous["id"]), previous)
        self.assertEqual([s["skillName"] for s in grades.preview_review(self.db, 1, self.spec["id"], None)["scores"]], ["New competency"])

    def test_rubric_answers_use_actual_levels_and_na_not_zero(self):
        import asyncio
        from app.scenario_engine import handle_button_response
        from app.models import Employee
        from app.grades.collections import process_pending
        collection_fixtures.GradeCollectionTests.prepare(self)
        self.apply(self.payload())
        run = create(self.db, 1, 1, {"request_id": str(uuid4()), "specialization_id": self.spec["id"],
                                   "recipient_ids": [2, 3], "open_questions": []})
        self.db.commit()
        messenger = collection_fixtures.ReviewMessenger()
        asyncio.run(process_pending(messenger, session_factory=self.sessions))
        self.db.expire_all()
        for respondent, option in ((2, 0), (3, 4)):
            self.assertTrue(asyncio.run(handle_button_response(messenger, self.db, self.db.get(Employee, respondent),
                run.scenario_key, f"skill_{self.skill['id']}", option)))
            self.assertEqual(report(self.db, run)["completed_count"], respondent - 2)
            self.assertTrue(asyncio.run(handle_button_response(messenger, self.db, self.db.get(Employee, respondent),
                run.scenario_key, "review_confirm", 0, message_id=len(messenger.texts))))
        result = report(self.db, run)
        self.assertEqual(result["completed_count"], 2)
        self.assertEqual(result["scores"][0]["currentLevel"], 1)
        self.assertEqual(result["scores"][0]["respondent_count"], 1)

