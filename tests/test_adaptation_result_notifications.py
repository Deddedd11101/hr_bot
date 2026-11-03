from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.messaging.identity import set_primary_chat_id
from app.models import Employee, EmployeeAdaptationPlanItem, EmployeeDocumentLink, EmployeeFile, FlowLaunchRequest, FlowStepTemplate, ScenarioTemplate, StepSendNotification
from app.scenario_engine import ADAPTATION_RESULT_SLOTS, handle_file_response, handle_text_response, start_scenario
from app.scheduler import schedule_all_employees
from tests.test_scenario_engine_smoke import FakeMessenger


class AdaptationResultTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.subject = Employee(full_name="Subject", employee_stage="staff", created_at=datetime(2026, 1, 1))
        self.manager = Employee(full_name="Manager", employee_stage="staff", created_at=datetime(2026, 1, 1))
        self.db.add_all([self.subject, self.manager])
        self.db.flush()
        self.subject.manager_employee_id = self.manager.id
        set_primary_chat_id(self.subject, "700001001", db=self.db)
        set_primary_chat_id(self.manager, "700001002", db=self.db)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def scenario(self, slot):
        self.db.add(ScenarioTemplate(scenario_key=slot, title="Result", role_scope="all", employee_scope="employees", recipient_mode="self", trigger_mode="manual_only"))
        upload = FlowStepTemplate(flow_key=slot, step_key="upload", step_title="Result", sort_order=0, default_text="Send result", response_type="file", target_field=slot, send_mode="immediate")
        done = FlowStepTemplate(flow_key=slot, step_key="done", step_title="Done", sort_order=1, default_text="Result saved", response_type="none", send_mode="immediate", is_terminal=True)
        self.db.add_all([upload, done])
        self.db.flush()
        self.db.add(StepSendNotification(flow_key=slot, step_id=done.id, recipient_scope="manager", message_text="Employee {employee_full_name} completed test: {" + slot + "}"))
        self.db.commit()

    async def test_link_results_are_separate_and_reach_reviewer_after_submission(self):
        messenger = FakeMessenger()
        for index, slot in enumerate(ADAPTATION_RESULT_SLOTS):
            with self.subTest(slot=slot):
                self.scenario(slot)
                self.assertTrue(await start_scenario(messenger, self.db, self.subject, slot))
                count = len(messenger.texts)
                self.assertTrue(await handle_text_response(messenger, self.db, self.subject, SimpleNamespace(text="Ready")))
                self.assertNotIn("700001002", [row["chat_id"] for row in messenger.texts[count:]])
                url = f"https://example.org/result/{index}"
                self.assertTrue(await handle_text_response(messenger, self.db, self.subject, SimpleNamespace(text=url)))
                self.assertIn(url, messenger.texts[-1]["text"])
                self.assertEqual(messenger.texts[-1]["chat_id"], "700001002")
                self.assertEqual(self.db.query(EmployeeDocumentLink).filter_by(employee_id=self.subject.id, slot_key=slot).one().url, url)
        self.assertEqual(self.db.query(EmployeeDocumentLink).filter_by(employee_id=self.subject.id).count(), 3)

    async def test_file_attaches_to_reviewer_not_other_employee_or_candidate_slot(self):
        slot = "adaptation_practice_result"
        self.scenario(slot)
        messenger = FakeMessenger()
        with TemporaryDirectory() as temp:
            path = Path(temp) / "result.pdf"
            path.write_bytes(b"result")
            row = EmployeeFile(employee_id=self.subject.id, stored_path=str(path), original_filename="result.pdf", category="candidate_file", direction="incoming", created_at=datetime(2026, 1, 1))
            self.db.add(row)
            self.db.commit()
            await start_scenario(messenger, self.db, self.subject, slot)
            self.assertEqual(messenger.documents, [])
            self.assertTrue(await handle_file_response(messenger, self.db, self.subject, row))
            self.assertEqual(row.category, slot)
            self.assertEqual(messenger.documents[-1]["chat_id"], "700001002")
            self.assertEqual(messenger.documents[-1]["filename"], "result.pdf")
            self.assertIsNone(self.db.query(EmployeeDocumentLink).filter_by(slot_key="test_task_result").first())

    async def test_paused_grade_conflict_is_visible_and_does_not_consume_plan_request(self):
        request = FlowLaunchRequest(employee_id=self.subject.id, flow_key="pulse", requested_at=datetime(2020, 1, 1), launch_type="adaptation_plan")
        self.db.add(request)
        self.db.flush()
        item = EmployeeAdaptationPlanItem(employee_id=self.subject.id, entry_key="pulse1", flow_key="pulse", title="Pulse", status="planned", requested_at=request.requested_at, launch_request_id=request.id, calculation_json="{}")
        self.db.add(item)
        self.db.commit()
        item_id, request_id = item.id, request.id
        with patch("app.scheduler.SessionLocal", return_value=self.db), patch("app.scheduler._load_all_employees", return_value=[]), patch("app.scheduler._load_scenarios", return_value=[]), patch("app.scheduler.grade_owns_scenario", return_value=True), patch("app.scheduler.grade_launch_conflict"), patch("app.grades.development.process_due", new_callable=AsyncMock):
            await schedule_all_employees(None, None)
        self.assertEqual(self.db.get(EmployeeAdaptationPlanItem, item_id).status, "blocked")
        self.assertIn("Грейд", self.db.get(EmployeeAdaptationPlanItem, item_id).last_error)
        self.assertIsNone(self.db.get(FlowLaunchRequest, request_id).processed_at)
