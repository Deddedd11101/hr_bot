import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Employee, FlowLaunchRequest, ScenarioTemplate, FlowStepTemplate, OnboardingEvent, EmployeeAdaptationPlanItem
from app.web.dashboard_routes import router, get_db
from app.web.operational_queue import queue_payload, request_utc
from app.web.operational_history import history_payload


class OperationalDashboardTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.now = datetime(2026, 11, 9, 9)
        self.db.add_all([Employee(id=1, full_name="Test Person", employee_stage="staff", created_at=self.now),
            ScenarioTemplate(id=1, scenario_key="onboard", title="Adaptation", recipient_mode="manager"),
            FlowStepTemplate(flow_key="onboard", step_key="hello", step_title="Greeting", default_text="Hello", response_type="none")])
        self.db.commit()
        app = FastAPI()
        app.include_router(router)
        @app.middleware("http")
        async def authenticate(request, call_next):
            if request.headers.get("x-test-auth"):
                request.state.current_user = SimpleNamespace(id=1, role="hr", login="operator")
            return await call_next(request)
        def session():
            yield self.db
        app.dependency_overrides[get_db] = session
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.db.close()
        self.engine.dispose()

    def test_auth_and_filter_validation(self):
        for url in ("/api/scenario-queue", "/api/dashboard/history"):
            self.assertEqual(self.client.get(url).status_code, 401)
            self.assertEqual(self.client.get(url, headers={"x-test-auth": "yes"}).status_code, 200)
            self.assertEqual(self.client.get(url + "?page=0", headers={"x-test-auth": "yes"}).status_code, 422)
        self.assertEqual(self.client.get("/api/scenario-queue?state=bad", headers={"x-test-auth": "yes"}).status_code, 422)
        self.assertEqual(self.client.get("/api/dashboard/history?kind=bad", headers={"x-test-auth": "yes"}).status_code, 422)
        self.assertEqual(self.client.get("/app/scenario-queue", follow_redirects=False).status_code, 303)
        page = self.client.get("/app/scenario-queue", headers={"x-test-auth": "yes"})
        self.assertIn('data-queue-page="true"', page.text)

    def test_missing_manager_and_scheduled_time_are_read_only(self):
        launch = FlowLaunchRequest(employee_id=1, flow_key="onboard", requested_at=self.now + timedelta(hours=2), launch_type="scheduled")
        self.db.add(launch)
        self.db.commit()
        # 11:00 Moscow is 08:00 UTC, already due at 09:00 UTC.
        with patch("app.web.operational_queue.utc_now", return_value=self.now):
            result = queue_payload(self.db)
        self.assertEqual(result["items"][0]["state"], "attention")
        self.assertIn("Руководитель", result["items"][0]["reason"])
        self.assertEqual(request_utc(launch), self.now - timedelta(hours=1))
        self.db.refresh(launch)
        self.assertIsNone(launch.processed_at)

    def test_failed_adaptation_visible_and_searchable(self):
        self.db.add(EmployeeAdaptationPlanItem(employee_id=1, entry_key="one", flow_key="onboard", title="Organization",
            requested_at=self.now, status="failed", calculation_json="{}", last_error="Old generic error"))
        self.db.commit()
        result = queue_payload(self.db, state="attention", search="test person")
        self.assertEqual(result["total"], 1)
        self.assertIn("Руководитель", result["items"][0]["reason"])
        self.assertEqual(queue_payload(self.db, search="no match")["total"], 0)

    def test_history_distinguishes_delivery_from_processed_requests(self):
        self.db.add_all([OnboardingEvent(employee_id=1, scheduled_at=self.now, sent_at=self.now,
            event_key="hello", message="Sent body", scenario_title="Frozen Adaptation", step_title="Frozen Greeting"),
            FlowLaunchRequest(employee_id=1, flow_key="onboard", requested_at=self.now, processed_at=self.now, launch_type="manual")])
        self.db.commit()
        steps = history_payload(self.db, kind="steps")["items"]
        self.assertEqual(len(steps), 1)
        self.assertIn("step_id=", steps[0]["scenario_href"])
        self.assertEqual(steps[0]["title"], "Frozen Adaptation")
        self.assertIn("Sent body", steps[0]["detail"])
        launches = history_payload(self.db, kind="launches")["items"]
        self.assertIn("не является подтверждением доставки", launches[0]["detail"])
        self.assertEqual(launches[0]["source"], "Вручную")

    def test_history_pagination_and_unknown_old_step(self):
        for index in range(5):
            self.db.add(OnboardingEvent(employee_id=1, scheduled_at=self.now, sent_at=self.now + timedelta(seconds=index),
                event_key="deleted", message=f"Body {index}"))
        self.db.commit()
        first = history_payload(self.db, page_size=2)
        second = history_payload(self.db, page=2, page_size=2)
        self.assertTrue(first["has_more"])
        self.assertFalse(set(r["id"] for r in first["items"]) & set(r["id"] for r in second["items"]))
        self.assertIsNone(first["items"][0]["scenario_href"])
