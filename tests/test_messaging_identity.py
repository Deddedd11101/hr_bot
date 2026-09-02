import unittest
from types import SimpleNamespace

from app.main import _apply_employee_telegram_identity
from app.messaging.identity import (
    get_primary_chat_id,
    get_public_chat_handle,
    normalize_public_chat_handle,
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
        set_public_chat_handle(employee, " @User_Name ")
        self.assertEqual(employee.telegram_user_id, "12345")
        self.assertEqual(employee.telegram_username, "user_name")

        set_primary_chat_id(employee, "   ")
        set_public_chat_handle(employee, "")
        self.assertIsNone(employee.telegram_user_id)
        self.assertIsNone(employee.telegram_username)

    def test_apply_employee_telegram_identity_sets_public_handle(self) -> None:
        employee = SimpleNamespace(telegram_user_id=None, telegram_username=None)

        _apply_employee_telegram_identity(employee, chat_id="", chat_handle=" @HR_Team ")

        self.assertIsNone(employee.telegram_user_id)
        self.assertEqual(employee.telegram_username, "hr_team")

    def test_username_normalization_treats_at_sign_case_and_spaces_as_same_handle(self) -> None:
        self.assertEqual(normalize_public_chat_handle(" @Name "), "name")
        self.assertEqual(normalize_public_chat_handle("Name"), "name")
        self.assertEqual(normalize_public_chat_handle(" name "), "name")
        self.assertIsNone(normalize_public_chat_handle(" @ "))


if __name__ == "__main__":
    unittest.main()
