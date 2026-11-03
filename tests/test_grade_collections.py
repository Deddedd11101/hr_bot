import asyncio
from datetime import datetime
import json
import unittest
from uuid import uuid4
from unittest.mock import patch

from sqlalchemy import select, text
from sqlalchemy.orm import sessionmaker

from app.grades import collections
from app.grades import development_actions
from app.grades.corrections import correct, history, view
from app.feedback_exports import latest_feedback_run
from app.messaging.identity import set_primary_chat_id
from app.models import Employee, EmployeeFeedbackRecipient, GradeAssessmentValue, GradeDevelopmentAction, ScenarioProgress, ScenarioTemplate, FlowStepTemplate
from app.scenario_engine import handle_button_response
from app.web import grades
from app.time_utils import utc_now
from tests import test_grades_services as fixtures
from tests.test_scenario_engine_smoke import FakeMessenger


class GradeCollectionTests(unittest.TestCase):
    setUp = fixtures.GradeServicesTests.setUp
    tearDown = fixtures.GradeServicesTests.tearDown
    review_request = fixtures.GradeServicesTests.review_request

    def prepare(self):
        self.db.get(Employee, 1).employee_stage = "staff"
        for employee_id in (2, 3):
            person = Employee(id=employee_id, full_name=f"Reviewer {employee_id}", employee_stage="staff", created_at=utc_now())
            self.db.add(person)
            self.db.flush()
            set_primary_chat_id(person, str(700001000 + employee_id), db=self.db)
        self.db.commit()
        self.sessions = sessionmaker(bind=self.engine, autoflush=False)

    def create(self):
        row = collections.create(self.db, 1, 1, dict(request_id=str(uuid4()), specialization_id=self.spec["id"], recipient_ids=[2, 3]))
        self.db.commit()
        return row

    def answer(self, messenger, collection, respondent, skill_id, option):
        person = self.db.get(Employee, respondent)
        self.assertTrue(asyncio.run(handle_button_response(messenger, self.db, person, collection.scenario_key, f"skill_{skill_id}", option)))

    def test_individual_reviews_fractional_mean_idempotence_and_feedback_isolation(self):
        # Existing stage SQLite uses INTEGER affinity; it must still retain 1.5.
        self.db.execute(text("DROP TABLE grade_assessment_values"))
        self.db.execute(text("CREATE TABLE grade_assessment_values (id INTEGER PRIMARY KEY, assessment_id INTEGER NOT NULL, skill_id INTEGER NOT NULL, level INTEGER NOT NULL CHECK(level BETWEEN 0 AND 4), UNIQUE(assessment_id, skill_id))"))
        self.db.commit()
        self.prepare()
        row = self.create()
        messenger = FakeMessenger()
        asyncio.run(collections.process_pending(messenger, session_factory=self.sessions))
        self.db.expire_all()
        self.answer(messenger, row, 2, self.skill["id"], 0)
        self.answer(messenger, row, 3, self.skill["id"], 3)
        report = collections.report(self.db, row)
        self.assertTrue(report["can_finalize"])
        self.assertEqual([r["categories"][0]["current"] for r in report["reviewers"]], [0, 3])
        self.assertEqual(report["categories"][0]["current"], 1.5)
        self.assertIsNone(latest_feedback_run(self.db, 1))
        final = collections.finalize(self.db, 1, row.id, 1)
        self.db.commit()
        self.db.expire_all()
        self.assertEqual(final["categories"][0]["current"], 1.5)
        self.assertEqual(self.db.scalar(select(GradeAssessmentValue.level)), 1.5)
        self.assertEqual(collections.finalize(self.db, 1, row.id, 1)["id"], final["id"])
        with self.assertRaises(LookupError):
            collections.finalize(self.db, 2, row.id, 1)
        # Editing grade only retains the fractional aggregate and a prior snapshot.
        editable = view(self.db, final["id"])
        changed = correct(self.db, final["id"], 1, dict(request_id=str(uuid4()), expected_token=editable["edit_token"], reason="Grade decision", values=[], current_grade_id=2))
        self.assertEqual(changed["categories"][0]["current"], 1.5)
        self.assertEqual(changed["current_grade_id"], 2)
        self.assertIsNone(history(self.db, final["id"])[0]["previous"]["current_grade_id"])

    def test_busy_reviewer_does_not_block_others_and_missing_is_not_zero(self):
        self.prepare()
        row = self.create()
        self.db.add(ScenarioProgress(employee_id=2, scenario_key="busy", current_step_key="question", waiting_for_response=True, is_completed=False, started_at=utc_now(), updated_at=utc_now()))
        self.db.add(ScenarioTemplate(scenario_key="busy", title="Busy", trigger_mode="manual_only"))
        self.db.add(FlowStepTemplate(flow_key="busy", step_key="question", step_title="Question", response_type="text", default_text="Question"))
        self.db.commit()
        messenger = FakeMessenger()
        asyncio.run(collections.process_pending(messenger, session_factory=self.sessions))
        self.db.expire_all()
        statuses = {r.respondent_employee_id: r.delivery_status for r in self.db.scalars(select(EmployeeFeedbackRecipient))}
        self.assertEqual(statuses, {2: "pending", 3: "sent"})
        self.answer(messenger, row, 3, self.skill["id"], 4)
        self.assertFalse(collections.report(self.db, row)["can_finalize"])
        busy = self.db.scalar(select(ScenarioProgress).where(ScenarioProgress.scenario_key == "busy"))
        busy.waiting_for_response, busy.is_completed = False, True
        self.db.commit()
        asyncio.run(collections.process_pending(messenger, session_factory=self.sessions))
        self.db.expire_all()
        self.answer(messenger, row, 2, self.skill["id"], 5)
        self.assertEqual(collections.report(self.db, row)["categories"][0]["current"], 4)
        self.assertTrue(collections.report(self.db, row)["can_finalize"])

    def test_template_frozen_and_request_replay_checked(self):
        self.prepare()
        data = dict(request_id=str(uuid4()), specialization_id=self.spec["id"], recipient_ids=[2, 3])
        row = collections.create(self.db, 1, 1, data)
        self.assertEqual(collections.create(self.db, 1, 1, data).id, row.id)
        with self.assertRaises(grades.GradeConflictError):
            collections.create(self.db, 1, 1, dict(data, recipient_ids=[2]))
        self.assertEqual(json.loads(row.snapshot_json)["scores"][0]["skillName"], "Interview")
        grades.save_catalog_item(self.db, "skills", {"name": "Renamed skill", "category_id": self.cat["id"]}, item_id=self.skill["id"])
        self.db.flush()
        self.assertEqual(collections.report(self.db, row)["scores"][0]["skillName"], "Interview")
        with self.assertRaises(ValueError):
            collections.finalize(self.db, 1, row.id, 1)

    def test_ambiguous_delivery_is_not_automatically_retried(self):
        self.prepare()
        row = self.create()
        messenger = FakeMessenger()
        from unittest.mock import AsyncMock
        messenger.send_text = AsyncMock(side_effect=RuntimeError("network"))
        asyncio.run(collections.process_pending(messenger, session_factory=self.sessions))
        count = messenger.send_text.await_count
        asyncio.run(collections.process_pending(messenger, session_factory=self.sessions))
        self.assertEqual(messenger.send_text.await_count, count)
        self.db.expire_all()
        statuses = list(self.db.scalars(select(EmployeeFeedbackRecipient.delivery_status).where(EmployeeFeedbackRecipient.run_id == row.feedback_run_id)))
        self.assertEqual(statuses, ["starting", "starting"])

    def test_optional_multiple_actions_and_reminder_only_stage(self):
        self.prepare()
        first = grades.save_review(self.db, 1, 1, self.review_request())
        self.db.commit()
        from app.grades.development import payload
        configured = development_actions.configure(self.db, 1, 1, dict(expected_revision=0, assessment_id=first["id"], anchor_date="2026-11-03", enabled=True,
            actions=dict(ipr6=[dict(key=str(uuid4()), type="review", specialization_id=self.spec["id"], recipient_ids=[2, 3]), dict(key=str(uuid4()), type="review", specialization_id=self.spec["id"], recipient_ids=[2])], ipr12=[], review12=[])))
        self.db.commit()
        self.assertEqual(len(configured["milestones"][0]["actions"]), 2)
        self.assertEqual(len(list(self.db.scalars(select(GradeDevelopmentAction)))), 4)
        self.assertTrue(payload(self.db, 1)["enabled"])
        from app.grades import development
        stage = self.db.scalar(select(development.Milestone).where(development.Milestone.kind == "ipr6"))
        with patch.object(development, "local_now", return_value=datetime(2027, 5, 4)), patch.object(development, "SessionLocal", self.sessions):
            asyncio.run(development._process_one(FakeMessenger(), stage.id))
        self.db.expire_all()
        self.assertEqual(len(collections.list_reports(self.db, 1)), 2)
        next_review = grades.save_review(self.db, 1, 1, self.review_request())
        self.db.commit()
        renewed = payload(self.db, 1)
        self.assertEqual(renewed["assessment_id"], next_review["id"])
        self.assertEqual(len(renewed["milestones"][0]["actions"]), 2)

    def test_uncertain_delivery_reserves_respondent_across_collections(self):
        self.prepare()
        first = self.create()
        second = self.create()
        recipient = self.db.scalar(select(EmployeeFeedbackRecipient).where(
            EmployeeFeedbackRecipient.run_id == first.feedback_run_id,
            EmployeeFeedbackRecipient.respondent_employee_id == 2))
        recipient.delivery_status = "starting"
        self.db.commit()
        asyncio.run(collections.process_pending(FakeMessenger(), session_factory=self.sessions))
        self.db.expire_all()
        pending = self.db.scalar(select(EmployeeFeedbackRecipient).where(
            EmployeeFeedbackRecipient.run_id == second.feedback_run_id,
            EmployeeFeedbackRecipient.respondent_employee_id == 2))
        self.assertEqual(pending.delivery_status, "pending")

    def test_mixed_scenario_feedback_review_stage_claimed_once(self):
        self.prepare()
        subject = self.db.get(Employee, 1)
        set_primary_chat_id(subject, "700001001", db=self.db)
        first = grades.save_review(self.db, 1, 1, self.review_request())
        for key, kind in (("plain", "scenario"), ("feedback", "survey")):
            self.db.add(ScenarioTemplate(scenario_key=key, scenario_kind=kind, title=key, trigger_mode="manual_only", role_scope="all", employee_scope="employees", recipient_mode="self"))
            self.db.add(FlowStepTemplate(flow_key=key, step_key="q", step_title="Question", default_text="Question", response_type="text" if kind == "survey" else "none", target_field="survey_answer" if kind == "survey" else None, send_mode="immediate", is_terminal=True))
        self.db.commit()
        actions = dict(ipr6=[dict(key=str(uuid4()), type="scenario", scenario_key="plain"), dict(key=str(uuid4()), type="feedback", scenario_key="feedback", recipient_ids=[2]), dict(key=str(uuid4()), type="review", specialization_id=self.spec["id"], recipient_ids=[3])], ipr12=[], review12=[])
        development_actions.configure(self.db, 1, 1, dict(expected_revision=0, assessment_id=first["id"], anchor_date="2026-11-03", enabled=True, actions=actions))
        self.db.commit()
        from app.grades import development
        self.assertTrue(development.owns_scenario(self.db, 1, "plain"))
        stage = self.db.scalar(select(development.Milestone).where(development.Milestone.kind == "ipr6"))
        messenger = FakeMessenger()
        with patch.object(development, "local_now", return_value=datetime(2027, 5, 4)), patch.object(development, "SessionLocal", self.sessions):
            asyncio.run(development._process_one(messenger, stage.id))
            asyncio.run(collections.process_pending(messenger, session_factory=self.sessions))
            calls = len(messenger.texts)
            asyncio.run(development._process_one(messenger, stage.id))
            asyncio.run(collections.process_pending(messenger, session_factory=self.sessions))
            self.assertEqual(len(messenger.texts), calls)
        self.db.expire_all()
        self.assertEqual({r.status for r in self.db.scalars(select(GradeDevelopmentAction).where(GradeDevelopmentAction.milestone_id == stage.id))}, {"started"})
