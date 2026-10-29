"""Isolated SQLite contracts; never opens the application database or sends Telegram."""
import asyncio
import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "ci-dummy-token")
os.environ.setdefault("ADMIN_SESSION_SECRET", "ci-admin-session-secret")
os.environ.setdefault("DATABASE_URL", "sqlite://")

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.grades import development as dev
from app.models import (Employee, FlowLaunchRequest, FlowStepTemplate,
                        GradeAssessment, GradeDevelopmentCycle as Cycle, GradeDevelopmentDelivery as Delivery,
                        GradeDevelopmentMilestone as Milestone, HrSettings, MassScenarioAction, ScenarioTemplate)
from app.web import grades

NOW = datetime(2026, 10, 27, 9)


class GradeDevelopmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix="grade-development-")
        self.engine = create_engine("sqlite:///" + str(Path(self.temp.name) / "isolated.db"),
                                    connect_args={"check_same_thread": False, "timeout": 10})
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine, autoflush=False)
        self.db = self.sessions()
        self.db.add_all([Employee(id=1, full_name="Test Employee", employee_stage="staff", manager_employee_id=2, created_at=NOW),
                         Employee(id=2, full_name="Manager", employee_stage="staff", telegram_user_id="222", created_at=NOW),
                         HrSettings(id=1, telegram_user_id="111", created_at=NOW, updated_at=NOW),
                         GradeAssessment(id=1, employee_id=1, specialization_id=1, assessor_admin_account_id=1,
                             status="final", created_at=NOW, updated_at=NOW, finalized_at=NOW,
                             catalog_snapshot=json.dumps({"id": 1, "status": "final", "import_source": None}))])
        for key in dev.KINDS:
            self.db.add(ScenarioTemplate(scenario_key=key, title=key, trigger_mode="manual_only"))
            self.db.add(FlowStepTemplate(flow_key=key, step_key=key + "-step", step_title="Step", default_text="Hello"))
        self.db.commit()
        self.patches = [patch.object(dev, "SessionLocal", self.sessions),
                        patch.object(dev, "local_now", return_value=NOW),
                        patch.object(dev, "get_primary_chat_id", side_effect=lambda employee, **kw: employee.telegram_user_id),
                        patch.object(dev, "chat_id_allowed", return_value=True),
                        patch.object(dev, "resolve_scenario_recipient", return_value=SimpleNamespace(employee_id=1, chat_id="333", error=None)),
                        patch.object(dev, "get_waiting_progress", return_value=None),
                        patch.object(dev, "get_conflicting_progress_for_survey_launch", return_value=None),
                        patch.object(dev, "start_scenario", new_callable=AsyncMock, return_value=True),
                        patch.object(dev, "as_messenger")]
        self.mocks = [p.start() for p in self.patches]
        self.started = self.mocks[-2]
        self.messenger = SimpleNamespace(send_text=AsyncMock())
        self.mocks[-1].return_value = self.messenger

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.db.close()
        self.engine.dispose()
        self.temp.cleanup()

    def config(self, **extra):
        return dict(expected_revision=0, assessment_id=1, anchor_date="2026-10-27", enabled=True,
                    **{k + "_scenario_key": k for k in dev.KINDS}, **extra)

    def enroll(self):
        result = dev.configure(self.db, 1, self.config())
        self.db.commit()
        return result

    def item(self, kind="ipr6"):
        self.db.expire_all()
        return self.db.scalar(select(Milestone).where(Milestone.kind == kind, Milestone.assessment_id == 1))

    def scan(self):
        self.db.commit()
        with patch.object(dev, "local_now", return_value=datetime(2027, 4, 28, 10)):
            asyncio.run(dev.process_due(object()))
        self.db.expire_all()

    def test_calendar_clamp_and_ten_minute_order(self):
        self.assertEqual(dev.add_months(date(2024, 8, 31), 6), date(2025, 2, 28))
        self.assertEqual(dev.add_months(date(2023, 8, 31), 6), date(2024, 2, 29))
        self.assertEqual(dev.add_months(date(2024, 2, 29), 12), date(2025, 2, 28))
        dates = dev.default_dates(date(2026, 10, 31))
        self.assertEqual(dates["ipr6"], datetime(2027, 4, 30, 10))
        self.assertEqual(dates["review12"] - dates["ipr12"], timedelta(minutes=10))

    def test_manual_ipr_templates_are_not_scheduled_from_adaptation_without_cycle(self):
        from app import scheduler
        employee = self.db.get(Employee, 1)
        employee.first_workday = NOW.date()
        employee.adaptation_midpoint = NOW.date()
        self.db.commit()
        jobs = MagicMock()
        with patch.object(scheduler, "SessionLocal", self.sessions), patch.object(dev, "process_due", new_callable=AsyncMock):
            asyncio.run(scheduler.schedule_all_employees(jobs, object()))
        jobs.add_job.assert_not_called()
        self.started.assert_not_awaited()

    def test_manual_ipr_templates_still_launch_at_six_and_twelve_month_cycle_dates(self):
        self.enroll()
        with patch.object(dev, "local_now", return_value=datetime(2027, 4, 26, 10)):
            asyncio.run(dev.process_due(object()))
        self.started.assert_not_awaited()
        self.scan()
        self.assertEqual([call.args[3] for call in self.started.await_args_list], ["ipr6"])
        with patch.object(dev, "local_now", return_value=datetime(2027, 10, 28, 10)):
            asyncio.run(dev.process_due(object()))
            asyncio.run(dev.process_due(object()))
        self.assertEqual([call.args[3] for call in self.started.await_args_list], list(dev.KINDS))

    def test_get_null_import_source_no_enrollment_and_default_anchor(self):
        result = dev.payload(self.db, 1)
        self.assertEqual(result["assessment_id"], 1)
        self.assertEqual(result["anchor_date"], "2026-10-27")
        self.assertFalse(result["needs_anchor"])
        self.assertEqual(result["milestones"], [])
        self.assertEqual(self.db.query(Cycle).count(), 0)

    def test_import_unknown_requires_explicit_anchor(self):
        assessment = self.db.get(GradeAssessment, 1)
        assessment.catalog_snapshot = json.dumps({"import_source": {"original_review_date": None}})
        self.db.commit()
        self.assertTrue(dev.payload(self.db, 1)["needs_anchor"])
        data = self.config()
        data["anchor_date"] = None
        with self.assertRaises(ValueError):
            dev.configure(self.db, 1, data)
        self.db.rollback()
        self.enroll()
        self.assertFalse(dev.payload(self.db, 1)["needs_anchor"])

    def test_known_import_date_not_import_timestamp(self):
        self.db.get(GradeAssessment, 1).catalog_snapshot = json.dumps({"import_source": {"original_review_date": "2026-10-01"}})
        self.db.commit()
        self.assertEqual(dev.payload(self.db, 1)["anchor_date"], "2026-10-01")

    def test_conflict_and_replay_do_not_duplicate(self):
        self.enroll()
        with self.assertRaises(grades.GradeConflictError):
            dev.configure(self.db, 1, self.config())
        self.db.rollback()
        self.assertEqual(self.db.query(Milestone).count(), 3)

    def test_activation_requires_all_scenarios(self):
        data = self.config()
        data["review12_scenario_key"] = None
        with self.assertRaises(ValueError):
            dev.configure(self.db, 1, data)
        self.db.rollback()
        data["enabled"] = False
        result = dev.configure(self.db, 1, data)
        self.assertFalse(result["enabled"])

    def test_past_due_activation_rejected_future_override_allowed(self):
        data = self.config()
        data["anchor_date"] = "2020-01-31"
        with self.assertRaises(ValueError):
            dev.configure(self.db, 1, data)
        self.db.rollback()
        data["due_dates"] = {"ipr6": "2027-01-01T10:00:00", "ipr12": "2027-02-01T10:00:00", "review12": "2027-02-01T10:10:00"}
        self.assertEqual(len(dev.configure(self.db, 1, data)["milestones"]), 3)

    def test_paused_cycle_neither_sends_nor_launches(self):
        self.enroll()
        data = self.config()
        data.update(expected_revision=1, enabled=False)
        dev.configure(self.db, 1, data)
        self.db.commit()
        self.scan()
        self.started.assert_not_awaited()
        self.messenger.send_text.assert_not_awaited()

    def test_busy_blocks_then_runs_once_without_repeating_reminders(self):
        self.enroll()
        with patch.object(dev, "get_waiting_progress", return_value=object()):
            self.scan()
        self.assertEqual(self.item().status, "blocked")
        self.assertEqual(self.messenger.send_text.await_count, 2)
        self.scan()
        self.scan()
        self.assertEqual(self.item().status, "started")
        self.assertEqual(self.started.await_count, 1)
        self.assertEqual(self.messenger.send_text.await_count, 2)

    def test_uncertain_launch_stays_starting_never_retries(self):
        self.enroll()
        self.started.side_effect = RuntimeError("simulated disconnect")
        self.scan()
        self.scan()
        self.assertEqual(self.item().status, "starting")
        self.assertIn("HR", self.item().last_error)
        self.assertEqual(self.started.await_count, 1)

    def test_failed_reminder_is_separate_and_never_silently_successful(self):
        self.enroll()
        self.messenger.send_text.side_effect = RuntimeError("simulated disconnect")
        self.scan()
        self.scan()
        deliveries = self.db.query(Delivery).all()
        self.assertEqual([d.status for d in deliveries], ["failed", "failed"])
        self.assertTrue(all(d.last_error for d in deliveries))
        self.assertEqual(self.messenger.send_text.await_count, 2)

    def test_pause_during_reminders_prevents_next_claim_and_scenario(self):
        self.enroll()
        async def pause(**kwargs):
            with self.sessions() as other:
                data = self.config()
                data.update(expected_revision=1, enabled=False)
                dev.configure(other, 1, data)
                other.commit()
        self.messenger.send_text.side_effect = pause
        self.scan()
        self.started.assert_not_awaited()
        self.assertEqual(self.messenger.send_text.await_count, 1)
        self.assertFalse(self.db.query(Cycle).one().enabled)

    def test_sent_dates_cannot_move_or_requeue(self):
        self.enroll()
        self.scan()
        data = self.config()
        data.update(expected_revision=1, enabled=False, due_dates={"ipr6": "2028-01-01T10:00:00"})
        with self.assertRaises(ValueError):
            dev.configure(self.db, 1, data)
        self.db.rollback()
        self.assertEqual(self.item().status, "started")

    def test_new_final_renews_existing_only_and_preserves_history(self):
        self.enroll()
        self.scan()
        assessment = GradeAssessment(id=2, employee_id=1, specialization_id=1, assessor_admin_account_id=1,
                                     status="draft", created_at=NOW + timedelta(days=1), updated_at=NOW,
                                     catalog_snapshot=json.dumps({"review_mode": "historical"}))
        self.db.add(assessment)
        self.db.commit()
        with patch.object(grades, "_draft_payload", return_value={"id": 2}), patch.object(grades, "utc_now", return_value=NOW + timedelta(days=1)):
            grades.finalize_assessment(self.db, 2)
        self.db.commit()
        result = dev.payload(self.db, 1)
        self.assertEqual(result["assessment_id"], 2)
        self.assertEqual(result["revision"], 2)
        self.assertEqual(len(result["milestones"]), 3)
        self.assertEqual(len(result["history"]), 3)
        self.assertEqual([item["status"] for item in result["history"]].count("started"), 1)
        grades.finalize_assessment(self.db, 2)
        self.assertEqual(self.db.query(Milestone).count(), 6)

    def test_finalization_does_not_enroll_unconfigured_employee(self):
        dev.renew_after_finalization(self.db, self.db.get(GradeAssessment, 1))
        self.assertEqual(self.db.query(Cycle).count(), 0)

    def test_purge_referenced_assessment_blocked_before_backup(self):
        self.enroll()
        self.db.add(GradeAssessment(id=2, employee_id=1, specialization_id=1, assessor_admin_account_id=1,
                                   status="final", created_at=NOW, updated_at=NOW, finalized_at=NOW))
        self.db.commit()
        with patch.object(grades, "_backup_before_grade_purge") as backup:
            with self.assertRaises(grades.GradeConflictError):
                grades.purge_other_reviews(self.db, 1, {"keep_id": 2, "expected_ids": [1]})
            backup.assert_not_called()

    def test_missing_source_assessment_disables_cycle_without_io(self):
        self.enroll()
        self.db.delete(self.db.get(GradeAssessment, 1))
        self.db.commit()
        self.scan()
        self.assertFalse(self.db.query(Cycle).one().enabled)
        self.started.assert_not_awaited()
        self.messenger.send_text.assert_not_awaited()

    def test_activation_pending_root_conflict_then_can_activate_after_resolution(self):
        request = FlowLaunchRequest(employee_id=1, flow_key="ipr6", launch_type="scheduled", requested_at=NOW)
        self.db.add(request)
        self.db.commit()
        with self.assertRaises(grades.GradeConflictError):
            self.enroll()
        self.db.rollback()
        request.processed_at = NOW
        self.db.commit()
        self.enroll()

    def test_late_pending_conflict_is_visible_and_can_resolve(self):
        self.enroll()
        request = FlowLaunchRequest(employee_id=1, flow_key="ipr6", launch_type="scheduled", requested_at=NOW)
        self.db.add(request)
        self.db.commit()
        self.scan()
        self.assertEqual(self.item().status, "blocked")
        self.assertIn("HR", self.item().last_error)
        request.processed_at = NOW
        self.db.commit()
        self.scan()
        self.assertEqual(self.item().status, "started")

    def test_root_ownership_includes_paused_and_started_but_not_cancelled(self):
        self.enroll()
        self.assertTrue(dev.owns_scenario(self.db, 1, "ipr6"))
        self.item().status = "started"
        self.db.commit()
        self.assertTrue(dev.owns_scenario(self.db, 1, "ipr6"))
        self.item().status = "cancelled"
        self.db.commit()
        self.assertFalse(dev.owns_scenario(self.db, 1, "ipr6"))

    def test_stale_manager_and_hr_snapshot_cancelled_before_claim(self):
        self.enroll()
        item = self.item()
        dev._seed_reminders(self.db, self.db.get(Employee, 1), item)
        self.db.commit()
        self.db.get(Employee, 1).manager_employee_id = None
        self.db.get(HrSettings, 1).telegram_user_id = "999"
        self.db.commit()
        asyncio.run(dev._deliver_reminders(self.db, object(), item))
        # Not due yet: no sending at all, then exercise due membership checks.
        with patch.object(dev, "local_now", return_value=datetime(2027, 4, 28)):
            asyncio.run(dev._deliver_reminders(self.db, object(), item))
        self.assertEqual([d.status for d in self.db.query(Delivery).all()], ["cancelled", "cancelled"])
        self.messenger.send_text.assert_not_awaited()

    def test_numeric_reminder_identity_no_username_fallback(self):
        self.enroll()
        self.db.get(Employee, 2).telegram_user_id = "@manager"
        self.db.get(HrSettings, 1).telegram_user_id = "@hr"
        self.db.commit()
        self.scan()
        self.assertEqual([d.status for d in self.db.query(Delivery).all()], ["failed", "failed"])
        self.messenger.send_text.assert_not_awaited()

    def test_unrelated_far_future_mass_action_does_not_block_cycle(self):
        self.db.add(MassScenarioAction(flow_key="ipr6", scenario_kind="scenario", requested_at=datetime(2035, 1, 1),
            created_at=NOW, target_employee_id=2, launch_type="scheduled"))
        self.db.commit()
        self.enroll()
        self.scan()
        self.assertEqual(self.item().status, "started")
        self.started.assert_awaited_once()

    def test_targeted_mass_action_blocks_activation(self):
        self.db.add(MassScenarioAction(flow_key="ipr6", scenario_kind="scenario", requested_at=datetime(2035, 1, 1),
            created_at=NOW, target_employee_id=1, launch_type="scheduled"))
        self.db.commit()
        with self.assertRaises(grades.GradeConflictError):
            self.enroll()

    def test_scheduler_root_guard_and_followup_request_preserved(self):
        from app import scheduler
        self.enroll()
        root = FlowLaunchRequest(employee_id=1, flow_key="ipr6", launch_type="scheduled", requested_at=NOW)
        followup = FlowLaunchRequest(employee_id=1, flow_key="ipr6", launch_type="manual", requested_at=NOW,
                                    skip_step_key=scheduler.SINGLE_STEP_REQUEST_PREFIX + "ipr6-step")
        self.db.add_all([root, followup])
        self.db.commit()
        with patch.object(scheduler, "SessionLocal", self.sessions), patch.object(scheduler, "send_step", new_callable=AsyncMock) as send:
            asyncio.run(scheduler.run_scheduled_step(object(), 1, "ipr6", "ipr6-step", NOW, explicit=True))
            send.assert_not_awaited()
            with patch.object(scheduler, "_local_now_naive", return_value=NOW + timedelta(minutes=1)):
                asyncio.run(scheduler.schedule_all_employees(MagicMock(), object()))
            send.assert_awaited_once()
        self.db.expire_all()
        self.assertIsNone(self.db.get(FlowLaunchRequest, root.id).processed_at)
        self.assertIsNotNone(self.db.get(FlowLaunchRequest, followup.id).processed_at)
        self.assertIn("HR", self.item().last_error)

    def test_concurrent_scans_claim_only_once(self):
        self.enroll()
        async def start(*args, **kwargs):
            await asyncio.sleep(0)
            return True
        self.started.side_effect = start
        async def scans():
            await asyncio.gather(dev._process_one(object(), self.item().id), dev._process_one(object(), self.item().id))
        with patch.object(dev, "local_now", return_value=datetime(2027, 4, 28)):
            asyncio.run(scans())
        self.assertEqual(self.started.await_count, 1)

    def test_unavailable_staff_rejected_at_configuration(self):
        for stage, blocked in (("candidate", False), (None, False), ("archived", False), ("dismissed", False), ("staff", True)):
            with self.subTest(stage=stage, blocked=blocked):
                employee = self.db.get(Employee, 1)
                employee.employee_stage, employee.is_bot_blocked = stage, blocked
                self.db.commit()
                with self.assertRaises(ValueError):
                    dev.configure(self.db, 1, self.config())
                self.db.rollback()

    def test_ipr_and_adaptation_are_active_working_stages(self):
        for stage in ("ipr", "adaptation"):
            with self.subTest(stage=stage):
                self.db.get(Employee, 1).employee_stage = stage
                self.db.commit()
                self.assertTrue(dev._active_staff(self.db.get(Employee, 1)))
                result = dev.configure(self.db, 1, self.config())
                self.assertTrue(result["enabled"])
                self.db.rollback()
        self.enroll()
        for stage in ("ipr", "adaptation"):
            self.db.get(Employee, 1).employee_stage = stage
            self.db.commit()
            self.scan()
            self.assertTrue(self.db.query(Cycle).one().enabled)
        self.started.assert_awaited_once()

    def test_staff_becomes_unavailable_before_due_no_reminder_or_scenario_io(self):
        self.enroll()
        employee = self.db.get(Employee, 1)
        employee.employee_stage = "candidate"
        self.db.commit()
        self.scan()
        self.assertEqual(self.item().status, "failed")
        self.assertFalse(self.db.query(Cycle).one().enabled)
        self.started.assert_not_awaited()
        self.messenger.send_text.assert_not_awaited()

    def test_blocked_employee_before_due_no_reminder_io(self):
        self.enroll()
        self.db.get(Employee, 1).is_bot_blocked = True
        self.db.commit()
        self.scan()
        self.assertFalse(self.db.query(Cycle).one().enabled)
        self.started.assert_not_awaited()
        self.messenger.send_text.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
