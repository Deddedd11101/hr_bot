import asyncio
import unittest
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from app.config import settings
from app.database import SessionLocal, init_db
from app.messaging.identity import get_primary_chat_id, set_primary_chat_id
from app.messaging.service import handle_start_command, handle_text_event, resolve_inbound_access
from app.models import Employee, EmployeeMessengerAccount, EmployeeTelegramEmailVerification
from app.scenario_engine import resolve_notification_recipients
from app.staff_email_verification import MAX_ATTEMPTS, chat_id_allowed, confirm_code, is_verified, prepare_challenge
from app.time_utils import utc_now
from app.web.bulk_actions import _send_mass_message
from app.web.employees import _reset_employee_bot_linkage


class FakeMessenger:
    def __init__(self):
        self.messages = []

    async def send_text(self, *, chat_id, text, **kwargs):
        self.messages.append((chat_id, text))

    async def send_menu(self, *, chat_id, text, **kwargs):
        self.messages.append((chat_id, text))


class StaffEmailVerificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.suffix = uuid4().hex[:10]
        self.chat_id = str(int(self.suffix[:7], 16) + 100000000)
        self.username = f"staff_{self.suffix}"
        self.email = f"staff-{self.suffix}@ze.studio"
        self.patches = [
            patch.object(settings, "STAFF_EMAIL_OTP_ENABLED", True),
            patch.object(settings, "STAFF_EMAIL_DOMAIN", "ze.studio"),
            patch.object(settings, "STAFF_EMAIL_SMTP_PASSWORD", "test-only-password"),
            patch.object(settings, "ADMIN_SESSION_SECRET", "test-only-secret-which-is-not-the-default"),
        ]
        for item in self.patches:
            item.start()
        with SessionLocal() as db:
            employee = Employee(
                full_name="Test Staff",
                telegram_user_id=None,
                telegram_username=self.username,
                work_email=self.email,
                employee_stage="staff",
                created_at=utc_now(),
                is_flow_scheduled=False,
            )
            db.add(employee)
            db.commit()
            self.employee_id = employee.id

    def tearDown(self):
        with SessionLocal() as db:
            db.query(EmployeeTelegramEmailVerification).filter_by(employee_id=self.employee_id).delete()
            db.query(EmployeeMessengerAccount).filter_by(employee_id=self.employee_id).delete()
            db.query(Employee).filter_by(id=self.employee_id).delete()
            db.commit()
        for item in reversed(self.patches):
            item.stop()

    def _request_code(self):
        messenger = FakeMessenger()
        with patch("app.messaging.service.send_code_email") as email_sender:
            with SessionLocal() as db:
                asyncio.run(handle_start_command(messenger, db, self.chat_id, self.username))
        self.assertEqual(email_sender.call_count, 1)
        self.assertEqual(email_sender.call_args.args[0], self.email)
        return email_sender.call_args.args[1], messenger

    def test_existing_numeric_link_requires_email_before_menu_and_inbound(self):
        with SessionLocal() as db:
            employee = db.get(Employee, self.employee_id)
            set_primary_chat_id(employee, self.chat_id, db=db)
            db.commit()
            self.assertIsNone(get_primary_chat_id(employee, db=db))
            self.assertEqual(get_primary_chat_id(employee, db=db, include_unverified=True), self.chat_id)
            self.assertEqual(resolve_inbound_access(db, self.chat_id, self.username).state, "verification_required")
        code, messenger = self._request_code()
        self.assertTrue(any("6 цифр" in text for _, text in messenger.messages))
        with SessionLocal() as db:
            employee = db.get(Employee, self.employee_id)
            self.assertTrue(confirm_code(db, employee, self.chat_id, code))
            self.assertEqual(get_primary_chat_id(employee, db=db), self.chat_id)
            self.assertEqual(resolve_inbound_access(db, self.chat_id, self.username).state, "ok")

    def test_wrong_code_expires_and_does_not_link(self):
        code, _ = self._request_code()
        with SessionLocal() as db:
            employee = db.get(Employee, self.employee_id)
            for _ in range(5):
                self.assertFalse(confirm_code(db, employee, self.chat_id, "000000" if code != "000000" else "111111"))
            row = db.get(EmployeeTelegramEmailVerification, self.employee_id)
            self.assertIsNone(row.code_hash)
            self.assertFalse(confirm_code(db, employee, self.chat_id, code))
            self.assertIsNone(get_primary_chat_id(employee, db=db))

    def test_correct_code_succeeds_on_fifth_attempt(self):
        code, _ = self._request_code()
        wrong_code = "000000" if code != "000000" else "111111"
        with SessionLocal() as db:
            employee = db.get(Employee, self.employee_id)
            for _ in range(MAX_ATTEMPTS - 1):
                self.assertFalse(confirm_code(db, employee, self.chat_id, wrong_code))
            self.assertTrue(confirm_code(db, employee, self.chat_id, code))
            row = db.get(EmployeeTelegramEmailVerification, self.employee_id)
            self.assertIsNone(row.code_hash)
            self.assertEqual(row.attempts, MAX_ATTEMPTS)

    def test_expired_code_and_changed_email_are_rejected(self):
        code, _ = self._request_code()
        with SessionLocal() as db:
            employee = db.get(Employee, self.employee_id)
            row = db.get(EmployeeTelegramEmailVerification, self.employee_id)
            row.expires_at = utc_now() - timedelta(seconds=1)
            db.commit()
            self.assertFalse(confirm_code(db, employee, self.chat_id, code))
            row.last_sent_at = utc_now() - timedelta(minutes=2)
            db.commit()
        second_code, _ = self._request_code()
        with SessionLocal() as db:
            employee = db.get(Employee, self.employee_id)
            employee.work_email = f"changed-{self.suffix}@ze.studio"
            db.commit()
            self.assertFalse(confirm_code(db, employee, self.chat_id, second_code))
            row = db.get(EmployeeTelegramEmailVerification, self.employee_id)
            self.assertIsNone(row.code_hash)
            self.assertIsNone(row.pending_work_email)

    def test_confirm_code_is_single_use_across_stale_sessions(self):
        code, _ = self._request_code()
        first_db = SessionLocal()
        second_db = SessionLocal()
        try:
            first_employee = first_db.get(Employee, self.employee_id)
            second_employee = second_db.get(Employee, self.employee_id)
            # Keep the second session's verification row stale to exercise the
            # conditional UPDATE rather than an ORM-side mutable check.
            second_db.get(EmployeeTelegramEmailVerification, self.employee_id)
            self.assertTrue(confirm_code(first_db, first_employee, self.chat_id, code))
            self.assertFalse(confirm_code(second_db, second_employee, self.chat_id, code))
        finally:
            first_db.close()
            second_db.close()

    def test_verified_state_rechecks_current_unique_work_email(self):
        code, _ = self._request_code()
        with SessionLocal() as db:
            employee = db.get(Employee, self.employee_id)
            self.assertTrue(confirm_code(db, employee, self.chat_id, code))
            self.assertTrue(is_verified(db, employee, self.chat_id))
            duplicate = Employee(
                full_name="Duplicate Verified Staff",
                work_email=self.email,
                employee_stage="staff",
                created_at=utc_now(),
            )
            db.add(duplicate)
            db.commit()
            duplicate_id = duplicate.id
            self.assertFalse(is_verified(db, employee, self.chat_id))
        with SessionLocal() as db:
            db.query(Employee).filter_by(id=duplicate_id).delete()
            db.commit()

    def test_prepare_challenge_returns_existing_active_challenge_during_cooldown(self):
        code, _ = self._request_code()
        self.assertTrue(code)
        with SessionLocal() as db:
            employee = db.get(Employee, self.employee_id)
            replacement_code, address = prepare_challenge(db, employee, self.chat_id)
        self.assertEqual(replacement_code, "")
        self.assertEqual(address, self.email)

    def test_username_cannot_replace_another_linked_telegram_id(self):
        with SessionLocal() as db:
            employee = db.get(Employee, self.employee_id)
            set_primary_chat_id(employee, self.chat_id, db=db)
            db.commit()
            self.assertEqual(resolve_inbound_access(db, "987654321", self.username).state, "conflict")
            self.assertEqual(employee.telegram_user_id, self.chat_id)

    def test_reset_removes_verification(self):
        code, _ = self._request_code()
        with SessionLocal() as db:
            employee = db.get(Employee, self.employee_id)
            self.assertTrue(confirm_code(db, employee, self.chat_id, code))
            _reset_employee_bot_linkage(db, employee)
            self.assertIsNone(db.get(EmployeeTelegramEmailVerification, self.employee_id))
            self.assertIsNone(employee.telegram_user_id)

    def test_code_message_is_handled_before_scenario_answers(self):
        code, _ = self._request_code()
        messenger = FakeMessenger()
        with SessionLocal() as db:
            result = asyncio.run(handle_text_event(messenger, db, self.chat_id, self.username, code))
            self.assertEqual(result, "handled")
            self.assertEqual(resolve_inbound_access(db, self.chat_id, self.username).state, "ok")

    def test_bulk_and_legacy_notification_cannot_bypass_verification(self):
        with SessionLocal() as db:
            employee = db.get(Employee, self.employee_id)
            set_primary_chat_id(employee, self.chat_id, db=db)
            db.commit()
            self.assertFalse(chat_id_allowed(db, self.chat_id))
            messenger = FakeMessenger()
            self.assertFalse(asyncio.run(_send_mass_message(db, messenger, employee, "Тест")))
            self.assertEqual(messenger.messages, [])
            employee.manager_telegram_id = self.chat_id
            self.assertEqual(resolve_notification_recipients(db, employee, None, "manager"), [])
        code, _ = self._request_code()
        with SessionLocal() as db:
            employee = db.get(Employee, self.employee_id)
            self.assertTrue(confirm_code(db, employee, self.chat_id, code))
            self.assertTrue(chat_id_allowed(db, self.chat_id))
            self.assertTrue(asyncio.run(_send_mass_message(db, FakeMessenger(), employee, "Тест")))

    def test_missing_or_duplicate_work_email_fails_closed(self):
        with SessionLocal() as db:
            employee = db.get(Employee, self.employee_id)
            employee.work_email = ""
            db.commit()
        messenger = FakeMessenger()
        with patch("app.messaging.service.send_code_email") as email_sender:
            with SessionLocal() as db:
                asyncio.run(handle_start_command(messenger, db, self.chat_id, self.username))
        email_sender.assert_not_called()
        self.assertTrue(any("Не удалось отправить код" in text for _, text in messenger.messages))

        with SessionLocal() as db:
            employee = db.get(Employee, self.employee_id)
            employee.work_email = self.email
            duplicate = Employee(full_name="Duplicate Staff", work_email=self.email, employee_stage="staff", created_at=utc_now())
            db.add(duplicate)
            db.commit()
            duplicate_id = duplicate.id
        try:
            messenger = FakeMessenger()
            with patch("app.messaging.service.send_code_email") as email_sender:
                with SessionLocal() as db:
                    asyncio.run(handle_start_command(messenger, db, self.chat_id, self.username))
            email_sender.assert_not_called()
            self.assertTrue(any("Не удалось отправить код" in text for _, text in messenger.messages))
        finally:
            with SessionLocal() as db:
                db.query(Employee).filter_by(id=duplicate_id).delete()
                db.commit()
