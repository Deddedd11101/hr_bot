import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.mass_scenario_delivery import delete_unstarted_action, deliver_mass_action, delivery_counts
from app.messaging.identity import set_primary_chat_id
from app.models import (Employee, FlowStepTemplate, MassScenarioAction, MassScenarioRecipient,
                        ScenarioProgress, ScenarioTemplate)
from tests.test_scheduler_smoke import _FakeMessenger


class MassScenarioDeliveryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_engine("sqlite:///" + str(Path(self.temp.name) / "queue.db"))
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine, autoflush=False)
        self.messenger = _FakeMessenger()
        with self.factory() as db:
            people = [Employee(full_name=f"Employee {i}", employee_stage="adaptation", created_at=datetime(2026, 1, 1)) for i in (1, 2)]
            db.add_all(people)
            db.flush()
            for person in people:
                set_primary_chat_id(person, str(700000000 + person.id), db=db)
            self.ids = [person.id for person in people]
            db.add(ScenarioTemplate(scenario_key="queued", title="Queued", role_scope="all",
                employee_scope="employees", scenario_kind="scenario", trigger_mode="manual_only", recipient_mode="self"))
            db.add(FlowStepTemplate(flow_key="queued", step_key="question", step_title="Question",
                default_text="Question", response_type="text", sort_order=0, send_mode="immediate"))
            action = MassScenarioAction(flow_key="queued", scenario_kind="scenario", launch_type="scheduled",
                requested_at=datetime(2026, 1, 1), created_at=datetime(2026, 1, 1))
            db.add(action)
            db.commit()
            self.action_id = action.id

    def tearDown(self):
        self.engine.dispose()
        self.temp.cleanup()

    def busy(self, db, employee_id):
        db.add(ScenarioProgress(employee_id=employee_id, recipient_employee_id=employee_id,
            scenario_key="other", current_step_key="waiting", waiting_for_response=True,
            is_completed=False, started_at=datetime(2026, 1, 1), updated_at=datetime(2026, 1, 1)))
        db.commit()

    async def test_busy_recipient_waits_and_started_recipient_is_not_replayed(self):
        with self.factory() as db:
            self.busy(db, self.ids[0])
            await deliver_mass_action(db, self.messenger, self.action_id, self.ids)
            self.assertEqual(delivery_counts(db, self.action_id), {"pending": 1, "started": 1})
            self.assertIsNone(db.get(MassScenarioAction, self.action_id).processed_at)
        # Simulate the next scheduler pass/restart using a new session.
        with self.factory() as db:
            await deliver_mass_action(db, self.messenger, self.action_id, self.ids)
            self.assertEqual(len(self.messenger.sent_texts), 1)
            progress = db.query(ScenarioProgress).filter_by(scenario_key="other").one()
            progress.is_completed, progress.waiting_for_response = True, False
            db.commit()
            await deliver_mass_action(db, self.messenger, self.action_id, self.ids)
            self.assertEqual(delivery_counts(db, self.action_id), {"started": 2})
            self.assertIsNotNone(db.get(MassScenarioAction, self.action_id).processed_at)
            await deliver_mass_action(db, self.messenger, self.action_id, self.ids)
        self.assertEqual(len(self.messenger.sent_texts), 2)

    async def test_snapshot_does_not_change_with_later_audience_filter(self):
        with self.factory() as db:
            self.busy(db, self.ids[0])
            await deliver_mass_action(db, self.messenger, self.action_id, [self.ids[0]])
            await deliver_mass_action(db, self.messenger, self.action_id, self.ids)
            self.assertEqual(db.query(MassScenarioRecipient).count(), 1)
            self.assertEqual(self.messenger.sent_texts, [])

    async def test_future_grade_configuration_does_not_reserve_mass_dialog(self):
        with patch("app.grades.development.owns_scenario", return_value=True):
            with self.factory() as db:
                await deliver_mass_action(db, self.messenger, self.action_id, [self.ids[0]])
                self.assertEqual(delivery_counts(db, self.action_id), {"started": 1})

    async def test_shared_manager_only_receives_one_interactive_dialog(self):
        with self.factory() as db:
            manager = Employee(full_name="Manager", employee_stage="staff", created_at=datetime(2026, 1, 1))
            db.add(manager)
            db.flush()
            set_primary_chat_id(manager, "799999999", db=db)
            for person in db.query(Employee).filter(Employee.id.in_(self.ids)):
                person.manager_employee_id = manager.id
            db.query(ScenarioTemplate).filter_by(scenario_key="queued").one().recipient_mode = "manager"
            db.commit()
            await deliver_mass_action(db, self.messenger, self.action_id, self.ids)
            self.assertEqual(delivery_counts(db, self.action_id), {"started": 1, "pending": 1})
            self.assertEqual(self.messenger.sent_texts[0][0], "799999999")

    async def test_concurrent_scan_does_not_reclaim_same_recipient(self):
        original = self.messenger.send_text
        entered = False
        async def reenter(**kwargs):
            nonlocal entered
            if not entered:
                entered = True
                with self.factory() as second:
                    await deliver_mass_action(second, self.messenger, self.action_id, self.ids)
            await original(**kwargs)
        with patch.object(self.messenger, "send_text", side_effect=reenter):
            with self.factory() as db:
                await deliver_mass_action(db, self.messenger, self.action_id, self.ids)
                self.assertEqual(delivery_counts(db, self.action_id), {"started": 2})
        self.assertEqual(len(self.messenger.sent_texts), 2)

    async def test_ambiguous_delivery_is_not_replayed_and_other_recipient_proceeds(self):
        original = self.messenger.send_text
        async def fail_one(chat_id, **kwargs):
            if chat_id == str(700000000 + self.ids[0]):
                raise OSError("ambiguous send")
            return await original(chat_id, **kwargs)
        with patch.object(self.messenger, "send_text", side_effect=fail_one):
            with self.factory() as db, self.assertLogs("app.mass_scenario_delivery", level="WARNING"):
                await deliver_mass_action(db, self.messenger, self.action_id, self.ids)
        with self.factory() as db:
            await deliver_mass_action(db, self.messenger, self.action_id, self.ids)
            self.assertEqual(delivery_counts(db, self.action_id), {"starting": 1, "started": 1})
            self.assertIsNone(db.get(MassScenarioAction, self.action_id).processed_at)
        self.assertEqual(len(self.messenger.sent_texts), 1)

    async def test_survey_progress_keeps_launch_id(self):
        with self.factory() as db:
            db.get(MassScenarioAction, self.action_id).scenario_kind = "survey"
            db.query(ScenarioTemplate).filter_by(scenario_key="queued").one().scenario_kind = "survey"
            db.commit()
            await deliver_mass_action(db, self.messenger, self.action_id, [self.ids[0]])
            progress = db.query(ScenarioProgress).one()
            self.assertEqual(progress.survey_launch_id, self.action_id)
            self.assertTrue(progress.waiting_for_response)

    async def test_delete_unstarted_snapshot_and_refuse_partial_delivery(self):
        with self.factory() as db:
            self.busy(db, self.ids[0])
            await deliver_mass_action(db, self.messenger, self.action_id, [self.ids[0]])
            delete_unstarted_action(db, self.action_id)
            db.commit()
            self.assertEqual(db.query(MassScenarioRecipient).count(), 0)
            self.assertIsNone(db.get(MassScenarioAction, self.action_id))

    async def test_cannot_delete_partially_started_action(self):
        with self.factory() as db:
            self.busy(db, self.ids[0])
            await deliver_mass_action(db, self.messenger, self.action_id, self.ids)
            with self.assertRaises(ValueError):
                delete_unstarted_action(db, self.action_id)
            db.rollback()
            self.assertEqual(delivery_counts(db, self.action_id), {"pending": 1, "started": 1})

    async def test_cancel_after_snapshot_commit_wins_before_delivery_claim(self):
        with self.factory() as db:
            original_commit = db.commit
            cancelled = False
            def cancel_on_first_commit():
                nonlocal cancelled
                original_commit()
                if not cancelled:
                    cancelled = True
                    with self.factory() as other:
                        delete_unstarted_action(other, self.action_id)
                        other.commit()
            with patch.object(db, "commit", side_effect=cancel_on_first_commit):
                await deliver_mass_action(db, self.messenger, self.action_id, self.ids)
        self.assertEqual(self.messenger.sent_texts, [])

    async def test_unavailable_subject_fails_without_sending(self):
        with self.factory() as db:
            db.get(Employee, self.ids[0]).is_bot_blocked = True
            db.commit()
            await deliver_mass_action(db, self.messenger, self.action_id, [self.ids[0]])
            self.assertEqual(delivery_counts(db, self.action_id), {"failed": 1})
            self.assertIsNotNone(db.get(MassScenarioAction, self.action_id).processed_at)
        self.assertEqual(self.messenger.sent_texts, [])

    def test_schema_patch_leaves_old_actions_legacy(self):
        import app.database as database
        with self.engine.begin() as conn:
            conn.execute(text("ALTER TABLE mass_scenario_actions DROP COLUMN recipient_queue_enabled"))
        with patch.object(database, "engine", self.engine):
            database._ensure_sqlite_schema()
        with self.factory() as db:
            self.assertFalse(db.get(MassScenarioAction, self.action_id).recipient_queue_enabled)
            new = MassScenarioAction(flow_key="queued", requested_at=datetime(2026, 1, 1), created_at=datetime(2026, 1, 1))
            db.add(new)
            db.commit()
            self.assertTrue(new.recipient_queue_enabled)
