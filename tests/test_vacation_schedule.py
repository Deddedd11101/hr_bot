from contextlib import contextmanager
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.models import CatalogGroup, CatalogMembership, Employee, EmployeeVacationRequest
from app.time_utils import utc_now
from app.vacation_schedule import schedule
from tests import test_vacation_ledger as ledger_tests


class VacationScheduleTests(unittest.TestCase):
    setUpDatabase = ledger_tests.VacationLedgerTests.setUp
    tearDownDatabase = ledger_tests.VacationLedgerTests.tearDown

    def setUp(self):
        from app.web import dashboard_routes, employee_cabinet
        self.setUpDatabase()
        self.db.get(Employee, 1).employee_stage = "staff"
        self.db.get(Employee, 1).full_name = "Тестовый аналитик"
        self.db.add(Employee(id=2, full_name="Другой сотрудник", employee_stage="staff", created_at=utc_now()))
        self.db.add(Employee(id=3, full_name="Кандидат", employee_stage="candidate", created_at=utc_now()))
        self.db.add(CatalogGroup(id=1, scope="people", name="Аналитики", normalized_name="аналитики"))
        self.db.add(CatalogMembership(scope="people", object_id=1, group_id=1))
        self.db.commit()
        self.add_leave(1, "approved", date(2026, 12, 25), date(2027, 1, 10))
        self.add_leave(2, "approved", date(2027, 1, 3), date(2027, 1, 12))
        for state in ("pending", "pending_hr", "rejected", "cancelled"):
            self.add_leave(1, state, date(2027, 1, 15), date(2027, 1, 20))
        self.add_leave(3, "approved", date(2027, 1, 1), date(2027, 1, 31))
        self.db.commit()
        app = FastAPI()
        app.include_router(dashboard_routes.router)
        app.include_router(employee_cabinet.router)
        app.dependency_overrides[dashboard_routes.get_db] = lambda: self.db

        @app.middleware("http")
        async def test_auth(request: Request, call_next):
            request.state.current_user = SimpleNamespace(id=9, role="hr") if request.headers.get("x-test-auth") else None
            return await call_next(request)

        @contextmanager
        def session():
            yield self.db

        self.session_patch = patch.object(employee_cabinet, "get_session", session)
        self.session_patch.start()
        self.cabinet = employee_cabinet
        self.client = TestClient(app)

    def add_leave(self, employee_id, state, start, end):
        self.db.add(EmployeeVacationRequest(employee_id=employee_id, starts_on=start, ends_on=end,
            workdays=1, status=state, created_at=utc_now(), manager_notice="secret-internal-delivery"))

    def tearDown(self):
        self.client.close()
        self.session_patch.stop()
        self.tearDownDatabase()

    def test_only_approved_staff_and_private_field_allowlist(self):
        data = schedule(self.db, month="2027-01")
        self.assertEqual(data["total"], 2)
        self.assertEqual(data["items"][0]["starts_on"], "2026-12-25")
        self.assertEqual(set(data["items"][0]), {"employee_id", "name", "group_id", "group_name", "starts_on", "ends_on"})
        self.assertNotIn("secret-internal-delivery", str(data))

    def test_group_search_and_pagination_combine(self):
        self.assertEqual(schedule(self.db, month="2027-01", group_id=1, search="тестовый")["total"], 1)
        self.assertEqual(schedule(self.db, month="2027-01", group_id=0)["total"], 1)
        self.assertEqual(schedule(self.db, month="2027-01", group_id=1, search="другой")["total"], 0)
        page = schedule(self.db, month="2027-01", page=2, page_size=1)
        self.assertEqual(page["items"][0]["employee_id"], 2)
        self.assertEqual(schedule(self.db, month="2027-02")["total"], 0)

    def test_full_year_is_not_paginated(self):
        for _ in range(40):
            self.add_leave(2, "approved", date(2027, 7, 1), date(2027, 7, 14))
        self.db.commit()
        data = schedule(self.db, year=2027)
        self.assertEqual(data["total"], 42)
        self.assertEqual(len(data["items"]), 42)
        self.assertEqual(data["period_start"], "2027-01-01")
        self.assertEqual(data["period_end"], "2027-12-31")
        self.assertEqual(len(data["people"]), 2)
        self.assertEqual(len(schedule(self.db, year=2028)["people"]), 2)
        self.assertEqual(schedule(self.db, year=2026)["total"], 1)
        with self.assertRaises(ValueError):
            schedule(self.db, year=2027, month="2027-01")

    def test_year_api_keeps_filters_and_authorization(self):
        response = self.client.get("/api/vacation-schedule?year=2027&search=тестовый&group_id=1", headers={"x-test-auth": "yes"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 1)
        self.assertEqual(self.client.get("/employee-cabinet/vacation/team-schedule?year=2027").status_code, 403)

    def test_admin_auth_and_validation(self):
        self.assertEqual(self.client.get("/api/vacation-schedule").status_code, 401)
        response = self.client.get("/api/vacation-schedule?month=2027-01&group_id=1", headers={"x-test-auth": "yes"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 1)
        self.assertEqual(self.client.get("/api/vacation-schedule?month=2027-13", headers={"x-test-auth": "yes"}).status_code, 422)
        self.assertEqual(self.client.get("/api/vacation-schedule?month=9999-12", headers={"x-test-auth": "yes"}).status_code, 422)

    def test_cabinet_authorization_and_private_cache(self):
        url = "/employee-cabinet/vacation/team-schedule?month=2027-01"
        self.assertEqual(self.client.get(url).status_code, 403)
        with patch.object(self.cabinet, "authorize", return_value=self.db.get(Employee, 1)):
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(response.json()["total"], 2)


if __name__ == "__main__":
    unittest.main()
