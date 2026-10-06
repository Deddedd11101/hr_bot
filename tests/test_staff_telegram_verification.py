import asyncio
import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import Base
from app.messaging.identity import get_primary_chat_id, set_primary_chat_id
from app.messaging.service import handle_start_command, handle_text_event, resolve_inbound_access
from app.messaging.verification import get_challenge
from app.models import Employee
from app.web.employees import _reset_employee_bot_linkage
from app.web.bulk_actions import _send_mass_message


class Messenger:
    def __init__(self):
        self.sent_texts = []

    async def send_text(self, chat_id, text, reply_markup=None):
        self.sent_texts.append((chat_id, text))


class StaffTelegramVerificationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.mail = []
        self.patches = [
            patch.object(settings, "SMTP_HOST", "smtp.example.test"),
            patch.object(settings, "SMTP_USERNAME", "hrbot@example.test"),
            patch.object(settings, "SMTP_PASSWORD", "test-secret"),
            patch.object(settings, "SMTP_FROM_EMAIL", "hrbot@example.test"),
            patch("app.messaging.verification.send_staff_code", side_effect=lambda email, code: self.mail.append((email, code))),
        ]
        for item in self.patches:
            item.start()
        self.employee = Employee(
            full_name="Тестовый сотрудник",
            telegram_username="staff_test",
            employee_stage="staff",
            work_email="staff@ze.studio",
            created_at=datetime.now(UTC).replace(tzinfo=None),
            is_flow_scheduled=False,
        )
        self.db.add(self.employee)
        self.db.commit()
        self.messenger = Messenger()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.db.close()
        self.engine.dispose()

    def test_username_hint_only_links_after_email_code(self):
        asyncio.run(handle_start_command(self.messenger, self.db, "123456", "STAFF_TEST"))
        self.assertEqual(len(self.mail), 1)
        self.assertIsNone(self.employee.telegram_user_id)
        self.assertEqual(resolve_inbound_access(self.db, "123456", "STAFF_TEST").state, "verification_required")
        self.assertEqual(self.mail[0][0], "staff@ze.studio")

        self.assertEqual(asyncio.run(handle_text_event(self.messenger, self.db, "123456", "STAFF_TEST", "00000000")), "handled")
        self.assertIsNone(self.employee.telegram_user_id)
        self.assertEqual(asyncio.run(handle_text_event(self.messenger, self.db, "123456", "STAFF_TEST", self.mail[0][1])), "handled")
        self.assertEqual(get_primary_chat_id(self.employee, db=self.db), "123456")
        self.assertEqual(self.employee.telegram_verified_user_id, "123456")
        self.assertIsNone(get_challenge(self.db, "123456"))
        self.assertEqual(resolve_inbound_access(self.db, "123456", "staff_test").state, "ok")

    def test_existing_numeric_link_must_be_verified_again(self):
        set_primary_chat_id(self.employee, "123456", db=self.db)
        self.db.commit()
        self.assertIsNone(get_primary_chat_id(self.employee, db=self.db))
        self.assertEqual(resolve_inbound_access(self.db, "123456", None).state, "verification_required")
        asyncio.run(handle_start_command(self.messenger, self.db, "123456", None))
        self.assertEqual(len(self.mail), 1)
        asyncio.run(handle_text_event(self.messenger, self.db, "123456", None, self.mail[0][1]))
        self.assertEqual(get_primary_chat_id(self.employee, db=self.db), "123456")

    def test_mass_message_cannot_use_old_unverified_numeric_id(self):
        set_primary_chat_id(self.employee, "123456", db=self.db)
        self.db.commit()
        self.assertFalse(asyncio.run(_send_mass_message(self.db, self.messenger, self.employee, "Секретный текст")))
        self.assertEqual(self.messenger.sent_texts, [])

    def test_resend_is_limited_and_does_not_link_other_telegram_id(self):
        asyncio.run(handle_start_command(self.messenger, self.db, "123456", "staff_test"))
        asyncio.run(handle_start_command(self.messenger, self.db, "123456", "staff_test"))
        self.assertEqual(len(self.mail), 1)
        asyncio.run(handle_start_command(self.messenger, self.db, "654321", "staff_test"))
        self.assertEqual(len(self.mail), 2)
        asyncio.run(handle_text_event(self.messenger, self.db, "123456", "staff_test", self.mail[0][1]))
        self.assertEqual(resolve_inbound_access(self.db, "654321", "staff_test").state, "verification_required")
        self.assertEqual(asyncio.run(handle_text_event(self.messenger, self.db, "654321", "staff_test", self.mail[1][1])), "handled")
        self.assertEqual(self.employee.telegram_verified_user_id, "123456")
        self.assertEqual(get_primary_chat_id(self.employee, db=self.db), "123456")

    def test_duplicate_work_email_fails_closed(self):
        self.db.add(Employee(
            full_name="Другой сотрудник", telegram_username="other_staff", employee_stage="staff",
            work_email=" STAFF@ze.studio ", created_at=datetime.now(UTC).replace(tzinfo=None), is_flow_scheduled=False,
        ))
        self.db.commit()
        asyncio.run(handle_start_command(self.messenger, self.db, "123456", "staff_test"))
        self.assertEqual(self.mail, [])
        self.assertIsNone(get_challenge(self.db, "123456"))

    def test_unavailable_mail_does_not_link_or_leave_valid_code(self):
        with patch.object(settings, "SMTP_PASSWORD", ""):
            asyncio.run(handle_start_command(self.messenger, self.db, "123456", "staff_test"))
        self.assertEqual(self.mail, [])
        self.assertIsNone(self.employee.telegram_user_id)
        self.assertIsNone(get_challenge(self.db, "123456"))

    def test_expired_code_and_attempt_limit_do_not_link(self):
        asyncio.run(handle_start_command(self.messenger, self.db, "123456", "staff_test"))
        challenge = get_challenge(self.db, "123456")
        challenge.expires_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=1)
        self.db.commit()
        asyncio.run(handle_text_event(self.messenger, self.db, "123456", "staff_test", self.mail[0][1]))
        self.assertIsNone(self.employee.telegram_verified_at)
        self.assertIsNone(challenge.code_hash)

        challenge.last_sent_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=2)
        self.db.commit()
        asyncio.run(handle_start_command(self.messenger, self.db, "123456", "staff_test"))
        self.assertEqual(len(self.mail), 2)
        for _ in range(5):
            asyncio.run(handle_text_event(self.messenger, self.db, "123456", "staff_test", "00000000"))
        asyncio.run(handle_text_event(self.messenger, self.db, "123456", "staff_test", self.mail[1][1]))
        self.assertIsNone(self.employee.telegram_verified_at)

    def test_reset_revokes_verification_and_pending_code(self):
        asyncio.run(handle_start_command(self.messenger, self.db, "123456", "staff_test"))
        asyncio.run(handle_text_event(self.messenger, self.db, "123456", "staff_test", self.mail[0][1]))
        self.assertEqual(self.employee.telegram_verified_user_id, "123456")
        _reset_employee_bot_linkage(self.db, self.employee)
        self.assertIsNone(self.employee.telegram_verified_user_id)
        self.assertIsNone(get_primary_chat_id(self.employee, db=self.db))
        self.assertIsNone(get_challenge(self.db, "123456"))


if __name__ == "__main__":
    unittest.main()
