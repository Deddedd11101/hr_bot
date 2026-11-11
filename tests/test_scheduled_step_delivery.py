import asyncio
import tempfile
import unittest
from datetime import UTC, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.messaging.identity import set_primary_chat_id
from app.models import Employee, FlowLaunchRequest, FlowStepTemplate, OnboardingEvent, ScenarioProgress, ScenarioStepDelivery, ScenarioTemplate
from app.scenario_engine import handle_text_response, reset_progress
from app.scheduled_step_delivery import deliver_due_steps, enqueue_step
from app.time_utils import utc_now
from app.scenario_watchdog import progress_health
from tests.test_scheduler_smoke import _FakeMessenger


class ScheduledStepDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_engine("sqlite:///" + str(Path(self.temp.name) / "steps.db"))
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine, autoflush=False)
        self.created = utc_now() - timedelta(minutes=10)
        self.messenger = _FakeMessenger()
        with self.factory() as db:
            for i in (1, 2):
                person = Employee(id=i, full_name=f"Person {i}", employee_stage="staff", created_at=self.created)
                db.add(person)
                db.flush()
                set_primary_chat_id(person, str(700000000 + i), db=db)
            db.add(ScenarioTemplate(scenario_key="timed", title="Timed", trigger_mode="manual_only", role_scope="all",
                employee_scope="employees", recipient_mode="self"))
            db.add_all([FlowStepTemplate(flow_key="timed", step_key="first", step_title="First", default_text="First",
                response_type="none", sort_order=0, send_mode="specific_time", send_time="10:00"),
                FlowStepTemplate(flow_key="timed", step_key="second", step_title="Second", default_text="Second",
                response_type="text", sort_order=1, send_mode="specific_time", send_time="11:00", is_terminal=True)])
            db.commit()

    def tearDown(self):
        self.engine.dispose()
        self.temp.cleanup()

    def enqueue(self, db, person=1):
        for index, key in enumerate(("first", "second")):
            enqueue_step(db, person, "timed", key, (utc_now() - timedelta(minutes=2-index)).replace(tzinfo=UTC),
                True, f"batch:{person}", self.created)
        db.commit()

    def test_restart_without_memory_jobs_continues_each_step_once(self):
        with self.factory() as db:
            self.enqueue(db)
        with self.factory() as db:
            asyncio.run(deliver_due_steps(db, self.messenger))
        with self.factory() as db:
            asyncio.run(deliver_due_steps(db, self.messenger))
            self.assertEqual([r.status for r in db.query(ScenarioStepDelivery).order_by(ScenarioStepDelivery.id)], ["sent", "sent"])
            self.assertTrue(db.query(ScenarioProgress).one().waiting_for_response)
        self.assertEqual([text for _, text in self.messenger.sent_texts], ["First", "Second"])

    def test_busy_chat_does_not_lose_due_steps_or_block_other_person(self):
        with self.factory() as db:
            db.add(ScenarioProgress(employee_id=1, recipient_employee_id=1, scenario_key="busy", current_step_key="q",
                waiting_for_response=True, is_completed=False, started_at=self.created, updated_at=self.created))
            db.commit()
            self.enqueue(db, 1)
            self.enqueue(db, 2)
            asyncio.run(deliver_due_steps(db, self.messenger))
            self.assertEqual({r.status for r in db.query(ScenarioStepDelivery).filter_by(employee_id=1)}, {"pending"})
            old = db.query(ScenarioProgress).filter_by(scenario_key="busy").one()
            old.is_completed, old.waiting_for_response = True, False
            db.commit()
        with self.factory() as db:
            asyncio.run(deliver_due_steps(db, self.messenger))
        self.assertEqual(len(self.messenger.sent_texts), 4)

    def test_uncertain_first_send_is_never_replayed(self):
        class Failing(_FakeMessenger):
            async def send_text(self, **kwargs):
                raise OSError("unknown send result")
        with self.factory() as db:
            self.enqueue(db)
            with self.assertLogs("app.scheduled_step_delivery", level="WARNING"):
                asyncio.run(deliver_due_steps(db, Failing()))
        with self.factory() as db:
            asyncio.run(deliver_due_steps(db, self.messenger))
            self.assertEqual(db.query(ScenarioStepDelivery).filter_by(is_root=True).one().status, "starting")
            self.assertEqual(db.query(ScenarioStepDelivery).filter_by(is_root=False).one().status, "pending")
        self.assertEqual(self.messenger.sent_texts, [])

    def test_old_continuation_cannot_enter_replaced_dialog(self):
        with self.factory() as db:
            self.enqueue(db)
            second = db.query(ScenarioStepDelivery).filter_by(is_root=False).one()
            second.due_at = utc_now() + timedelta(days=1)
            db.commit()
            asyncio.run(deliver_due_steps(db, self.messenger))
            reset_progress(db, 1, "timed")
            db.commit()
            second.due_at = utc_now() - timedelta(seconds=1)
            db.commit()
            asyncio.run(deliver_due_steps(db, self.messenger))
            self.assertEqual(second.status, "cancelled")
        self.assertEqual(len(self.messenger.sent_texts), 1)

    def test_new_root_waits_for_pending_continuation(self):
        with self.factory() as db:
            self.enqueue(db)
            second = db.query(ScenarioStepDelivery).filter_by(is_root=False).one()
            second.due_at = utc_now() + timedelta(days=1)
            db.commit()
            asyncio.run(deliver_due_steps(db, self.messenger))
            new_root = enqueue_step(db, 1, "timed", "first", utc_now().replace(tzinfo=UTC),
                True, "batch:new", self.created)
            db.commit()
            asyncio.run(deliver_due_steps(db, self.messenger))
            self.assertEqual(new_root.status, "pending")
            second.due_at = utc_now() - timedelta(seconds=1)
            db.commit()
            asyncio.run(deliver_due_steps(db, self.messenger))
            self.assertEqual(second.status, "sent")
            self.assertEqual(new_root.status, "pending")
        self.assertEqual([text for _, text in self.messenger.sent_texts], ["First", "Second"])

    def test_waiting_human_is_not_skipped_and_timing_has_one_owner(self):
        with self.factory() as db:
            db.query(FlowStepTemplate).filter_by(step_key="first").one().response_type = "text"
            db.commit()
            self.enqueue(db)
            asyncio.run(deliver_due_steps(db, self.messenger))
            self.assertEqual(len(self.messenger.sent_texts), 1)
            self.assertTrue(asyncio.run(handle_text_response(self.messenger, db, db.get(Employee, 1), SimpleNamespace(text="Answer"))))
            self.assertEqual(db.query(FlowLaunchRequest).count(), 0)
            asyncio.run(deliver_due_steps(db, self.messenger))
            self.assertEqual(len(self.messenger.sent_texts), 2)
            self.assertIn("first", db.query(ScenarioProgress).one().step_history)

    def test_enqueue_is_idempotent_and_keeps_future_due_in_utc(self):
        due = (utc_now() + timedelta(days=2)).replace(tzinfo=UTC)
        with self.factory() as db:
            first = enqueue_step(db, 1, "timed", "first", due, True, "same", self.created)
            second = enqueue_step(db, 1, "timed", "first", due, True, "same", self.created)
            self.assertEqual(first.id, second.id)
            db.commit()
            asyncio.run(deliver_due_steps(db, self.messenger))
            self.assertEqual(first.due_at, due.replace(tzinfo=None))
        self.assertEqual(self.messenger.sent_texts, [])

    def test_catchup_keeps_original_schedule_identity_across_scans(self):
        with self.factory() as db:
            scheduled = self.created.replace(tzinfo=UTC)
            first_scan = scheduled + timedelta(minutes=5)
            first = enqueue_step(db, 1, "timed", "first", first_scan, False, "auto:anchor",
                self.created, scheduled_at=scheduled)
            db.commit()
            second = enqueue_step(db, 1, "timed", "first", first_scan + timedelta(minutes=1),
                False, "auto:anchor", self.created, scheduled_at=scheduled)
            self.assertEqual(first.id, second.id)
            self.assertEqual(second.due_at, first_scan.replace(tzinfo=None))
            self.assertEqual(db.query(ScenarioStepDelivery).count(), 1)

    def test_template_delete_cancels_pending_steps(self):
        from app.web.scenarios import _delete_template_entity
        with self.factory() as db:
            self.enqueue(db)
            _delete_template_entity(db, db.query(ScenarioTemplate).one())
            db.commit()
            asyncio.run(deliver_due_steps(db, self.messenger))
            self.assertEqual({r.status for r in db.query(ScenarioStepDelivery)}, {"cancelled"})
        self.assertEqual(self.messenger.sent_texts, [])

    def test_new_table_is_additive_and_compatibility_is_idempotent(self):
        import app.database as database
        ScenarioStepDelivery.__table__.drop(self.engine)
        with patch.object(database, "engine", self.engine):
            database._ensure_sqlite_schema()
            database._ensure_sqlite_schema()
        with self.factory() as db:
            self.assertEqual(db.query(ScenarioStepDelivery).count(), 0)
            self.assertEqual(db.query(Employee).count(), 2)

    def test_admin_cancel_root_keeps_history_and_cancels_only_its_batch(self):
        from app.web.scenario_queue import cancel_step_delivery
        with self.factory() as db:
            self.enqueue(db)
            root = db.query(ScenarioStepDelivery).filter_by(is_root=True).one()
            user = SimpleNamespace(id=1, role="admin")
            with patch("app.web.scenario_queue.require_api_admin", return_value=user), patch("app.web.scenario_queue.require_api_auth", return_value=user):
                cancel_step_delivery(SimpleNamespace(), 1, root.id, {"expected_at": root.due_at.isoformat()}, db)
            asyncio.run(deliver_due_steps(db, self.messenger))
            self.assertEqual({r.status for r in db.query(ScenarioStepDelivery)}, {"cancelled"})
        self.assertEqual(self.messenger.sent_texts, [])

    def test_cancel_rejects_wrong_card_continuation_and_started_delivery(self):
        from fastapi import HTTPException
        from app.web.scenario_queue import cancel_step_delivery
        with self.factory() as db:
            self.enqueue(db)
            root = db.query(ScenarioStepDelivery).filter_by(is_root=True).one()
            continuation = db.query(ScenarioStepDelivery).filter_by(is_root=False).one()
            user = SimpleNamespace(id=1, role="admin")
            with patch("app.web.scenario_queue.require_api_admin", return_value=user):
                for owner, row in ((2, root), (1, continuation)):
                    with self.assertRaises(HTTPException) as raised:
                        cancel_step_delivery(SimpleNamespace(), owner, row.id, {"expected_at": row.due_at.isoformat()}, db)
                    self.assertEqual(raised.exception.status_code, 409)
                    db.rollback()
                root.status = "starting"
                db.commit()
                with self.assertRaises(HTTPException) as raised:
                    cancel_step_delivery(SimpleNamespace(), 1, root.id, {"expected_at": root.due_at.isoformat()}, db)
                self.assertEqual(raised.exception.status_code, 409)
                db.rollback()
            self.assertEqual(root.status, "starting")

    def test_independent_manual_batches_are_not_collapsed_by_step_name(self):
        with self.factory() as db:
            self.enqueue(db)
            enqueue_step(db, 1, "timed", "first", (utc_now() - timedelta(seconds=10)).replace(tzinfo=UTC),
                True, "later", self.created)
            db.commit()
            asyncio.run(deliver_due_steps(db, self.messenger))
            self.assertEqual(len(self.messenger.sent_texts), 2)
            self.assertTrue(asyncio.run(handle_text_response(self.messenger, db, db.get(Employee, 1), SimpleNamespace(text="Done"))))
            asyncio.run(deliver_due_steps(db, self.messenger))
        self.assertEqual([text for _, text in self.messenger.sent_texts], ["First", "Second", "First"])

    def test_durable_future_step_does_not_create_false_watchdog_alert(self):
        with self.factory() as db:
            self.enqueue(db)
            second = db.query(ScenarioStepDelivery).filter_by(is_root=False).one()
            second.due_at = utc_now() + timedelta(days=2)
            db.commit()
            asyncio.run(deliver_due_steps(db, self.messenger))
            progress = db.query(ScenarioProgress).one()
            progress.updated_at = utc_now() - timedelta(hours=4)
            db.commit()
            self.assertFalse(progress_health(db, progress)["alert_due"])
            self.assertEqual(progress_health(db, progress)["state"], "scheduled")
            progress.last_delivery_error = "Unknown delivery"
            db.commit()
            self.assertTrue(progress_health(db, progress)["alert_due"])

    def test_legacy_pending_followup_with_unattributed_send_is_not_replayed(self):
        from app.scheduler import _queue_step_request
        with self.factory() as db:
            request = FlowLaunchRequest(employee_id=1, flow_key="timed", requested_at=self.created, launch_type="scheduled")
            db.add(request)
            db.add(OnboardingEvent(employee_id=1, event_key="first", scenario_title="Timed", message="Old send",
                scheduled_at=self.created, sent_at=utc_now()))
            db.commit()
            asyncio.run(_queue_step_request(self.messenger, db, db.get(Employee, 1), db.query(ScenarioTemplate).one(),
                db.query(FlowStepTemplate).filter_by(step_key="first").one(), request))
            self.assertIsNotNone(request.processed_at)
            self.assertEqual(db.query(ScenarioStepDelivery).one().status, "starting")
            asyncio.run(deliver_due_steps(db, self.messenger))
        self.assertEqual(self.messenger.sent_texts, [])
