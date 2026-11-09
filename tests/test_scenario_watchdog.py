import unittest
from datetime import datetime, timedelta, UTC
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Employee, ScenarioProgress, ScenarioTemplate, FlowLaunchRequest
from app.scenario_watchdog import check_runtime, progress_health


class WatchdogTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.now = datetime(2026, 11, 9, 12)
        self.db.add_all([Employee(id=1, full_name="Person", created_at=self.now),
            ScenarioTemplate(scenario_key="watch", title="Scenario")])
        self.progress = ScenarioProgress(employee_id=1, scenario_key="watch", started_at=self.now - timedelta(days=1),
            updated_at=self.now - timedelta(hours=4), waiting_for_response=False, is_completed=False,
            step_history="preserved", response_undo_history="preserved")
        self.db.add(self.progress)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def health(self):
        return progress_health(self.db, self.progress, now=self.now)

    async def test_waiting_for_human_never_expires_or_alerts(self):
        self.progress.waiting_for_response = True
        self.progress.updated_at = self.now - timedelta(days=30)
        self.db.commit()
        self.assertEqual(self.health()["state"], "waiting_human")
        with patch("app.scenario_watchdog.utc_now", return_value=self.now), patch("app.scenario_watchdog.notify_hr", new_callable=AsyncMock) as notify:
            await check_runtime(self.db, object())
            notify.assert_not_awaited()
        self.assertFalse(self.progress.is_completed)

    async def test_future_continuation_is_not_a_stall(self):
        self.db.add(FlowLaunchRequest(employee_id=1, flow_key="watch", launch_type="scheduled",
            requested_at=self.now + timedelta(days=1), skip_step_key="step:next"))
        self.db.commit()
        self.assertEqual(self.health()["state"], "scheduled")
        self.assertFalse(self.health()["alert_due"])

    async def test_uncertain_delivery_alerts_once_without_changing_runtime(self):
        self.progress.last_delivery_error = "private failure details"
        self.db.commit()
        before = (self.progress.updated_at, self.progress.step_history, self.progress.response_undo_history)
        self.assertEqual(self.health()["state"], "delivery_uncertain")
        with patch("app.scenario_watchdog.utc_now", return_value=self.now), patch("app.scenario_watchdog.notify_hr", new_callable=AsyncMock) as notify:
            await check_runtime(self.db, object())
            await check_runtime(self.db, object())
            notify.assert_awaited_once()
            self.assertNotIn("private failure", notify.call_args.args[1])
        self.db.refresh(self.progress)
        self.assertEqual(before, (self.progress.updated_at, self.progress.step_history, self.progress.response_undo_history))
        self.assertFalse(self.progress.is_completed)
        self.assertIsNone(self.progress.interrupted_at)
        self.assertEqual(self.db.query(FlowLaunchRequest).count(), 0)

    async def test_future_scheduler_job_suppresses_alert(self):
        scheduler = SimpleNamespace(get_jobs=lambda: [SimpleNamespace(args=(None, 1, "watch"),
            next_run_time=(self.now + timedelta(days=1)).replace(tzinfo=UTC))])
        with patch("app.scenario_watchdog.utc_now", return_value=self.now), patch("app.scenario_watchdog.notify_hr", new_callable=AsyncMock) as notify:
            await check_runtime(self.db, object(), scheduler)
            notify.assert_not_awaited()

    async def test_recent_or_closed_does_not_alert(self):
        self.progress.updated_at = self.now - timedelta(minutes=2)
        self.assertEqual(self.health()["state"], "processing")
        self.progress.is_completed = True
        self.assertEqual(self.health()["state"], "closed")

    async def test_alert_failure_is_not_replayed_automatically(self):
        with patch("app.scenario_watchdog.utc_now", return_value=self.now), patch("app.scenario_watchdog.notify_hr", new_callable=AsyncMock, side_effect=RuntimeError("network")) as notify:
            await check_runtime(self.db, object())
            await check_runtime(self.db, object())
            notify.assert_awaited_once()

    async def test_digest_escapes_titles_and_fits_telegram_limit(self):
        self.db.query(ScenarioTemplate).one().title = "<b>&" * 50
        for _ in range(25):
            self.db.add(ScenarioProgress(employee_id=1, scenario_key="watch", started_at=self.progress.started_at,
                updated_at=self.progress.updated_at, waiting_for_response=False, is_completed=False))
        self.db.commit()
        with patch("app.scenario_watchdog.utc_now", return_value=self.now), patch("app.scenario_watchdog.notify_hr", new_callable=AsyncMock) as notify:
            await check_runtime(self.db, object())
            message = notify.call_args.args[1]
            self.assertLess(len(message), 4096)
            self.assertNotIn("<b>", message)
            self.assertIn("&lt;b&gt;", message)
            self.assertIn("Ещё записей", message)

    async def test_schema_patch_is_repeatable_and_preserves_state(self):
        self.db.close()
        with self.engine.begin() as conn:
            conn.execute(text("ALTER TABLE scenario_progress DROP COLUMN watchdog_alert_key"))
        from app import database
        with patch.object(database, "engine", self.engine):
            database._ensure_sqlite_schema()
            database._ensure_sqlite_schema()
        self.db = Session(self.engine)
        row = self.db.query(ScenarioProgress).one()
        self.assertIsNone(row.watchdog_alert_key)
        self.assertEqual(row.step_history, "preserved")
