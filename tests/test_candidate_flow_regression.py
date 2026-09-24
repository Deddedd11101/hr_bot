"""Сквозная регрессия критического пути кандидата.

Существующие тесты проверяют звенья по отдельности: постановку launch request
при смене статуса, приём файла/ссылки на шаге тестового, завершение terminal-шага.
Здесь тот же путь проходится целиком через реальные точки входа — API карточки,
тик планировщика, обработчики бота — и проверяется главное продуктовое
требование: каждый шаг доставляется ровно один раз, данные сохраняются,
после финала бот молчит.
"""

import unittest
from unittest.mock import AsyncMock
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import GetFile

from app import bot_runner
from app.auth import authenticate_account, create_admin_session_token
from app.config import settings
from app.database import SessionLocal, init_db
from app.main import AUTH_COOKIE_NAME, app
from app.messaging.identity import set_primary_chat_id
from app.messaging.service import handle_text_event
from app.models import (
    Employee,
    EmployeeDocumentLink,
    EmployeeFile,
    EmployeeMessengerAccount,
    FlowLaunchRequest,
    FlowStepTemplate,
    OnboardingEvent,
    ScenarioProgress,
    ScenarioTemplate,
)
from app.scenario_engine import extract_test_task_answer_link
from app.scheduler import schedule_all_employees


class _FakeScheduler:
    def __init__(self) -> None:
        self.jobs: dict[str, dict] = {}

    def get_job(self, job_id: str):
        return self.jobs.get(job_id)

    def add_job(self, func, trigger, run_date, args, id, replace_existing=False):
        if not replace_existing and id in self.jobs:
            return
        self.jobs[id] = {"func": func, "run_date": run_date, "args": args}


class _RecordingMessenger:
    """Запоминает всё, что бот отправил, по chat_id — включая медиа и меню."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []
        self.closed = False

    def texts_for(self, chat_id: str) -> list[str]:
        return [text for target, text in self.sent if target == chat_id]

    async def send_text(self, chat_id: str, text: str, reply_markup=None) -> None:
        self.sent.append((chat_id, text))

    async def edit_text(self, chat_id: str, message_id: int, text: str, reply_markup=None) -> None:
        self.sent.append((chat_id, f"[edit] {text}"))

    async def send_menu(self, chat_id: str, text: str, buttons) -> None:
        self.sent.append((chat_id, text))

    async def send_inline_menu(self, chat_id: str, text: str, buttons):
        self.sent.append((chat_id, text))
        return SimpleNamespace(message_id=1)

    async def edit_inline_menu(self, chat_id: str, message_id: int, text: str, buttons):
        self.sent.append((chat_id, f"[edit] {text}"))

    async def delete_message(self, chat_id: str, message_id: int):
        return None

    async def send_photo_path(self, chat_id: str, path, filename=None, reply_markup=None, caption=None) -> None:
        self.sent.append((chat_id, f"[photo] {caption or ''}"))

    async def send_photo_bytes(self, chat_id: str, data: bytes, filename: str, reply_markup=None, caption=None) -> None:
        self.sent.append((chat_id, f"[photo-bytes] {caption or ''}"))

    async def send_document_path(self, chat_id: str, path, filename=None, reply_markup=None, caption=None) -> None:
        self.sent.append((chat_id, f"[document] {caption or ''}"))

    async def close(self) -> None:
        self.closed = True


class _FakeTelegramBot:
    async def get_file(self, file_id: str):
        return SimpleNamespace(file_path=f"telegram/{file_id}")

    async def download_file(self, file_path: str, destination):
        Path(destination).write_bytes(f"downloaded:{file_path}".encode("utf-8"))


STEP_INTRO = "Привет! Впереди тестовое задание."
STEP_TASK = "Пришлите результат тестового: файл, видео или ссылку."
STEP_FINAL = "Спасибо, тестовое получено. Вернёмся с ответом."
STEP_NEVER = "ЭТОТ ШАГ НЕ ДОЛЖЕН ОТПРАВЛЯТЬСЯ"


def _employee_payload(candidate_work_stage: str, chat_id: str, *, is_bot_blocked: bool = False) -> dict:
    # chat_id передаётся как в реальной карточке: пустое значение сбросило бы привязку.
    return {
        "full_name": "Кандидат Регрессия",
        "chat_id": chat_id,
        "chat_handle": "",
        "first_workday": "",
        "desired_position": "Аналитик",
        "birth_date": "",
        "work_email": "",
        "work_hours": "",
        "manager_employee_id": "",
        "mentor_adaptation_employee_id": "",
        "mentor_ipr_employee_id": "",
        "adaptation_tasks_url": "",
        "adaptation_feedback_url": "",
        "adaptation_midpoint": "",
        "adaptation_end": "",
        "employee_stage": "candidate",
        "candidate_work_stage": candidate_work_stage,
        "salary_expectation": "",
        "personal_data_consent": False,
        "employee_data_consent": False,
        "is_bot_blocked": is_bot_blocked,
        "test_task_due_at": "",
        "notes": "",
    }


class CandidateFlowRegressionTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        init_db()
        cls.client = TestClient(app)
        with SessionLocal() as db:
            account = authenticate_account(db, "admin", "admin123")
            if account is None:
                raise AssertionError("Admin account is not available.")
            cls.client.cookies.set(AUTH_COOKIE_NAME, create_admin_session_token(account.id))

    def setUp(self) -> None:
        self.tag = uuid4().hex[:8]
        self.chat_id = str(900000000 + int(self.tag[:6], 16) % 90000000)
        self.scenario_key = f"regress_testing_{self.tag}"
        self.messenger = _RecordingMessenger()
        self.scheduler = _FakeScheduler()
        self._previous_factory = bot_runner.create_telegram_messenger
        bot_runner.create_telegram_messenger = lambda _token: self.messenger
        self._tmpdir = TemporaryDirectory()
        self._previous_storage_dir = settings.FILE_STORAGE_DIR
        settings.FILE_STORAGE_DIR = self._tmpdir.name
        with SessionLocal() as db:
            employee = Employee(
                full_name="Кандидат Регрессия",
                telegram_user_id=None,
                telegram_username=None,
                first_workday=None,
                created_at=datetime.now(UTC).replace(tzinfo=None),
                is_flow_scheduled=False,
                candidate_status="new",
                employee_stage="candidate",
                candidate_work_stage="hr_interview",
                desired_position="Аналитик",
            )
            scenario = ScenarioTemplate(
                scenario_key=self.scenario_key,
                title=f"Тестовое задание {self.tag}",
                sort_order=10,
                scenario_kind="scenario",
                role_scope="all",
                employee_scope="candidates",
                trigger_mode="candidate_hr_stage",
                candidate_work_stage_trigger="testing",
                target_employee_id=None,
                description="candidate flow regression",
            )
            db.add_all([employee, scenario])
            db.flush()
            steps = [
                FlowStepTemplate(flow_key=self.scenario_key, step_key="intro", step_title="Интро", sort_order=10,
                                 default_text=STEP_INTRO, response_type="none", send_mode="immediate", day_offset_workdays=0),
                FlowStepTemplate(flow_key=self.scenario_key, step_key="task", step_title="Тестовое", sort_order=20,
                                 default_text=STEP_TASK, response_type="file", target_field="test_task_result",
                                 send_mode="immediate", day_offset_workdays=0),
                FlowStepTemplate(flow_key=self.scenario_key, step_key="final", step_title="Финал", sort_order=30,
                                 default_text=STEP_FINAL, response_type="none", send_mode="immediate",
                                 day_offset_workdays=0, is_terminal=True),
                FlowStepTemplate(flow_key=self.scenario_key, step_key="never", step_title="После финала", sort_order=40,
                                 default_text=STEP_NEVER, response_type="none", send_mode="immediate", day_offset_workdays=0),
            ]
            db.add_all(steps)
            db.flush()
            set_primary_chat_id(employee, self.chat_id, db=db)
            db.commit()
            self.employee_id = employee.id

    def tearDown(self) -> None:
        bot_runner.create_telegram_messenger = self._previous_factory
        settings.FILE_STORAGE_DIR = self._previous_storage_dir
        self._tmpdir.cleanup()
        with SessionLocal() as db:
            for model in (OnboardingEvent, ScenarioProgress, FlowLaunchRequest, EmployeeDocumentLink, EmployeeFile):
                db.query(model).filter(model.employee_id == self.employee_id).delete(synchronize_session=False)
            db.query(FlowStepTemplate).filter(FlowStepTemplate.flow_key == self.scenario_key).delete(synchronize_session=False)
            db.query(ScenarioTemplate).filter(ScenarioTemplate.scenario_key == self.scenario_key).delete(synchronize_session=False)
            db.query(EmployeeMessengerAccount).filter(EmployeeMessengerAccount.employee_id == self.employee_id).delete(synchronize_session=False)
            employee = db.get(Employee, self.employee_id)
            if employee is not None:
                db.delete(employee)
            db.commit()

    # ------------------------------------------------------------------ helpers
    def _set_stage(self, stage: str, *, is_bot_blocked: bool = False) -> None:
        response = self.client.post(
            f"/api/employees/{self.employee_id}",
            json=_employee_payload(stage, self.chat_id, is_bot_blocked=is_bot_blocked),
        )
        self.assertEqual(response.status_code, 200, response.text)

    def _pending_requests(self) -> list[FlowLaunchRequest]:
        with SessionLocal() as db:
            return (
                db.query(FlowLaunchRequest)
                .filter(
                    FlowLaunchRequest.employee_id == self.employee_id,
                    FlowLaunchRequest.flow_key == self.scenario_key,
                    FlowLaunchRequest.processed_at.is_(None),
                )
                .all()
            )

    def _progress(self) -> ScenarioProgress | None:
        with SessionLocal() as db:
            return (
                db.query(ScenarioProgress)
                .filter_by(employee_id=self.employee_id, scenario_key=self.scenario_key)
                .first()
            )

    async def _tick(self) -> None:
        await schedule_all_employees(self.scheduler, self.messenger)

    async def _reach_task_step(self) -> None:
        """Статус -> тик -> кандидат получил интро и вопрос про тестовое, бот ждёт файл."""
        self._set_stage("testing")
        self.assertEqual(len(self._pending_requests()), 1)
        await self._tick()
        self.assertEqual(self.messenger.texts_for(self.chat_id), [STEP_INTRO, STEP_TASK])
        progress = self._progress()
        self.assertIsNotNone(progress)
        self.assertEqual(progress.current_step_key, "task")
        self.assertTrue(progress.waiting_for_response)
        self.assertFalse(progress.is_completed)

    def _photo_message(self, file_id: str):
        return SimpleNamespace(
            from_user=SimpleNamespace(id=self.chat_id, username=None),
            caption=None,
            photo=[SimpleNamespace(file_id=file_id, file_unique_id=f"{file_id}-unique", file_size=111)],
        )

    def _assert_finished_after_task_answer(self) -> None:
        progress = self._progress()
        self.assertIsNotNone(progress)
        self.assertTrue(progress.is_completed)
        self.assertIsNotNone(progress.completed_at)
        self.assertFalse(progress.waiting_for_response)
        texts = self.messenger.texts_for(self.chat_id)
        self.assertEqual(texts.count(STEP_FINAL), 1, texts)
        self.assertNotIn(STEP_NEVER, texts)
        with SessionLocal() as db:
            slot = (
                db.query(EmployeeDocumentLink)
                .filter(EmployeeDocumentLink.employee_id == self.employee_id, EmployeeDocumentLink.slot_key == "test_task_result")
                .first()
            )
            self.assertIsNotNone(slot, "актуальный слот ответа на тестовое не записан")

    # ------------------------------------------------------------------- flow 1
    async def test_status_change_launches_scenario_exactly_once(self) -> None:
        await self._reach_task_step()
        self.assertEqual(self._pending_requests(), [])

        # Повторный тик и повторное сохранение карточки с тем же статусом ничего не шлют.
        await self._tick()
        self._set_stage("testing")
        await self._tick()
        self.assertEqual(self.messenger.texts_for(self.chat_id), [STEP_INTRO, STEP_TASK])
        self.assertEqual(self._pending_requests(), [])

    async def test_status_flip_before_tick_starts_only_the_current_stage_scenario(self) -> None:
        # HR поставил «Тестирование», тут же передумал и вернул «Собеседование с HR»:
        # запрос устарел, сценарий тестового стартовать не должен.
        self._set_stage("testing")
        self._set_stage("hr_interview")
        await self._tick()
        self.assertEqual(self.messenger.texts_for(self.chat_id), [])
        self.assertEqual(self._pending_requests(), [])
        self.assertIsNone(self._progress())

    async def test_blocked_candidate_does_not_receive_scenario(self) -> None:
        # Блокировка и смена статуса сохраняются одной карточкой — как это делает HR.
        self._set_stage("testing", is_bot_blocked=True)
        await self._tick()
        self.assertEqual(self.messenger.texts_for(self.chat_id), [])
        self.assertEqual(self._pending_requests(), [])

    # ------------------------------------------------------------------- flow 2

    async def test_link_with_prose_saves_url(self) -> None:
        await self._reach_task_step()
        answer = "Готово: https://example.com/answer?x=1&y=2 спасибо"
        with SessionLocal() as db:
            await handle_text_event(self.messenger, db, self.chat_id, None, answer)
            slot = db.query(EmployeeDocumentLink).filter_by(employee_id=self.employee_id, slot_key="test_task_result").one()
            self.assertEqual(slot.url, "https://example.com/answer?x=1&y=2")
        self._assert_finished_after_task_answer()

    async def test_text_mode_test_result_accepts_link(self) -> None:
        with SessionLocal() as db:
            step = db.query(FlowStepTemplate).filter_by(flow_key=self.scenario_key, step_key="task").one()
            step.response_type = "text"
            db.commit()
        await self.test_link_with_prose_saves_url()

    async def test_text_mode_test_result_accepts_document(self) -> None:
        with SessionLocal() as db:
            step = db.query(FlowStepTemplate).filter_by(flow_key=self.scenario_key, step_key="task").one()
            step.response_type = "text"
            db.commit()
        await self._reach_task_step()
        message = SimpleNamespace(from_user=SimpleNamespace(id=self.chat_id, username=None), caption=None,
            document=SimpleNamespace(file_id="word", file_unique_id="word", file_size=18000,
                file_name="answer.docx", mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"))
        await bot_runner.on_document(message, _FakeTelegramBot())
        self._assert_finished_after_task_answer()
        payload = self.client.get(f"/api/employees/{self.employee_id}").json()
        self.assertEqual(payload["test_task_result"]["kind"], "file")
        self.assertIn("answer.docx", payload["test_task_result"]["label"])
        self.assertTrue(payload["test_task_result"]["download_url"])

    async def test_multiple_links_keep_waiting_without_slot(self) -> None:
        await self._reach_task_step()
        with SessionLocal() as db:
            await handle_text_event(self.messenger, db, self.chat_id, None, "https://example.com/a https://example.com/b")
            self.assertIsNone(db.query(EmployeeDocumentLink).filter_by(employee_id=self.employee_id, slot_key="test_task_result").first())
        self.assertTrue(self._progress().waiting_for_response)

    async def test_oversized_document_stays_waiting_without_download(self) -> None:
        await self._reach_task_step()
        bot = SimpleNamespace(get_file=AsyncMock(), download_file=AsyncMock())
        message = SimpleNamespace(from_user=SimpleNamespace(id=self.chat_id, username=None), caption=None,
            document=SimpleNamespace(file_id="large", file_unique_id="large", file_size=32600000,
                file_name="answer.mp4", mime_type="video/mp4"))
        await bot_runner.on_document(message, bot)
        bot.get_file.assert_not_awaited()
        bot.download_file.assert_not_awaited()
        self.assertTrue(self._progress().waiting_for_response)
        self.assertIn(bot_runner.OVERSIZED_FILE_TEXT, self.messenger.texts_for(self.chat_id))
        with SessionLocal() as db:
            self.assertEqual(db.query(EmployeeFile).filter_by(employee_id=self.employee_id).count(), 0)

    async def test_unknown_size_too_big_and_partial_download_errors_keep_waiting(self) -> None:
        await self._reach_task_step()
        message = SimpleNamespace(from_user=SimpleNamespace(id=self.chat_id, username=None), caption=None,
            document=SimpleNamespace(file_id="unknown", file_unique_id="unknown", file_size=None,
                file_name="answer.mp4", mime_type="video/mp4"))
        bot = SimpleNamespace(get_file=AsyncMock(side_effect=TelegramBadRequest(
            method=GetFile(file_id="unknown"), message="Bad Request: file is too big")), download_file=AsyncMock())
        await bot_runner.on_document(message, bot)
        self.assertIn(bot_runner.OVERSIZED_FILE_TEXT, self.messenger.texts_for(self.chat_id))
        bot.download_file.assert_not_awaited()

        async def failed_download(file_path, destination):
            Path(destination).write_bytes(b"partial")
            raise OSError("synthetic download failure")

        bot.get_file = AsyncMock(return_value=SimpleNamespace(file_path="remote/test"))
        bot.download_file = failed_download
        await bot_runner.on_document(message, bot)
        self.assertEqual(list(Path(self._tmpdir.name).rglob("*.mp4")), [])
        self.assertTrue(self._progress().waiting_for_response)
        self.assertTrue(self.messenger.closed)
        with SessionLocal() as db:
            self.assertEqual(db.query(EmployeeFile).filter_by(employee_id=self.employee_id).count(), 0)

    async def test_back_restores_previous_test_result_after_link_answer(self) -> None:
        from app.scenario_engine import handle_back_response
        with SessionLocal() as db:
            final = db.query(FlowStepTemplate).filter_by(flow_key=self.scenario_key, step_key="final").one()
            final.response_type = "text"
            db.add(EmployeeDocumentLink(employee_id=self.employee_id, slot_key="test_task_result",
                title="Previous result", item_kind="link", url="https://example.com/previous",
                created_at=datetime.now(UTC).replace(tzinfo=None)))
            db.commit()
        await self._reach_task_step()
        with SessionLocal() as db:
            await handle_text_event(self.messenger, db, self.chat_id, None, "Result https://example.com/new")
            employee = db.get(Employee, self.employee_id)
            self.assertTrue(await handle_back_response(self.messenger, db, employee))
            slot = db.query(EmployeeDocumentLink).filter_by(employee_id=self.employee_id, slot_key="test_task_result").one()
            self.assertEqual(slot.url, "https://example.com/previous")

    def test_answer_url_extraction_is_unambiguous(self) -> None:
        self.assertEqual(extract_test_task_answer_link("Готово (https://example.com/result)."), "https://example.com/result")
        self.assertEqual(extract_test_task_answer_link("https://example.com/a_(b)"), "https://example.com/a_(b)")
        for value in ("no link", "https://", "https://user:secret@example.com", "https://example.com:abc", "javascript:alert(1)"):
            self.assertIsNone(extract_test_task_answer_link(value), value)

    def test_workspace_rejects_text_file_destination_without_changing_step(self) -> None:
        with SessionLocal() as db:
            step = db.query(FlowStepTemplate).filter_by(flow_key=self.scenario_key, step_key="task").one()
            step_id = step.id
        result = self.client.post(f"/api/flows/workspace/steps/{step_id}", json={"response_type": "text", "target_field": "candidate_file"})
        self.assertEqual(result.status_code, 422, result.text)
        with SessionLocal() as db:
            self.assertEqual(db.get(FlowStepTemplate, step_id).target_field, "test_task_result")
            self.assertEqual(db.get(FlowStepTemplate, step_id).response_type, "file")
    async def test_photo_answer_saves_slot_and_finishes_scenario(self) -> None:
        await self._reach_task_step()
        await bot_runner.on_photo(self._photo_message("photo-1"), _FakeTelegramBot())
        self._assert_finished_after_task_answer()
        with SessionLocal() as db:
            file_row = (
                db.query(EmployeeFile)
                .filter(EmployeeFile.employee_id == self.employee_id)
                .order_by(EmployeeFile.id.desc())
                .first()
            )
            self.assertIsNotNone(file_row)
            self.assertEqual(file_row.category, "test_result")

    async def test_video_answer_saves_slot_and_finishes_scenario(self) -> None:
        await self._reach_task_step()
        message = SimpleNamespace(
            from_user=SimpleNamespace(id=self.chat_id, username=None),
            caption=None,
            video=SimpleNamespace(file_id="video-1", file_unique_id="video-1-unique", file_size=222,
                                  mime_type="video/mp4", file_name="answer.mp4"),
        )
        await bot_runner.on_video(message, _FakeTelegramBot())
        self._assert_finished_after_task_answer()

    async def test_link_answer_saves_slot_and_finishes_scenario(self) -> None:
        await self._reach_task_step()
        with SessionLocal() as db:
            result = await handle_text_event(self.messenger, db, self.chat_id, None, "https://example.com/answer")
        self.assertEqual(result, "handled")
        self._assert_finished_after_task_answer()

    async def test_plain_text_on_task_step_prompts_and_keeps_waiting(self) -> None:
        await self._reach_task_step()
        with SessionLocal() as db:
            result = await handle_text_event(self.messenger, db, self.chat_id, None, "сделал, отправлю позже")
        self.assertEqual(result, "handled")
        progress = self._progress()
        self.assertEqual(progress.current_step_key, "task")
        self.assertTrue(progress.waiting_for_response)
        texts = self.messenger.texts_for(self.chat_id)
        self.assertEqual(len(texts), 3, texts)  # интро, тестовое, подсказка
        self.assertNotIn(STEP_FINAL, texts)

    # ------------------------------------------------------------------- flow 3
    async def test_terminal_step_ends_scenario_and_bot_stays_silent(self) -> None:
        await self._reach_task_step()
        await bot_runner.on_photo(self._photo_message("photo-final"), _FakeTelegramBot())
        self._assert_finished_after_task_answer()
        sent_before = list(self.messenger.texts_for(self.chat_id))

        # Тик планировщика, лишний текст и второй файл после финала не должны ничего слать.
        await self._tick()
        with SessionLocal() as db:
            result = await handle_text_event(self.messenger, db, self.chat_id, None, "а когда ответ?")
        self.assertEqual(result, "ignored")
        await bot_runner.on_photo(self._photo_message("photo-late"), _FakeTelegramBot())

        self.assertEqual(self.messenger.texts_for(self.chat_id), sent_before)
        self.assertEqual(self._pending_requests(), [])
        self.assertTrue(self._progress().is_completed)

    async def test_returning_to_stage_restarts_scenario_once(self) -> None:
        # Повторный вход в статус — осознанный перезапуск: шаги приходят снова, но один раз.
        await self._reach_task_step()
        await bot_runner.on_photo(self._photo_message("photo-1"), _FakeTelegramBot())
        self._assert_finished_after_task_answer()
        self._set_stage("hr_interview")
        self._set_stage("testing")
        await self._tick()
        await self._tick()
        texts = self.messenger.texts_for(self.chat_id)
        self.assertEqual(texts.count(STEP_INTRO), 2, texts)
        self.assertEqual(texts.count(STEP_TASK), 2, texts)
        self.assertEqual(texts.count(STEP_FINAL), 1, texts)
        progress = self._progress()
        self.assertFalse(progress.is_completed)
        self.assertEqual(progress.current_step_key, "task")


if __name__ == "__main__":
    unittest.main()
