from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from app.database import SessionLocal
from app.models import Employee, FlowStepTemplate, ScenarioTemplate
from app.web.employees import _build_employee_detail_payload
from app.web.scenario_routes import update_workspace_scenario_api
from tests import test_adaptation_pulse_files as fixtures


class ScenarioPurposeTests(fixtures.AdaptationPulseFilesTests):
    async def test_purpose_preserves_runtime_metadata_and_appears_in_card(self):
        with SessionLocal() as db:
            subject = db.get(Employee, self.ids[0])
            row = ScenarioTemplate(scenario_key=self.key, title="Adaptation", scenario_kind="scenario", role_scope="all", employee_scope="employees", recipient_mode="manager", trigger_mode="first_workday")
            db.add(row)
            db.add(FlowStepTemplate(flow_key=self.key, step_key="q", step_title="Plan", default_text="Plan", response_type="file", target_field="adaptation_tasks_url"))
            db.commit()
            payload = {"title": row.title, "scenario_kind": "scenario", "purpose": "adaptation", "role_scope": "all", "employee_scope": "employees", "recipient_mode": "manager", "trigger_mode": "first_workday"}
            with patch("app.web.scenario_routes.require_api_auth"):
                result = update_workspace_scenario_api(SimpleNamespace(), row.id, payload, db)
                self.assertEqual(result["payload"]["workspace"]["scenario"]["purpose"], "adaptation")
                self.assertEqual(row.trigger_mode, "first_workday")
                self.assertEqual(row.recipient_mode, "manager")
                card = _build_employee_detail_payload(db, subject)
                self.assertEqual(card["adaptation_scenarios"][0]["status"], "not_started")
                self.assertEqual(next(item for item in card["options"]["scenarios"] if item["value"] == self.key)["purpose"], "adaptation")
                with self.assertRaises(HTTPException) as raised:
                    update_workspace_scenario_api(SimpleNamespace(), row.id, {**payload, "scenario_kind": "survey"}, db)
                self.assertEqual(raised.exception.status_code, 409)
