from datetime import datetime, timedelta
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import (Employee, FlowLaunchRequest, ScenarioProgress,
                        ScenarioTemplate, ScenarioAnswerRun, OnboardingEvent)
from app.web.scenario_queue import cancel_request, interrupt_progress, snapshot


class ScenarioQueueTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.now = datetime(2026, 11, 5, 9)
        self.db.add_all([Employee(id=1, full_name="Subject", employee_stage="staff", created_at=self.now),
                         Employee(id=2, full_name="Manager", employee_stage="staff", created_at=self.now),
                         ScenarioTemplate(scenario_key="test_queue", title="Queue", trigger_mode="manual_only")])
        self.db.commit()
        self.auth = patch("app.web.scenario_queue.require_api_auth", return_value=SimpleNamespace(id=1, role="admin"))
        self.admin = patch("app.web.scenario_queue.require_api_admin", return_value=SimpleNamespace(id=1, role="admin"))
        self.auth.start(); self.admin.start()

    def tearDown(self):
        self.auth.stop(); self.admin.stop()
        self.db.close(); self.engine.dispose()

    def progress(self, waiting=True):
        run = ScenarioAnswerRun(employee_id=1, scenario_key="test_queue", scenario_title="Queue", started_at=self.now, status="in_progress")
        self.db.add(run); self.db.flush()
        progress = ScenarioProgress(employee_id=1, recipient_employee_id=2, scenario_key="test_queue",
            started_at=self.now, updated_at=self.now, waiting_for_response=waiting, is_completed=False,
            answer_run_id=run.id, current_step_key="answer", step_history='["intro"]', pending_confirmation_value="yes")
        self.db.add(progress); self.db.commit()
        return progress, run

    def test_interrupt_preserves_answers_history_and_clears_pending(self):
        progress, run = self.progress()
        interrupt_progress(None, 1, progress.id, {"expected_at": self.now.isoformat()}, self.db)
        self.db.refresh(progress); self.db.refresh(run)
        self.assertIsNotNone(progress.interrupted_at)
        self.assertFalse(progress.waiting_for_response)
        self.assertIsNone(progress.pending_confirmation_value)
        self.assertEqual(progress.step_history, '["intro"]')
        self.assertEqual(run.status, "interrupted")
        self.assertEqual(self.db.query(OnboardingEvent).count(), 1)

    def test_stale_or_sending_progress_cannot_be_interrupted(self):
        progress, _ = self.progress(False)
        with self.assertRaises(HTTPException) as error:
            interrupt_progress(None, 1, progress.id, {"expected_at": self.now.isoformat()}, self.db)
        self.assertEqual(error.exception.status_code, 409)
        progress.waiting_for_response = True; self.db.commit()
        with self.assertRaises(HTTPException):
            interrupt_progress(None, 1, progress.id, {"expected_at": (self.now - timedelta(seconds=1)).isoformat()}, self.db)
        self.assertIsNone(progress.interrupted_at)

    def test_scope_and_admin_guards(self):
        progress, _ = self.progress()
        self.db.add(Employee(id=3, full_name="Other", created_at=self.now)); self.db.commit()
        with self.assertRaises(HTTPException):
            interrupt_progress(None, 3, progress.id, {"expected_at": self.now.isoformat()}, self.db)
        with patch("app.web.scenario_queue.require_api_admin", side_effect=HTTPException(403)):
            with self.assertRaises(HTTPException):
                interrupt_progress(None, 1, progress.id, {"expected_at": self.now.isoformat()}, self.db)
        self.assertIsNone(progress.interrupted_at)

    def test_cancel_is_guarded_and_preserves_future_request(self):
        rows = [FlowLaunchRequest(employee_id=1, flow_key="test_queue", requested_at=self.now + timedelta(days=i), launch_type="scheduled") for i in (0, 1)]
        self.db.add_all(rows); self.db.commit()
        cancel_request(None, 1, rows[0].id, {"expected_at": self.now.isoformat()}, self.db)
        self.db.refresh(rows[0]); self.db.refresh(rows[1])
        self.assertIsNotNone(rows[0].processed_at)
        self.assertIsNone(rows[1].processed_at)
        with self.assertRaises(HTTPException):
            cancel_request(None, 1, rows[0].id, {"expected_at": self.now.isoformat()}, self.db)

    def test_manager_sees_subject_dialog_without_private_answers(self):
        progress, _ = self.progress()
        data = snapshot(self.db, 2)
        self.assertEqual(data["active"][0]["id"], progress.id)
        self.assertNotIn("pending_confirmation_value", data["active"][0])

    def test_interrupted_dialog_cannot_send_until_explicit_reset(self):
        import asyncio
        from unittest.mock import AsyncMock
        from app.scenario_engine import reset_progress, send_step
        progress, _ = self.progress()
        interrupt_progress(None, 1, progress.id, {"expected_at": self.now.isoformat()}, self.db)
        messenger = AsyncMock()
        with patch("app.scenario_engine.as_messenger", return_value=messenger):
            sent = asyncio.run(send_step(messenger, self.db, self.db.get(Employee, 1),
                self.db.query(ScenarioTemplate).first(), SimpleNamespace()))
        self.assertFalse(sent)
        self.assertEqual(messenger.mock_calls, [])
        progress = reset_progress(self.db, 1, "test_queue")
        self.assertIsNone(progress.interrupted_at)

    def test_legacy_schema_patch_is_additive_and_repeatable(self):
        from sqlalchemy import text
        from app import database
        progress, _ = self.progress()
        progress_id = progress.id
        self.db.close()
        with self.engine.begin() as connection:
            connection.execute(text("ALTER TABLE scenario_progress DROP COLUMN interrupted_at"))
        with patch.object(database, "engine", self.engine), patch.object(database.settings, "DATABASE_URL", "sqlite://"):
            database._ensure_sqlite_schema()
            database._ensure_sqlite_schema()
        with self.engine.connect() as connection:
            row = connection.execute(text("SELECT waiting_for_response, interrupted_at FROM scenario_progress WHERE id=:id"), {"id": progress_id}).one()
        self.assertEqual(tuple(row), (1, None))


if __name__ == "__main__":
    unittest.main()
