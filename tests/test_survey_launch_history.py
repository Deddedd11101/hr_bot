import asyncio
from datetime import UTC, datetime
from io import BytesIO
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from openpyxl import load_workbook

from app.auth import authenticate_account, create_admin_session_token
from app.database import SessionLocal, init_db
from app.main import AUTH_COOKIE_NAME, app
from app.models import Employee, FlowStepTemplate, ScenarioProgress, ScenarioTemplate, SurveyAnswer
from app.scenario_engine import handle_button_response, handle_text_response


class FakeMessenger:
    def __init__(self):
        self.messages = []

    async def send_text(self, chat_id, text, reply_markup=None):
        self.messages.append((chat_id, text))

    async def send_photo_path(self, chat_id, path, filename=None, reply_markup=None, caption=None):
        pass

    async def close(self):
        pass


class SurveyLaunchHistoryTests(TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)
        with SessionLocal() as db:
            account = authenticate_account(db, "admin", "admin123")
            cls.client.cookies.set(AUTH_COOKIE_NAME, create_admin_session_token(account.id))

    def setUp(self):
        suffix = uuid4().hex[:12]
        self.scenario_key = f"survey_history_{suffix}"
        now = datetime.now(UTC).replace(tzinfo=None)
        with SessionLocal() as db:
            employees = [
                Employee(full_name="Первый участник", telegram_user_id=str(uuid4().int % 10**12), employee_stage="staff", created_at=now),
                Employee(full_name="Второй участник", telegram_user_id=str(uuid4().int % 10**12), employee_stage="staff", created_at=now),
            ]
            db.add_all(employees)
            db.flush()
            self.employee_ids = [employee.id for employee in employees]
            survey = ScenarioTemplate(
                scenario_key=self.scenario_key, title="Опрос истории", scenario_kind="survey",
                role_scope="all", employee_scope="employees", recipient_mode="self",
                trigger_mode="manual_only", sort_order=0,
            )
            db.add(survey)
            db.flush()
            self.survey_id = survey.id
            db.add(FlowStepTemplate(
                flow_key=self.scenario_key, step_key="question", step_title="Ваш ответ?",
                default_text="Ваш ответ?", response_type="text", sort_order=0,
            ))
            db.commit()

    def _launch(self, employee_ids, messenger):
        with patch("app.web.bulk_action_routes.create_telegram_messenger", return_value=messenger):
            return self.client.post("/api/bulk-actions/surveys/launch", json={
                "flow_key": self.scenario_key,
                "target_employee_ids": employee_ids,
                "confirmed": True,
            })

    def _answer(self, employee_id, value, messenger):
        with SessionLocal() as db:
            employee = db.get(Employee, employee_id)
            self.assertTrue(asyncio.run(handle_text_response(messenger, db, employee, SimpleNamespace(text=value))))

    def _rows(self, run):
        response = self.client.get(run["download_url"])
        self.assertEqual(response.status_code, 200, response.text)
        return list(load_workbook(BytesIO(response.content), read_only=True).active.values)

    def test_each_launch_has_one_growing_excel_and_repeat_keeps_first(self):
        messenger = FakeMessenger()
        response = self._launch(self.employee_ids, messenger)
        self.assertEqual(response.status_code, 200, response.text)
        runs = self.client.get(f"/api/surveys/{self.survey_id}/runs").json()["runs"]
        self.assertEqual(len(runs), 1)
        first_run = runs[0]
        self.assertEqual(first_run["recipient_count"], 2)
        self.assertIsNone(first_run["download_url"])

        self._answer(self.employee_ids[0], "Первый ответ", messenger)
        first_run = self.client.get(f"/api/surveys/{self.survey_id}/runs").json()["runs"][0]
        self.assertEqual([row[2] for row in self._rows(first_run)[1:]], ["Первый ответ"])
        self._answer(self.employee_ids[1], "Второй ответ", messenger)
        first_run = self.client.get(f"/api/surveys/{self.survey_id}/runs").json()["runs"][0]
        self.assertEqual(first_run["respondent_count"], 2)
        self.assertEqual({row[0]: row[2] for row in self._rows(first_run)[1:]}, {
            "Первый участник": "Первый ответ", "Второй участник": "Второй ответ",
        })

        response = self._launch([self.employee_ids[0]], messenger)
        self.assertEqual(response.status_code, 200, response.text)
        self._answer(self.employee_ids[0], "Новый ответ", messenger)
        new_run, old_run = self.client.get(f"/api/surveys/{self.survey_id}/runs").json()["runs"]
        self.assertNotEqual(new_run["id"], old_run["id"])
        self.assertEqual([row[2] for row in self._rows(new_run)[1:]], ["Новый ответ"])
        self.assertEqual({row[2] for row in self._rows(old_run)[1:]}, {"Первый ответ", "Второй ответ"})
        with SessionLocal() as db:
            self.assertEqual(db.query(SurveyAnswer).filter_by(scenario_key=self.scenario_key).count(), 3)

    def test_branching_survey_saves_choice_and_terminal_branch_answer(self):
        with SessionLocal() as db:
            root = db.query(FlowStepTemplate).filter_by(flow_key=self.scenario_key, step_key="question").one()
            root_id = root.id
        saved = self.client.post(f"/api/flows/workspace/steps/{root_id}", json={
            "text": "Выберите путь", "response_type": "branching", "button_options": "Да\nНет",
        })
        self.assertEqual(saved.status_code, 200, saved.text)
        branch_response = self.client.post(f"/api/flows/workspace/steps/{root_id}/branches", json={"option_index": 0})
        self.assertEqual(branch_response.status_code, 200, branch_response.text)
        branch_id = branch_response.json()["step_id"]
        saved = self.client.post(f"/api/flows/workspace/steps/{branch_id}", json={
            "text": "Почему да?", "response_type": "text", "is_terminal": True,
        })
        self.assertEqual(saved.status_code, 200, saved.text)
        messenger = FakeMessenger()
        self.assertEqual(self._launch([self.employee_ids[0]], messenger).status_code, 200)
        with SessionLocal() as db:
            employee = db.get(Employee, self.employee_ids[0])
            self.assertTrue(asyncio.run(handle_button_response(
                messenger, db, employee, self.scenario_key, "question", 0,
            )))
            progress = db.query(ScenarioProgress).filter_by(employee_id=employee.id, scenario_key=self.scenario_key).one()
            self.assertEqual(progress.current_step_key, f"question__branch_0")
        self._answer(self.employee_ids[0], "Потому что", messenger)
        with SessionLocal() as db:
            progress = db.query(ScenarioProgress).filter_by(employee_id=self.employee_ids[0], scenario_key=self.scenario_key).one()
            self.assertTrue(progress.is_completed)
        run = self.client.get(f"/api/surveys/{self.survey_id}/runs").json()["runs"][0]
        self.assertEqual({row[1]: row[2] for row in self._rows(run)[1:]}, {
            "Выберите путь": "Да", "Почему да?": "Потому что",
        })

    def test_export_rejects_run_from_other_survey(self):
        messenger = FakeMessenger()
        self.assertEqual(self._launch([self.employee_ids[0]], messenger).status_code, 200)
        self._answer(self.employee_ids[0], "Ответ", messenger)
        run = self.client.get(f"/api/surveys/{self.survey_id}/runs").json()["runs"][0]
        self.assertEqual(self.client.get(f"/api/surveys/{self.survey_id + 99999}/runs/{run['id']}/export").status_code, 404)
