import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from app.database import SessionLocal, init_db
from app.models import Employee, FlowStepTemplate, HrSettings, ScenarioProgress, ScenarioTemplate
from app.scenario_engine import (
    SCENARIO_BACK_BUTTON_TEXT,
    DATE_CALLBACK_PREFIX,
    handle_button_response,
    handle_back_response,
    handle_date_response_by_step_id,
    matches_role_scope,
    resolve_notification_recipients,
    scenario_anchor_date,
    send_step,
    send_step_attachment,
)


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

    async def send_photo_path(self, chat_id: str, path, filename: str | None = None) -> None:
        self.photos.append({"chat_id": chat_id, "path": str(path), "filename": filename})

    async def send_photo_bytes(self, chat_id: str, data: bytes, filename: str) -> None:
        self.photos.append({"chat_id": chat_id, "bytes": len(data), "filename": filename})

    async def send_document_path(self, chat_id: str, path, filename: str | None = None) -> None:
        self.documents.append({"chat_id": chat_id, "path": str(path), "filename": filename})


class ScenarioEngineSmokeTests(unittest.IsolatedAsyncioTestCase):
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
            settings = db.get(HrSettings, 1)
            if settings is None:
                settings = HrSettings(id=1, telegram_user_id="555001")
                db.add(settings)
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


if __name__ == "__main__":
    unittest.main()
