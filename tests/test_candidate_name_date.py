"""Candidate FIO and calendar regressions, using an isolated database and no network."""

import json
import unittest
from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.messaging.service import handle_back_event, handle_date_event, handle_text_event
from app.models import Employee, FlowStepTemplate, ScenarioProgress, ScenarioTemplate
from app.scenario_engine import (
    DATE_CALLBACK_PREFIX,
    format_message,
    render_menu_text,
    resolve_employee_first_name,
    start_scenario,
)
from tests.test_scenario_engine_smoke import FakeMessenger


class CandidateNameTests(unittest.TestCase):
    def test_surname_first_fio_and_explicit_override(self):
        for full_name, explicit, expected in [
            ("Surname Given Patronymic", None, "Given"),
            ("  Surname\tGiven  Patronymic ", "  ", "Given"),
            ("Given", None, "Given"),
            (" ", None, ""),
            (None, None, ""),
            ("Surname Given", " Preferred ", "Preferred"),
        ]:
            with self.subTest(full_name=full_name, explicit=explicit):
                employee = SimpleNamespace(full_name=full_name, first_name=explicit)
                self.assertEqual(resolve_employee_first_name(employee), expected)
                self.assertEqual(employee.first_name, explicit)

    def test_menu_aliases_escape_derived_name(self):
        employee = Employee(full_name="Surname A&B")
        self.assertEqual(render_menu_text("{first_name}/{name}", employee), "A&amp;B/A&amp;B")


class CandidateDateTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.db.close)
        self.messenger = FakeMessenger()
        self.employee = Employee(
            full_name="Candidate", telegram_user_id="990001", employee_stage="candidate",
            created_at=datetime.now(UTC).replace(tzinfo=None),
        )
        self.scenario = ScenarioTemplate(
            scenario_key="candidate_name_date", title="Name/date regression", role_scope="all",
            scenario_kind="scenario", trigger_mode="manual_only",
        )
        self.name_step = self.step("name", 10, "text", "full_name", "Enter FIO")
        self.date_step = self.step("date", 20, "date", "first_workday", "{first_name}/{name}: choose date")
        self.next_step = self.step("next", 30, "text", None, "Next question")
        self.db.add_all([self.employee, self.scenario, self.name_step, self.date_step, self.next_step])
        self.db.commit()

    def step(self, key, order, response_type, target_field, text):
        return FlowStepTemplate(
            flow_key="candidate_name_date", step_key=key, step_title=key, sort_order=order,
            default_text=text, response_type=response_type, target_field=target_field,
            send_mode="immediate", day_offset_workdays=0,
        )

    @property
    def progress(self):
        return self.db.query(ScenarioProgress).filter_by(employee_id=self.employee.id).one()

    async def open_calendar(self, previous_date=None):
        self.employee.first_workday = previous_date
        self.db.commit()
        self.assertTrue(await start_scenario(self.messenger, self.db, self.employee, self.scenario.scenario_key))
        self.assertEqual(await handle_text_event(
            self.messenger, self.db, "990001", None, "Surname Given Patronymic",
        ), "handled")

    async def select(self, value, action="set"):
        return await handle_date_event(
            self.messenger, self.db, "990001", None,
            f"{DATE_CALLBACK_PREFIX}{self.date_step.id}:{action}:{value}",
        )

    async def back(self):
        self.assertEqual(await handle_back_event(self.messenger, self.db, "990001", None), "handled")

    async def test_fio_input_immediately_populates_both_aliases_without_writing_first_name(self):
        await self.open_calendar()
        self.assertEqual(self.messenger.texts[-1]["text"], "Given/Given: choose date")
        self.assertIsNone(self.employee.first_name)
        self.assertEqual(format_message(self.db, "{first_name}/{name}", self.employee, date.today(), None), "Given/Given")

    async def test_selection_is_readable_and_replay_does_not_redeliver(self):
        await self.open_calendar()
        before = len(self.messenger.texts)
        handled, result = await self.select("2026-10-12")
        self.assertEqual((handled, result.action), ("handled", "selected"))
        self.assertEqual(self.employee.first_workday, date(2026, 10, 12))
        self.assertEqual([item["text"] for item in self.messenger.texts[before:]], [
            "\u0412\u044b \u0432\u044b\u0431\u0440\u0430\u043b\u0438 \u0434\u0430\u0442\u0443: 12.10.2026", "Next question",
        ])
        delivered = len(self.messenger.texts)
        history = self.progress.response_undo_history
        for value in ("2026-10-12", "2026-10-15"):
            self.assertEqual((await self.select(value))[0], "ignored")
        self.assertEqual(len(self.messenger.texts), delivered)
        self.assertEqual(self.progress.response_undo_history, history)
        self.assertEqual(self.employee.first_workday, date(2026, 10, 12))

    async def test_choose_next_back_replace_and_undo_with_existing_date(self):
        original = date(2026, 9, 1)
        await self.open_calendar(original)
        self.assertEqual((await self.select("2026-10-12"))[0], "handled")
        self.assertEqual(self.progress.current_step_key, "next")
        snapshot = json.loads(self.progress.response_undo_history)[-1]
        self.assertEqual(snapshot["employee_before"]["first_workday"], "2026-09-01")
        self.db.expire_all()  # Undo must work after a database round trip, not just in memory.
        await self.back()
        self.assertEqual(self.employee.first_workday, original)
        self.assertEqual(self.progress.current_step_key, "date")
        self.assertTrue(self.progress.waiting_for_response)
        self.assertIsNotNone(self.messenger.texts[-1]["reply_markup"])
        self.assertEqual((await self.select("2026-10-15"))[0], "handled")
        self.assertEqual(self.employee.first_workday, date(2026, 10, 15))
        self.assertEqual(self.progress.current_step_key, "next")
        self.assertEqual(sum(item["text"] == "Next question" for item in self.messenger.texts), 2)
        self.db.expire_all()
        await self.back()
        self.assertEqual(self.employee.first_workday, original)

    async def test_empty_date_back_same_date_and_replay(self):
        await self.open_calendar()
        await self.select("2026-10-12")
        await self.back()
        self.assertIsNone(self.employee.first_workday)
        self.assertEqual((await self.select("2026-10-12"))[0], "handled")
        self.assertEqual((await self.select("2026-10-12"))[0], "ignored")
        self.assertEqual(sum(item["text"] == "Next question" for item in self.messenger.texts), 2)

    async def test_same_as_existing_date_can_be_selected_and_undone(self):
        await self.open_calendar(date(2026, 10, 12))
        self.assertEqual((await self.select("2026-10-12"))[0], "handled")
        await self.back()
        self.assertEqual(self.employee.first_workday, date(2026, 10, 12))

    async def test_replay_during_receipt_delivery_is_ignored(self):
        await self.open_calendar()
        send_text = self.messenger.send_text
        replay_results = []

        async def send_with_replay(chat_id, text, reply_markup=None):
            if text.endswith("12.10.2026"):
                replay_results.append((await self.select("2026-10-12"))[0])
            await send_text(chat_id, text, reply_markup)

        with patch.object(self.messenger, "send_text", side_effect=send_with_replay):
            self.assertEqual((await self.select("2026-10-12"))[0], "handled")
        self.assertEqual(replay_results, ["ignored"])
        self.assertEqual(sum(item["text"] == "Next question" for item in self.messenger.texts), 1)
        self.assertEqual(len(json.loads(self.progress.response_undo_history)), 2)

    async def test_receipt_delivery_failure_does_not_strand_accepted_date(self):
        await self.open_calendar()
        send_text = self.messenger.send_text

        async def fail_receipt(chat_id, text, reply_markup=None):
            if text.endswith("12.10.2026"):
                raise RuntimeError("receipt delivery failed")
            await send_text(chat_id, text, reply_markup)

        with patch.object(self.messenger, "send_text", side_effect=fail_receipt):
            with self.assertRaisesRegex(RuntimeError, "receipt delivery failed"):
                await self.select("2026-10-12")
        self.assertEqual(self.employee.first_workday, date(2026, 10, 12))
        self.assertEqual(self.progress.current_step_key, "next")
        self.assertEqual((await self.select("2026-10-12"))[0], "ignored")
        await self.back()
        self.assertIsNone(self.employee.first_workday)

    async def test_navigation_invalid_date_and_back_do_not_change_data(self):
        original = date(2026, 9, 1)
        await self.open_calendar(original)
        history = self.progress.response_undo_history
        handled, result = await self.select("2026-11", action="nav")
        self.assertEqual((handled, result.action), ("handled", "updated"))
        callbacks = [button.callback_data for row in result.reply_markup.inline_keyboard for button in row]
        self.assertIn(f"{DATE_CALLBACK_PREFIX}{self.date_step.id}:set:2026-11-01", callbacks)
        self.assertEqual((await self.select("2026-02-30"))[0], "ignored")
        self.assertEqual(self.employee.first_workday, original)
        self.assertEqual(self.progress.response_undo_history, history)
        await self.back()
        self.assertEqual(self.progress.current_step_key, "name")
        self.assertEqual(self.employee.full_name, "Candidate")
        self.assertEqual(self.employee.first_workday, original)
