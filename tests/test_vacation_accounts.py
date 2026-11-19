import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.models import Employee, EmployeeLeaveAccount, EmployeeLeaveOperation
from app.vacation_accounts import AccountInput, save_account
from tests import test_vacation_ledger as ledger_tests


class VacationAccountApiTests(unittest.TestCase):
    setUpDatabase = ledger_tests.VacationLedgerTests.setUp
    tearDownDatabase = ledger_tests.VacationLedgerTests.tearDown
    record = ledger_tests.VacationLedgerTests.record

    def setUp(self):
        from app.web.employee_routes import router, get_db

        self.setUpDatabase()
        self.app = FastAPI()
        self.app.include_router(router)
        self.app.dependency_overrides[get_db] = lambda: self.db

        @self.app.middleware("http")
        async def test_auth(request: Request, call_next):
            role = request.headers.get("x-test-role")
            request.state.current_user = SimpleNamespace(id=9, role=role) if role else None
            return await call_next(request)

        self.client = TestClient(self.app)
        self.clock = patch("app.vacation_accounts.today", return_value=date(2027, 4, 19))
        self.clock.start()
        self.url = "/api/employees/1/leave-accounts"
        self.values = dict(contract_key="contract-a", employed_on="2026-02-05", reviewed_through="2027-04-19",
                           month_end_policy=None, revision=0, reason="HR confirmed")
        self.headers = {"x-test-role": "hr"}

    def tearDown(self):
        self.client.close()
        self.clock.stop()
        self.tearDownDatabase()

    def test_auth_and_role(self):
        self.assertEqual(self.client.get(self.url).status_code, 401)
        self.assertEqual(self.client.get(self.url, headers={"x-test-role": "viewer"}).status_code, 403)
        self.assertEqual(self.client.put(self.url, json=self.values).status_code, 401)
        self.assertEqual(self.client.put(self.url, json=self.values, headers={"x-test-role": "viewer"}).status_code, 403)

    def test_save_date_independent_of_adaptation(self):
        employee = self.db.get(Employee, 1)
        employee.first_workday = date(2026, 11, 9)
        self.db.commit()
        response = self.client.put(self.url, headers=self.headers, json=self.values)
        self.assertEqual(response.status_code, 200, response.text)
        row = response.json()[0]
        self.assertEqual(row["revision"], 1)
        self.assertIsNone(row["balances"][0]["available"])
        self.assertEqual(self.db.get(Employee, 1).first_workday, date(2026, 11, 9))
        self.assertEqual(self.db.query(EmployeeLeaveOperation).count(), 0)
        self.assertEqual(self.client.put(self.url, headers=self.headers, json=self.values).status_code, 409)

    def test_invalid_inputs_and_not_found(self):
        for values in ({"employed_on": "2028-01-01"}, {"reviewed_through": "2028-01-01"},
                       {"reason": " "}):
            response = self.client.put(self.url, headers=self.headers, json={**self.values, **values})
            self.assertEqual(response.status_code, 409)
            self.db.rollback()
        self.assertEqual(self.client.get("/api/employees/999/leave-accounts", headers=self.headers).status_code, 404)

    def test_preview_does_not_post(self):
        self.record(amount="2.34")
        self.db.commit()
        save_account(self.db, 1, 9, AccountInput(**self.values))
        self.db.commit()
        response = self.client.post(self.url + "/accrual-preview", headers=self.headers,
                                   json={"contract_key": "contract-a", "through": "2027-04-19"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["new_total"], "9.33")
        self.assertEqual(len(response.json()["items"]), 4)
        self.assertEqual(self.db.query(EmployeeLeaveOperation).count(), 1)

    def test_missing_opening_and_unreviewed_period(self):
        save_account(self.db, 1, 9, AccountInput(**self.values))
        self.db.commit()
        for through in ("2027-04-19", "2027-05-19"):
            response = self.client.post(self.url + "/accrual-preview", headers=self.headers,
                                       json={"contract_key": "contract-a", "through": through})
            self.assertEqual(response.status_code, 409)
        self.assertEqual(self.db.query(EmployeeLeaveOperation).count(), 0)

    def test_anchor_change_blocked_after_operations(self):
        save_account(self.db, 1, 9, AccountInput(**self.values))
        self.record()
        self.db.commit()
        response = self.client.put(self.url, headers=self.headers,
            json={**self.values, "revision": 1, "employed_on": "2026-02-06"})
        self.assertEqual(response.status_code, 409)
        self.db.rollback()
        self.assertEqual(self.db.query(EmployeeLeaveAccount).one().employed_on, date(2026, 2, 5))

    def test_one_account_per_employee(self):
        self.client.put(self.url, headers=self.headers, json=self.values)
        response = self.client.put(self.url, headers=self.headers, json={**self.values, "contract_key": "another"})
        self.assertEqual(response.status_code, 409)
        self.db.rollback()
        self.assertEqual(self.db.query(EmployeeLeaveAccount).count(), 1)


if __name__ == "__main__":
    unittest.main()
