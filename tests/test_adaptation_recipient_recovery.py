import asyncio
from datetime import datetime
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app.adaptation_delivery import deliver_plan_request
from app.adaptation_planning import build_preview
from app.messaging.identity import set_primary_chat_id
from app.models import Employee, EmployeeAdaptationPlanItem, FlowLaunchRequest, ScenarioTemplate
from app.scenario_engine import resolve_scenario_recipient
from app.web.adaptation_plan_routes import apply_plan, edit_item
from tests import test_adaptation_planning as fixtures


class RecipientRecoveryTests(unittest.TestCase):
    setUp = fixtures.AdaptationPlanTests.setUp
    tearDown = fixtures.AdaptationPlanTests.tearDown

    def failed_item(self):
        scenario = self.db.query(ScenarioTemplate).filter_by(scenario_key="scenario_6c14bc1720c2").one()
        scenario.recipient_mode = "manager"
        self.db.commit()
        view = build_preview(self.db, self.employee)
        apply_plan(None, self.employee.id, {"fingerprint": view["fingerprint"], "rules_confirmed": True,
            "rows": [{"key": "organization", "requested_at": "2092-01-08T10:00"}]}, self.db)
        launch = self.db.query(FlowLaunchRequest).one()
        asyncio.run(deliver_plan_request(self.db, None, launch))
        item = self.db.query(EmployeeAdaptationPlanItem).one()
        self.assertEqual(item.status, "failed")
        self.assertIsNone(item.started_at)
        return item, launch

    def test_missing_roles_are_explicit(self):
        scenario = self.db.query(ScenarioTemplate).first()
        for mode, label in (("manager", "Руководитель"), ("mentor_adaptation", "Наставник адаптации"), ("mentor_ipr", "Наставник ИПР")):
            scenario.recipient_mode = mode
            result = resolve_scenario_recipient(self.db, self.employee, scenario, requires_response=True)
            self.assertIn(label, result.error)

    def test_assigning_recipient_enables_explicit_retry_once(self):
        item, old = self.failed_item()
        expected = item.requested_at.isoformat(timespec="minutes")
        view = next(r for r in build_preview(self.db, self.employee)["rows"] if r["key"] == "organization")
        self.assertIn("Руководитель", view["last_error"])
        self.assertFalse(view["can_retry"])
        with self.assertRaises(HTTPException) as error:
            edit_item(None, self.employee.id, item.id, {"action": "retry", "expected_at": expected}, self.db)
        self.assertEqual(error.exception.status_code, 409)
        self.db.rollback()
        manager = Employee(full_name="Manager", employee_stage="staff", created_at=datetime(2091, 1, 1))
        self.db.add(manager)
        self.db.flush()
        set_primary_chat_id(manager, "123456789", db=self.db)
        self.employee.manager_employee_id = manager.id
        self.db.commit()
        view = next(r for r in build_preview(self.db, self.employee)["rows"] if r["key"] == "organization")
        self.assertTrue(view["can_retry"])
        # Merely editing a card or reading preview must never launch a scenario.
        self.assertEqual(self.db.query(FlowLaunchRequest).count(), 1)
        with patch("app.web.adaptation_plan_routes.local_now", return_value=datetime(2092, 1, 8, 12)):
            edit_item(None, self.employee.id, item.id, {"action": "retry", "expected_at": expected}, self.db)
        self.assertEqual(item.status, "planned")
        self.assertIsNotNone(old.processed_at)
        self.assertNotEqual(item.launch_request_id, old.id)
        self.assertEqual(self.db.query(FlowLaunchRequest).count(), 2)
        with self.assertRaises(HTTPException):
            edit_item(None, self.employee.id, item.id, {"action": "retry", "expected_at": expected}, self.db)

    def test_uncertain_delivery_is_not_quick_retried(self):
        item, _ = self.failed_item()
        item.started_at = datetime(2092, 1, 8, 10)
        self.db.commit()
        self.assertFalse(next(r for r in build_preview(self.db, self.employee)["rows"] if r["key"] == "organization")["can_retry"])
        with self.assertRaises(HTTPException) as error:
            edit_item(None, self.employee.id, item.id, {"action": "retry", "expected_at": item.requested_at.isoformat(timespec="minutes")}, self.db)
        self.assertEqual(error.exception.status_code, 409)
