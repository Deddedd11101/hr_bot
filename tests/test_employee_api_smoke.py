import unittest
from uuid import uuid4
from datetime import datetime

from fastapi.testclient import TestClient

from app.auth import authenticate_account
from app.database import SessionLocal, init_db
from app.main import AUTH_COOKIE_NAME, app
from app.messaging.identity import get_primary_chat_id, set_primary_chat_id
from app.messaging.service import get_or_create_employee_by_chat
from app.models import (
    BotMenuButton,
    BotMenuSet,
    Employee,
    EmployeeMessengerAccount,
    HrSettings,
    MassMessageAction,
    ScenarioTemplate,
)


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
        self.unique_tag = uuid4().hex[:12]
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
            hr_settings = db.query(HrSettings).first()
            self.hr_settings_snapshot = None
            if hr_settings is not None:
                self.hr_settings_snapshot = {
                    "id": hr_settings.id,
                    "hr_name": hr_settings.hr_name,
                    "telegram_user_id": hr_settings.telegram_user_id,
                    "notification_recipient_ids": hr_settings.notification_recipient_ids,
                    "notify_scenario_completed": hr_settings.notify_scenario_completed,
                    "notify_test_task_received": hr_settings.notify_test_task_received,
                    "notify_user_actions": hr_settings.notify_user_actions,
                    "default_menu_set_id": hr_settings.default_menu_set_id,
                }

    def tearDown(self) -> None:
        with SessionLocal() as db:
            db.query(BotMenuButton).filter(BotMenuButton.label.like(f"codex-%-{self.unique_tag}%")).delete(synchronize_session=False)
            created_menu_sets = db.query(BotMenuSet).filter(BotMenuSet.title.like(f"codex-%-{self.unique_tag}%")).all()
            created_menu_set_ids = [menu_set.id for menu_set in created_menu_sets]
            if created_menu_set_ids:
                db.query(BotMenuButton).filter(BotMenuButton.menu_set_id.in_(created_menu_set_ids)).delete(synchronize_session=False)
                db.query(BotMenuButton).filter(BotMenuButton.target_menu_set_id.in_(created_menu_set_ids)).update(
                    {
                        BotMenuButton.action_type: "inactive",
                        BotMenuButton.target_menu_set_id: None,
                    },
                    synchronize_session=False,
                )
                db.query(Employee).filter(Employee.current_menu_set_id.in_(created_menu_set_ids)).update(
                    {Employee.current_menu_set_id: None},
                    synchronize_session=False,
                )
                for menu_set in created_menu_sets:
                    db.delete(menu_set)
            db.query(MassMessageAction).filter(MassMessageAction.message_text.like(f"%{self.unique_tag}%")).delete(synchronize_session=False)
            db.query(EmployeeMessengerAccount).filter(EmployeeMessengerAccount.employee_id == self.employee_id).delete()
            employee = db.get(Employee, self.employee_id)
            if employee is not None:
                db.delete(employee)
            if self.hr_settings_snapshot is not None:
                hr_settings = db.get(HrSettings, self.hr_settings_snapshot["id"])
                if hr_settings is not None:
                    hr_settings.hr_name = self.hr_settings_snapshot["hr_name"]
                    hr_settings.telegram_user_id = self.hr_settings_snapshot["telegram_user_id"]
                    hr_settings.notification_recipient_ids = self.hr_settings_snapshot["notification_recipient_ids"]
                    hr_settings.notify_scenario_completed = self.hr_settings_snapshot["notify_scenario_completed"]
                    hr_settings.notify_test_task_received = self.hr_settings_snapshot["notify_test_task_received"]
                    hr_settings.notify_user_actions = self.hr_settings_snapshot["notify_user_actions"]
                    hr_settings.default_menu_set_id = self.hr_settings_snapshot["default_menu_set_id"]
            db.commit()

    def test_employee_detail_api_returns_ok(self) -> None:
        response = self.client.get(f"/api/employees/{self.employee_id}")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["employee"]["id"], self.employee_id)

    def test_classic_operator_entrypoints_redirect_to_react_surfaces(self) -> None:
        expected_redirects = {
            "/candidates": "/app/employees?list_kind=candidates",
            "/employees": "/app/employees",
            "/bulk-actions": "/app/bulk-actions",
            "/flows": "/app/flows/workspace-v2",
            "/surveys": "/app/surveys/workspace",
            "/settings": "/app/settings",
        }

        for path, expected_location in expected_redirects.items():
            with self.subTest(path=path):
                response = self.client.get(path, follow_redirects=False)
                self.assertEqual(response.status_code, 303)
                self.assertEqual(response.headers.get("location"), expected_location)

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

    def test_bot_start_does_not_create_candidate_when_card_is_missing(self) -> None:
        with SessionLocal() as db:
            unique_suffix = uuid4().hex[:12]
            chat_id = str(910000000000 + (int(unique_suffix, 16) % 100000000000))
            before_count = db.query(Employee).count()

            employee, created = get_or_create_employee_by_chat(db, chat_id, f"new_candidate_{unique_suffix}")

            self.assertFalse(created)
            self.assertIsNone(employee)
            self.assertEqual(db.query(Employee).count(), before_count)

    def test_update_employee_api_persists_shared_fields_for_candidate(self) -> None:
        response = self.client.post(
            f"/api/employees/{self.employee_id}",
            json={
                "full_name": "Кандидат Тест",
                "chat_id": "",
                "chat_handle": "",
                "first_workday": "2026-05-20",
                "desired_position": "Дизайнер",
                "birth_date": "",
                "work_email": "",
                "work_hours": "",
                "manager_chat_id": "",
                "mentor_adaptation_chat_id": "",
                "mentor_ipr_chat_id": "",
                "employee_stage": "candidate",
                "candidate_work_stage": "offer",
                "salary_expectation": "300000",
                "personal_data_consent": True,
                "employee_data_consent": False,
                "is_bot_blocked": False,
                "test_task_due_at": "",
                "notes": "candidate-notes",
            },
        )

        self.assertEqual(response.status_code, 200)
        with SessionLocal() as db:
            employee = db.get(Employee, self.employee_id)
            self.assertIsNotNone(employee)
            self.assertEqual(employee.first_workday.isoformat() if employee.first_workday else None, "2026-05-20")
            self.assertEqual(employee.desired_position, "Дизайнер")
            self.assertEqual(employee.salary_expectation, "300000")
            self.assertEqual(employee.notes, "candidate-notes")
            self.assertFalse(employee.is_bot_blocked)

    def test_update_employee_api_persists_shared_fields_for_employee(self) -> None:
        with SessionLocal() as db:
            employee = db.get(Employee, self.employee_id)
            self.assertIsNotNone(employee)
            employee.employee_stage = "staff"
            employee.candidate_work_stage = None
            db.commit()

        response = self.client.post(
            f"/api/employees/{self.employee_id}",
            json={
                "full_name": "Сотрудник Тест",
                "chat_id": "",
                "chat_handle": "",
                "first_workday": "2026-05-21",
                "desired_position": "Аналитик",
                "birth_date": "",
                "work_email": "",
                "work_hours": "",
                "manager_chat_id": "",
                "mentor_adaptation_chat_id": "",
                "mentor_ipr_chat_id": "",
                "employee_stage": "staff",
                "candidate_work_stage": "",
                "salary_expectation": "350000",
                "personal_data_consent": False,
                "employee_data_consent": True,
                "is_bot_blocked": True,
                "test_task_due_at": "",
                "notes": "employee-notes",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["employee"]["is_bot_blocked"])
        with SessionLocal() as db:
            employee = db.get(Employee, self.employee_id)
            self.assertIsNotNone(employee)
            self.assertEqual(employee.first_workday.isoformat() if employee.first_workday else None, "2026-05-21")
            self.assertEqual(employee.desired_position, "Аналитик")
            self.assertEqual(employee.salary_expectation, "350000")
            self.assertEqual(employee.notes, "employee-notes")
            self.assertTrue(employee.is_bot_blocked)

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

    def test_launch_flow_api_rejects_blocked_employee(self) -> None:
        with SessionLocal() as db:
            employee = db.get(Employee, self.employee_id)
            self.assertIsNotNone(employee)
            employee.is_bot_blocked = True
            employee.employee_stage = "staff"
            db.commit()

        response = self.client.post(
            f"/api/employees/{self.employee_id}/launch",
            json={"flow_key": "recruitment_hiring"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("доступ к боту заблокирован", response.json()["detail"].lower())

    def test_bulk_actions_preview_api_uses_candidate_stage_split(self) -> None:
        response = self.client.post(
            "/api/bulk-actions/preview",
            json={
                "target_role_scope": "",
                "target_employee_id": None,
                "target_employee_stages": [],
                "target_candidate_stages": ["testing"],
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertGreaterEqual(payload["recipient_count"], 1)
        self.assertIn("Кандидаты", payload["recipient_scope"])

    def test_bulk_actions_schedule_message_api_persists_react_workspace_payload(self) -> None:
        message_text = f"codex-message-{self.unique_tag}"
        response = self.client.post(
            "/api/bulk-actions/messages/schedule",
            json={
                "message_text": message_text,
                "requested_at": "2026-06-01T10:30",
                "target_role_scope": "",
                "target_employee_id": None,
                "target_employee_stages": [],
                "target_candidate_stages": ["testing"],
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()["payload"]
        self.assertIn("scheduled_message_actions", payload)
        with SessionLocal() as db:
            action = db.query(MassMessageAction).filter(MassMessageAction.message_text == message_text).one_or_none()
            self.assertIsNotNone(action)
            self.assertEqual(action.launch_type, "scheduled")
            self.assertEqual(action.target_candidate_stages, "testing")
            self.assertEqual(action.target_employee_stages, None)
            self.assertGreaterEqual(action.recipient_count, 1)

    def test_settings_hr_update_api_persists_workspace_fields(self) -> None:
        response = self.client.post(
            "/api/settings/hr",
            json={
                "hr_name": f"codex-hr-{self.unique_tag}",
                "telegram_user_id": f"tg-{self.unique_tag}",
                "notification_recipient_ids": f"tg-a-{self.unique_tag},tg-b-{self.unique_tag}",
                "default_menu_set_id": None,
                "notify_scenario_completed": False,
                "notify_test_task_received": True,
                "notify_user_actions": False,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["hr_settings"]["hr_name"], f"codex-hr-{self.unique_tag}")
        with SessionLocal() as db:
            hr_settings = db.query(HrSettings).first()
            self.assertIsNotNone(hr_settings)
            self.assertEqual(hr_settings.hr_name, f"codex-hr-{self.unique_tag}")
            self.assertEqual(hr_settings.telegram_user_id, f"tg-{self.unique_tag}")
            self.assertFalse(hr_settings.notify_scenario_completed)
            self.assertFalse(hr_settings.notify_user_actions)

    def test_settings_menu_set_api_supports_react_workspace_create_and_delete(self) -> None:
        title = f"codex-menu-{self.unique_tag}"
        create_response = self.client.post(
            "/api/settings/menu-sets",
            json={"title": title, "description": "workspace smoke"},
        )

        self.assertEqual(create_response.status_code, 200)
        created_workspace = create_response.json()
        created_menu_set = next((item for item in created_workspace["menu_sets"] if item["title"] == title), None)
        self.assertIsNotNone(created_menu_set)

        delete_response = self.client.delete(f"/api/settings/menu-sets/{created_menu_set['id']}")
        self.assertEqual(delete_response.status_code, 200)
        deleted_workspace = delete_response.json()
        self.assertFalse(any(item["id"] == created_menu_set["id"] for item in deleted_workspace["menu_sets"]))
