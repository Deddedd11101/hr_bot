import unittest
from types import SimpleNamespace

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


if __name__ == "__main__":
    unittest.main()
