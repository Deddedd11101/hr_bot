import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.database import SessionLocal, init_db
from app.messaging.identity import set_primary_chat_id
from app.models import Employee, EmployeeDocumentLink, EmployeeFile, EmployeeMessengerAccount, FlowStepTemplate, ScenarioProgress, ScenarioTemplate
from app.scenario_engine import (
    SCENARIO_BACK_BUTTON_TEXT,
    WAITING_PROGRESS_CONFLICT_TEXT,
    handle_button_response,
    handle_back_response,
    handle_date_response_by_step_id,
    handle_file_response,
    handle_text_response,
    matches_role_scope,
    resolve_notification_recipients,
    resolve_tagged_employee_documents,
    scenario_anchor_date,
    send_step,
    send_step_attachment,
    start_scenario,
)
from app.web.settings import _get_or_create_hr_settings


class FakeBot:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def send_photo(self, **kwargs) -> None:
        self.calls.append(("photo", kwargs))

    async def send_document(self, **kwargs) -> None:
        self.calls.append(("document", kwargs))


class FakeMessenger:
    def __init__(self) -> None:
        self.texts: list[dict] = []
        self.documents: list[dict] = []
        self.photos: list[dict] = []

    async def send_text(self, chat_id: str, text: str, reply_markup=None) -> None:
        self.texts.append({"chat_id": chat_id, "text": text, "reply_markup": reply_markup})

    async def send_menu(self, chat_id: str, text: str, buttons: list[str]) -> None:
        self.texts.append({"chat_id": chat_id, "text": text, "buttons": buttons})

    async def send_photo_path(
        self,
        chat_id: str,
        path,
        filename: str | None = None,
        reply_markup=None,
        caption: str | None = None,
    ) -> None:
        self.photos.append(
            {
                "chat_id": chat_id,
                "path": str(path),
                "filename": filename,
                "reply_markup": reply_markup,
                "caption": caption,
            }
        )

    async def send_photo_bytes(
        self,
        chat_id: str,
        data: bytes,
        filename: str,
        reply_markup=None,
        caption: str | None = None,
    ) -> None:
        self.photos.append(
            {
                "chat_id": chat_id,
                "bytes": len(data),
                "filename": filename,
                "reply_markup": reply_markup,
                "caption": caption,
            }
        )

    async def send_document_path(
        self,
        chat_id: str,
        path,
        filename: str | None = None,
        reply_markup=None,
        caption: str | None = None,
    ) -> None:
        self.documents.append(
            {
                "chat_id": chat_id,
                "path": str(path),
                "filename": filename,
                "reply_markup": reply_markup,
                "caption": caption,
            }
        )


class ScenarioEngineSmokeTests(unittest.IsolatedAsyncioTestCase):
    def test_resolve_tagged_employee_documents_returns_file_backed_offer_slot(self) -> None:
        init_db()
        now = datetime.now(UTC).replace(tzinfo=None)
        with tempfile.TemporaryDirectory() as tmp_dir:
            offer_path = Path(tmp_dir) / "offer.pdf"
            offer_path.write_bytes(b"fake-offer")
            with SessionLocal() as db:
                employee = Employee(
                    full_name="Offer Candidate",
                    telegram_user_id="555001",
                    first_workday=None,
                    created_at=now,
                    is_flow_scheduled=False,
                    employee_stage="candidate",
                )
                db.add(employee)
                db.commit()
                db.refresh(employee)
                employee_file = EmployeeFile(
                    employee_id=employee.id,
                    direction="outbound",
                    category="offer_document",
                    telegram_file_id=None,
                    telegram_file_unique_id=None,
                    original_filename="offer.pdf",
                    stored_path=str(offer_path),
                    mime_type="application/pdf",
                    file_size=10,
                    created_at=now,
                )
                db.add(employee_file)
                db.commit()
                db.refresh(employee_file)
                db.add(
                    EmployeeDocumentLink(
                        employee_id=employee.id,
                        slot_key="offer",
                        title="Оффер",
                        url="",
                        item_kind="file",
                        employee_file_id=employee_file.id,
                        created_at=now,
                    )
                )
                db.commit()

                files = resolve_tagged_employee_documents(db, "Лови {doc:Оффер}", employee)

                self.assertEqual([item.id for item in files], [employee_file.id])

    async def test_send_step_sends_buttons_after_attachment_when_text_exists(self) -> None:
        init_db()
        now = datetime.now(UTC).replace(tzinfo=None)
        scenario_key = f"test_attachment_buttons_{int(datetime.now(UTC).timestamp() * 1000000)}"

        with tempfile.TemporaryDirectory() as tmp_dir, SessionLocal() as db:
            attachment_path = Path(tmp_dir) / "guide.pdf"
            attachment_path.write_bytes(b"fake-pdf")
            scenario = ScenarioTemplate(
                scenario_key=scenario_key,
                title="Attachment buttons",
                role_scope="all",
                scenario_kind="scenario",
                sort_order=0,
                trigger_mode="manual_only",
            )
            step = FlowStepTemplate(
                flow_key=scenario_key,
                step_key="step_one",
                step_title="Step one",
                sort_order=10,
                default_text="Выбери вариант",
                response_type="buttons",
                button_options="Да\nНет",
                send_mode="immediate",
                day_offset_workdays=0,
                attachment_path=str(attachment_path),
                attachment_filename="guide.pdf",
            )
            employee = Employee(
                full_name="Tester",
                telegram_user_id="123456789",
                created_at=now,
                is_flow_scheduled=False,
                employee_stage="candidate",
            )
            db.add_all([scenario, step, employee])
            db.commit()

            messenger = FakeMessenger()
            await send_step(messenger, db, employee, scenario, step)

            self.assertEqual(len(messenger.texts), 1)
            self.assertEqual(messenger.texts[0]["text"], "Выбери вариант")
            self.assertIsNone(messenger.texts[0]["reply_markup"])
            self.assertEqual(len(messenger.documents), 1)
            self.assertIsNotNone(messenger.documents[0]["reply_markup"])

    async def test_send_step_attachment_only_buttons_uses_media_without_technical_prompt(self) -> None:
        init_db()
        now = datetime.now(UTC).replace(tzinfo=None)
        scenario_key = f"test_attachment_only_buttons_{int(datetime.now(UTC).timestamp() * 1000000)}"

        with tempfile.TemporaryDirectory() as tmp_dir, SessionLocal() as db:
            attachment_path = Path(tmp_dir) / "welcome.png"
            attachment_path.write_bytes(b"fake-image")
            scenario = ScenarioTemplate(
                scenario_key=scenario_key,
                title="Attachment only buttons",
                role_scope="all",
                scenario_kind="scenario",
                sort_order=0,
                trigger_mode="manual_only",
            )
            step = FlowStepTemplate(
                flow_key=scenario_key,
                step_key="step_one",
                step_title="Step one",
                sort_order=10,
                default_text="",
                response_type="buttons",
                button_options="Понятно",
                send_mode="immediate",
                day_offset_workdays=0,
                attachment_path=str(attachment_path),
                attachment_filename="welcome.png",
            )
            employee = Employee(
                full_name="Tester",
                telegram_user_id="123456789",
                created_at=now,
                is_flow_scheduled=False,
                employee_stage="candidate",
            )
            db.add_all([scenario, step, employee])
            db.commit()

            messenger = FakeMessenger()
            await send_step(messenger, db, employee, scenario, step)

            self.assertEqual(len(messenger.texts), 0)
            self.assertEqual(len(messenger.photos), 1)
            self.assertIsNotNone(messenger.photos[0]["reply_markup"])

    async def test_send_step_attachment_uses_photo_for_image_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            image_path = Path(tmp_dir) / "mentor-card.png"
            image_path.write_bytes(b"fake-image")
            step = SimpleNamespace(
                attachment_path=str(image_path),
                attachment_filename="mentor-card.png",
            )
            bot = FakeBot()

            await send_step_attachment(bot, "employee-chat", step)

        self.assertEqual(len(bot.calls), 1)
        self.assertEqual(bot.calls[0][0], "photo")
        self.assertEqual(bot.calls[0][1]["chat_id"], "employee-chat")

    async def test_send_step_attachment_uses_document_for_non_image_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "offer.pdf"
            file_path.write_bytes(b"fake-pdf")
            step = SimpleNamespace(
                attachment_path=str(file_path),
                attachment_filename="offer.pdf",
            )
            bot = FakeBot()

            await send_step_attachment(bot, "employee-chat", step)

        self.assertEqual(len(bot.calls), 1)
        self.assertEqual(bot.calls[0][0], "document")
        self.assertEqual(bot.calls[0][1]["chat_id"], "employee-chat")

    async def test_start_scenario_defaults_recipient_to_subject_employee(self) -> None:
        init_db()
        now = datetime.now(UTC).replace(tzinfo=None)
        scenario_key = f"test_recipient_self_{int(datetime.now(UTC).timestamp() * 1000000)}"

        with SessionLocal() as db:
            scenario = ScenarioTemplate(
                scenario_key=scenario_key,
                title="Self recipient",
                role_scope="all",
                scenario_kind="scenario",
                sort_order=0,
                trigger_mode="manual_only",
            )
            step = FlowStepTemplate(
                flow_key=scenario_key,
                step_key="step_one",
                step_title="Step one",
                sort_order=10,
                default_text="Привет, {name}",
                response_type="none",
                send_mode="immediate",
                day_offset_workdays=0,
            )
            employee = Employee(
                full_name="Self Tester",
                telegram_user_id="123456789",
                created_at=now,
                is_flow_scheduled=False,
                employee_stage="candidate",
            )
            db.add_all([scenario, step, employee])
            db.commit()
            db.refresh(employee)

            messenger = FakeMessenger()
            started = await start_scenario(messenger, db, employee, scenario_key)

            self.assertTrue(started)
            self.assertEqual([item["chat_id"] for item in messenger.texts], ["123456789"])
            progress = db.query(ScenarioProgress).filter_by(employee_id=employee.id, scenario_key=scenario_key).first()
            self.assertIsNotNone(progress)
            self.assertEqual(progress.recipient_mode, "self")
            self.assertEqual(progress.recipient_employee_id, employee.id)
            self.assertEqual(progress.last_delivery_error, None)

    async def test_manager_recipient_routes_message_and_reply_through_subject_progress(self) -> None:
        init_db()
        now = datetime.now(UTC).replace(tzinfo=None)
        scenario_key = f"test_recipient_manager_{int(datetime.now(UTC).timestamp() * 1000000)}"

        with SessionLocal() as db:
            manager = Employee(
                full_name="Manager Receiver",
                telegram_user_id="555001",
                created_at=now,
                is_flow_scheduled=False,
                employee_stage="staff",
            )
            employee = Employee(
                full_name="Subject Employee",
                telegram_user_id="123456789",
                created_at=now,
                is_flow_scheduled=False,
                employee_stage="adaptation",
            )
            scenario = ScenarioTemplate(
                scenario_key=scenario_key,
                title="Manager recipient",
                role_scope="all",
                scenario_kind="scenario",
                sort_order=0,
                trigger_mode="manual_only",
                recipient_mode="manager",
            )
            step = FlowStepTemplate(
                flow_key=scenario_key,
                step_key="step_one",
                step_title="Step one",
                sort_order=10,
                default_text="Введи имя наставника",
                response_type="text",
                send_mode="immediate",
                day_offset_workdays=0,
                target_field="full_name",
            )
            next_step = FlowStepTemplate(
                flow_key=scenario_key,
                step_key="step_two",
                step_title="Step two",
                sort_order=20,
                default_text="Спасибо",
                response_type="none",
                send_mode="immediate",
                day_offset_workdays=0,
            )
            db.add_all([manager, employee, scenario, step, next_step])
            db.commit()
            db.refresh(manager)
            db.refresh(employee)
            employee.manager_employee_id = manager.id
            db.commit()

            messenger = FakeMessenger()
            started = await start_scenario(messenger, db, employee, scenario_key)

            self.assertTrue(started)
            self.assertEqual([item["chat_id"] for item in messenger.texts[:1]], ["555001"])
            progress = db.query(ScenarioProgress).filter_by(employee_id=employee.id, scenario_key=scenario_key).first()
            self.assertIsNotNone(progress)
            self.assertEqual(progress.employee_id, employee.id)
            self.assertEqual(progress.recipient_employee_id, manager.id)
            self.assertEqual(progress.current_step_key, "step_one")
            self.assertTrue(progress.waiting_for_response)

            handled = await handle_text_response(messenger, db, manager, SimpleNamespace(text="Новый наставник"))

            self.assertTrue(handled)
            db.refresh(employee)
            self.assertEqual(employee.full_name, "Новый наставник")
            refreshed_progress = db.query(ScenarioProgress).filter_by(employee_id=employee.id, scenario_key=scenario_key).first()
            self.assertIsNotNone(refreshed_progress)
            self.assertTrue(refreshed_progress.is_completed)
            self.assertEqual(messenger.texts[-1]["chat_id"], "555001")
            self.assertEqual(messenger.texts[-1]["text"], "Спасибо")

    async def test_manager_recipient_fails_when_manager_missing(self) -> None:
        init_db()
        now = datetime.now(UTC).replace(tzinfo=None)
        scenario_key = f"test_recipient_manager_missing_{int(datetime.now(UTC).timestamp() * 1000000)}"

        with SessionLocal() as db:
            employee = Employee(
                full_name="Subject Employee",
                telegram_user_id="123456789",
                created_at=now,
                is_flow_scheduled=False,
                employee_stage="adaptation",
            )
            scenario = ScenarioTemplate(
                scenario_key=scenario_key,
                title="Manager missing",
                role_scope="all",
                scenario_kind="scenario",
                sort_order=0,
                trigger_mode="manual_only",
                recipient_mode="manager",
            )
            step = FlowStepTemplate(
                flow_key=scenario_key,
                step_key="step_one",
                step_title="Step one",
                sort_order=10,
                default_text="Назначь наставника",
                response_type="text",
                send_mode="immediate",
                day_offset_workdays=0,
            )
            db.add_all([employee, scenario, step])
            db.commit()
            db.refresh(employee)

            messenger = FakeMessenger()
            started = await start_scenario(messenger, db, employee, scenario_key)

            self.assertFalse(started)
            self.assertEqual(messenger.texts, [])
            progress = db.query(ScenarioProgress).filter_by(employee_id=employee.id, scenario_key=scenario_key).first()
            self.assertIsNotNone(progress)
            self.assertIn("не назначен", progress.last_delivery_error or "")

    async def test_manager_recipient_fails_when_manager_has_no_telegram(self) -> None:
        init_db()
        now = datetime.now(UTC).replace(tzinfo=None)
        scenario_key = f"test_recipient_manager_no_tg_{int(datetime.now(UTC).timestamp() * 1000000)}"

        with SessionLocal() as db:
            manager = Employee(
                full_name="Manager Without Telegram",
                telegram_user_id=None,
                created_at=now,
                is_flow_scheduled=False,
                employee_stage="staff",
            )
            employee = Employee(
                full_name="Subject Employee",
                telegram_user_id="123456789",
                created_at=now,
                is_flow_scheduled=False,
                employee_stage="adaptation",
            )
            scenario = ScenarioTemplate(
                scenario_key=scenario_key,
                title="Manager no telegram",
                role_scope="all",
                scenario_kind="scenario",
                sort_order=0,
                trigger_mode="manual_only",
                recipient_mode="manager",
            )
            step = FlowStepTemplate(
                flow_key=scenario_key,
                step_key="step_one",
                step_title="Step one",
                sort_order=10,
                default_text="Назначь наставника",
                response_type="text",
                send_mode="immediate",
                day_offset_workdays=0,
            )
            db.add_all([manager, employee, scenario, step])
            db.commit()
            db.refresh(manager)
            db.refresh(employee)
            employee.manager_employee_id = manager.id
            db.commit()

            messenger = FakeMessenger()
            started = await start_scenario(messenger, db, employee, scenario_key)

            self.assertFalse(started)
            self.assertEqual(messenger.texts, [])
            progress = db.query(ScenarioProgress).filter_by(employee_id=employee.id, scenario_key=scenario_key).first()
            self.assertIsNotNone(progress)
            self.assertIn("Telegram", progress.last_delivery_error or "")

    async def test_manager_assigned_adaptation_uses_subject_employee_but_sends_to_manager(self) -> None:
        init_db()
        now = datetime.now(UTC).replace(tzinfo=None)
        scenario_key = f"test_manager_trigger_recipient_{int(datetime.now(UTC).timestamp() * 1000000)}"

        with SessionLocal() as db:
            manager = Employee(
                full_name="Manager Trigger",
                telegram_user_id="909001",
                created_at=now,
                is_flow_scheduled=False,
                employee_stage="staff",
                is_manager=True,
            )
            employee = Employee(
                full_name="Adaptation Subject",
                telegram_user_id="909002",
                created_at=now,
                is_flow_scheduled=False,
                employee_stage="adaptation",
            )
            scenario = ScenarioTemplate(
                scenario_key=scenario_key,
                title="Manager trigger scenario",
                role_scope="all",
                scenario_kind="scenario",
                sort_order=0,
                trigger_mode="manager_assigned_adaptation",
            )
            step = FlowStepTemplate(
                flow_key=scenario_key,
                step_key="step_one",
                step_title="Step one",
                sort_order=10,
                default_text="Привет, {full_name}",
                response_type="none",
                send_mode="immediate",
                day_offset_workdays=0,
            )
            db.add_all([manager, employee, scenario, step])
            db.commit()
            db.refresh(manager)
            db.refresh(employee)
            employee.manager_employee_id = manager.id
            db.commit()

            messenger = FakeMessenger()
            started = await start_scenario(messenger, db, employee, scenario_key)

            self.assertTrue(started)
            self.assertEqual(messenger.texts[0]["chat_id"], "909001")
            self.assertIn("Adaptation Subject", messenger.texts[0]["text"])
            progress = db.query(ScenarioProgress).filter_by(employee_id=employee.id, scenario_key=scenario_key).first()
            self.assertIsNotNone(progress)
            self.assertEqual(progress.recipient_mode, "manager")
            self.assertEqual(progress.recipient_employee_id, manager.id)

    def test_resolve_notification_recipients_merges_explicit_and_employee_scope(self) -> None:
        employee = SimpleNamespace(
            manager_employee_id=None,
            mentor_adaptation_employee_id=None,
            mentor_ipr_employee_id=None,
            manager_telegram_id="manager-id",
            mentor_adaptation_telegram_id="mentor-id",
            mentor_ipr_telegram_id="mentor-id",
        )

        recipients = resolve_notification_recipients(
            None,
            employee,
            explicit_ids="hr-id, manager-id",
            recipient_scope="manager,mentor_adaptation,mentor_ipr",
        )

        self.assertEqual(recipients, ["hr-id", "manager-id", "mentor-id"])

    def test_scenario_anchor_date_prefers_explicit_adaptation_dates(self) -> None:
        employee = SimpleNamespace(
            created_at=datetime(2026, 6, 1),
            first_workday=datetime(2026, 6, 2).date(),
            adaptation_midpoint=datetime(2026, 6, 16).date(),
            adaptation_end=datetime(2026, 7, 1).date(),
        )

        self.assertEqual(
            scenario_anchor_date(employee, SimpleNamespace(trigger_mode="mid_probation")),
            datetime(2026, 6, 16).date(),
        )
        self.assertEqual(
            scenario_anchor_date(employee, SimpleNamespace(trigger_mode="end_probation")),
            datetime(2026, 7, 1).date(),
        )

    def test_resolve_notification_recipients_uses_selected_staff_employee_chat(self) -> None:
        init_db()
        now = datetime.now(UTC).replace(tzinfo=None)
        with SessionLocal() as db:
            manager = Employee(
                full_name="Manager Staff",
                telegram_user_id="123456",
                first_workday=None,
                created_at=now,
                is_flow_scheduled=False,
                employee_stage="staff",
            )
            employee = Employee(
                full_name="Target Employee",
                telegram_user_id=None,
                first_workday=None,
                created_at=now,
                is_flow_scheduled=False,
                employee_stage="staff",
            )
            db.add(manager)
            db.add(employee)
            db.commit()
            db.refresh(manager)
            db.refresh(employee)
            employee.manager_employee_id = manager.id
            employee.manager_telegram_id = None
            db.commit()

            recipients = resolve_notification_recipients(db, employee, explicit_ids="hr-id", recipient_scope="manager")

            self.assertEqual(recipients, ["hr-id", "123456"])
            db.delete(employee)
            db.delete(manager)
            db.commit()

    def test_resolve_notification_recipients_supports_hr_token(self) -> None:
        init_db()
        with SessionLocal() as db:
            settings = _get_or_create_hr_settings(db)
            previous_chat_id = settings.telegram_user_id
            settings.telegram_user_id = "555001"
            db.commit()
            employee = SimpleNamespace(
                manager_employee_id=None,
                mentor_adaptation_employee_id=None,
                mentor_ipr_employee_id=None,
                manager_telegram_id=None,
                mentor_adaptation_telegram_id=None,
                mentor_ipr_telegram_id=None,
            )

            recipients = resolve_notification_recipients(db, employee, explicit_ids="hr", recipient_scope="")

            self.assertEqual(recipients, ["555001"])
            settings.telegram_user_id = previous_chat_id
            db.commit()

    def test_matches_role_scope_respects_candidate_and_employee_scope(self) -> None:
        candidate = SimpleNamespace(id=1, employee_stage="candidate", desired_position="")
        employee = SimpleNamespace(id=2, employee_stage="staff", desired_position="")

        candidate_scenario = SimpleNamespace(employee_scope="candidates", target_employee_id=None, role_scope="all")
        employee_scenario = SimpleNamespace(employee_scope="employees", target_employee_id=None, role_scope="all")

        self.assertTrue(matches_role_scope(candidate, candidate_scenario))
        self.assertFalse(matches_role_scope(employee, candidate_scenario))
        self.assertTrue(matches_role_scope(employee, employee_scenario))
        self.assertFalse(matches_role_scope(candidate, employee_scenario))

    def test_matches_role_scope_supports_new_catalog_slug(self) -> None:
        employee = SimpleNamespace(id=2, employee_stage="staff", desired_position="QA engineer")
        scenario = SimpleNamespace(employee_scope="employees", target_employee_id=None, role_scope="qa_engineer")

        self.assertTrue(matches_role_scope(employee, scenario))

    async def test_handle_button_response_persists_target_field_value(self) -> None:
        init_db()
        now = datetime.now(UTC).replace(tzinfo=None)
        scenario_key = f"test_button_target_{int(datetime.now(UTC).timestamp() * 1000000)}"

        with SessionLocal() as db:
            scenario = ScenarioTemplate(
                scenario_key=scenario_key,
                title="Button target field",
                role_scope="all",
                scenario_kind="scenario",
                sort_order=0,
                trigger_mode="manual_only",
            )
            step = FlowStepTemplate(
                flow_key=scenario_key,
                step_key="salary_step",
                step_title="Ожидаемый доход",
                sort_order=10,
                default_text="Выбери ожидаемый доход",
                response_type="buttons",
                button_options="200000\n300000",
                send_mode="immediate",
                day_offset_workdays=0,
                target_field="salary_expectation",
            )
            employee = Employee(
                full_name="Candidate Tester",
                telegram_user_id="123456789",
                created_at=now,
                is_flow_scheduled=False,
                employee_stage="candidate",
            )
            db.add_all([scenario, step, employee])
            db.commit()
            db.refresh(employee)

            messenger = FakeMessenger()
            await send_step(messenger, db, employee, scenario, step)
            handled = await handle_button_response(messenger, db, employee, scenario_key, "salary_step", 1)

            self.assertTrue(handled)
            db.refresh(employee)
            self.assertEqual(employee.salary_expectation, "300000")

            db.delete(step)
            db.delete(scenario)
            db.delete(employee)
            db.commit()

    async def test_handle_back_response_returns_to_previous_interactive_step(self) -> None:
        init_db()
        now = datetime.now(UTC).replace(tzinfo=None)
        scenario_key = f"test_back_flow_{int(datetime.now(UTC).timestamp() * 1000000)}"

        with SessionLocal() as db:
            scenario = ScenarioTemplate(
                scenario_key=scenario_key,
                title="Back flow",
                role_scope="all",
                scenario_kind="scenario",
                sort_order=0,
                trigger_mode="manual_only",
            )
            step_one = FlowStepTemplate(
                flow_key=scenario_key,
                step_key="step_one",
                step_title="Step one",
                sort_order=10,
                default_text="Введите ФИО",
                response_type="text",
                send_mode="immediate",
                day_offset_workdays=0,
                target_field="full_name",
            )
            step_two = FlowStepTemplate(
                flow_key=scenario_key,
                step_key="step_two",
                step_title="Step two",
                sort_order=20,
                default_text="Загрузите файл",
                response_type="file",
                send_mode="immediate",
                day_offset_workdays=0,
            )
            employee = Employee(
                full_name="Tester",
                telegram_user_id="123456789",
                created_at=now,
                is_flow_scheduled=False,
                employee_stage="candidate",
            )
            db.add_all([scenario, step_one, step_two, employee])
            db.commit()
            db.refresh(employee)
            db.refresh(step_one)
            db.refresh(step_two)

            messenger = FakeMessenger()
            await send_step(messenger, db, employee, scenario, step_one)
            await send_step(messenger, db, employee, scenario, step_two)

            handled = await handle_back_response(messenger, db, employee)

            self.assertTrue(handled)
            progress = db.query(ScenarioProgress).filter_by(employee_id=employee.id, scenario_key=scenario_key).first()
            self.assertIsNotNone(progress)
            self.assertEqual(progress.current_step_key, "step_one")
            self.assertTrue(progress.waiting_for_response)
            self.assertGreaterEqual(len(messenger.texts), 3)
            self.assertEqual(messenger.texts[-1]["text"], "Введите ФИО")

            db.delete(step_two)
            db.delete(step_one)
            db.delete(scenario)
            db.delete(employee)
            db.commit()

    async def test_handle_back_response_accepts_back_label_as_control(self) -> None:
        self.assertEqual(SCENARIO_BACK_BUTTON_TEXT, "Назад")

    async def test_handle_back_response_restores_employee_field_value(self) -> None:
        init_db()
        now = datetime.now(UTC).replace(tzinfo=None)
        scenario_key = f"test_back_restore_field_{int(datetime.now(UTC).timestamp() * 1000000)}"

        with SessionLocal() as db:
            scenario = ScenarioTemplate(
                scenario_key=scenario_key,
                title="Back restore field",
                role_scope="all",
                scenario_kind="scenario",
                sort_order=0,
                trigger_mode="manual_only",
            )
            step_one = FlowStepTemplate(
                flow_key=scenario_key,
                step_key="step_one",
                step_title="Step one",
                sort_order=10,
                default_text="Введите ФИО",
                response_type="text",
                send_mode="immediate",
                day_offset_workdays=0,
                target_field="full_name",
            )
            step_two = FlowStepTemplate(
                flow_key=scenario_key,
                step_key="step_two",
                step_title="Step two",
                sort_order=20,
                default_text="Следующий шаг",
                response_type="text",
                send_mode="immediate",
                day_offset_workdays=0,
            )
            employee = Employee(
                full_name="Original Name",
                telegram_user_id="123456789",
                created_at=now,
                is_flow_scheduled=False,
                employee_stage="candidate",
            )
            db.add_all([scenario, step_one, step_two, employee])
            db.commit()

            messenger = FakeMessenger()
            await send_step(messenger, db, employee, scenario, step_one)
            handled = await handle_text_response(messenger, db, employee, SimpleNamespace(text="Updated Name"))

            self.assertTrue(handled)
            db.refresh(employee)
            self.assertEqual(employee.full_name, "Updated Name")

            handled_back = await handle_back_response(messenger, db, employee)

            self.assertTrue(handled_back)
            db.refresh(employee)
            self.assertEqual(employee.full_name, "Original Name")
            progress = db.query(ScenarioProgress).filter_by(employee_id=employee.id, scenario_key=scenario_key).first()
            self.assertIsNotNone(progress)
            self.assertEqual(progress.current_step_key, "step_one")
            self.assertTrue(progress.waiting_for_response)

            db.delete(step_two)
            db.delete(step_one)
            db.delete(scenario)
            db.delete(employee)
            db.commit()

    async def test_handle_back_response_deletes_uploaded_file_and_restores_step(self) -> None:
        init_db()
        now = datetime.now(UTC).replace(tzinfo=None)
        scenario_key = f"test_back_restore_file_{int(datetime.now(UTC).timestamp() * 1000000)}"

        with tempfile.TemporaryDirectory() as tmp_dir, SessionLocal() as db:
            stored_path = Path(tmp_dir) / "resume.pdf"
            stored_path.write_bytes(b"resume")
            scenario = ScenarioTemplate(
                scenario_key=scenario_key,
                title="Back restore file",
                role_scope="all",
                scenario_kind="scenario",
                sort_order=0,
                trigger_mode="manual_only",
            )
            step_one = FlowStepTemplate(
                flow_key=scenario_key,
                step_key="step_one",
                step_title="Step one",
                sort_order=10,
                default_text="Загрузите резюме",
                response_type="file",
                send_mode="immediate",
                day_offset_workdays=0,
                target_field="resume",
            )
            step_two = FlowStepTemplate(
                flow_key=scenario_key,
                step_key="step_two",
                step_title="Step two",
                sort_order=20,
                default_text="Следующий шаг",
                response_type="text",
                send_mode="immediate",
                day_offset_workdays=0,
            )
            employee = Employee(
                full_name="File Tester",
                telegram_user_id="123456789",
                created_at=now,
                is_flow_scheduled=False,
                employee_stage="candidate",
            )
            db.add_all([scenario, step_one, step_two, employee])
            db.commit()
            db.refresh(employee)

            db_file = EmployeeFile(
                employee_id=employee.id,
                direction="inbound",
                category="candidate_file",
                telegram_file_id=None,
                telegram_file_unique_id=None,
                original_filename="resume.pdf",
                stored_path=str(stored_path),
                mime_type="application/pdf",
                file_size=6,
                created_at=now,
            )
            db.add(db_file)
            db.commit()
            db.refresh(db_file)

            messenger = FakeMessenger()
            await send_step(messenger, db, employee, scenario, step_one)
            handled = await handle_file_response(messenger, db, employee, db_file)

            self.assertTrue(handled)
            self.assertTrue(stored_path.exists())
            self.assertIsNotNone(db.get(EmployeeFile, db_file.id))

            handled_back = await handle_back_response(messenger, db, employee)

            self.assertTrue(handled_back)
            self.assertFalse(stored_path.exists())
            self.assertIsNone(db.get(EmployeeFile, db_file.id))
            progress = db.query(ScenarioProgress).filter_by(employee_id=employee.id, scenario_key=scenario_key).first()
            self.assertIsNotNone(progress)
            self.assertEqual(progress.current_step_key, "step_one")

            db.delete(step_two)
            db.delete(step_one)
            db.delete(scenario)
            db.delete(employee)
            db.commit()

    async def test_handle_back_response_restores_recruitment_button_side_effects(self) -> None:
        init_db()
        now = datetime.now(UTC).replace(tzinfo=None)
        scenario_key = f"test_recruitment_back_{int(datetime.now(UTC).timestamp() * 1000000)}"

        with SessionLocal() as db:
            scenario = ScenarioTemplate(
                scenario_key=scenario_key,
                title="Recruitment",
                role_scope="all",
                scenario_kind="scenario",
                sort_order=0,
                trigger_mode="manual_only",
            )
            step_one = FlowStepTemplate(
                flow_key=scenario_key,
                step_key="step_one",
                step_title="Step one",
                sort_order=10,
                default_text="Кого регистрируем?",
                response_type="branching",
                button_options="Кандидат\nСотрудник",
                send_mode="immediate",
                day_offset_workdays=0,
            )
            step_two = FlowStepTemplate(
                flow_key=scenario_key,
                step_key="step_two",
                step_title="Step two",
                sort_order=20,
                default_text="Следующий шаг",
                response_type="text",
                send_mode="immediate",
                day_offset_workdays=0,
            )
            employee = Employee(
                full_name="Recruitment Tester",
                telegram_user_id="123456789",
                created_at=now,
                is_flow_scheduled=False,
                employee_stage="candidate",
                candidate_status="original_status",
            )
            db.add_all([scenario, step_one, step_two, employee])
            db.commit()

            messenger = FakeMessenger()
            await send_step(messenger, db, employee, scenario, step_one)
            with patch("app.scenario_engine.RECRUITMENT_SCENARIO_KEY", scenario_key):
                handled = await handle_button_response(messenger, db, employee, scenario_key, "step_one", 1)

            self.assertTrue(handled)
            db.refresh(employee)
            self.assertEqual(employee.employee_stage, "staff")
            self.assertEqual(employee.candidate_status, "step_one")

            handled_back = await handle_back_response(messenger, db, employee)

            self.assertTrue(handled_back)
            db.refresh(employee)
            self.assertEqual(employee.employee_stage, "candidate")
            self.assertEqual(employee.candidate_status, "original_status")

            db.delete(step_two)
            db.delete(step_one)
            db.delete(scenario)
            db.delete(employee)
            db.commit()

    async def test_send_step_launch_scenario_marks_progress_completed_and_starts_target(self) -> None:
        init_db()
        now = datetime.now(UTC).replace(tzinfo=None)
        scenario_key = f"test_launch_transition_{int(datetime.now(UTC).timestamp() * 1000000)}"

        with SessionLocal() as db:
            scenario = ScenarioTemplate(
                scenario_key=scenario_key,
                title="Launch transition",
                role_scope="all",
                scenario_kind="scenario",
                sort_order=0,
                trigger_mode="manual_only",
            )
            step = FlowStepTemplate(
                flow_key=scenario_key,
                step_key="step_one",
                step_title="Step one",
                sort_order=10,
                default_text="Переход",
                response_type="launch_scenario",
                launch_scenario_key="target_flow",
                send_mode="immediate",
                day_offset_workdays=0,
            )
            employee = Employee(
                full_name="Tester",
                telegram_user_id="123456789",
                created_at=now,
                is_flow_scheduled=False,
                employee_stage="candidate",
            )
            db.add_all([scenario, step, employee])
            db.commit()
            db.refresh(employee)

            messenger = FakeMessenger()
            with patch("app.scenario_engine.start_scenario", new=AsyncMock(return_value=True)) as mocked_start:
                await send_step(messenger, db, employee, scenario, step)

            progress = db.query(ScenarioProgress).filter_by(employee_id=employee.id, scenario_key=scenario_key).first()
            self.assertIsNotNone(progress)
            self.assertFalse(progress.waiting_for_response)
            self.assertTrue(progress.is_completed)
            mocked_start.assert_awaited_once()
            self.assertEqual(mocked_start.await_args.args[3], "target_flow")

    async def test_handle_button_response_saves_selected_value_to_salary_expectation(self) -> None:
        init_db()
        now = datetime.now(UTC).replace(tzinfo=None)
        scenario_key = f"test_buttons_target_field_{int(datetime.now(UTC).timestamp() * 1000000)}"

        with SessionLocal() as db:
            scenario = ScenarioTemplate(
                scenario_key=scenario_key,
                title="Buttons target field",
                role_scope="all",
                scenario_kind="scenario",
                sort_order=0,
                trigger_mode="manual_only",
            )
            step = FlowStepTemplate(
                flow_key=scenario_key,
                step_key="step_one",
                step_title="Salary step",
                sort_order=10,
                default_text="Выбери ожидания по доходу",
                response_type="buttons",
                button_options="100 000\n150 000\n200 000",
                target_field="salary_expectation",
                send_mode="immediate",
                day_offset_workdays=0,
            )
            next_step = FlowStepTemplate(
                flow_key=scenario_key,
                step_key="step_two",
                step_title="Next step",
                sort_order=20,
                default_text="Спасибо",
                response_type="none",
                send_mode="immediate",
                day_offset_workdays=0,
            )
            employee = Employee(
                full_name="Tester",
                telegram_user_id="123456789",
                created_at=now,
                is_flow_scheduled=False,
                employee_stage="candidate",
            )
            db.add_all([scenario, step, next_step, employee])
            db.commit()

            messenger = FakeMessenger()
            await send_step(messenger, db, employee, scenario, step)
            handled = await handle_button_response(messenger, db, employee, scenario_key, "step_one", 1)

            self.assertTrue(handled)
            db.refresh(employee)
            self.assertEqual(employee.salary_expectation, "150 000")

    async def test_handle_date_response_persists_first_workday(self) -> None:
        init_db()
        now = datetime.now(UTC).replace(tzinfo=None)
        scenario_key = f"test_date_target_{int(datetime.now(UTC).timestamp() * 1000000)}"

        with SessionLocal() as db:
            scenario = ScenarioTemplate(
                scenario_key=scenario_key,
                title="Date target field",
                role_scope="all",
                scenario_kind="scenario",
                sort_order=0,
                trigger_mode="manual_only",
            )
            step = FlowStepTemplate(
                flow_key=scenario_key,
                step_key="workday_step",
                step_title="Дата выхода",
                sort_order=10,
                default_text="Выбери дату выхода",
                response_type="date",
                send_mode="immediate",
                day_offset_workdays=0,
                target_field="first_workday",
            )
            employee = Employee(
                full_name="Offer Candidate",
                telegram_user_id="123456789",
                created_at=now,
                is_flow_scheduled=False,
                employee_stage="candidate",
            )
            db.add_all([scenario, step, employee])
            db.commit()
            db.refresh(employee)
            db.refresh(step)

            messenger = FakeMessenger()
            await send_step(messenger, db, employee, scenario, step)
            result = await handle_date_response_by_step_id(
                messenger,
                db,
                employee,
                step.id,
                "set",
                "2026-07-15",
            )

            self.assertTrue(result.handled)
            self.assertEqual(result.action, "selected")
            db.refresh(employee)
            self.assertEqual(employee.first_workday.isoformat() if employee.first_workday else None, "2026-07-15")

    async def test_branch_step_can_return_to_later_root_step(self) -> None:
        init_db()
        now = datetime.now(UTC).replace(tzinfo=None)
        scenario_key = f"test_branch_return_{int(datetime.now(UTC).timestamp() * 1000000)}"

        with SessionLocal() as db:
            scenario = ScenarioTemplate(
                scenario_key=scenario_key,
                title="Branch return",
                role_scope="all",
                scenario_kind="scenario",
                sort_order=0,
                trigger_mode="manual_only",
            )
            root_step = FlowStepTemplate(
                flow_key=scenario_key,
                step_key="step_one",
                step_title="Step one",
                sort_order=10,
                default_text="Согласен?",
                response_type="branching",
                button_options="Да\nНет",
                send_mode="immediate",
                day_offset_workdays=0,
            )
            skipped_root = FlowStepTemplate(
                flow_key=scenario_key,
                step_key="step_two",
                step_title="Skipped root",
                sort_order=20,
                default_text="Сюда не должны попасть",
                response_type="none",
                send_mode="immediate",
                day_offset_workdays=0,
            )
            target_root = FlowStepTemplate(
                flow_key=scenario_key,
                step_key="step_three",
                step_title="Merged root",
                sort_order=30,
                default_text="Общий поток после ветки",
                response_type="none",
                send_mode="immediate",
                day_offset_workdays=0,
            )
            employee = Employee(
                full_name="Tester",
                telegram_user_id="123456789",
                created_at=now,
                is_flow_scheduled=False,
                employee_stage="candidate",
            )
            db.add_all([scenario, root_step, skipped_root, target_root, employee])
            db.commit()
            db.refresh(root_step)
            db.refresh(target_root)
            db.refresh(employee)

            branch_step = FlowStepTemplate(
                flow_key=scenario_key,
                step_key="step_one_branch_yes",
                parent_step_id=root_step.id,
                branch_option_index=0,
                step_title="Branch yes",
                sort_order=1001,
                default_text="Локальная ветка",
                response_type="none",
                return_to_step_key=target_root.step_key,
                send_mode="immediate",
                day_offset_workdays=0,
            )
            db.add(branch_step)
            db.commit()

            messenger = FakeMessenger()
            await send_step(messenger, db, employee, scenario, root_step)

            handled = await handle_button_response(messenger, db, employee, scenario_key, root_step.step_key, 0)

            self.assertTrue(handled)
            sent_texts = [item["text"] for item in messenger.texts]
            self.assertIn("Локальная ветка", sent_texts)
            self.assertIn("Общий поток после ветки", sent_texts)
            self.assertNotIn("Сюда не должны попасть", sent_texts)

    async def test_text_response_conflict_fails_closed_when_multiple_progresses_wait(self) -> None:
        init_db()
        now = datetime.now(UTC).replace(tzinfo=None)
        unique_suffix = str(int(datetime.now(UTC).timestamp() * 1000000))
        scenario_key_a = f"waiting_conflict_a_{unique_suffix}"
        scenario_key_b = f"waiting_conflict_b_{unique_suffix}"
        chat_id = f"99{unique_suffix[-10:]}"
        messenger = FakeMessenger()
        employee_id: int | None = None
        try:
            with SessionLocal() as db:
                employee = Employee(
                    full_name="Waiting Conflict User",
                    telegram_user_id=chat_id,
                    telegram_username=None,
                    first_workday=None,
                    created_at=now,
                    is_flow_scheduled=False,
                    candidate_status="new",
                    employee_stage="candidate",
                )
                scenario_a = ScenarioTemplate(
                    scenario_key=scenario_key_a,
                    title="Waiting conflict A",
                    role_scope="all",
                    employee_scope="candidates",
                    scenario_kind="scenario",
                    sort_order=0,
                    trigger_mode="manual_only",
                )
                scenario_b = ScenarioTemplate(
                    scenario_key=scenario_key_b,
                    title="Waiting conflict B",
                    role_scope="all",
                    employee_scope="candidates",
                    scenario_kind="scenario",
                    sort_order=0,
                    trigger_mode="manual_only",
                )
                db.add_all([employee, scenario_a, scenario_b])
                db.flush()
                employee_id = employee.id
                set_primary_chat_id(employee, chat_id, db=db)
                db.add_all(
                    [
                        FlowStepTemplate(
                            flow_key=scenario_key_a,
                            step_key="salary_a",
                            step_title="Salary A",
                            sort_order=10,
                            default_text="Salary A?",
                            response_type="text",
                            target_field="salary_expectation",
                        ),
                        FlowStepTemplate(
                            flow_key=scenario_key_b,
                            step_key="salary_b",
                            step_title="Salary B",
                            sort_order=10,
                            default_text="Salary B?",
                            response_type="text",
                            target_field="salary_expectation",
                        ),
                        ScenarioProgress(
                            employee_id=employee.id,
                            scenario_key=scenario_key_a,
                            recipient_mode="self",
                            recipient_employee_id=employee.id,
                            recipient_chat_id=chat_id,
                            current_step_key="salary_a",
                            waiting_for_response=True,
                            is_completed=False,
                            started_at=now,
                            updated_at=now,
                        ),
                        ScenarioProgress(
                            employee_id=employee.id,
                            scenario_key=scenario_key_b,
                            recipient_mode="self",
                            recipient_employee_id=employee.id,
                            recipient_chat_id=chat_id,
                            current_step_key="salary_b",
                            waiting_for_response=True,
                            is_completed=False,
                            started_at=now,
                            updated_at=now,
                        ),
                    ]
                )
                db.commit()

            with SessionLocal() as db:
                employee = db.get(Employee, employee_id)
                assert employee is not None
                handled = await handle_text_response(
                    messenger,
                    db,
                    employee,
                    SimpleNamespace(text="100000"),
                )

                self.assertTrue(handled)
                self.assertIsNone(employee.salary_expectation)
                progress_errors = [
                    row.last_delivery_error
                    for row in db.query(ScenarioProgress)
                    .filter(ScenarioProgress.employee_id == employee_id)
                    .order_by(ScenarioProgress.scenario_key.asc())
                    .all()
                ]

            self.assertEqual([item["text"] for item in messenger.texts], [WAITING_PROGRESS_CONFLICT_TEXT])
            self.assertTrue(all("Multiple active waiting progress" in (error or "") for error in progress_errors))
        finally:
            if employee_id is not None:
                with SessionLocal() as db:
                    db.query(ScenarioProgress).filter(ScenarioProgress.employee_id == employee_id).delete(synchronize_session=False)
                    db.query(EmployeeFile).filter(EmployeeFile.employee_id == employee_id).delete(synchronize_session=False)
                    db.query(EmployeeMessengerAccount).filter(EmployeeMessengerAccount.employee_id == employee_id).delete(synchronize_session=False)
                    employee = db.get(Employee, employee_id)
                    if employee is not None:
                        db.delete(employee)
                    db.query(FlowStepTemplate).filter(FlowStepTemplate.flow_key.in_([scenario_key_a, scenario_key_b])).delete(synchronize_session=False)
                    db.query(ScenarioTemplate).filter(ScenarioTemplate.scenario_key.in_([scenario_key_a, scenario_key_b])).delete(synchronize_session=False)
                    db.commit()


if __name__ == "__main__":
    unittest.main()
