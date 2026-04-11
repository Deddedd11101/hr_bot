import unittest
from uuid import uuid4
from datetime import datetime

from fastapi.testclient import TestClient

from app.auth import authenticate_account
from app.database import SessionLocal, init_db
from app.main import AUTH_COOKIE_NAME, app
from app.messaging.identity import get_primary_chat_id, set_primary_chat_id
from app.messaging.service import get_or_create_employee_by_chat
from app.models import Employee, EmployeeMessengerAccount, ScenarioTemplate


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

    def test_update_employee_api_preserves_chat_id_when_payload_omits_it(self) -> None:
        with SessionLocal() as db:
            employee = db.get(Employee, self.employee_id)
            self.assertIsNotNone(employee)
            set_primary_chat_id(employee, "777000111", db=db)
            db.commit()

        response = self.client.post(
            f"/api/employees/{self.employee_id}",
            json={
                "full_name": "Updated API Smoke Employee",
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
        self.assertEqual(payload["employee"]["chat_id"], "777000111")
        self.assertEqual(payload["employee"]["chat_handle"], "hr_team")

        with SessionLocal() as db:
            employee = db.get(Employee, self.employee_id)
            self.assertIsNotNone(employee)
            self.assertEqual(employee.telegram_user_id, "777000111")
            self.assertEqual(employee.telegram_username, "hr_team")

    def test_bot_start_links_existing_employee_by_public_username(self) -> None:
        with SessionLocal() as db:
            employee = db.get(Employee, self.employee_id)
            self.assertIsNotNone(employee)
            unique_suffix = uuid4().hex[:12]
            username = f"codex_link_{unique_suffix}"
            chat_id = str(900000000000 + (int(unique_suffix, 16) % 100000000000))
            employee.telegram_username = f"@{username}"
            db.commit()

            employee, created = get_or_create_employee_by_chat(db, chat_id, username.upper())

            self.assertFalse(created)
            self.assertEqual(employee.id, self.employee_id)
            self.assertEqual(get_primary_chat_id(employee, db=db), chat_id)
            self.assertEqual(employee.telegram_username, username.upper())
            self.assertEqual(db.query(Employee).filter(Employee.id == self.employee_id).count(), 1)

    def test_bot_start_creates_candidate_when_card_is_missing(self) -> None:
        with SessionLocal() as db:
            unique_suffix = uuid4().hex[:12]
            chat_id = str(910000000000 + (int(unique_suffix, 16) % 100000000000))

            employee, created = get_or_create_employee_by_chat(db, chat_id, f"new_candidate_{unique_suffix}")

            self.assertTrue(created)
            self.assertEqual(employee.employee_stage, "candidate")
            self.assertEqual(employee.candidate_work_stage, "testing")
            self.assertEqual(get_primary_chat_id(employee, db=db), chat_id)
            created_employee_id = employee.id

        with SessionLocal() as db:
            db.query(EmployeeMessengerAccount).filter(EmployeeMessengerAccount.employee_id == created_employee_id).delete()
            employee = db.get(Employee, created_employee_id)
            if employee is not None:
                db.delete(employee)
            db.commit()

    def test_workspace_scenario_settings_api_updates_scope_and_description(self) -> None:
        scenario_key = f"codex_settings_{uuid4().hex[:12]}"
        with SessionLocal() as db:
            scenario = ScenarioTemplate(
                scenario_key=scenario_key,
                title="Workspace Settings Smoke",
                sort_order=999999,
                scenario_kind="scenario",
                role_scope="all",
                employee_scope="all",
                trigger_mode="manual_only",
                target_employee_id=None,
                description=None,
            )
            db.add(scenario)
            db.commit()
            db.refresh(scenario)
            scenario_id = scenario.id

        try:
            response = self.client.post(
                f"/api/flows/workspace/scenarios/{scenario_id}/settings",
                json={
                    "description": "x" * 60,
                    "role_scope": "analyst",
                    "employee_scope": "employees",
                    "trigger_mode": "bot_registration",
                    "target_employee_id": str(self.employee_id),
                },
            )

            self.assertEqual(response.status_code, 200)
            scenario_payload = response.json()["payload"]["workspace"]["scenario"]
            self.assertEqual(scenario_payload["description"], "x" * 50)
            self.assertEqual(scenario_payload["role_scope"], "analyst")
            self.assertEqual(scenario_payload["employee_scope"], "employees")
            self.assertEqual(scenario_payload["trigger_mode"], "bot_registration")
            self.assertEqual(scenario_payload["target_employee_id"], self.employee_id)
        finally:
            with SessionLocal() as db:
                scenario = db.get(ScenarioTemplate, scenario_id)
                if scenario is not None:
                    db.delete(scenario)
                db.commit()

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
