import unittest
from datetime import datetime

from fastapi.testclient import TestClient

from app.auth import authenticate_account
from app.database import SessionLocal, init_db
from app.main import AUTH_COOKIE_NAME, app
from app.models import Employee, EmployeeMessengerAccount


class EmployeeApiSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        init_db()
        cls.client = TestClient(app)
        with SessionLocal() as db:
            account = authenticate_account(db, "admin", "admin123")
            if account is None:
                raise AssertionError("Admin account is not available for API smoke tests.")
            cls.client.cookies.set(AUTH_COOKIE_NAME, str(account.id))

    def setUp(self) -> None:
        with SessionLocal() as db:
            employee = Employee(
                full_name="API Smoke Employee",
                telegram_user_id=None,
                telegram_username=None,
                first_workday=datetime.utcnow().date(),
                created_at=datetime.utcnow(),
                is_flow_scheduled=False,
                candidate_status="new",
                employee_stage="candidate",
                candidate_work_stage="testing",
            )
            db.add(employee)
            db.commit()
            db.refresh(employee)
            self.employee_id = employee.id

    def tearDown(self) -> None:
        with SessionLocal() as db:
            db.query(EmployeeMessengerAccount).filter(EmployeeMessengerAccount.employee_id == self.employee_id).delete()
            employee = db.get(Employee, self.employee_id)
            if employee is not None:
                db.delete(employee)
                db.commit()

    def test_employee_detail_api_returns_ok(self) -> None:
        response = self.client.get(f"/api/employees/{self.employee_id}")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["employee"]["id"], self.employee_id)

    def test_update_employee_api_accepts_public_chat_handle_without_chat_id(self) -> None:
        response = self.client.post(
            f"/api/employees/{self.employee_id}",
            json={
                "full_name": "Updated API Smoke Employee",
                "chat_id": "",
                "chat_handle": "hr_team",
                "first_workday": "",
                "desired_position": "",
                "birth_date": "",
                "work_email": "",
                "work_hours": "",
                "manager_chat_id": "",
                "mentor_adaptation_chat_id": "",
                "mentor_ipr_chat_id": "",
                "employee_stage": "candidate",
                "candidate_work_stage": "testing",
                "salary_expectation": "",
                "personal_data_consent": False,
                "employee_data_consent": False,
                "test_task_due_at": "",
                "notes": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["employee"]["chat_id"], "")
        self.assertEqual(payload["employee"]["chat_handle"], "hr_team")

        with SessionLocal() as db:
            employee = db.get(Employee, self.employee_id)
            self.assertIsNotNone(employee)
            self.assertEqual(employee.telegram_user_id, None)
            self.assertEqual(employee.telegram_username, "hr_team")

    def test_update_employee_api_returns_conflict_for_duplicate_chat_id(self) -> None:
        with SessionLocal() as db:
            other_employee = Employee(
                full_name="Existing Chat Owner",
                telegram_user_id="777888999",
                telegram_username="existing_owner",
                first_workday=datetime.utcnow().date(),
                created_at=datetime.utcnow(),
                is_flow_scheduled=False,
                candidate_status="new",
                employee_stage="candidate",
                candidate_work_stage="testing",
            )
            db.add(other_employee)
            db.commit()
            db.refresh(other_employee)
            conflict_employee_id = other_employee.id

        try:
            response = self.client.post(
                f"/api/employees/{self.employee_id}",
                json={
                    "full_name": "Updated API Smoke Employee",
                    "chat_id": "777888999",
                    "chat_handle": "hr_team",
                    "first_workday": "",
                    "desired_position": "",
                    "birth_date": "",
                    "work_email": "",
                    "work_hours": "",
                    "manager_chat_id": "",
                    "mentor_adaptation_chat_id": "",
                    "mentor_ipr_chat_id": "",
                    "employee_stage": "candidate",
                    "candidate_work_stage": "testing",
                    "salary_expectation": "",
                    "personal_data_consent": False,
                    "employee_data_consent": False,
                    "test_task_due_at": "",
                    "notes": "",
                },
            )

            self.assertEqual(response.status_code, 409)
            self.assertIn("777888999", response.json()["detail"])
        finally:
            with SessionLocal() as db:
                db.query(EmployeeMessengerAccount).filter(EmployeeMessengerAccount.employee_id == conflict_employee_id).delete()
                other_employee = db.get(Employee, conflict_employee_id)
                if other_employee is not None:
                    db.delete(other_employee)
                    db.commit()
