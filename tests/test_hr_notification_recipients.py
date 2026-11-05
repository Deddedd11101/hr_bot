from datetime import datetime
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.database import Base
from app.models import Employee, HrSettings
from app.notifications import _notification_recipients
from app.scenario_engine import resolve_notification_recipients


class HrNotificationRecipientsTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.hr = HrSettings(id=1, telegram_user_id="9001", notification_recipient_ids="employee:78,9001,invalid", created_at=datetime(2026, 1, 1), updated_at=datetime(2026, 1, 1))
        self.person = Employee(id=78, full_name="Extra HR", employee_stage="staff", created_at=datetime(2026, 1, 1))
        self.db.add_all([self.hr, self.person])
        self.db.commit()
        self.identity = patch("app.messaging.identity.get_primary_chat_id", return_value="9078")
        self.identity.start()
        self.allowed = patch("app.notifications.chat_id_allowed", return_value=True)
        self.allowed.start()

    def tearDown(self):
        self.identity.stop()
        self.allowed.stop()
        self.db.close()
        self.engine.dispose()

    def test_hr_expands_both_token_formats_without_duplicates(self):
        self.assertEqual(_notification_recipients(self.hr, db=self.db), ["9001", "9078"])
        subject = SimpleNamespace()
        self.assertEqual(resolve_notification_recipients(self.db, subject, "hr,hr", "hr"), ["9001", "9078"])

    def test_non_hr_notification_does_not_gain_additional_recipient(self):
        self.assertEqual(resolve_notification_recipients(self.db, SimpleNamespace(), "", ""), [])

    def test_observer_receives_related_role_notifications_without_hr_and_dedupes(self):
        self.hr.notification_recipient_ids = "observer:employee:78,employee:78"
        self.db.flush()
        subject = SimpleNamespace(manager_employee_id=78, manager_telegram_id=None)
        self.assertEqual(resolve_notification_recipients(self.db, subject, "manager", ""), ["9078"])
        with patch("app.scenario_engine._resolve_related_employee_chat_id", return_value="9080"):
            self.assertEqual(resolve_notification_recipients(self.db, subject, "manager", ""), ["9080", "9078"])
        self.assertEqual(resolve_notification_recipients(self.db, subject, "", ""), [])
        self.assertEqual(_notification_recipients(self.hr, db=self.db), ["9001", "9078"])

    def test_blocked_candidate_and_unlinked_recipient_are_excluded(self):
        for stage, blocked in (("candidate", False), ("archived", False), ("staff", True)):
            self.person.employee_stage, self.person.is_bot_blocked = stage, blocked
            self.db.flush()
            self.assertEqual(_notification_recipients(self.hr, db=self.db), ["9001"])

    def test_settings_recipient_changes_require_admin_and_verified_staff(self):
        from app.web.settings_routes import _validated_hr_notification_ids
        with patch("app.web.settings_routes.require_api_admin", side_effect=HTTPException(403)) as admin:
            self.assertEqual(_validated_hr_notification_ids(None, self.db, "employee:78", "employee:78"), "employee:78")
            admin.assert_not_called()
            with self.assertRaises(HTTPException):
                _validated_hr_notification_ids(None, self.db, "", "employee:78")
        with patch("app.web.settings_routes.require_api_admin"), patch("app.web.settings_routes.get_primary_chat_id", return_value="9078"):
            self.assertEqual(_validated_hr_notification_ids(None, self.db, "", "employee:78"), "employee:78")
            self.assertEqual(_validated_hr_notification_ids(None, self.db, "", "observer:employee:78"), "observer:employee:78")
            self.person.employee_stage = "candidate"
            self.db.flush()
            with self.assertRaises(HTTPException) as error:
                _validated_hr_notification_ids(None, self.db, "", "employee:78")
            self.assertEqual(error.exception.status_code, 422)
            with self.assertRaises(HTTPException):
                _validated_hr_notification_ids(None, self.db, "", "observer:employee:78")
        self.person.employee_stage, self.person.is_bot_blocked = "staff", False
        self.db.flush()
        with patch("app.messaging.identity.get_primary_chat_id", return_value=None):
            self.assertEqual(_notification_recipients(self.hr, db=self.db), ["9001"])
