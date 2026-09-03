import unittest
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from tempfile import TemporaryDirectory
from uuid import uuid4

from app import bot_runner
from app.config import settings
from app.database import SessionLocal, init_db
from app.mass_targeting import deserialize_target_values, mass_target_employee_query
from app.messaging.identity import set_primary_chat_id
from app.messaging.service import resolve_inbound_access, save_incoming_file, handle_text_event
from app.models import (
    Employee,
    EmployeeDocumentLink,
    EmployeeFile,
    EmployeeMessengerAccount,
    FlowStepTemplate,
    ScenarioProgress,
    ScenarioTemplate,
)


class _FakeMessenger:
    def __init__(self) -> None:
        self.texts: list[dict] = []
        self.closed = False

    async def send_text(self, *args, **kwargs):
        self.texts.append({"args": args, "kwargs": kwargs})
        return None

    async def send_photo_path(self, *args, **kwargs):
        return None

    async def send_photo_bytes(self, *args, **kwargs):
        return None

    async def send_document_path(self, *args, **kwargs):
        return None

    async def close(self):
        self.closed = True


class _FakeTelegramBot:
    async def get_file(self, file_id: str):
        return SimpleNamespace(file_path=f"telegram/{file_id}")

    async def download_file(self, file_path: str, destination):
        Path(destination).write_bytes(f"downloaded:{file_path}".encode("utf-8"))


class P0BehaviourTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        init_db()

    def setUp(self) -> None:
        self.employee_ids: list[int] = []
        self.scenario_keys: list[str] = []
        unique_suffix = uuid4().hex[:8]
        self.candidate_chat_id = f"tg-{unique_suffix}"
        self.blocked_chat_id = f"blocked-{unique_suffix}"
        with SessionLocal() as db:
            candidate_testing = Employee(
                full_name=f"Candidate Testing {unique_suffix}",
                telegram_user_id=None,
                telegram_username=None,
                first_workday=None,
                created_at=datetime.now(UTC).replace(tzinfo=None),
                is_flow_scheduled=False,
                candidate_status="new",
                employee_stage="candidate",
                candidate_work_stage="testing",
            )
            candidate_offer = Employee(
                full_name=f"Candidate Offer {unique_suffix}",
                telegram_user_id=None,
                telegram_username=None,
                first_workday=None,
                created_at=datetime.now(UTC).replace(tzinfo=None),
                is_flow_scheduled=False,
                candidate_status="new",
                employee_stage="candidate",
                candidate_work_stage="offer",
            )
            employee_staff = Employee(
                full_name=f"Employee Staff {unique_suffix}",
                telegram_user_id=None,
                telegram_username=None,
                first_workday=None,
                created_at=datetime.now(UTC).replace(tzinfo=None),
                is_flow_scheduled=False,
                candidate_status="new",
                employee_stage="staff",
                desired_position="Аналитик",
            )
            blocked_employee = Employee(
                full_name=f"Blocked Employee {unique_suffix}",
                telegram_user_id=None,
                telegram_username=None,
                first_workday=None,
                created_at=datetime.now(UTC).replace(tzinfo=None),
                is_flow_scheduled=False,
                is_bot_blocked=True,
                candidate_status="new",
                employee_stage="staff",
                desired_position="Аналитик",
            )
            db.add_all([candidate_testing, candidate_offer, employee_staff, blocked_employee])
            db.commit()
            db.refresh(candidate_testing)
            db.refresh(candidate_offer)
            db.refresh(employee_staff)
            db.refresh(blocked_employee)
            set_primary_chat_id(candidate_testing, self.candidate_chat_id, db=db)
            set_primary_chat_id(blocked_employee, self.blocked_chat_id, db=db)
            db.commit()
            self.employee_ids = [candidate_testing.id, candidate_offer.id, employee_staff.id, blocked_employee.id]
            self.candidate_testing_id = candidate_testing.id
            self.candidate_offer_id = candidate_offer.id
            self.employee_staff_id = employee_staff.id
            self.blocked_employee_id = blocked_employee.id

    def tearDown(self) -> None:
        with SessionLocal() as db:
            db.query(ScenarioProgress).filter(ScenarioProgress.employee_id.in_(self.employee_ids)).delete(synchronize_session=False)
            db.query(EmployeeFile).filter(EmployeeFile.employee_id.in_(self.employee_ids)).delete(synchronize_session=False)
            db.query(EmployeeDocumentLink).filter(EmployeeDocumentLink.employee_id.in_(self.employee_ids)).delete(synchronize_session=False)
            db.query(EmployeeMessengerAccount).filter(EmployeeMessengerAccount.employee_id.in_(self.employee_ids)).delete(synchronize_session=False)
            if self.scenario_keys:
                db.query(FlowStepTemplate).filter(FlowStepTemplate.flow_key.in_(self.scenario_keys)).delete(synchronize_session=False)
                db.query(ScenarioTemplate).filter(ScenarioTemplate.scenario_key.in_(self.scenario_keys)).delete(synchronize_session=False)
            for employee_id in self.employee_ids:
                employee = db.get(Employee, employee_id)
                if employee is not None:
                    db.delete(employee)
            db.commit()

    def test_mass_targeting_uses_candidate_stage_split(self) -> None:
        with SessionLocal() as db:
            rows = (
                mass_target_employee_query(
                    db,
                    target_all=False,
                    target_employee_stages=[],
                    target_candidate_stages=["testing"],
                )
                .order_by(Employee.id.asc())
                .all()
            )

        matched_ids = [row.id for row in rows if row.id in self.employee_ids]
        self.assertEqual(matched_ids, [self.candidate_testing_id])

    def test_mass_targeting_reads_legacy_candidate_status(self) -> None:
        with SessionLocal() as db:
            rows = (
                mass_target_employee_query(
                    db,
                    target_all=False,
                    target_employee_stages=[],
                    target_candidate_stages=[],
                    legacy_target_statuses=deserialize_target_values("candidate", kind="legacy"),
                )
                .order_by(Employee.id.asc())
                .all()
            )

        matched_ids = [row.id for row in rows if row.id in self.employee_ids]
        self.assertEqual(matched_ids, [self.candidate_testing_id, self.candidate_offer_id])

    def test_resolve_inbound_access_marks_unknown_and_blocked(self) -> None:
        with SessionLocal() as db:
            unknown_access = resolve_inbound_access(db, "unknown-user", "nobody")
            blocked_access = resolve_inbound_access(db, self.blocked_chat_id, None)

        self.assertEqual(unknown_access.state, "unknown")
        self.assertIsNone(unknown_access.employee)
        self.assertEqual(blocked_access.state, "blocked")

    async def test_handle_text_event_ignores_stray_text_for_known_employee(self) -> None:
        with SessionLocal() as db:
            result = await handle_text_event(_FakeMessenger(), db, self.candidate_chat_id, None, "лишний текст")

        self.assertEqual(result, "ignored")

    async def test_save_incoming_file_rejects_unknown_user(self) -> None:
        with SessionLocal() as db:
            before_count = db.query(EmployeeFile).count()
            employee, db_file, state = await save_incoming_file(
                db,
                "unknown-file-user",
                None,
                original_name="resume.pdf",
                stored_path="D:/tmp/resume.pdf",
                category="resume",
                mime_type="application/pdf",
                file_size=123,
            )
            after_count = db.query(EmployeeFile).count()

        self.assertEqual(state, "unknown")
        self.assertIsNone(employee)
        self.assertIsNone(db_file)
        self.assertEqual(before_count, after_count)

    async def test_save_incoming_file_accepts_known_user(self) -> None:
        with SessionLocal() as db:
            employee, db_file, state = await save_incoming_file(
                db,
                self.candidate_chat_id,
                None,
                original_name="portfolio.pdf",
                stored_path="D:/tmp/portfolio.pdf",
                category="candidate_file",
                mime_type="application/pdf",
                file_size=456,
            )

        self.assertEqual(state, "saved")
        self.assertIsNotNone(employee)
        self.assertIsNotNone(db_file)

    def _create_waiting_file_scenario(self, db, scenario_key: str, *, target_field: str = "candidate_file") -> None:
        self.scenario_keys.append(scenario_key)
        scenario = ScenarioTemplate(
            scenario_key=scenario_key,
            title=f"Video answer {scenario_key}",
            sort_order=10,
            scenario_kind="scenario",
            role_scope="all",
            employee_scope="all",
            trigger_mode="manual_only",
        )
        step = FlowStepTemplate(
            flow_key=scenario_key,
            step_key=f"{scenario_key}_file",
            step_title="Файл",
            sort_order=10,
            default_text="Пришлите файл",
            response_type="file",
            send_mode="immediate",
            target_field=target_field,
        )
        db.add_all([scenario, step])
        db.flush()
        db.add(
            ScenarioProgress(
                employee_id=self.candidate_testing_id,
                scenario_key=scenario_key,
                current_step_key=step.step_key,
                waiting_for_response=True,
                is_completed=False,
                started_at=datetime.now(UTC).replace(tzinfo=None),
                updated_at=datetime.now(UTC).replace(tzinfo=None),
                recipient_chat_id=self.candidate_chat_id,
            )
        )
        db.commit()

    async def test_telegram_document_with_video_mime_is_saved_and_counts_as_file_response(self) -> None:
        fake_messenger = _FakeMessenger()
        previous_factory = bot_runner.create_telegram_messenger
        previous_storage_dir = settings.FILE_STORAGE_DIR
        scenario_key = f"video_document_{uuid4().hex[:8]}"
        with TemporaryDirectory() as tmpdir:
            settings.FILE_STORAGE_DIR = tmpdir
            bot_runner.create_telegram_messenger = lambda _token: fake_messenger
            try:
                with SessionLocal() as db:
                    self._create_waiting_file_scenario(db, scenario_key)
                message = SimpleNamespace(
                    from_user=SimpleNamespace(id=self.candidate_chat_id, username=None),
                    caption="тест",
                    document=SimpleNamespace(
                        file_id="doc-video-id",
                        file_unique_id="doc-video-unique",
                        file_name="answer.mp4",
                        mime_type="video/mp4",
                        file_size=321,
                    ),
                )

                await bot_runner.on_document(message, _FakeTelegramBot())

                with SessionLocal() as db:
                    files = (
                        db.query(EmployeeFile)
                        .filter(EmployeeFile.employee_id == self.candidate_testing_id)
                        .order_by(EmployeeFile.id.desc())
                        .all()
                    )
                    progress = db.query(ScenarioProgress).filter_by(employee_id=self.candidate_testing_id, scenario_key=scenario_key).first()
                self.assertTrue(files)
                self.assertEqual(files[0].category, "test_result")
                self.assertEqual(files[0].original_filename, "answer.mp4")
                self.assertEqual(files[0].mime_type, "video/mp4")
                self.assertEqual(files[0].telegram_file_id, "doc-video-id")
                self.assertTrue(Path(files[0].stored_path).exists())
                self.assertIsNotNone(progress)
                self.assertTrue(progress.is_completed)
            finally:
                bot_runner.create_telegram_messenger = previous_factory
                settings.FILE_STORAGE_DIR = previous_storage_dir

    async def test_test_task_document_answer_without_caption_saves_slot_and_counts_as_file_response(self) -> None:
        fake_messenger = _FakeMessenger()
        previous_factory = bot_runner.create_telegram_messenger
        previous_storage_dir = settings.FILE_STORAGE_DIR
        scenario_key = f"test_task_document_{uuid4().hex[:8]}"
        with TemporaryDirectory() as tmpdir:
            settings.FILE_STORAGE_DIR = tmpdir
            bot_runner.create_telegram_messenger = lambda _token: fake_messenger
            try:
                with SessionLocal() as db:
                    self._create_waiting_file_scenario(db, scenario_key, target_field="test_task_result")
                message = SimpleNamespace(
                    from_user=SimpleNamespace(id=self.candidate_chat_id, username=None),
                    caption=None,
                    document=SimpleNamespace(
                        file_id="test-doc-id",
                        file_unique_id="test-doc-unique",
                        file_name="analytics-answer.pdf",
                        mime_type="application/pdf",
                        file_size=321,
                    ),
                )

                await bot_runner.on_document(message, _FakeTelegramBot())

                with SessionLocal() as db:
                    file_row = (
                        db.query(EmployeeFile)
                        .filter(EmployeeFile.employee_id == self.candidate_testing_id)
                        .order_by(EmployeeFile.id.desc())
                        .first()
                    )
                    slot = (
                        db.query(EmployeeDocumentLink)
                        .filter(
                            EmployeeDocumentLink.employee_id == self.candidate_testing_id,
                            EmployeeDocumentLink.slot_key == "test_task_result",
                        )
                        .first()
                    )
                    progress = db.query(ScenarioProgress).filter_by(employee_id=self.candidate_testing_id, scenario_key=scenario_key).first()
                self.assertIsNotNone(file_row)
                self.assertEqual(file_row.category, "test_result")
                self.assertEqual(file_row.original_filename, "analytics-answer.pdf")
                self.assertIsNotNone(slot)
                self.assertEqual(slot.item_kind, "file")
                self.assertEqual(slot.employee_file_id, file_row.id)
                self.assertIsNotNone(progress)
                self.assertTrue(progress.is_completed)
            finally:
                bot_runner.create_telegram_messenger = previous_factory
                settings.FILE_STORAGE_DIR = previous_storage_dir

    async def test_test_task_photo_answer_saves_slot_and_counts_as_file_response(self) -> None:
        fake_messenger = _FakeMessenger()
        previous_factory = bot_runner.create_telegram_messenger
        previous_storage_dir = settings.FILE_STORAGE_DIR
        scenario_key = f"test_task_photo_{uuid4().hex[:8]}"
        with TemporaryDirectory() as tmpdir:
            settings.FILE_STORAGE_DIR = tmpdir
            bot_runner.create_telegram_messenger = lambda _token: fake_messenger
            try:
                with SessionLocal() as db:
                    self._create_waiting_file_scenario(db, scenario_key, target_field="test_task_result")
                message = SimpleNamespace(
                    from_user=SimpleNamespace(id=self.candidate_chat_id, username=None),
                    caption=None,
                    photo=[
                        SimpleNamespace(
                            file_id="photo-id",
                            file_unique_id="photo-unique",
                            file_size=111,
                        )
                    ],
                )

                await bot_runner.on_photo(message, _FakeTelegramBot())

                with SessionLocal() as db:
                    file_row = (
                        db.query(EmployeeFile)
                        .filter(EmployeeFile.employee_id == self.candidate_testing_id)
                        .order_by(EmployeeFile.id.desc())
                        .first()
                    )
                    slot = (
                        db.query(EmployeeDocumentLink)
                        .filter(
                            EmployeeDocumentLink.employee_id == self.candidate_testing_id,
                            EmployeeDocumentLink.slot_key == "test_task_result",
                        )
                        .first()
                    )
                    progress = db.query(ScenarioProgress).filter_by(employee_id=self.candidate_testing_id, scenario_key=scenario_key).first()
                self.assertIsNotNone(file_row)
                self.assertEqual(file_row.category, "test_result")
                self.assertEqual(file_row.mime_type, "image/jpeg")
                self.assertIsNotNone(slot)
                self.assertEqual(slot.employee_file_id, file_row.id)
                self.assertIsNotNone(progress)
                self.assertTrue(progress.is_completed)
            finally:
                bot_runner.create_telegram_messenger = previous_factory
                settings.FILE_STORAGE_DIR = previous_storage_dir

    async def test_test_task_video_answer_without_caption_saves_slot_and_counts_as_file_response(self) -> None:
        fake_messenger = _FakeMessenger()
        previous_factory = bot_runner.create_telegram_messenger
        previous_storage_dir = settings.FILE_STORAGE_DIR
        scenario_key = f"test_task_video_{uuid4().hex[:8]}"
        with TemporaryDirectory() as tmpdir:
            settings.FILE_STORAGE_DIR = tmpdir
            bot_runner.create_telegram_messenger = lambda _token: fake_messenger
            try:
                with SessionLocal() as db:
                    self._create_waiting_file_scenario(db, scenario_key, target_field="test_task_result")
                message = SimpleNamespace(
                    from_user=SimpleNamespace(id=self.candidate_chat_id, username=None),
                    caption=None,
                    video=SimpleNamespace(
                        file_id="test-video-id",
                        file_unique_id="test-video-unique",
                        file_name=None,
                        mime_type="video/mp4",
                        file_size=654,
                    ),
                )

                await bot_runner.on_video(message, _FakeTelegramBot())

                with SessionLocal() as db:
                    file_row = (
                        db.query(EmployeeFile)
                        .filter(EmployeeFile.employee_id == self.candidate_testing_id)
                        .order_by(EmployeeFile.id.desc())
                        .first()
                    )
                    slot = (
                        db.query(EmployeeDocumentLink)
                        .filter(
                            EmployeeDocumentLink.employee_id == self.candidate_testing_id,
                            EmployeeDocumentLink.slot_key == "test_task_result",
                        )
                        .first()
                    )
                    progress = db.query(ScenarioProgress).filter_by(employee_id=self.candidate_testing_id, scenario_key=scenario_key).first()
                self.assertIsNotNone(file_row)
                self.assertEqual(file_row.category, "test_result")
                self.assertEqual(file_row.original_filename, "test-video-unique.mp4")
                self.assertEqual(file_row.mime_type, "video/mp4")
                self.assertIsNotNone(slot)
                self.assertEqual(slot.employee_file_id, file_row.id)
                self.assertIsNotNone(progress)
                self.assertTrue(progress.is_completed)
            finally:
                bot_runner.create_telegram_messenger = previous_factory
                settings.FILE_STORAGE_DIR = previous_storage_dir

    async def test_test_task_video_note_answer_saves_slot_and_counts_as_file_response(self) -> None:
        fake_messenger = _FakeMessenger()
        previous_factory = bot_runner.create_telegram_messenger
        previous_storage_dir = settings.FILE_STORAGE_DIR
        scenario_key = f"test_task_video_note_{uuid4().hex[:8]}"
        with TemporaryDirectory() as tmpdir:
            settings.FILE_STORAGE_DIR = tmpdir
            bot_runner.create_telegram_messenger = lambda _token: fake_messenger
            try:
                with SessionLocal() as db:
                    self._create_waiting_file_scenario(db, scenario_key, target_field="test_task_result")
                message = SimpleNamespace(
                    from_user=SimpleNamespace(id=self.candidate_chat_id, username=None),
                    video_note=SimpleNamespace(
                        file_id="test-video-note-id",
                        file_unique_id="test-video-note-unique",
                        file_size=987,
                    ),
                )

                await bot_runner.on_video_note(message, _FakeTelegramBot())

                with SessionLocal() as db:
                    file_row = (
                        db.query(EmployeeFile)
                        .filter(EmployeeFile.employee_id == self.candidate_testing_id)
                        .order_by(EmployeeFile.id.desc())
                        .first()
                    )
                    slot = (
                        db.query(EmployeeDocumentLink)
                        .filter(
                            EmployeeDocumentLink.employee_id == self.candidate_testing_id,
                            EmployeeDocumentLink.slot_key == "test_task_result",
                        )
                        .first()
                    )
                    progress = db.query(ScenarioProgress).filter_by(employee_id=self.candidate_testing_id, scenario_key=scenario_key).first()
                self.assertIsNotNone(file_row)
                self.assertEqual(file_row.category, "test_result")
                self.assertEqual(file_row.original_filename, "test-video-note-unique.mp4")
                self.assertEqual(file_row.telegram_file_unique_id, "test-video-note-unique")
                self.assertIsNotNone(slot)
                self.assertEqual(slot.employee_file_id, file_row.id)
                self.assertIsNotNone(progress)
                self.assertTrue(progress.is_completed)
            finally:
                bot_runner.create_telegram_messenger = previous_factory
                settings.FILE_STORAGE_DIR = previous_storage_dir

    async def test_test_task_http_link_answer_saves_slot_and_counts_as_response(self) -> None:
        scenario_key = f"test_task_link_{uuid4().hex[:8]}"
        link = "https://example.com/analytics-answer"
        with SessionLocal() as db:
            self._create_waiting_file_scenario(db, scenario_key, target_field="test_task_result")
            result = await handle_text_event(_FakeMessenger(), db, self.candidate_chat_id, None, link)

            slot = (
                db.query(EmployeeDocumentLink)
                .filter(
                    EmployeeDocumentLink.employee_id == self.candidate_testing_id,
                    EmployeeDocumentLink.slot_key == "test_task_result",
                )
                .first()
            )
            progress = db.query(ScenarioProgress).filter_by(employee_id=self.candidate_testing_id, scenario_key=scenario_key).first()

        self.assertEqual(result, "handled")
        self.assertIsNotNone(slot)
        self.assertEqual(slot.item_kind, "link")
        self.assertEqual(slot.url, link)
        self.assertIsNotNone(progress)
        self.assertTrue(progress.is_completed)

    async def test_test_task_non_link_text_answer_prompts_and_keeps_waiting(self) -> None:
        scenario_key = f"test_task_plain_text_{uuid4().hex[:8]}"
        messenger = _FakeMessenger()
        with SessionLocal() as db:
            self._create_waiting_file_scenario(db, scenario_key, target_field="test_task_result")
            result = await handle_text_event(messenger, db, self.candidate_chat_id, None, "сделал, отправлю позже")

            files_count = db.query(EmployeeFile).filter(EmployeeFile.employee_id == self.candidate_testing_id).count()
            slot = (
                db.query(EmployeeDocumentLink)
                .filter(
                    EmployeeDocumentLink.employee_id == self.candidate_testing_id,
                    EmployeeDocumentLink.slot_key == "test_task_result",
                )
                .first()
            )
            progress = db.query(ScenarioProgress).filter_by(employee_id=self.candidate_testing_id, scenario_key=scenario_key).first()

        self.assertEqual(result, "handled")
        self.assertEqual(files_count, 0)
        self.assertIsNone(slot)
        self.assertIsNotNone(progress)
        self.assertTrue(progress.waiting_for_response)
        self.assertFalse(progress.is_completed)
        self.assertTrue(messenger.texts)
        self.assertIn("ссылку http/https", messenger.texts[-1]["kwargs"]["text"])

    async def test_telegram_video_is_saved_and_counts_as_file_response(self) -> None:
        fake_messenger = _FakeMessenger()
        previous_factory = bot_runner.create_telegram_messenger
        previous_storage_dir = settings.FILE_STORAGE_DIR
        scenario_key = f"telegram_video_{uuid4().hex[:8]}"
        with TemporaryDirectory() as tmpdir:
            settings.FILE_STORAGE_DIR = tmpdir
            bot_runner.create_telegram_messenger = lambda _token: fake_messenger
            try:
                with SessionLocal() as db:
                    self._create_waiting_file_scenario(db, scenario_key)
                message = SimpleNamespace(
                    from_user=SimpleNamespace(id=self.candidate_chat_id, username=None),
                    caption="тест",
                    video=SimpleNamespace(
                        file_id="video-id",
                        file_unique_id="video-unique",
                        file_name=None,
                        mime_type="video/mp4",
                        file_size=654,
                    ),
                )

                await bot_runner.on_video(message, _FakeTelegramBot())

                with SessionLocal() as db:
                    files = (
                        db.query(EmployeeFile)
                        .filter(EmployeeFile.employee_id == self.candidate_testing_id)
                        .order_by(EmployeeFile.id.desc())
                        .all()
                    )
                    progress = db.query(ScenarioProgress).filter_by(employee_id=self.candidate_testing_id, scenario_key=scenario_key).first()
                self.assertTrue(files)
                self.assertEqual(files[0].category, "test_result")
                self.assertEqual(files[0].original_filename, "video-unique.mp4")
                self.assertEqual(files[0].mime_type, "video/mp4")
                self.assertEqual(files[0].file_size, 654)
                self.assertTrue(Path(files[0].stored_path).exists())
                self.assertIsNotNone(progress)
                self.assertTrue(progress.is_completed)
            finally:
                bot_runner.create_telegram_messenger = previous_factory
                settings.FILE_STORAGE_DIR = previous_storage_dir

    async def test_telegram_video_note_is_saved_and_counts_as_file_response(self) -> None:
        fake_messenger = _FakeMessenger()
        previous_factory = bot_runner.create_telegram_messenger
        previous_storage_dir = settings.FILE_STORAGE_DIR
        scenario_key = f"telegram_video_note_{uuid4().hex[:8]}"
        with TemporaryDirectory() as tmpdir:
            settings.FILE_STORAGE_DIR = tmpdir
            bot_runner.create_telegram_messenger = lambda _token: fake_messenger
            try:
                with SessionLocal() as db:
                    self._create_waiting_file_scenario(db, scenario_key)
                message = SimpleNamespace(
                    from_user=SimpleNamespace(id=self.candidate_chat_id, username=None),
                    video_note=SimpleNamespace(
                        file_id="video-note-id",
                        file_unique_id="video-note-unique",
                        file_size=987,
                    ),
                )

                await bot_runner.on_video_note(message, _FakeTelegramBot())

                with SessionLocal() as db:
                    files = (
                        db.query(EmployeeFile)
                        .filter(EmployeeFile.employee_id == self.candidate_testing_id)
                        .order_by(EmployeeFile.id.desc())
                        .all()
                    )
                    progress = db.query(ScenarioProgress).filter_by(employee_id=self.candidate_testing_id, scenario_key=scenario_key).first()
                self.assertTrue(files)
                self.assertEqual(files[0].category, "candidate_file")
                self.assertEqual(files[0].original_filename, "video-note-unique.mp4")
                self.assertEqual(files[0].mime_type, "video/mp4")
                self.assertEqual(files[0].telegram_file_unique_id, "video-note-unique")
                self.assertTrue(Path(files[0].stored_path).exists())
                self.assertIsNotNone(progress)
                self.assertTrue(progress.is_completed)
            finally:
                bot_runner.create_telegram_messenger = previous_factory
                settings.FILE_STORAGE_DIR = previous_storage_dir
