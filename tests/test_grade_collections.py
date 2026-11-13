import asyncio
from datetime import datetime
import json
import unittest
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import patch

from sqlalchemy import select, text
from sqlalchemy.orm import sessionmaker

from app.grades import collections
from app.grades import development_actions
from app.grades.corrections import correct, history, view
from app.feedback_exports import latest_feedback_run
from app.messaging.identity import set_primary_chat_id
from app.models import Employee, EmployeeFeedbackRecipient, GradeAssessmentValue, GradeDevelopmentAction, ScenarioProgress, ScenarioTemplate, FlowStepTemplate
from app.scenario_engine import ScenarioRecipientBusy, handle_button_response
from app.web import grades
from app.time_utils import utc_now
from tests import test_grades_services as fixtures
from tests.test_scenario_engine_smoke import FakeMessenger


class ReviewMessenger(FakeMessenger):
    async def send_text(self, chat_id, text, reply_markup=None):
        await super().send_text(chat_id, text, reply_markup)
        return SimpleNamespace(message_id=len(self.texts))


class GradeCollectionTests(unittest.TestCase):
    setUp = fixtures.GradeServicesTests.setUp
    tearDown = fixtures.GradeServicesTests.tearDown
    review_request = fixtures.GradeServicesTests.review_request

    def prepare(self):
        self.db.get(Employee, 1).employee_stage = "staff"
        for employee_id in (2, 3):
            person = Employee(id=employee_id, full_name=f"Reviewer {employee_id}", employee_stage="staff", created_at=utc_now())
            self.db.add(person)
            self.db.flush()
            set_primary_chat_id(person, str(700001000 + employee_id), db=self.db)
        self.db.commit()
        self.sessions = sessionmaker(bind=self.engine, autoflush=False)

    def create(self):
        row = collections.create(self.db, 1, 1, dict(request_id=str(uuid4()), specialization_id=self.spec["id"], recipient_ids=[2, 3]))
        self.db.commit()
        return row

    def answer(self, messenger, collection, respondent, skill_id, option):
        person = self.db.get(Employee, respondent)
        progress = self.db.query(ScenarioProgress).filter_by(employee_id=respondent, scenario_key=collection.scenario_key).one()
        self.assertTrue(asyncio.run(handle_button_response(messenger, self.db, person, collection.scenario_key, f"skill_{skill_id}", option,
            message_id=progress.grade_widget_message_id)))
        if progress.current_step_key == "review_confirm":
            self.assertTrue(self.confirm(messenger, collection, respondent, 0, progress.pending_confirmation_message_id))

    def confirm(self, messenger, collection, respondent, option, message_id):
        return asyncio.run(handle_button_response(messenger, self.db, self.db.get(Employee, respondent),
            collection.scenario_key, "review_confirm", option, message_id=message_id))

    def test_mini_app_invites_and_locks_own_review_on_submission(self):
        import time

        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from app.web import grade_review_mini_app as mini
        from tests import test_employee_cabinet as cabinet_fixtures

        self.prepare()
        with patch.object(collections.settings, "GRADE_REVIEW_WEBAPP_URL", "https://example.test/grade-review"):
            row = self.create()
            messenger = ReviewMessenger()
            asyncio.run(collections.process_pending(messenger, session_factory=self.sessions))
        self.db.expire_all()
        self.assertEqual(len(messenger.texts), 2)
        self.assertEqual(self.db.query(ScenarioProgress).count(), 0)
        app = FastAPI()
        app.include_router(mini.router)
        path = f"/grade-review/{row.id}/answers"

        def headers(employee_id):
            signed = cabinet_fixtures.EmployeeCabinetTests.signed(int(time.time()), 700001000 + employee_id)
            return {"X-Telegram-Init-Data": signed}

        with patch.object(mini, "get_session", self.sessions), patch.object(mini.settings, "TELEGRAM_BOT_TOKEN", "test-token"), \
                patch.object(mini.settings, "STAFF_EMAIL_OTP_ENABLED", False), TestClient(app) as client:
            self.assertEqual(client.get(path).status_code, 403)
            self.assertEqual(client.get(path, headers=headers(1)).status_code, 403)
            initial = client.get(path, headers=headers(2)).json()
            skill = initial["questions"][0]["key"]
            submission = {"answers": {skill: "2"}, "revision": initial["revision"]}
            self.assertTrue(initial["editable"])
            self.assertEqual(client.put(path, headers=headers(2), json=submission).status_code, 200)
            self.assertEqual(client.get(path, headers=headers(3)).json()["answers"], {})
            saved = client.get(path, headers=headers(2)).json()
            self.assertTrue(saved["completed"])
            self.assertFalse(saved["editable"])
            self.assertEqual(saved["answers"], {skill: "2"})
            update = {"answers": {skill: "4"}, "revision": saved["revision"]}
            self.assertEqual(client.put(path, headers=headers(2), json=update).status_code, 409)
            self.assertEqual(client.put(path, headers=headers(2), json=submission).status_code, 200)
            self.db.expire_all()
            self.assertEqual(collections.report(self.db, row)["scores"][0]["currentLevel"], 2)
            row.status = "finalized"
            self.db.commit()
            self.assertEqual(client.put(path, headers=headers(2), json=update).status_code, 409)

    def test_self_assessment_is_visible_but_excluded_from_average(self):
        from app.models import SurveyAnswer

        self.prepare()
        set_primary_chat_id(self.db.get(Employee, 1), "700001001", db=self.db)
        data = dict(request_id=str(uuid4()), specialization_id=self.spec["id"], recipient_ids=[1, 2])
        with patch.object(collections.settings, "GRADE_REVIEW_WEBAPP_URL", "https://example.test/grade-review"):
            with self.assertRaisesRegex(ValueError, "самооценку"):
                collections.create(self.db, 1, 1, data)
            row = collections.create(self.db, 1, 1, data, include_self=True)
        for recipient in self.db.query(EmployeeFeedbackRecipient).filter_by(run_id=row.feedback_run_id):
            recipient.delivery_status = "completed"
            reviewer_id = recipient.respondent_employee_id
            self.db.add(SurveyAnswer(employee_id=reviewer_id, scenario_key=row.scenario_key,
                feedback_run_id=row.feedback_run_id, step_key=f"skill_{self.skill['id']}",
                answer_value="4" if reviewer_id == 1 else "2", answered_at=utc_now()))
        self.db.flush()
        result = collections.report(self.db, row)
        self.assertTrue(result["reviewers"][0]["is_self_assessment"])
        self.assertEqual(result["reviewers"][0]["scores"][0]["currentLevel"], 4)
        self.assertEqual(result["scores"][0]["currentLevel"], 2)
        self.assertEqual(result["scores"][0]["respondent_count"], 1)

    def test_review_retry_ignores_old_confirmation_and_only_final_attempt_counts(self):
        self.prepare()
        row = self.create()
        messenger = ReviewMessenger()
        asyncio.run(collections.process_pending(messenger, session_factory=self.sessions))
        self.db.expire_all()
        employee = self.db.get(Employee, 2)
        progress = self.db.query(ScenarioProgress).filter_by(employee_id=2, scenario_key=row.scenario_key).one()
        skill = f"skill_{self.skill['id']}"
        self.assertTrue(asyncio.run(handle_button_response(messenger, self.db, employee, row.scenario_key, skill, 1)))
        first_message = progress.pending_confirmation_message_id
        self.assertTrue(any("<pre>Interview: 1</pre>" == msg["text"] for msg in messenger.texts))
        self.assertEqual(collections.report(self.db, row)["completed_count"], 0)
        self.assertTrue(self.confirm(messenger, row, 2, 1, first_message))
        self.assertTrue(asyncio.run(handle_button_response(messenger, self.db, employee, row.scenario_key, skill, 3)))
        self.assertFalse(self.confirm(messenger, row, 2, 0, first_message))
        self.assertTrue(self.confirm(messenger, row, 2, 0, progress.pending_confirmation_message_id))
        self.assertEqual(collections.report(self.db, row)["scores"][0]["currentLevel"], 3)

    def test_review_summary_uses_native_table_with_escaped_answers(self):
        from unittest.mock import AsyncMock
        from app.scenario_engine import handle_text_response

        self.prepare()
        row = collections.create(self.db, 1, 1, dict(request_id=str(uuid4()), specialization_id=self.spec["id"],
            recipient_ids=[2], open_questions=["<Вопрос>"]))
        self.db.commit()
        messenger = ReviewMessenger()
        messenger.send_rich_text = AsyncMock(return_value=True)
        asyncio.run(collections.process_pending(messenger, session_factory=self.sessions))
        self.db.expire_all()
        self.answer(messenger, row, 2, self.skill["id"], 2)
        asyncio.run(handle_text_response(messenger, self.db, self.db.get(Employee, 2), SimpleNamespace(text="<Ответ>")))
        messenger.send_rich_text.assert_awaited_once()
        chat_id, markup = messenger.send_rich_text.call_args.args
        self.assertEqual(chat_id, "700001002")
        self.assertIn("<table>", markup)
        self.assertIn("<td>&lt;Вопрос&gt;</td><td>&lt;Ответ&gt;</td>", markup)
        self.assertEqual(collections.report(self.db, row)["completed_count"], 0)

    def test_native_table_transport_falls_back_only_on_definite_rejection(self):
        from aiogram.exceptions import TelegramNotFound
        from unittest.mock import AsyncMock
        from app.messaging.telegram import TelegramMessenger

        bot = AsyncMock()
        messenger = TelegramMessenger(bot)
        self.assertTrue(asyncio.run(messenger.send_rich_text("123", "<table></table>")))
        method = bot.call_args.args[0]
        self.assertEqual(method.__api_method__, "sendRichMessage")
        self.assertEqual(method.model_dump()["rich_message"], {"html": "<table></table>", "skip_entity_detection": True})
        bot.side_effect = TelegramNotFound(method=method, message="unknown method")
        self.assertFalse(asyncio.run(messenger.send_rich_text("123", "<table></table>")))
        bot.side_effect = TimeoutError()
        with self.assertRaises(TimeoutError):
            asyncio.run(messenger.send_rich_text("123", "<table></table>"))

    def test_widget_pilot_keeps_native_callbacks_and_open_questions(self):
        from unittest.mock import AsyncMock
        from aiogram.types import Update
        from app.bot_runner import on_widget_update
        from app.config import settings
        from app.scenario_engine import handle_text_response

        self.prepare()
        row = collections.create(self.db, 1, 1, dict(request_id=str(uuid4()), specialization_id=self.spec["id"],
            recipient_ids=[2, 3], open_questions=["Что улучшить?", "Комментарий"]))
        snapshot = json.loads(row.snapshot_json)
        levels = {str(n): f"Критерий {n}. " * 12 + "Конец." for n in range(1, 5)}
        snapshot["scores"][0]["rubric"] = {"levels": levels, "na": "Нет информации"}
        snapshot["scores"].append({**snapshot["scores"][0], "skillId": 999, "skillName": "Second skill"})
        row.snapshot_json = json.dumps(snapshot)
        first_step = self.db.query(FlowStepTemplate).filter_by(flow_key=row.scenario_key,
            step_key=f"skill_{self.skill['id']}").one()
        first_step.button_options = "1\n2\n3\n4\nНе могу оценить"
        long_question = "\n\n".join(f"{n}. {description}" for n, description in levels.items())
        second_step = FlowStepTemplate(flow_key=row.scenario_key, step_key="skill_999", step_title="Second skill",
            sort_order=0, default_text=long_question, response_type="buttons", button_options=first_step.button_options,
            target_field="survey_answer", send_mode="immediate")
        self.db.add(second_step)
        self.db.commit()
        messenger = ReviewMessenger()
        messenger.send_widget = AsyncMock(return_value=SimpleNamespace(message_id=42))
        messenger.update_widget = AsyncMock(return_value=True)
        with patch.object(settings, "GRADE_WIDGET_REVIEWER_IDS", "2"):
            asyncio.run(collections.process_pending(messenger, session_factory=self.sessions))
            self.db.expire_all()
            messenger.send_widget.assert_awaited_once()
            widget = messenger.send_widget.call_args
            self.assertEqual(widget.args[0], "700001002")
            self.assertIn("Interview", widget.kwargs["chat_data"])
            first = json.loads(widget.kwargs["chat_data"])
            self.assertIn(self.db.get(Employee, 1).full_name, first["label"])
            self.assertGreater(first["pages"], 1)
            self.assertIsNone(widget.kwargs["reply_markup"])
            text_count = len(messenger.texts)
            bot = AsyncMock()
            def query(action, index, message_id=42, step=None):
                update = Update.model_validate({"update_id": 1, "widget_query": {"id": "query",
                    "from": {"id": 700001002}, "chat": {"type": "private", "id": 700001002},
                    "message_id": message_id, "data": f"g:{action}:{(step or first_step).id}:{index}"}})
                asyncio.run(on_widget_update(AsyncMock(), update, {"bot": bot}))
                return bot.call_args.args[0].data

            with patch("app.bot_runner.SessionLocal", self.sessions), patch("app.bot_runner.TelegramMessenger", return_value=messenger):
                self.assertEqual(query("r", 0, message_id=41), "error")
                self.assertEqual(query("k", 0, message_id=41), "error")
                bot.edit_message_reply_markup.assert_not_awaited()
                self.assertEqual(json.loads(query("r", 0)), first)
                self.assertEqual("".join(json.loads(query("r", i))["prompt"] for i in range(first["pages"])),
                    "\n\n".join(f"{level}. {description}" for level, description in levels.items()))
                self.assertEqual(query("k", 0), "ok")
                keyboard = bot.edit_message_reply_markup.call_args.kwargs["reply_markup"].inline_keyboard
                self.assertEqual([[button.text for button in row] for row in keyboard], [["Обычные кнопки"]])
                self.assertEqual(query("p", 1, message_id=41), "error")
                self.assertEqual(query("a", 1, step=second_step), "error")
                bot.edit_message_reply_markup.reset_mock()
                prefetched = json.loads(query("q", 1))
                self.assertEqual(prefetched["step"], second_step.id)
                bot.edit_message_reply_markup.assert_not_awaited()
                self.assertEqual(query("a", 1), "ok")
                self.assertEqual(query("a", 3), "error")
                self.assertEqual(json.loads(query("r", 1, step=second_step))["prompt"], prefetched["prompt"])
                self.assertEqual("".join(json.loads(query("r", i, step=second_step))["prompt"]
                    for i in range(prefetched["pages"])), long_question)
                self.assertEqual(query("b", 0, step=second_step), "ok")
                self.assertEqual(query("a", 1), "ok")
            self.db.expire_all()
            self.assertEqual(messenger.update_widget.call_args.args[1], 42)
            self.assertIn("Second skill", messenger.update_widget.call_args.args[2])
            self.assertIsNone(messenger.update_widget.call_args.args[3])
            self.assertFalse(asyncio.run(handle_button_response(messenger, self.db, self.db.get(Employee, 2),
                row.scenario_key, "skill_999", -2, message_id=42)))
            self.assertEqual(len(messenger.texts), text_count)
            self.answer(messenger, row, 2, 999, 2)
            self.assertIn("Что улучшить?", messenger.texts[-1]["text"])
            asyncio.run(handle_text_response(messenger, self.db, self.db.get(Employee, 2), SimpleNamespace(text="<Ответ>")))
            asyncio.run(handle_text_response(messenger, self.db, self.db.get(Employee, 2), SimpleNamespace(text="Я" * 450 + " Конец")))
            messenger.send_widget.assert_awaited_once()
            self.assertEqual(messenger.update_widget.call_args.args[1], 42)
            self.assertEqual(json.loads(messenger.update_widget.call_args.args[2])["rows"], [["Interview", "2"], ["Second skill", "3"]])
            self.assertFalse(self.confirm(messenger, row, 2, -2, 42))
            self.assertFalse(self.confirm(messenger, row, 2, -2, 41))
            self.assertEqual(collections.report(self.db, row)["completed_count"], 0)
            self.assertTrue(self.confirm(messenger, row, 2, 0, 42))
            self.assertIn("Ответы утверждены", messenger.update_widget.call_args.args[2])
            self.assertEqual(collections.report(self.db, row)["completed_count"], 1)

    def test_widget_transport_rejects_oversize_and_does_not_retry_timeout(self):
        from aiogram.exceptions import TelegramNotFound
        from unittest.mock import AsyncMock
        from app.messaging.telegram import TelegramMessenger

        bot = AsyncMock(return_value=SimpleNamespace(message_id=42))
        messenger = TelegramMessenger(bot)
        self.assertIsNone(asyncio.run(messenger.send_widget("123", "x" * 32769)))
        bot.assert_not_awaited()
        self.assertEqual(asyncio.run(messenger.send_widget("123", "<p>QA</p>")).message_id, 42)
        method = bot.call_args.args[0]
        self.assertEqual(method.__api_method__, "sendWidget")
        self.assertTrue(method.protect_content)
        bot.side_effect = TelegramNotFound(method=method, message="unknown method")
        self.assertIsNone(asyncio.run(messenger.send_widget("123", "<p>QA</p>")))
        bot.side_effect = TimeoutError()
        with self.assertRaises(TimeoutError):
            asyncio.run(messenger.send_widget("123", "<p>QA</p>"))

    def test_admission_race_keeps_review_recipients_pending(self):
        self.prepare()
        row = self.create()
        with patch.object(collections, "start_scenario", side_effect=ScenarioRecipientBusy()):
            asyncio.run(collections.process_pending(FakeMessenger(), session_factory=self.sessions))
        self.db.expire_all()
        statuses = list(self.db.scalars(select(EmployeeFeedbackRecipient.delivery_status).where(EmployeeFeedbackRecipient.run_id == row.feedback_run_id)))
        self.assertEqual(statuses, ["pending", "pending"])

    def test_individual_reviews_fractional_mean_idempotence_and_feedback_isolation(self):
        # Existing stage SQLite uses INTEGER affinity; it must still retain 1.5.
        self.db.execute(text("DROP TABLE grade_assessment_values"))
        self.db.execute(text("CREATE TABLE grade_assessment_values (id INTEGER PRIMARY KEY, assessment_id INTEGER NOT NULL, skill_id INTEGER NOT NULL, level INTEGER NOT NULL CHECK(level BETWEEN 0 AND 4), UNIQUE(assessment_id, skill_id))"))
        self.db.commit()
        self.prepare()
        row = self.create()
        messenger = ReviewMessenger()
        asyncio.run(collections.process_pending(messenger, session_factory=self.sessions))
        self.db.expire_all()
        self.answer(messenger, row, 2, self.skill["id"], 0)
        self.answer(messenger, row, 3, self.skill["id"], 3)
        report = collections.report(self.db, row)
        self.assertTrue(report["can_finalize"])
        self.assertEqual([r["categories"][0]["current"] for r in report["reviewers"]], [0, 3])
        self.assertEqual(report["categories"][0]["current"], 1.5)
        self.assertIsNone(latest_feedback_run(self.db, 1))
        final = collections.finalize(self.db, 1, row.id, 1)
        self.db.commit()
        self.db.expire_all()
        self.assertEqual(final["categories"][0]["current"], 1.5)
        self.assertEqual(self.db.scalar(select(GradeAssessmentValue.level)), 1.5)
        self.assertEqual(collections.finalize(self.db, 1, row.id, 1)["id"], final["id"])
        with self.assertRaises(LookupError):
            collections.finalize(self.db, 2, row.id, 1)
        # Editing grade only retains the fractional aggregate and a prior snapshot.
        editable = view(self.db, final["id"])
        changed = correct(self.db, final["id"], 1, dict(request_id=str(uuid4()), expected_token=editable["edit_token"], reason="Grade decision", values=[], current_grade_id=2))
        self.assertEqual(changed["categories"][0]["current"], 1.5)
        self.assertEqual(changed["current_grade_id"], 2)
        self.assertIsNone(history(self.db, final["id"])[0]["previous"]["current_grade_id"])

    def test_busy_reviewer_does_not_block_others_and_missing_is_not_zero(self):
        self.prepare()
        row = self.create()
        self.db.add(ScenarioProgress(employee_id=2, scenario_key="busy", current_step_key="question", waiting_for_response=True, is_completed=False, started_at=utc_now(), updated_at=utc_now()))
        self.db.add(ScenarioTemplate(scenario_key="busy", title="Busy", trigger_mode="manual_only"))
        self.db.add(FlowStepTemplate(flow_key="busy", step_key="question", step_title="Question", response_type="text", default_text="Question"))
        self.db.commit()
        messenger = ReviewMessenger()
        asyncio.run(collections.process_pending(messenger, session_factory=self.sessions))
        self.db.expire_all()
        statuses = {r.respondent_employee_id: r.delivery_status for r in self.db.scalars(select(EmployeeFeedbackRecipient))}
        self.assertEqual(statuses, {2: "pending", 3: "sent"})
        self.answer(messenger, row, 3, self.skill["id"], 4)
        self.assertFalse(collections.report(self.db, row)["can_finalize"])
        busy = self.db.scalar(select(ScenarioProgress).where(ScenarioProgress.scenario_key == "busy"))
        busy.waiting_for_response, busy.is_completed = False, True
        self.db.commit()
        asyncio.run(collections.process_pending(messenger, session_factory=self.sessions))
        self.db.expire_all()
        self.answer(messenger, row, 2, self.skill["id"], 5)
        self.assertEqual(collections.report(self.db, row)["categories"][0]["current"], 4)
        self.assertTrue(collections.report(self.db, row)["can_finalize"])

    def test_template_frozen_and_request_replay_checked(self):
        self.prepare()
        data = dict(request_id=str(uuid4()), specialization_id=self.spec["id"], recipient_ids=[2, 3])
        row = collections.create(self.db, 1, 1, data)
        self.assertEqual(collections.create(self.db, 1, 1, data).id, row.id)
        with self.assertRaises(grades.GradeConflictError):
            collections.create(self.db, 1, 1, dict(data, recipient_ids=[2]))
        self.assertEqual(json.loads(row.snapshot_json)["scores"][0]["skillName"], "Interview")
        grades.save_catalog_item(self.db, "skills", {"name": "Renamed skill", "category_id": self.cat["id"]}, item_id=self.skill["id"])
        self.db.flush()
        self.assertEqual(collections.report(self.db, row)["scores"][0]["skillName"], "Interview")
        with self.assertRaises(ValueError):
            collections.finalize(self.db, 1, row.id, 1)

    def test_open_questions_and_individual_details_survive_finalization_and_correction(self):
        from types import SimpleNamespace
        from app.scenario_engine import handle_text_response
        self.prepare()
        row = collections.create(self.db, 1, 1, dict(request_id=str(uuid4()), specialization_id=self.spec["id"],
            recipient_ids=[2, 3], open_questions=["Что получается хорошо?"]))
        self.db.commit()
        messenger = ReviewMessenger()
        asyncio.run(collections.process_pending(messenger, session_factory=self.sessions))
        self.db.expire_all()
        self.answer(messenger, row, 2, self.skill["id"], 2)
        self.assertEqual(collections.report(self.db, row)["completed_count"], 0)
        asyncio.run(handle_text_response(messenger, self.db, self.db.get(Employee, 2), SimpleNamespace(text="Хорошо объясняет решения")))
        self.assertIsNone(collections.report(self.db, row)["reviewers"][0]["comments"][0]["answer"])
        self.assertTrue(self.confirm(messenger, row, 2, 0, len(messenger.texts)))
        first = collections.report(self.db, row)
        self.assertEqual(first["completed_count"], 1)
        self.assertEqual(first["scores"][0]["currentLevel"], 2)
        self.assertEqual(first["reviewers"][0]["comments"][0]["answer"], "Хорошо объясняет решения")
        self.answer(messenger, row, 3, self.skill["id"], 4)
        asyncio.run(handle_text_response(messenger, self.db, self.db.get(Employee, 3), SimpleNamespace(text="Помогает команде")))
        self.assertTrue(self.confirm(messenger, row, 3, 0, len(messenger.texts)))
        result = collections.report(self.db, row)
        self.assertEqual(result["scores"][0]["currentLevel"], 3)
        self.assertTrue(result["can_finalize"])
        final = collections.finalize(self.db, 1, row.id, 1, dict(current_grade_id=2, comment="Решение HR"))
        self.db.commit()
        self.assertEqual(final["current_grade_id"], 2)
        self.assertEqual(final["colleague_reviews"][1]["comments"][0]["answer"], "Помогает команде")
        editable = view(self.db, final["id"])
        changed = correct(self.db, final["id"], 1, dict(request_id=str(uuid4()), expected_token=editable["edit_token"], reason="Уточнение решения", values=[], current_grade_id=1))
        self.assertEqual(changed["colleague_reviews"], final["colleague_reviews"])
        self.assertEqual(changed["current_grade_id"], 1)
        with self.assertRaises(ValueError):
            collections.finalize(self.db, 1, row.id, 1, dict(current_grade_id=2))

    def test_open_question_validation_and_template_freezing(self):
        self.prepare()
        data = dict(request_id=str(uuid4()), specialization_id=self.spec["id"], recipient_ids=[2, 3])
        for invalid in ("not a list", [""], ["x" * 2001], ["a"] * 21, [None]):
            with self.assertRaises(ValueError):
                collections.create(self.db, 1, 1, dict(data, open_questions=invalid))
        row = collections.create(self.db, 1, 1, dict(data, open_questions=["<b>Комментарий</b>"]))
        question = self.db.scalar(select(FlowStepTemplate).where(FlowStepTemplate.flow_key == row.scenario_key, FlowStepTemplate.step_key == "open_0"))
        self.assertEqual(question.response_type, "text")
        self.assertIn("&lt;b&gt;", question.default_text)
        self.assertEqual(collections.report(self.db, row)["reviewers"][0]["comments"][0]["answer"], None)

    def test_finalization_does_not_overwrite_concurrent_hr_grade(self):
        self.prepare()
        row = self.create()
        grades.update_employee_grade(self.db, 1, dict(specialization_id=self.spec["id"], current_grade_id=2,
            target_grade_id=None, target_specialization_id=None, comment="Other HR"), actor_id=1)
        self.db.commit()
        with self.assertRaises(grades.GradeConflictError):
            collections.finalize(self.db, 1, row.id, 1, dict(current_grade_id=1, expected_current_grade_id=None))
        self.assertIsNone(row.assessment_id)

    def test_new_personnel_grade_keeps_label_without_changing_frozen_matrix(self):
        self.prepare()
        row = self.create()
        new_grade = grades.save_catalog_item(self.db, "grades", dict(name="Principal", slug="principal", rank=5))
        grades.update_employee_grade(self.db, 1, dict(specialization_id=self.spec["id"], current_grade_id=new_grade["id"],
            target_grade_id=None, target_specialization_id=None, comment="Decision"), actor_id=1)
        self.db.commit()
        self.assertIn(new_grade["id"], [g["id"] for g in collections.report(self.db, row)["grades"]])
        messenger = ReviewMessenger()
        asyncio.run(collections.process_pending(messenger, session_factory=self.sessions))
        self.db.expire_all()
        self.answer(messenger, row, 2, self.skill["id"], 2)
        self.answer(messenger, row, 3, self.skill["id"], 3)
        final = collections.finalize(self.db, 1, row.id, 1, dict(current_grade_id=new_grade["id"], expected_current_grade_id=new_grade["id"]))
        self.assertIn("Principal", [g["name"] for g in final["catalog"]["grades"]])
        self.assertNotIn(new_grade["id"], [g["grade_id"] for g in final["recommendation"]["levels"]])

    def test_ambiguous_delivery_is_not_automatically_retried(self):
        self.prepare()
        row = self.create()
        messenger = FakeMessenger()
        from unittest.mock import AsyncMock
        messenger.send_text = AsyncMock(side_effect=RuntimeError("network"))
        asyncio.run(collections.process_pending(messenger, session_factory=self.sessions))
        count = messenger.send_text.await_count
        asyncio.run(collections.process_pending(messenger, session_factory=self.sessions))
        self.assertEqual(messenger.send_text.await_count, count)
        self.db.expire_all()
        statuses = list(self.db.scalars(select(EmployeeFeedbackRecipient.delivery_status).where(EmployeeFeedbackRecipient.run_id == row.feedback_run_id)))
        self.assertEqual(statuses, ["starting", "starting"])

    def test_optional_multiple_actions_and_reminder_only_stage(self):
        self.prepare()
        first = grades.save_review(self.db, 1, 1, self.review_request())
        self.db.commit()
        from app.grades.development import payload
        configured = development_actions.configure(self.db, 1, 1, dict(expected_revision=0, assessment_id=first["id"], anchor_date="2026-11-03", enabled=True,
            actions=dict(ipr6=[], ipr12=[dict(key=str(uuid4()), type="review", specialization_id=self.spec["id"], recipient_ids=[2, 3]), dict(key=str(uuid4()), type="review", specialization_id=self.spec["id"], recipient_ids=[2])], review12=[])))
        self.db.commit()
        self.assertEqual(len(next(m for m in configured["milestones"] if m["kind"] == "ipr12")["actions"]), 2)
        self.assertEqual(len(list(self.db.scalars(select(GradeDevelopmentAction)))), 4)
        self.assertTrue(payload(self.db, 1)["enabled"])
        from app.grades import development
        stage = self.db.scalar(select(development.Milestone).where(development.Milestone.kind == "ipr12"))
        with patch.object(development, "local_now", return_value=datetime(2027, 11, 4)), patch.object(development, "SessionLocal", self.sessions):
            asyncio.run(development._process_one(FakeMessenger(), stage.id))
        self.db.expire_all()
        self.assertEqual(len(collections.list_reports(self.db, 1)), 2)
        next_review = grades.save_review(self.db, 1, 1, self.review_request())
        self.db.commit()
        renewed = payload(self.db, 1)
        self.assertEqual(renewed["assessment_id"], next_review["id"])
        self.assertEqual(len(next(m for m in renewed["milestones"] if m["kind"] == "ipr12")["actions"]), 2)

    def test_new_midyear_review_is_rejected(self):
        self.prepare()
        choice = dict(key=str(uuid4()), type="review", specialization_id=self.spec["id"], recipient_ids=[2])
        with self.assertRaisesRegex(ValueError, "6 месяцев"):
            development_actions.validate(self.db, self.db.get(Employee, 1), dict(ipr6=[choice], ipr12=[], review12=[]))

    def test_annual_360_launch_is_idempotent_and_hr_selects_team(self):
        from app.grades import development
        from app.models import AdminAccount

        self.prepare()
        employee = self.db.get(Employee, 1)
        employee.manager_employee_id = 2
        set_primary_chat_id(employee, "700001001", db=self.db)
        first = grades.save_review(self.db, 1, 1, self.review_request())
        if not self.db.get(AdminAccount, 1):
            self.db.add(AdminAccount(id=1, login="test-hr", password_hash="unused", role="hr", is_active=True,
                                     created_at=utc_now(), updated_at=utc_now()))
        self.db.commit()
        choice = dict(key=str(uuid4()), type="review360", specialization_id=self.spec["id"])
        development_actions.configure(self.db, 1, 1, dict(expected_revision=0, assessment_id=first["id"],
            anchor_date="2026-11-03", enabled=True, actions=dict(ipr6=[], ipr12=[], review12=[choice])))
        self.db.commit()
        stage = self.db.scalar(select(development.Milestone).where(development.Milestone.kind == "review12"))
        with patch.object(collections.settings, "GRADE_REVIEW_WEBAPP_URL", "https://example.test/grade-review"), \
                patch.object(development, "local_now", return_value=datetime(2027, 11, 4)), \
                patch.object(development, "SessionLocal", self.sessions):
            asyncio.run(development._process_one(FakeMessenger(), stage.id))
            asyncio.run(development._process_one(FakeMessenger(), stage.id))
        self.db.expire_all()
        run, = collections.list_reports(self.db, 1)
        self.assertEqual([r["employee_id"] for r in run["reviewers"]], [1, 2])
        self.assertFalse(run["can_finalize"])
        with self.assertRaises(ValueError):
            collections.select_review_team(self.db, 1, run["id"], [2])
        result = collections.select_review_team(self.db, 1, run["id"], [3])
        self.assertTrue(result["review_360"]["team_selected"])
        self.assertEqual([r["employee_id"] for r in result["reviewers"]], [1, 2, 3])

    def test_uncertain_delivery_reserves_respondent_across_collections(self):
        self.prepare()
        first = self.create()
        second = self.create()
        recipient = self.db.scalar(select(EmployeeFeedbackRecipient).where(
            EmployeeFeedbackRecipient.run_id == first.feedback_run_id,
            EmployeeFeedbackRecipient.respondent_employee_id == 2))
        recipient.delivery_status = "starting"
        self.db.commit()
        asyncio.run(collections.process_pending(FakeMessenger(), session_factory=self.sessions))
        self.db.expire_all()
        pending = self.db.scalar(select(EmployeeFeedbackRecipient).where(
            EmployeeFeedbackRecipient.run_id == second.feedback_run_id,
            EmployeeFeedbackRecipient.respondent_employee_id == 2))
        self.assertEqual(pending.delivery_status, "pending")

    def test_mixed_scenario_feedback_review_stage_claimed_once(self):
        self.prepare()
        subject = self.db.get(Employee, 1)
        set_primary_chat_id(subject, "700001001", db=self.db)
        first = grades.save_review(self.db, 1, 1, self.review_request())
        for key, kind in (("plain", "scenario"), ("feedback", "survey")):
            self.db.add(ScenarioTemplate(scenario_key=key, scenario_kind=kind, title=key, trigger_mode="manual_only", role_scope="all", employee_scope="employees", recipient_mode="self"))
            self.db.add(FlowStepTemplate(flow_key=key, step_key="q", step_title="Question", default_text="Question", response_type="text" if kind == "survey" else "none", target_field="survey_answer" if kind == "survey" else None, send_mode="immediate", is_terminal=True))
        self.db.commit()
        actions = dict(ipr6=[], ipr12=[dict(key=str(uuid4()), type="scenario", scenario_key="plain"), dict(key=str(uuid4()), type="feedback", scenario_key="feedback", recipient_ids=[2]), dict(key=str(uuid4()), type="review", specialization_id=self.spec["id"], recipient_ids=[3])], review12=[])
        development_actions.configure(self.db, 1, 1, dict(expected_revision=0, assessment_id=first["id"], anchor_date="2026-11-03", enabled=True, actions=actions))
        self.db.commit()
        from app.grades import development
        self.assertTrue(development.owns_scenario(self.db, 1, "plain"))
        stage = self.db.scalar(select(development.Milestone).where(development.Milestone.kind == "ipr12"))
        messenger = FakeMessenger()
        with patch.object(development, "local_now", return_value=datetime(2027, 11, 4)), patch.object(development, "SessionLocal", self.sessions):
            asyncio.run(development._process_one(messenger, stage.id))
            asyncio.run(collections.process_pending(messenger, session_factory=self.sessions))
            calls = len(messenger.texts)
            asyncio.run(development._process_one(messenger, stage.id))
            asyncio.run(collections.process_pending(messenger, session_factory=self.sessions))
            self.assertEqual(len(messenger.texts), calls)
        self.db.expire_all()
        self.assertEqual({r.status for r in self.db.scalars(select(GradeDevelopmentAction).where(GradeDevelopmentAction.milestone_id == stage.id))}, {"started"})

    def test_legacy_started_stage_can_be_preserved_while_editing_future_actions(self):
        self.prepare()
        first = grades.save_review(self.db, 1, 1, self.review_request())
        self.db.add(ScenarioTemplate(scenario_key="legacy", scenario_kind="scenario", title="Legacy", trigger_mode="manual_only", role_scope="all", employee_scope="employees", recipient_mode="self"))
        self.db.add(FlowStepTemplate(flow_key="legacy", step_key="done", step_title="Done", default_text="Done", response_type="none", send_mode="immediate", is_terminal=True))
        self.db.commit()
        from app.grades import development
        development.configure(self.db, 1, dict(expected_revision=0, assessment_id=first["id"], anchor_date="2026-11-03", enabled=False,
            **{k + "_scenario_key": "legacy" for k in development.KINDS}))
        stage = self.db.scalar(select(development.Milestone).where(development.Milestone.kind == "ipr6"))
        stage.status = "started"
        self.db.commit()
        key = str(uuid4())
        result = development_actions.configure(self.db, 1, 1, dict(expected_revision=1, assessment_id=first["id"], anchor_date="2026-11-03", enabled=False,
            actions=dict(ipr6=[dict(key=key, type="scenario", scenario_key="legacy")], ipr12=[], review12=[])))
        self.db.commit()
        self.assertEqual(result["milestones"][0]["status"], "started")
        self.assertEqual(result["milestones"][0]["actions"][0]["status"], "started")
        result = development_actions.configure(self.db, 1, 1, dict(expected_revision=2, assessment_id=first["id"], anchor_date="2026-11-03", enabled=False,
            actions=dict(ipr6=[dict(key=key, type="scenario", scenario_key="legacy")], ipr12=[], review12=[])))
        self.db.commit()
        self.assertEqual(result["revision"], 3)
