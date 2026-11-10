import asyncio
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.messaging.identity import set_primary_chat_id
from app.models import Employee, EmployeeAdaptationPlanItem, FlowLaunchRequest, FlowStepTemplate, ScenarioProgress, ScenarioTemplate
from app.adaptation_delivery import deliver_plan_request
from app.scenario_engine import ScenarioRecipientBusy, start_scenario
import app.scenario_engine as engine_module
from tests.test_scheduler_smoke import _FakeMessenger


class RecipientAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_engine("sqlite:///" + str(Path(self.temp.name) / "admission.db"),
            connect_args={"check_same_thread": False, "timeout": 5})
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine, autoflush=False)
        with self.factory() as db:
            for i in range(1, 5):
                person = Employee(id=i, full_name=f"Person {i}", employee_stage="staff", created_at=datetime(2026, 1, 1),
                    manager_employee_id=3 if i < 3 else None)
                db.add(person)
                db.flush()
                set_primary_chat_id(person, str(700000000 + i), db=db)
            db.add(ScenarioTemplate(scenario_key="managed", title="Managed", role_scope="all", employee_scope="employees",
                scenario_kind="scenario", recipient_mode="manager", trigger_mode="manual_only"))
            db.add(FlowStepTemplate(flow_key="managed", step_key="question", step_title="Question", default_text="Question",
                sort_order=0, response_type="text", send_mode="immediate"))
            db.commit()

    def tearDown(self):
        self.engine.dispose()
        self.temp.cleanup()

    def test_competing_connections_only_one_can_enter_shared_manager_dialog(self):
        barrier, loser_finished, local = threading.Barrier(2), threading.Event(), threading.local()
        resolve = engine_module.resolve_scenario_recipient
        def synchronize(*args, **kwargs):
            count = getattr(local, "count", 0)
            local.count = count + 1
            result = resolve(*args, **kwargs)
            if count == 0:
                barrier.wait(timeout=5)
            return result
        test = self
        class Messenger(_FakeMessenger):
            async def send_text(self, **kwargs):
                test.assertTrue(loser_finished.wait(timeout=4), "Second connection did not observe durable admission before I/O")
                await super().send_text(**kwargs)
        messenger = Messenger()
        def launch(subject_id):
            with self.factory() as db:
                result = asyncio.run(start_scenario(messenger, db, db.get(Employee, subject_id), "managed"))
                if not result:
                    loser_finished.set()
                return result
        with patch.object(engine_module, "resolve_scenario_recipient", side_effect=synchronize), ThreadPoolExecutor(max_workers=2) as pool:
            first, second = pool.submit(launch, 1), pool.submit(launch, 2)
            results = [first.result(timeout=12), second.result(timeout=12)]
        self.assertCountEqual(results, [True, False])
        self.assertEqual(len(messenger.sent_texts), 1)
        with self.factory() as db:
            progress = db.query(ScenarioProgress).one()
            self.assertEqual(progress.recipient_employee_id, 3)
            self.assertTrue(progress.waiting_for_response)

    def test_busy_is_distinct_for_durable_callers_and_does_not_reset_answers(self):
        messenger = _FakeMessenger()
        with self.factory() as db:
            self.assertTrue(asyncio.run(start_scenario(messenger, db, db.get(Employee, 1), "managed")))
            progress = db.query(ScenarioProgress).one()
            progress.step_history = '["saved-step"]'
            db.commit()
        with self.factory() as db:
            with self.assertRaises(ScenarioRecipientBusy):
                asyncio.run(start_scenario(messenger, db, db.get(Employee, 2), "managed", defer_if_busy=True))
            db.rollback()
            progress = db.query(ScenarioProgress).one()
            self.assertEqual(progress.step_history, '["saved-step"]')
        self.assertEqual(len(messenger.sent_texts), 1)

    def test_uncertain_send_remains_reserved_after_new_session(self):
        class Fail(_FakeMessenger):
            async def send_text(self, **kwargs):
                raise OSError("unknown send result")
        with self.factory() as db:
            with self.assertRaises(OSError):
                asyncio.run(start_scenario(Fail(), db, db.get(Employee, 1), "managed"))
            db.rollback()
        with self.factory() as db:
            messenger = _FakeMessenger()
            self.assertFalse(asyncio.run(start_scenario(messenger, db, db.get(Employee, 2), "managed")))
            progress = db.query(ScenarioProgress).one()
            self.assertIsNotNone(progress.last_delivery_error)
            self.assertFalse(progress.waiting_for_response)
            self.assertEqual(messenger.sent_texts, [])

    def test_changed_manager_before_lock_requires_a_fresh_attempt(self):
        resolve = engine_module.resolve_scenario_recipient
        changed = False
        def change_manager(*args, **kwargs):
            nonlocal changed
            result = resolve(*args, **kwargs)
            if not changed:
                changed = True
                with self.factory() as other:
                    other.get(Employee, 1).manager_employee_id = 4
                    other.commit()
            return result
        messenger = _FakeMessenger()
        with self.factory() as db, patch.object(engine_module, "resolve_scenario_recipient", side_effect=change_manager):
            with self.assertRaises(ScenarioRecipientBusy):
                asyncio.run(start_scenario(messenger, db, db.get(Employee, 1), "managed", defer_if_busy=True))
            db.rollback()
        self.assertEqual(messenger.sent_texts, [])
        with self.factory() as db:
            self.assertTrue(asyncio.run(start_scenario(messenger, db, db.get(Employee, 1), "managed")))
        self.assertEqual(messenger.sent_texts[0][0], "700000004")

    def test_completed_dialog_releases_admission_without_deleting_history(self):
        messenger = _FakeMessenger()
        with self.factory() as db:
            asyncio.run(start_scenario(messenger, db, db.get(Employee, 1), "managed"))
            progress = db.query(ScenarioProgress).one()
            progress.is_completed, progress.waiting_for_response = True, False
            db.commit()
        with self.factory() as db:
            self.assertTrue(asyncio.run(start_scenario(messenger, db, db.get(Employee, 2), "managed")))
            self.assertEqual(db.query(ScenarioProgress).count(), 2)

    def test_adaptation_claim_returns_to_queue_after_admission_race(self):
        with self.factory() as db:
            request = FlowLaunchRequest(employee_id=1, flow_key="managed", requested_at=datetime(2026, 1, 1), launch_type="adaptation_plan")
            db.add(request)
            db.flush()
            item = EmployeeAdaptationPlanItem(employee_id=1, entry_key="organization", flow_key="managed", title="Managed",
                requested_at=datetime(2026, 1, 1), launch_request_id=request.id, calculation_json="{}")
            db.add(item)
            db.commit()
            with patch("app.adaptation_delivery.start_scenario", side_effect=ScenarioRecipientBusy()):
                self.assertTrue(asyncio.run(deliver_plan_request(db, _FakeMessenger(), request)))
            db.refresh(item)
            db.refresh(request)
            self.assertEqual(item.status, "blocked")
            self.assertIsNone(item.started_at)
            self.assertIsNone(request.processed_at)
            self.assertTrue(asyncio.run(deliver_plan_request(db, _FakeMessenger(), request)))
            self.assertEqual(item.status, "in_progress")

    def test_first_delivery_does_not_switch_manager_after_admission_commit(self):
        messenger = _FakeMessenger()
        with self.factory() as db:
            original = db.commit
            changed = False
            def change_after_commit():
                nonlocal changed
                original()
                if not changed:
                    changed = True
                    with self.factory() as other:
                        other.get(Employee, 1).manager_employee_id = 4
                        other.commit()
            with patch.object(db, "commit", side_effect=change_after_commit):
                self.assertTrue(asyncio.run(start_scenario(messenger, db, db.get(Employee, 1), "managed")))
            self.assertEqual(db.query(ScenarioProgress).one().recipient_employee_id, 3)
        self.assertEqual(messenger.sent_texts[0][0], "700000003")
