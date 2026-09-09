import asyncio
import unittest
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.auth import authenticate_account, create_admin_session_token
from app.database import SessionLocal, init_db
from app.hr_linking import consume_hr_link_token, hash_hr_link_token
from app.main import AUTH_COOKIE_NAME, app
from app.messaging.service import handle_menu_callback, handle_start_command
from app.models import BotMenuButton, BotMenuSet, Employee, HrSettings
from app.scenario_engine import _resolve_explicit_notification_recipient
from app.time_utils import utc_now
from app.web.settings import _get_or_create_hr_settings


class InlineMessenger:
    def __init__(self) -> None:
        self.sent_texts: list[tuple[str, str]] = []
        self.inline_sends: list[dict] = []
        self.inline_edits: list[dict] = []

    async def send_text(self, chat_id: str, text: str, reply_markup=None) -> None:
        self.sent_texts.append((chat_id, text))

    async def send_inline_menu(self, chat_id: str, text: str, buttons: list[tuple[str, str]]):
        message = SimpleNamespace(message_id=700)
        self.inline_sends.append({"chat_id": chat_id, "text": text, "buttons": buttons})
        return message

    async def edit_inline_menu(self, chat_id: str, message_id: int, text: str, buttons: list[tuple[str, str]]):
        self.inline_edits.append(
            {"chat_id": chat_id, "message_id": message_id, "text": text, "buttons": buttons}
        )
        return SimpleNamespace(message_id=message_id)

    async def send_menu(self, chat_id: str, text: str, buttons: list[str]) -> None:
        raise AssertionError("inline menu path expected")

    async def send_document_path(self, *args, **kwargs) -> None:
        return None


class HrLinkAndInlineMenuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        init_db()
        cls.client = TestClient(app)
        with SessionLocal() as db:
            account = authenticate_account(db, "admin", "admin123")
            if account is not None:
                cls.client.cookies.set(AUTH_COOKIE_NAME, create_admin_session_token(account.id))

    def test_hr_link_api_exposes_pending_state_and_disconnects(self) -> None:
        with SessionLocal() as db:
            settings = _get_or_create_hr_settings(db)
            settings.telegram_user_id = None
            settings.telegram_username = None
            settings.telegram_link_token_hash = None
            settings.telegram_link_expires_at = None
            db.commit()
        with patch("app.web.settings_routes.settings.TELEGRAM_BOT_USERNAME", ""):
            response = self.client.post("/api/settings/hr/telegram-link")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["start_parameter"].startswith("hr_link_"))
        self.assertIsNone(payload["deep_link"])
        self.assertTrue(payload["requires_telegram_bot_username"])
        self.assertEqual(payload["workspace"]["hr_settings"]["telegram_connection_state"], "pending")

        disconnected = self.client.delete("/api/settings/hr/telegram-link")
        self.assertEqual(disconnected.status_code, 200)
        self.assertEqual(disconnected.json()["hr_settings"]["telegram_connection_state"], "disconnected")

    def test_hr_link_consumes_token_without_creating_candidate(self) -> None:
        token = f"token-{uuid4().hex}"
        chat_id = str(970000000000 + (uuid4().int % 100000000000))
        username = f"hr_{uuid4().hex[:8]}"
        with SessionLocal() as db:
            settings = _get_or_create_hr_settings(db)
            before_count = db.query(Employee).count()
            settings.telegram_user_id = None
            settings.telegram_username = None
            settings.telegram_link_token_hash = hash_hr_link_token(token)
            settings.telegram_link_expires_at = utc_now() + timedelta(minutes=5)
            db.commit()
            messenger = InlineMessenger()

            asyncio.run(handle_start_command(messenger, db, chat_id, username, f"hr_link_{token}"))

            db.refresh(settings)
            self.assertEqual(settings.telegram_user_id, chat_id)
            self.assertEqual(settings.telegram_username, username)
            self.assertIsNone(settings.telegram_link_token_hash)
            self.assertEqual(db.query(Employee).count(), before_count)
            self.assertIn((chat_id, "Telegram успешно подключен к HR-настройкам."), messenger.sent_texts)

            messenger.sent_texts.clear()
            asyncio.run(handle_start_command(messenger, db, chat_id, username, f"hr_link_{token}"))
            self.assertIn((chat_id, "Ссылка подключения HR недействительна или уже истекла. Запросите новую ссылку в админке."), messenger.sent_texts)

    def test_existing_hr_binding_cannot_be_replaced_or_changed_via_settings(self) -> None:
        token = f"token-{uuid4().hex}"
        with SessionLocal() as db:
            settings = _get_or_create_hr_settings(db)
            settings.telegram_user_id = "100000000001"
            settings.telegram_username = "owner"
            settings.telegram_link_token_hash = hash_hr_link_token(token)
            settings.telegram_link_expires_at = utc_now() + timedelta(minutes=5)
            db.commit()
            messenger = InlineMessenger()

            asyncio.run(handle_start_command(messenger, db, "100000000002", "other", f"hr_link_{token}"))

            db.refresh(settings)
            self.assertEqual(settings.telegram_user_id, "100000000001")
            self.assertEqual(settings.telegram_username, "owner")
            self.assertEqual(settings.telegram_link_token_hash, hash_hr_link_token(token))

        link_response = self.client.post("/api/settings/hr/telegram-link")
        self.assertEqual(link_response.status_code, 409)
        response = self.client.post("/api/settings/hr", json={"telegram_user_id": "100000000002"})
        self.assertEqual(response.status_code, 409)
        with SessionLocal() as db:
            settings = _get_or_create_hr_settings(db)
            self.assertEqual(settings.telegram_user_id, "100000000001")

        self.client.delete("/api/settings/hr/telegram-link")

    def test_hr_link_claim_is_one_time_and_rejects_reuse(self) -> None:
        token = f"token-{uuid4().hex}"
        now = utc_now()
        with SessionLocal() as db:
            settings = _get_or_create_hr_settings(db)
            settings.telegram_user_id = None
            settings.telegram_username = None
            settings.telegram_link_token_hash = hash_hr_link_token(token)
            settings.telegram_link_expires_at = now + timedelta(minutes=5)
            db.commit()

            self.assertTrue(consume_hr_link_token(db, token, "100000000003", "first", now))
            self.assertFalse(consume_hr_link_token(db, token, "100000000004", "second", now))
            db.refresh(settings)
            self.assertEqual(settings.telegram_user_id, "100000000003")
            self.assertIsNone(settings.telegram_link_token_hash)

        self.client.delete("/api/settings/hr/telegram-link")

    def test_hr_notification_role_requires_numeric_confirmed_id(self) -> None:
        with SessionLocal() as db:
            settings = _get_or_create_hr_settings(db)
            previous_id = settings.telegram_user_id
            settings.telegram_user_id = "@hr_username"
            db.commit()
            self.assertIsNone(_resolve_explicit_notification_recipient(db, "hr"))
            settings.telegram_user_id = "99112233"
            db.commit()
            self.assertEqual(_resolve_explicit_notification_recipient(db, "hr"), "99112233")
            settings.telegram_user_id = previous_id
            db.commit()

    def test_inline_menu_navigation_edits_same_message(self) -> None:
        chat_id = str(980000000000 + (uuid4().int % 100000000000))
        with SessionLocal() as db:
            employee = Employee(
                full_name=f"Inline {uuid4().hex[:8]}",
                telegram_user_id=chat_id,
                employee_stage="staff",
                created_at=utc_now(),
                is_flow_scheduled=False,
            )
            root = BotMenuSet(
                title="Root",
                description='<b>Главное</b> & <script>raw</script>',
                sort_order=1,
                employee_scope="employees",
            )
            child = BotMenuSet(title="Child", description="Документы", sort_order=2, employee_scope="employees")
            db.add_all([employee, root, child])
            db.commit()
            db.refresh(employee)
            db.refresh(root)
            db.refresh(child)
            button = BotMenuButton(
                menu_set_id=root.id,
                label="Документы",
                sort_order=1,
                action_type="open_set",
                target_menu_set_id=child.id,
            )
            db.add(button)
            db.commit()
            messenger = InlineMessenger()

            from app.messaging.service import show_main_menu

            asyncio.run(show_main_menu(messenger, db, employee, "ignored"))
            self.assertEqual(messenger.inline_sends[0]["text"], "<b>Главное</b> &amp; raw")
            db.refresh(employee)
            employee.current_menu_set_id = root.id
            employee.current_menu_path = str(root.id)
            employee.current_menu_message_id = 700
            db.commit()
            self.assertEqual(employee.current_menu_message_id, 700)

            result = asyncio.run(
                handle_menu_callback(
                    messenger,
                    db,
                    chat_id,
                    None,
                    f"menu:button:{button.id}",
                    700,
                )
            )
            db.refresh(employee)
            self.assertEqual(result, "handled")
            self.assertEqual(employee.current_menu_message_id, 700)
            self.assertEqual(len(messenger.inline_edits), 1)
            self.assertEqual(messenger.inline_edits[0]["message_id"], 700)
            self.assertEqual(messenger.inline_edits[0]["text"], "Документы")
            self.assertIn(("Назад", "menu:back"), messenger.inline_edits[0]["buttons"])


if __name__ == "__main__":
    unittest.main()
