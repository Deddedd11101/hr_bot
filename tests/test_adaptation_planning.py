import json
import unittest
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.adaptation_planning import CalendarDates, build_preview, default_entries, validate_entries
from app.adaptation_delivery import deliver_plan_request
from app.database import Base
from app.models import AdaptationPlanTemplate, Employee, EmployeeAdaptationPlanItem, FlowLaunchRequest, ProductionCalendarVersion, ProductionCalendarYear, ScenarioProgress, ScenarioTemplate
from app.web.adaptation_plan_routes import apply_plan, edit_item


class AdaptationPlanTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.employee = Employee(full_name="Plan test", created_at=datetime(2091, 1, 1), employee_stage="adaptation", desired_position="project_manager", first_workday=date(2092, 1, 7), adaptation_end=date(2092, 4, 1))
        self.db.add(self.employee)
        days = []
        day = date(2092, 1, 1)
        while day.year == 2092:
            days.append({"date": day.isoformat(), "is_workday": day.weekday() < 5})
            day += timedelta(days=1)
        version = ProductionCalendarVersion(year=2092, digest="a" * 64, days_json=json.dumps(days), source_name="test", created_at=datetime(2091, 1, 1), created_by="test")
        self.db.add(version)
        self.db.flush()
        self.db.add(ProductionCalendarYear(year=2092, current_version_id=version.id))
        for key in {entry["scenario_key"] for entry in default_entries()}:
            self.db.add(ScenarioTemplate(scenario_key=key, title=key, scenario_kind="scenario", purpose="adaptation", trigger_mode="manual_only", role_scope="all", employee_scope="all"))
        self.db.commit()
        self.auth = patch("app.web.adaptation_plan_routes.require_api_auth")
        self.auth.start()

    def tearDown(self):
        self.auth.stop()
        self.db.close()
        self.engine.dispose()

    def test_preview_read_only_repeated_pulse_and_spacing(self):
        preview = build_preview(self.db, self.employee)
        self.assertEqual(self.db.query(AdaptationPlanTemplate).count(), 0)
        self.assertEqual(self.db.query(FlowLaunchRequest).count(), 0)
        rows = {row["key"]: row for row in preview["rows"]}
        self.assertFalse(rows["organization"]["error"])
        self.assertTrue(rows["organization"]["proposed_at"].endswith("10:00"))
        self.assertTrue(rows["first_day"]["proposed_at"].endswith("10:10"))
        self.assertNotEqual(rows["pulse1"]["proposed_at"], rows["pulse2"]["proposed_at"])
        self.assertEqual(len(preview["rows"]), 9)

    def test_calendar_missing_year_and_workday_offsets(self):
        calendar = CalendarDates(self.db)
        self.assertEqual(calendar.shift(date(2092, 1, 7), 5, "workday"), date(2092, 1, 14))
        with self.assertRaisesRegex(ValueError, "2093"):
            calendar.shift(date(2092, 12, 31), 5, "workday")

    def test_apply_rejects_duplicates_stale_and_keeps_manual_date(self):
        preview = build_preview(self.db, self.employee)
        row = preview["rows"][0]
        value = "2092-01-08T11:20"
        payload = {"fingerprint": preview["fingerprint"], "rules_confirmed": True, "rows": [{"key": row["key"], "requested_at": value}]}
        apply_plan(None, self.employee.id, payload, self.db)
        self.assertEqual(self.db.query(FlowLaunchRequest).count(), 1)
        item = self.db.query(EmployeeAdaptationPlanItem).one()
        self.assertTrue(item.manual_date)
        with self.assertRaises(HTTPException) as caught:
            apply_plan(None, self.employee.id, payload, self.db)
        self.assertEqual(caught.exception.status_code, 409)
        self.db.rollback()
        self.assertEqual(build_preview(self.db, self.employee)["rows"][0]["requested_at"], value)
        edit_item(None, self.employee.id, item.id, {"expected_at": value, "requested_at": "2092-01-09T10:00"}, self.db)
        self.assertEqual(self.db.query(FlowLaunchRequest).count(), 1)

    def test_cycles_rejected_and_removed_entries_retained(self):
        entries = default_entries()
        entries[0]["anchor"] = entries[1]["key"]
        entries[1]["anchor"] = entries[0]["key"]
        with self.assertRaises(ValueError):
            validate_entries(self.db, entries)
        self.db.add(EmployeeAdaptationPlanItem(employee_id=self.employee.id, entry_key="removed", flow_key="old", title="Old", requested_at=datetime(2092, 1, 8), status="completed", calculation_json="{}"))
        self.db.commit()
        self.assertEqual(build_preview(self.db, self.employee)["rows"][-1]["key"], "removed")

    async def test_waiting_recipient_defers_without_consuming_then_claims_once(self):
        preview = build_preview(self.db, self.employee)
        apply_plan(None, self.employee.id, {"fingerprint": preview["fingerprint"], "rules_confirmed": True, "rows": [{"key": "organization", "requested_at": "2092-01-08T10:00"}]}, self.db)
        request = self.db.query(FlowLaunchRequest).one()
        item = self.db.query(EmployeeAdaptationPlanItem).one()
        from app.scenario_engine import ScenarioRecipientResolution
        recipient = ScenarioRecipientResolution("self", self.employee.id, "123", "Test")
        with patch("app.adaptation_delivery.resolve_scenario_recipient", return_value=recipient), patch("app.adaptation_delivery.get_waiting_progress", return_value=object()):
            self.assertTrue(await deliver_plan_request(self.db, None, request))
        self.assertEqual(item.status, "blocked")
        self.assertIsNone(request.processed_at)
        with patch("app.adaptation_delivery.resolve_scenario_recipient", return_value=recipient), patch("app.adaptation_delivery.get_waiting_progress", return_value=None), patch("app.adaptation_delivery.start_scenario", new_callable=AsyncMock, return_value=True) as start:
            await deliver_plan_request(self.db, None, request)
            await deliver_plan_request(self.db, None, request)
            self.assertEqual(start.await_count, 1)
        self.assertEqual(item.status, "in_progress")

    def test_completion_keeps_independent_plan_history(self):
        from app.scenario_engine import _complete_feedback_recipient, reset_progress
        item = EmployeeAdaptationPlanItem(employee_id=self.employee.id, entry_key="pulse1", flow_key="test", title="Pulse", requested_at=datetime(2092, 1, 8), status="in_progress", calculation_json="{}")
        self.db.add(item)
        self.db.flush()
        progress = ScenarioProgress(employee_id=self.employee.id, scenario_key="test", adaptation_plan_item_id=item.id, is_completed=True, started_at=datetime(2091, 1, 1), updated_at=datetime(2091, 1, 1))
        self.db.add(progress)
        self.db.flush()
        _complete_feedback_recipient(self.db, progress)
        reset_progress(self.db, self.employee.id, "test")
        self.assertEqual(item.status, "completed")
        self.assertIsNone(progress.adaptation_plan_item_id)

    def test_template_revision_prevents_lost_reorder(self):
        from app.web.adaptation_plan_routes import save_template
        entries = default_entries()
        entries[0], entries[1] = entries[1], entries[0]
        saved = save_template(None, {"revision": 0, "entries": entries}, self.db)
        self.assertEqual(saved["revision"], 1)
        self.assertEqual(build_preview(self.db, self.employee)["rows"][0]["key"], "first_day")
        with self.assertRaises(HTTPException) as caught:
            save_template(None, {"revision": 0, "entries": default_entries()}, self.db)
        self.assertEqual(caught.exception.status_code, 409)

    async def test_orphan_queue_never_falls_back_to_legacy_delivery(self):
        request = FlowLaunchRequest(employee_id=self.employee.id, flow_key="missing", launch_type="adaptation_plan", requested_at=datetime(2092, 1, 8))
        self.db.add(request)
        self.db.commit()
        with patch("app.adaptation_delivery.start_scenario", new_callable=AsyncMock) as start:
            self.assertTrue(await deliver_plan_request(self.db, None, request))
            start.assert_not_awaited()
        self.assertIsNotNone(request.processed_at)

    def test_plan_due_cutoff_uses_local_clock(self):
        from app.scheduler import _load_pending_flow_requests
        request = FlowLaunchRequest(employee_id=self.employee.id, flow_key="test", launch_type="adaptation_plan", requested_at=datetime(2092, 1, 8, 10))
        self.db.add(request)
        self.db.commit()
        with patch("app.scheduler._local_now_naive", return_value=datetime(2092, 1, 8, 9, 59)), patch("app.scheduler.utc_now", return_value=datetime(2092, 1, 8, 7)):
            self.assertEqual(_load_pending_flow_requests(self.db), [])
        with patch("app.scheduler._local_now_naive", return_value=datetime(2092, 1, 8, 10)), patch("app.scheduler.utc_now", return_value=datetime(2092, 1, 8, 7)):
            self.assertEqual([row.id for row in _load_pending_flow_requests(self.db)], [request.id])

    def test_reset_cancels_future_entries_without_erasing_completed_history(self):
        from app.web.employees import _delete_employee_active_scenario_runtime_state
        preview = build_preview(self.db, self.employee)
        apply_plan(None, self.employee.id, {"fingerprint": preview["fingerprint"], "rules_confirmed": True, "rows": [{"key": "organization", "requested_at": "2092-01-08T10:00"}]}, self.db)
        item = self.db.query(EmployeeAdaptationPlanItem).one()
        _delete_employee_active_scenario_runtime_state(self.db, self.employee.id)
        self.db.commit()
        self.assertEqual(item.status, "cancelled")
        self.assertEqual(self.db.query(FlowLaunchRequest).count(), 0)
        self.assertEqual(self.db.query(EmployeeAdaptationPlanItem).count(), 1)
