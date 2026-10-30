from contextlib import nullcontext
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.adaptation_planning import default_entries
from app.adaptation_retest import apply, preview
from app.database import Base
from app.models import Employee, EmployeeAdaptationPlanItem, FlowLaunchRequest, ScenarioProgress
from app.web import adaptation_plan_routes as routes


class AdaptationRetestTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.engine = create_engine("sqlite:///" + str(Path(self.temp.name) / "test.db"))
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        now = datetime(2026, 10, 21)
        self.key = next(e["scenario_key"] for e in default_entries() if e["key"] == "middle")
        self.db.add(Employee(id=80, full_name="Fixture", created_at=now, telegram_user_id="123",
            profile_photo_path="fixture.png", employee_stage="staff"))
        self.db.add(Employee(id=81, full_name="Other", created_at=now))
        self.db.add(ScenarioProgress(id=136, employee_id=80, recipient_employee_id=80, scenario_key=self.key,
            current_step_key="waiting", waiting_for_response=True, is_completed=False, step_history="history",
            started_at=now, updated_at=now))
        self.db.add(FlowLaunchRequest(id=1, employee_id=80, flow_key=self.key, requested_at=now, launch_type="adaptation_plan"))
        self.db.add(EmployeeAdaptationPlanItem(id=1, employee_id=80, entry_key="middle", flow_key=self.key,
            title="Fixture", status="cancelled", requested_at=now, calculation_json="{}", launch_request_id=1))
        self.db.add(EmployeeAdaptationPlanItem(id=2, employee_id=81, entry_key="middle", flow_key=self.key,
            title="Other", status="planned", requested_at=now, calculation_json="{}"))
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        self.temp.cleanup()

    def test_archive_release_preserves_history_identity_and_other_employee(self):
        plan = preview(self.db, 80)
        result = apply(self.db, 80, plan["fingerprint"])
        self.assertTrue(Path(result["backup"]).is_file())
        self.assertEqual(result["interrupted_progress_ids"], [136])
        progress = self.db.get(ScenarioProgress, 136)
        self.assertFalse(progress.waiting_for_response)
        self.assertEqual(progress.step_history, "history")
        self.assertEqual(self.db.get(Employee, 80).telegram_user_id, "123")
        self.assertEqual(self.db.get(Employee, 80).profile_photo_path, "fixture.png")
        item = self.db.get(EmployeeAdaptationPlanItem, 1)
        self.assertEqual(item.status, "archived")
        self.assertEqual(json.loads(item.calculation_json)["retest_archive"]["entry_key"], "middle")
        self.assertEqual(self.db.get(EmployeeAdaptationPlanItem, 2).status, "planned")
        self.assertIsNotNone(self.db.get(FlowLaunchRequest, 1).processed_at)
        self.assertEqual(preview(self.db, 80)["items"], [])

    def test_stale_preview_and_foreign_dialog_block_reset(self):
        plan = preview(self.db, 80)
        self.db.get(ScenarioProgress, 136).updated_at = datetime(2026, 10, 30)
        self.db.commit()
        with self.assertRaisesRegex(ValueError, "изменилось"):
            apply(self.db, 80, plan["fingerprint"])
        p = self.db.get(ScenarioProgress, 136)
        p.employee_id = 81
        self.db.commit()
        plan = preview(self.db, 80)
        self.assertEqual(plan["blockers"], [136])
        with self.assertRaisesRegex(ValueError, "посторонний"):
            apply(self.db, 80, plan["fingerprint"])
        self.assertEqual(self.db.get(EmployeeAdaptationPlanItem, 1).status, "cancelled")

    def test_http_session_and_same_origin_guard(self):
        app = FastAPI()
        app.include_router(routes.router)
        with patch.object(routes, "get_session", return_value=nullcontext(self.db)), patch.object(routes, "require_api_admin"):
            client = TestClient(app)
            self.assertEqual(client.get("/app/employees/80/adaptation-retest").status_code, 200)
            data = {"fingerprint": preview(self.db, 80)["fingerprint"]}
            self.assertEqual(client.post("/app/employees/80/adaptation-retest", data=data).status_code, 403)
            self.assertEqual(client.post("/app/employees/80/adaptation-retest", data=data,
                headers={"origin": "http://testserver"}).status_code, 200)
