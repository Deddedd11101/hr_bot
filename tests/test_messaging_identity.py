import unittest
from types import SimpleNamespace

from app.main import _apply_employee_telegram_identity
from app.messaging.identity import (
    get_primary_chat_id,
    get_public_chat_handle,
    set_primary_chat_id,
    set_public_chat_handle,
)


class MessagingIdentityTests(unittest.TestCase):
    def test_getters_normalize_empty_values(self) -> None:
        employee = SimpleNamespace(telegram_user_id="  ", telegram_username="")

        self.assertIsNone(get_primary_chat_id(employee))
        self.assertIsNone(get_public_chat_handle(employee))

    def test_setters_strip_values_and_store_none_for_empty(self) -> None:
        employee = SimpleNamespace(telegram_user_id=None, telegram_username=None)

        set_primary_chat_id(employee, " 12345 ")
        set_public_chat_handle(employee, " user_name ")
        self.assertEqual(employee.telegram_user_id, "12345")
        self.assertEqual(employee.telegram_username, "user_name")

        set_primary_chat_id(employee, "   ")
        set_public_chat_handle(employee, "")
        self.assertIsNone(employee.telegram_user_id)
        self.assertIsNone(employee.telegram_username)

    def test_apply_employee_telegram_identity_sets_public_handle(self) -> None:
        employee = SimpleNamespace(telegram_user_id=None, telegram_username=None)

        _apply_employee_telegram_identity(employee, chat_id="", chat_handle=" hr_team ")

        self.assertIsNone(employee.telegram_user_id)
        self.assertEqual(employee.telegram_username, "hr_team")


if __name__ == "__main__":
    unittest.main()
