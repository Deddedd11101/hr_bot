import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.database import SessionLocal, init_db
from app.models import (
    DocumentLibraryItem,
    Employee,
    EmployeeDocumentLink,
    EmployeeFile,
    FlowStepTemplate,
    ScenarioProgress,
    ScenarioTemplate,
    StepButtonNotification,
    StepSendNotification,
)
from app.scenario_engine import (
    SCENARIO_BACK_BUTTON_TEXT,
    format_message,
    handle_button_response,
    handle_back_response,
    handle_date_response_by_step_id,
    handle_choice_confirmation_response_by_step_id,
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
    def test_format_message_supports_employee_template_tags(self) -> None:
        init_db()
        now = datetime.now(UTC).replace(tzinfo=None)
        with SessionLocal() as db:
            employee = Employee(
                full_name="Антон Востриков",
                desired_position="Аналитик",
                telegram_user_id="100001",
                first_workday=datetime(2026, 9, 1).date(),
                created_at=now,
                is_flow_scheduled=False,
                employee_stage="candidate",
            )
            db.add(employee)
            db.commit()
            db.refresh(employee)

            message = format_message(
                db,
                "ФИО: {employee_full_name}; должность: {position}; первый день: {first_workday}",
                employee,
                datetime(2026, 9, 1).date(),
                None,
            )

            self.assertEqual(
                message,
                "ФИО: Антон Востриков; должность: Аналитик; первый день: 01.09.2026",
            )

    def test_format_message_uses_safe_fallbacks_for_empty_employee_tags(self) -> None:
        init_db()
        now = datetime.now(UTC).replace(tzinfo=None)
        with SessionLocal() as db:
            employee = Employee(
                full_name="",
                desired_position="",
                telegram_user_id="100002",
                first_workday=None,
                created_at=now,
                is_flow_scheduled=False,
                employee_stage="candidate",
            )
            db.add(employee)
            db.commit()
            db.refresh(employee)

            message = format_message(
                db,
                "{employee_full_name} / {position} / {first_workday} / {resume}",
                employee,
                datetime(2026, 9, 1).date(),
                None,
            )

            self.assertEqual(
                message,
                f"Employee #{employee.id} / не указана / не указана / резюме не загружено",
            )

    def test_format_message_prefers_resume_slot_over_legacy_resume_file(self) -> None:
        init_db()
        now = datetime.now(UTC).replace(tzinfo=None)
        with SessionLocal() as db:
            employee = Employee(
                full_name="Resume Slot Tester",
                desired_position="Project manager",
                telegram_user_id="777112",
                created_at=now,
            )
            db.add(employee)
            db.commit()
            db.refresh(employee)
            legacy_file = EmployeeFile(
                employee_id=employee.id,
                direction="inbound",
                category="resume",
                telegram_file_id=None,
                telegram_file_unique_id=None,
                original_filename="legacy_resume.pdf",
                stored_path="D:/tmp/legacy_resume.pdf",
                mime_type="application/pdf",
                file_size=10,
                created_at=now,
            )
            slot_file = EmployeeFile(
                employee_id=employee.id,
                direction="inbound",
                category="resume",
                telegram_file_id=None,
                telegram_file_unique_id=None,
                original_filename="actual_resume.pdf",
                stored_path="D:/tmp/actual_resume.pdf",
                mime_type="application/pdf",
                file_size=12,
                created_at=now,
            )
            db.add_all([legacy_file, slot_file])
            db.commit()
            db.refresh(slot_file)
            db.add(
                EmployeeDocumentLink(
                    employee_id=employee.id,
                    slot_key="resume",
                    title="Резюме",
                    url="",
                    item_kind="file",
                    employee_file_id=slot_file.id,
                    created_at=now,
                )
            )
            db.commit()

            message = format_message(db, "Резюме: {resume}", employee, datetime(2026, 9, 1).date(), None)

            self.assertEqual(message, "Резюме: actual_resume.pdf")

    def test_format_message_keeps_document_tags_working(self) -> None:
        init_db()
        now = datetime.now(UTC).replace(tzinfo=None)
        with SessionLocal() as db:
            employee = Employee(
                full_name="Doc Candidate",
                telegram_user_id="100004",
                first_workday=None,
                created_at=now,
                is_flow_scheduled=False,
                employee_stage="candidate",
            )
            db.add(employee)
            db.commit()
            db.refresh(employee)
            db.add(
                EmployeeDocumentLink(
                    employee_id=employee.id,
                    slot_key="offer",
                    title="Оффер",
                    url="https://example.com/offer.pdf",
                    item_kind="link",
                    employee_file_id=None,
                    created_at=now,
                )
            )
            db.commit()

            message = format_message(db, "Лови {doc:Оффер}", employee, datetime(2026, 9, 1).date(), None)

            self.assertEqual(message, 'Лови <a href="https://example.com/offer.pdf">Оффер</a>')

    def test_format_message_sanitizes_telegram_safe_html_subset(self) -> None:
        init_db()
        now = datetime.now(UTC).replace(tzinfo=None)
        with SessionLocal() as db:
            employee = Employee(
                full_name="Safe HTML",
                telegram_user_id="100006",
                created_at=now,
                employee_stage="candidate",
            )
            db.add(employee)
            db.commit()
            db.refresh(employee)

            message = format_message(
                db,
                '<b data-x="1">Жирный</b> <span>plain</span> <a href="https://example.com?a=1&b=2">link</a>',
                employee,
                datetime(2026, 9, 1).date(),
                None,
            )

            self.assertEqual(
                message,
                '<b>Жирный</b> plain <a href="https://example.com?a=1&amp;b=2">link</a>',
            )

    def test_format_message_blocks_unsafe_html_and_hrefs(self) -> None:
        init_db()
        now = datetime.now(UTC).replace(tzinfo=None)
        with SessionLocal() as db:
            employee = Employee(
                full_name="Unsafe HTML",
                telegram_user_id="100007",
                created_at=now,
                employee_stage="candidate",
            )
            db.add(employee)
            db.commit()
            db.refresh(employee)

            message = format_message(
                db,
                '<script>alert(1)</script> <a href="javascript:alert(1)" onclick="bad()">click</a> <b>broken',
                employee,
                datetime(2026, 9, 1).date(),
                None,
            )

            self.assertEqual(message, "alert(1) click <b>broken</b>")

    def test_format_message_allows_http_https_and_mailto_links(self) -> None:
        init_db()
        now = datetime.now(UTC).replace(tzinfo=None)
        with SessionLocal() as db:
            employee = Employee(
                full_name="Link Tester",
                telegram_user_id="100008",
                created_at=now,
                employee_stage="candidate",
            )
            db.add(employee)
            db.commit()
            db.refresh(employee)

            message = format_message(
                db,
                '<a href="http://example.com">http</a> <a href="https://example.com">https</a> <a href="mailto:hr@example.com">mail</a>',
                employee,
                datetime(2026, 9, 1).date(),
                None,
            )

            self.assertEqual(
                message,
                '<a href="http://example.com">http</a> <a href="https://example.com">https</a> <a href="mailto:hr@example.com">mail</a>',
            )

    def test_format_message_escapes_template_values(self) -> None:
        init_db()
        now = datetime.now(UTC).replace(tzinfo=None)
        with SessionLocal() as db:
            employee = Employee(
                full_name="<script>A&B</script>",
                desired_position="<b>PM</b>",
                telegram_user_id="100009",
                first_workday=datetime(2026, 9, 1).date(),
                created_at=now,
                employee_stage="candidate",
            )
            db.add(employee)
            db.commit()
            db.refresh(employee)

            message = format_message(
                db,
                "<b>{employee_full_name}</b> / {position}",
                employee,
                datetime(2026, 9, 1).date(),
                None,
            )

            self.assertEqual(message, "<b>&lt;script&gt;A&amp;B&lt;/script&gt;</b> / &lt;b&gt;PM&lt;/b&gt;")

    def test_format_message_keeps_unknown_template_fields_as_text(self) -> None:
        init_db()
        now = datetime.now(UTC).replace(tzinfo=None)
        with SessionLocal() as db:
            employee = Employee(
                full_name="Unknown Field",
                telegram_user_id="100010",
                created_at=now,
                employee_stage="candidate",
            )
            db.add(employee)
            db.commit()
            db.refresh(employee)

            message = format_message(db, "Текст {unknown_tag}", employee, datetime(2026, 9, 1).date(), None)

            self.assertEqual(message, "Текст {unknown_tag}")

    async def test_step_send_notification_formats_employee_and_resume_tags(self) -> None:
        init_db()
        now = datetime.now(UTC).replace(tzinfo=None)
        scenario_key = f"test_notification_tags_{int(datetime.now(UTC).timestamp() * 1000000)}"
        with SessionLocal() as db:
            scenario = ScenarioTemplate(
                scenario_key=scenario_key,
                title="Notification tags",
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
                default_text="Шаг для {employee_full_name}",
                response_type="none",
                send_mode="immediate",
                day_offset_workdays=0,
            )
            employee = Employee(
                full_name="Ирина Смирнова",
                desired_position="Дизайнер",
                telegram_user_id="100003",
                first_workday=datetime(2026, 9, 2).date(),
                created_at=now,
                is_flow_scheduled=False,
                employee_stage="candidate",
            )
            db.add_all([scenario, step, employee])
            db.commit()
            db.refresh(step)
            db.refresh(employee)
            hr_settings = _get_or_create_hr_settings(db)
            hr_settings.telegram_user_id = "999003"
            db.add(
                EmployeeFile(
                    employee_id=employee.id,
                    direction="inbound",
                    category="resume",
                    telegram_file_id=None,
                    telegram_file_unique_id=None,
                    original_filename="irina_resume.pdf",
                    stored_path="D:/tmp/irina_resume.pdf",
                    mime_type="application/pdf",
                    file_size=20,
                    created_at=now,
                )
            )
            db.add(
                StepSendNotification(
                    flow_key=scenario_key,
                    step_id=step.id,
                    rule_index=0,
                    message_text="{employee_full_name} / {position} / {resume}",
                    recipient_ids="hr",
                    recipient_scope="",
                )
            )
            db.commit()

            messenger = FakeMessenger()
            await send_step(messenger, db, employee, scenario, step)

            self.assertEqual(messenger.texts[0]["text"], "Шаг для Ирина Смирнова")
            self.assertEqual(messenger.texts[1]["chat_id"], "999003")
            self.assertEqual(messenger.texts[1]["text"], "Ирина Смирнова / Дизайнер / irina_resume.pdf")

    async def test_step_send_notification_uses_telegram_safe_html_renderer(self) -> None:
        init_db()
        now = datetime.now(UTC).replace(tzinfo=None)
        scenario_key = f"test_notification_safe_html_{int(datetime.now(UTC).timestamp() * 1000000)}"
        with SessionLocal() as db:
            scenario = ScenarioTemplate(
                scenario_key=scenario_key,
                title="Notification safe html",
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
                default_text="Шаг",
                response_type="none",
                send_mode="immediate",
                day_offset_workdays=0,
            )
            employee = Employee(
                full_name="<script>Ирина</script>",
                desired_position="Дизайнер",
                telegram_user_id="100011",
                created_at=now,
                employee_stage="candidate",
            )
            db.add_all([scenario, step, employee])
            db.commit()
            db.refresh(step)
            db.refresh(employee)
            hr_settings = _get_or_create_hr_settings(db)
            hr_settings.telegram_user_id = "999011"
            db.add(
                StepSendNotification(
                    flow_key=scenario_key,
                    step_id=step.id,
                    rule_index=0,
                    message_text='<b>{employee_full_name}</b> <img src=x> <a href="javascript:bad()">bad</a>',
                    recipient_ids="hr",
                    recipient_scope="",
                )
            )
            db.commit()

            messenger = FakeMessenger()
            await send_step(messenger, db, employee, scenario, step)

            self.assertEqual(
                messenger.texts[1]["text"],
                "<b>&lt;script&gt;Ирина&lt;/script&gt;</b>  bad",
            )

    async def test_button_notification_formats_employee_tags(self) -> None:
        init_db()
        now = datetime.now(UTC).replace(tzinfo=None)
        scenario_key = f"test_button_notification_tags_{int(datetime.now(UTC).timestamp() * 1000000)}"
        with SessionLocal() as db:
            scenario = ScenarioTemplate(
                scenario_key=scenario_key,
                title="Button notification tags",
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
                default_text="Выберите",
                response_type="buttons",
                button_options="Да\nНет",
                send_mode="immediate",
                day_offset_workdays=0,
            )
            employee = Employee(
                full_name="Петр Иванов",
                desired_position="Project manager",
                telegram_user_id="100005",
                first_workday=datetime(2026, 9, 3).date(),
                created_at=now,
                is_flow_scheduled=False,
                employee_stage="candidate",
            )
            db.add_all([scenario, step, employee])
            db.commit()
            db.refresh(step)
            db.refresh(employee)
            hr_settings = _get_or_create_hr_settings(db)
            hr_settings.telegram_user_id = "999005"
            db.add(
                ScenarioProgress(
                    employee_id=employee.id,
                    scenario_key=scenario_key,
                    current_step_key=step.step_key,
                    waiting_for_response=True,
                    is_completed=False,
                    started_at=now,
                    updated_at=now,
                )
            )
            db.add(
                StepButtonNotification(
                    flow_key=scenario_key,
                    step_id=step.id,
                    option_index=0,
                    rule_index=0,
                    message_text="{employee_full_name} выбрал кнопку, должность: {position}",
                    recipient_ids="hr",
                    recipient_scope="",
                )
            )
            db.commit()

            messenger = FakeMessenger()
            handled = await handle_button_response(messenger, db, employee, scenario_key, step.step_key, 0)

            self.assertTrue(handled)
            self.assertEqual(messenger.texts[0]["chat_id"], "999005")
            self.assertEqual(messenger.texts[0]["text"], "Петр Иванов выбрал кнопку, должность: Project manager")

    async def test_button_notification_uses_telegram_safe_html_renderer(self) -> None:
        init_db()
        now = datetime.now(UTC).replace(tzinfo=None)
        scenario_key = f"test_button_notification_safe_html_{int(datetime.now(UTC).timestamp() * 1000000)}"
        with SessionLocal() as db:
            scenario = ScenarioTemplate(
                scenario_key=scenario_key,
                title="Button notification safe html",
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
                default_text="Выберите",
                response_type="buttons",
                button_options="Да\nНет",
                send_mode="immediate",
                day_offset_workdays=0,
            )
            employee = Employee(
                full_name="Петр & Иванов",
                desired_position="<PM>",
                telegram_user_id="100012",
                created_at=now,
                employee_stage="candidate",
            )
            db.add_all([scenario, step, employee])
            db.commit()
            db.refresh(step)
            db.refresh(employee)
            hr_settings = _get_or_create_hr_settings(db)
            hr_settings.telegram_user_id = "999012"
            db.add(
                ScenarioProgress(
                    employee_id=employee.id,
                    scenario_key=scenario_key,
                    current_step_key=step.step_key,
                    waiting_for_response=True,
                    is_completed=False,
                    started_at=now,
                    updated_at=now,
                )
            )
            db.add(
                StepButtonNotification(
                    flow_key=scenario_key,
                    step_id=step.id,
                    option_index=0,
                    rule_index=0,
                    message_text='<u>{employee_full_name}</u> / <code>{position}</code>',
                    recipient_ids="hr",
                    recipient_scope="",
                )
            )
            db.commit()

            messenger = FakeMessenger()
            handled = await handle_button_response(messenger, db, employee, scenario_key, step.step_key, 0)

            self.assertTrue(handled)
            self.assertEqual(messenger.texts[0]["text"], "<u>Петр &amp; Иванов</u> / <code>&lt;PM&gt;</code>")

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

    async def test_send_step_attachment_prefers_library_file_over_upload_attachment(self) -> None:
        init_db()
        now = datetime.now(UTC).replace(tzinfo=None)
        with tempfile.TemporaryDirectory() as tmp_dir, SessionLocal() as db:
            old_attachment_path = Path(tmp_dir) / "old-guide.pdf"
            old_attachment_path.write_bytes(b"old")
            library_path = Path(tmp_dir) / "library-guide.pdf"
            library_path.write_bytes(b"library")
            item = DocumentLibraryItem(
                title="Library guide",
                description="",
                category="Tests",
                item_kind="file",
                external_url=None,
                original_filename="library-guide.pdf",
                stored_path=str(library_path),
                mime_type="application/pdf",
                file_size=7,
                is_active=True,
                sort_order=10,
                created_at=now,
                updated_at=now,
            )
            db.add(item)
            db.commit()
            db.refresh(item)
            step = SimpleNamespace(
                attachment_document_item_id=item.id,
                attachment_path=str(old_attachment_path),
                attachment_filename="old-guide.pdf",
            )
            messenger = FakeMessenger()

            handled = await send_step_attachment(messenger, "employee-chat", step, db=db)

            self.assertTrue(handled)
            self.assertEqual(len(messenger.documents), 1)
            self.assertEqual(messenger.documents[0]["path"], str(library_path))
            self.assertEqual(messenger.documents[0]["filename"], "library-guide.pdf")

    async def test_send_step_attachment_sends_library_link_as_text(self) -> None:
        init_db()
        now = datetime.now(UTC).replace(tzinfo=None)
        with SessionLocal() as db:
            item = DocumentLibraryItem(
                title="Company policy",
                description="Read before start",
                category="Tests",
                item_kind="link",
                external_url="https://example.com/policy",
                original_filename=None,
                stored_path=None,
                mime_type=None,
                file_size=None,
                is_active=True,
                sort_order=10,
                created_at=now,
                updated_at=now,
            )
            db.add(item)
            db.commit()
            db.refresh(item)
            step = SimpleNamespace(
                attachment_document_item_id=item.id,
                attachment_path="",
                attachment_filename="",
            )
            messenger = FakeMessenger()

            handled = await send_step_attachment(messenger, "employee-chat", step, db=db)

            self.assertTrue(handled)
            self.assertEqual(len(messenger.texts), 1)
            self.assertEqual(
                messenger.texts[0]["text"],
                "Company policy\n\nRead before start\n\nhttps://example.com/policy",
            )

    async def test_send_step_attachment_falls_back_to_upload_when_library_file_is_broken(self) -> None:
        init_db()
        now = datetime.now(UTC).replace(tzinfo=None)
        with tempfile.TemporaryDirectory() as tmp_dir, SessionLocal() as db:
            old_attachment_path = Path(tmp_dir) / "fallback-guide.pdf"
            old_attachment_path.write_bytes(b"fallback")
            item = DocumentLibraryItem(
                title="Broken library guide",
                description="",
                category="Tests",
                item_kind="file",
                external_url=None,
                original_filename="missing-guide.pdf",
                stored_path=str(Path(tmp_dir) / "missing-guide.pdf"),
                mime_type="application/pdf",
                file_size=7,
                is_active=True,
                sort_order=10,
                created_at=now,
                updated_at=now,
            )
            db.add(item)
            db.commit()
            db.refresh(item)
            step = SimpleNamespace(
                attachment_document_item_id=item.id,
                attachment_path=str(old_attachment_path),
                attachment_filename="fallback-guide.pdf",
            )
            messenger = FakeMessenger()

            handled = await send_step_attachment(messenger, "employee-chat", step, db=db)

            self.assertTrue(handled)
            self.assertEqual(len(messenger.documents), 1)
            self.assertEqual(messenger.documents[0]["path"], str(old_attachment_path))

    async def test_send_step_records_error_when_library_attachment_is_only_content_and_broken(self) -> None:
        init_db()
        now = datetime.now(UTC).replace(tzinfo=None)
        with tempfile.TemporaryDirectory() as tmp_dir, SessionLocal() as db:
            employee = Employee(
                full_name="Library Attachment User",
                telegram_user_id="900001",
                created_at=now,
                is_flow_scheduled=False,
                employee_stage="candidate",
            )
            scenario = ScenarioTemplate(
                scenario_key="library_attachment_failure",
                title="Library attachment failure",
                sort_order=10,
                scenario_kind="scenario",
                role_scope="all",
                employee_scope="all",
                recipient_mode="self",
                trigger_mode="manual_only",
            )
            item = DocumentLibraryItem(
                title="Broken only content",
                description="",
                category="Tests",
                item_kind="file",
                external_url=None,
                original_filename="missing-guide.pdf",
                stored_path=str(Path(tmp_dir) / "missing-guide.pdf"),
                mime_type="application/pdf",
                file_size=7,
                is_active=True,
                sort_order=10,
                created_at=now,
                updated_at=now,
            )
            db.add_all([employee, scenario, item])
            db.flush()
            step = FlowStepTemplate(
                flow_key=scenario.scenario_key,
                step_key="step_one",
                step_title="Broken file",
                sort_order=10,
                default_text="",
                response_type="none",
                send_mode="immediate",
                day_offset_workdays=0,
                attachment_document_item_id=item.id,
            )
            db.add(step)
            db.commit()
            messenger = FakeMessenger()

            sent = await send_step(messenger, db, employee, scenario, step)

            self.assertFalse(sent)
            self.assertEqual(messenger.texts, [])
            self.assertEqual(messenger.documents, [])
            progress = (
                db.query(ScenarioProgress)
                .filter(
                    ScenarioProgress.employee_id == employee.id,
                    ScenarioProgress.scenario_key == scenario.scenario_key,
                )
                .one()
            )
            self.assertIn("missing on disk", progress.last_delivery_error or "")

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

        self.assertEqual(recipients, ["manager-id", "mentor-id"])

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

            self.assertEqual(recipients, ["123456"])
            db.delete(employee)
            db.delete(manager)
            db.commit()

    def test_resolve_notification_recipients_rejects_raw_chat_ids(self) -> None:
        init_db()
        with SessionLocal() as db:
            employee = SimpleNamespace(
                manager_employee_id=None,
                mentor_adaptation_employee_id=None,
                mentor_ipr_employee_id=None,
                manager_telegram_id=None,
                mentor_adaptation_telegram_id=None,
                mentor_ipr_telegram_id=None,
            )

            recipients = resolve_notification_recipients(db, employee, explicit_ids="999999, raw-chat", recipient_scope="")

            self.assertEqual(recipients, [])

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

    def test_matches_role_scope_supports_multiple_position_slugs(self) -> None:
        analyst = SimpleNamespace(id=2, employee_stage="staff", desired_position="Аналитик")
        designer = SimpleNamespace(id=3, employee_stage="staff", desired_position="Дизайнер")
        pm = SimpleNamespace(id=4, employee_stage="staff", desired_position="Project manager")
        scenario = SimpleNamespace(
            employee_scope="employees",
            target_employee_id=None,
            role_scope="designer, analyst",
        )

        self.assertTrue(matches_role_scope(analyst, scenario))
        self.assertTrue(matches_role_scope(designer, scenario))
        self.assertFalse(matches_role_scope(pm, scenario))

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
            saved_file = db.get(EmployeeFile, db_file.id)
            self.assertIsNotNone(saved_file)
            if saved_file is not None:
                self.assertEqual(saved_file.category, "resume")
            resume_slot = (
                db.query(EmployeeDocumentLink)
                .filter(
                    EmployeeDocumentLink.employee_id == employee.id,
                    EmployeeDocumentLink.slot_key == "resume",
                )
                .first()
            )
            self.assertIsNotNone(resume_slot)
            if resume_slot is not None:
                self.assertEqual(resume_slot.title, "Резюме")
                self.assertEqual(resume_slot.employee_file_id, db_file.id)
            self.assertEqual(format_message(db, "{resume}", employee, datetime(2026, 9, 1).date(), None), "resume.pdf")

            handled_back = await handle_back_response(messenger, db, employee)

            self.assertTrue(handled_back)
            self.assertFalse(stored_path.exists())
            self.assertIsNone(db.get(EmployeeFile, db_file.id))
            self.assertIsNone(
                db.query(EmployeeDocumentLink)
                .filter(
                    EmployeeDocumentLink.employee_id == employee.id,
                    EmployeeDocumentLink.slot_key == "resume",
                )
                .first()
            )
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

    async def test_confirm_choice_defers_button_side_effects_until_confirm(self) -> None:
        init_db()
        now = datetime.now(UTC).replace(tzinfo=None)
        scenario_key = f"test_confirm_choice_{int(datetime.now(UTC).timestamp() * 1000000)}"

        with SessionLocal() as db:
            scenario = ScenarioTemplate(
                scenario_key=scenario_key,
                title="Confirm choice",
                role_scope="all",
                scenario_kind="scenario",
                sort_order=0,
                trigger_mode="manual_only",
            )
            step = FlowStepTemplate(
                flow_key=scenario_key,
                step_key="salary_step",
                step_title="Salary step",
                sort_order=10,
                default_text="Выбери ожидания по доходу",
                response_type="buttons",
                button_options="100 000\n150 000\n200 000",
                confirm_choice=True,
                target_field="salary_expectation",
                send_mode="immediate",
                day_offset_workdays=0,
            )
            next_step = FlowStepTemplate(
                flow_key=scenario_key,
                step_key="next_step",
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
            db.refresh(step)
            db.refresh(employee)
            hr_settings = _get_or_create_hr_settings(db)
            hr_settings.telegram_user_id = "999020"
            db.add(
                StepButtonNotification(
                    flow_key=scenario_key,
                    step_id=step.id,
                    option_index=1,
                    rule_index=0,
                    message_text="HR: 150 000",
                    recipient_ids="hr",
                    recipient_scope="",
                )
            )
            db.commit()

            messenger = FakeMessenger()
            await send_step(messenger, db, employee, scenario, step)
            handled = await handle_button_response(messenger, db, employee, scenario_key, "salary_step", 1)

            self.assertTrue(handled)
            db.refresh(employee)
            self.assertIsNone(employee.salary_expectation)
            progress = db.query(ScenarioProgress).filter_by(employee_id=employee.id, scenario_key=scenario_key).first()
            self.assertIsNotNone(progress)
            self.assertEqual(progress.pending_confirmation_step_key, "salary_step")
            self.assertEqual(progress.pending_confirmation_option_index, 1)
            self.assertEqual(progress.pending_confirmation_value, "150 000")
            self.assertEqual(messenger.texts[-1]["text"], "Вы выбрали: 150 000. Подтвердить?")
            self.assertNotIn("Спасибо", [item["text"] for item in messenger.texts])
            self.assertNotIn("HR: 150 000", [item["text"] for item in messenger.texts])

            confirmed = await handle_choice_confirmation_response_by_step_id(messenger, db, employee, step.id, "confirm")

            self.assertTrue(confirmed)
            db.refresh(employee)
            self.assertEqual(employee.salary_expectation, "150 000")
            db.refresh(progress)
            self.assertIsNone(progress.pending_confirmation_step_key)
            self.assertIn("Спасибо", [item["text"] for item in messenger.texts])
            self.assertIn("HR: 150 000", [item["text"] for item in messenger.texts])

    async def test_confirm_choice_repeated_same_button_does_not_duplicate_confirmation_message(self) -> None:
        init_db()
        now = datetime.now(UTC).replace(tzinfo=None)
        scenario_key = f"test_confirm_choice_repeat_{int(datetime.now(UTC).timestamp() * 1000000)}"

        with SessionLocal() as db:
            scenario = ScenarioTemplate(
                scenario_key=scenario_key,
                title="Confirm choice repeat",
                role_scope="all",
                scenario_kind="scenario",
                sort_order=0,
                trigger_mode="manual_only",
            )
            step = FlowStepTemplate(
                flow_key=scenario_key,
                step_key="salary_step",
                step_title="Salary step",
                sort_order=10,
                default_text="Выбери ожидания по доходу",
                response_type="buttons",
                button_options="100 000\n150 000",
                confirm_choice=True,
                target_field="salary_expectation",
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

            messenger = FakeMessenger()
            await send_step(messenger, db, employee, scenario, step)
            handled = await handle_button_response(messenger, db, employee, scenario_key, "salary_step", 0)
            confirmation_count = len(messenger.texts)
            repeated = await handle_button_response(messenger, db, employee, scenario_key, "salary_step", 0)

            self.assertTrue(handled)
            self.assertTrue(repeated)
            self.assertEqual(len(messenger.texts), confirmation_count)

    async def test_confirm_choice_change_returns_to_original_buttons_without_saving(self) -> None:
        init_db()
        now = datetime.now(UTC).replace(tzinfo=None)
        scenario_key = f"test_confirm_choice_change_{int(datetime.now(UTC).timestamp() * 1000000)}"

        with SessionLocal() as db:
            scenario = ScenarioTemplate(
                scenario_key=scenario_key,
                title="Confirm choice change",
                role_scope="all",
                scenario_kind="scenario",
                sort_order=0,
                trigger_mode="manual_only",
            )
            step = FlowStepTemplate(
                flow_key=scenario_key,
                step_key="salary_step",
                step_title="Salary step",
                sort_order=10,
                default_text="Выбери ожидания по доходу",
                response_type="buttons",
                button_options="100 000\n150 000",
                confirm_choice=True,
                target_field="salary_expectation",
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
            db.refresh(step)

            messenger = FakeMessenger()
            await send_step(messenger, db, employee, scenario, step)
            await handle_button_response(messenger, db, employee, scenario_key, "salary_step", 1)

            changed = await handle_choice_confirmation_response_by_step_id(messenger, db, employee, step.id, "change")

            self.assertTrue(changed)
            db.refresh(employee)
            self.assertIsNone(employee.salary_expectation)
            progress = db.query(ScenarioProgress).filter_by(employee_id=employee.id, scenario_key=scenario_key).first()
            self.assertIsNotNone(progress)
            self.assertIsNone(progress.pending_confirmation_step_key)
            self.assertEqual(messenger.texts[-1]["text"], "Выбери ожидания по доходу")

    async def test_back_cancels_pending_choice_confirmation(self) -> None:
        init_db()
        now = datetime.now(UTC).replace(tzinfo=None)
        scenario_key = f"test_confirm_choice_back_{int(datetime.now(UTC).timestamp() * 1000000)}"

        with SessionLocal() as db:
            scenario = ScenarioTemplate(
                scenario_key=scenario_key,
                title="Confirm choice back",
                role_scope="all",
                scenario_kind="scenario",
                sort_order=0,
                trigger_mode="manual_only",
            )
            step = FlowStepTemplate(
                flow_key=scenario_key,
                step_key="salary_step",
                step_title="Salary step",
                sort_order=10,
                default_text="Выбери ожидания по доходу",
                response_type="buttons",
                button_options="100 000\n150 000",
                confirm_choice=True,
                target_field="salary_expectation",
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

            messenger = FakeMessenger()
            await send_step(messenger, db, employee, scenario, step)
            await handle_button_response(messenger, db, employee, scenario_key, "salary_step", 1)
            handled_back = await handle_back_response(messenger, db, employee)

            self.assertTrue(handled_back)
            db.refresh(employee)
            self.assertIsNone(employee.salary_expectation)
            progress = db.query(ScenarioProgress).filter_by(employee_id=employee.id, scenario_key=scenario_key).first()
            self.assertIsNotNone(progress)
            self.assertEqual(progress.current_step_key, "salary_step")
            self.assertIsNone(progress.pending_confirmation_step_key)

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


if __name__ == "__main__":
    unittest.main()
