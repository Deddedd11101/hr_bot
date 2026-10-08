import asyncio
import json
import unittest
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.auth import authenticate_account, create_admin_session_token
from app.database import SessionLocal, init_db
from app.hr_linking import consume_hr_link_token, hash_hr_link_token
from app.main import AUTH_COOKIE_NAME, app
from app.messaging.service import handle_menu_callback, handle_root_menu_command, handle_start_command, menu_button_option_rows, show_main_menu
from app.models import BotMenuButton, BotMenuSet, Employee, HrSettings
from app.scenario_engine import _resolve_explicit_notification_recipient
from app.time_utils import utc_now
from app.web.settings import _get_or_create_hr_settings


class InlineMessenger:
    def __init__(self) -> None:
        self.sent_texts: list[tuple[str, str]] = []
        self.inline_sends: list[dict] = []
        self.inline_edits: list[dict] = []
        self.reply_menus: list[dict] = []

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
        self.reply_menus.append({"chat_id": chat_id, "text": text, "buttons": buttons})

    async def send_document_path(self, *args, **kwargs) -> None:
        return None

    async def close(self) -> None:
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

    def test_custom_emoji_catalog_validates_numeric_id_and_returns_fallback(self) -> None:
        emoji_id = str(990000000000000000 + (uuid4().int % 1000000))
        created = self.client.post(
            "/api/settings/custom-emojis",
            json={"title": "HR success", "emoji_id": emoji_id, "fallback": "✅"},
        )
        self.assertEqual(created.status_code, 200)
        item = next(row for row in created.json()["custom_emojis"] if row["emoji_id"] == emoji_id)
        self.assertEqual(item["fallback"], "✅")
        invalid = self.client.post(
            "/api/settings/custom-emojis",
            json={"title": "Broken", "emoji_id": "not-numeric"},
        )
        self.assertEqual(invalid.status_code, 400)
        removed = self.client.delete(f"/api/settings/custom-emojis/{item['id']}")
        self.assertEqual(removed.status_code, 200)
        self.assertFalse(next(row for row in removed.json()["custom_emojis"] if row["id"] == item["id"])["is_active"])

    def test_custom_emoji_set_import_is_idempotent_and_keeps_disabled_items(self) -> None:
        first_id = str(990000000000000000 + (uuid4().int % 1000000))
        second_id = str(990000000000000000 + (uuid4().int % 1000000))
        sticker_set = SimpleNamespace(
            title="Fraudex",
            sticker_type="custom_emoji",
            stickers=[
                SimpleNamespace(custom_emoji_id=first_id, emoji="🙂"),
                SimpleNamespace(custom_emoji_id=second_id, emoji="✨"),
            ],
        )
        messenger = SimpleNamespace(
            bot=SimpleNamespace(get_sticker_set=AsyncMock(return_value=sticker_set)),
            close=AsyncMock(),
        )
        with patch("app.web.settings_routes.create_telegram_messenger", return_value=messenger), patch(
            "app.web.settings_routes.settings.TELEGRAM_BOT_TOKEN", "test-token"
        ):
            imported = self.client.post(
                "/api/settings/custom-emojis/import-set",
                json={"url": "https://t.me/addemoji/fraudex"},
            )
            self.assertEqual(imported.status_code, 200)
            self.assertEqual(imported.json()["added_count"], 2)
            self.assertEqual(imported.json()["skipped_count"], 0)
            messenger.bot.get_sticker_set.assert_awaited_with("fraudex")

            first = next(row for row in imported.json()["workspace"]["custom_emojis"] if row["emoji_id"] == first_id)
            self.assertEqual(first["fallback"], "🙂")
            self.client.delete(f"/api/settings/custom-emojis/{first['id']}")
            repeated = self.client.post(
                "/api/settings/custom-emojis/import-set",
                json={"url": "https://t.me/addemoji/fraudex"},
            )
            self.assertEqual(repeated.status_code, 200)
            self.assertEqual(repeated.json()["added_count"], 0)
            self.assertEqual(repeated.json()["skipped_count"], 2)
            first_after = next(row for row in repeated.json()["workspace"]["custom_emojis"] if row["emoji_id"] == first_id)
            self.assertFalse(first_after["is_active"])
            messenger.close.assert_awaited()

    def test_custom_emoji_set_import_rejects_other_links_and_stickers(self) -> None:
        with patch("app.web.settings_routes.create_telegram_messenger") as factory:
            for url in ("https://example.com/addemoji/fraudex", "https://t.me/addstickers/fraudex", "http://t.me/addemoji/fraudex"):
                response = self.client.post("/api/settings/custom-emojis/import-set", json={"url": url})
                self.assertEqual(response.status_code, 400)
            factory.assert_not_called()

        messenger = SimpleNamespace(
            bot=SimpleNamespace(get_sticker_set=AsyncMock(return_value=SimpleNamespace(sticker_type="regular"))),
            close=AsyncMock(),
        )
        with patch("app.web.settings_routes.create_telegram_messenger", return_value=messenger), patch(
            "app.web.settings_routes.settings.TELEGRAM_BOT_TOKEN", "test-token"
        ):
            response = self.client.post("/api/settings/custom-emojis/import-set", json={"url": "https://t.me/addemoji/fraudex"})
            self.assertEqual(response.status_code, 400)
            messenger.close.assert_awaited_once()

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
            hr_settings = _get_or_create_hr_settings(db)
            hr_settings.default_menu_set_id = root.id
            hr_settings.default_employee_menu_set_id = root.id
            db.commit()
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
            self.assertEqual(messenger.reply_menus[0]["text"], "<b>Главное</b> &amp; raw")
            self.assertEqual(messenger.reply_menus[0]["buttons"], ["Документы"])
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

    def test_inline_menu_does_not_send_keyboard_cleanup_message(self) -> None:
        from app.messaging.telegram import TelegramMessenger

        class Bot:
            def __init__(self):
                self.calls = []

            async def send_message(self, **kwargs):
                self.calls.append(kwargs)
                return SimpleNamespace(message_id=1)

        bot = Bot()
        asyncio.run(TelegramMessenger(bot).send_inline_menu("1", "Nested", [("x", "menu:x")]))
        self.assertEqual(len(bot.calls), 1)

    def test_url_action_validates_api_and_renders_nested_link(self) -> None:
        from app.messaging.service import set_current_menu_set
        from app.messaging.telegram import TelegramMessenger

        chat_id = str(984000000000 + (uuid4().int % 100000000000))
        url = "https://example.com/help?topic=documents&lang=ru"
        with SessionLocal() as db:
            employee = Employee(full_name="Link recipient", telegram_user_id=chat_id, employee_stage="candidate", created_at=utc_now())
            root = BotMenuSet(title="Root links", employee_scope="candidates", sort_order=1)
            child = BotMenuSet(title="Nested links", employee_scope="candidates", sort_order=2)
            db.add_all([employee, root, child])
            db.commit()
            root.target_employee_ids = str(employee.id)
            child.target_employee_ids = str(employee.id)
            settings = _get_or_create_hr_settings(db)
            settings.default_candidate_menu_set_id = root.id
            root_button = BotMenuButton(menu_set_id=root.id, label="Сайт", action_type="open_url", url=url)
            db.add(root_button)
            db.commit()

            for invalid_url in ("", "javascript:alert(1)", "https://user@example.com", "https://example.com\\@evil.com"):
                invalid = self.client.post(
                    f"/api/settings/menu-sets/{child.id}/buttons",
                    json={"label": "Bad", "action_type": "open_url", "url": invalid_url},
                )
                self.assertEqual(invalid.status_code, 400, invalid_url)
            self.assertEqual(db.query(BotMenuButton).filter_by(menu_set_id=child.id).count(), 0)

            created = self.client.post(
                f"/api/settings/menu-sets/{child.id}/buttons",
                json={"label": "Помощь", "action_type": "open_url", "url": url},
            )
            self.assertEqual(created.status_code, 200)
            child_button = db.query(BotMenuButton).filter_by(menu_set_id=child.id).one()
            self.assertEqual(child_button.url, url)
            self.assertEqual(next(menu for menu in created.json()["menu_sets"] if menu["id"] == child.id)["buttons"][0]["url"], url)

            set_current_menu_set(db, employee, child, path_ids=[root.id, child.id])
            options = menu_button_option_rows(db, employee)
            self.assertEqual(options[0], ("Помощь", url))
            markup = TelegramMessenger._inline_markup(options)
            self.assertEqual(markup.inline_keyboard[0][0].url, url)
            self.assertIsNone(markup.inline_keyboard[0][0].callback_data)
            self.assertEqual(markup.inline_keyboard[-2][0].callback_data, "menu:back")
            self.assertEqual(markup.inline_keyboard[-1][0].callback_data, "menu:home")

            set_current_menu_set(db, employee, root, path_ids=[root.id])
            messenger = InlineMessenger()
            self.assertTrue(asyncio.run(handle_root_menu_command(messenger, db, employee, "Сайт")))
            self.assertEqual(messenger.inline_sends[-1]["buttons"], [("Сайт", url)])
            self.assertEqual(employee.current_menu_set_id, root.id)

            changed = self.client.post(
                f"/api/settings/menu-buttons/{child_button.id}",
                json={"label": "Помощь", "action_type": "inactive", "url": url},
            )
            self.assertEqual(changed.status_code, 200)
            db.refresh(child_button)
            self.assertIsNone(child_button.url)

    def test_empty_root_menu_removes_previous_reply_keyboard(self) -> None:
        from aiogram.types import ReplyKeyboardRemove
        from app.messaging.telegram import TelegramMessenger

        class Bot:
            async def send_message(self, **kwargs):
                self.sent = kwargs

        bot = Bot()
        asyncio.run(TelegramMessenger(bot).send_menu("1", "Нет активных кнопок", []))
        self.assertIsInstance(bot.sent["reply_markup"], ReplyKeyboardRemove)

    def test_menu_button_rows_are_preserved_and_rendered_as_nested_rows(self) -> None:
        chat_id = str(981000000000 + (uuid4().int % 100000000000))
        with SessionLocal() as db:
            employee = Employee(
                full_name=f"Rows {uuid4().hex[:8]}",
                telegram_user_id=chat_id,
                employee_stage="staff",
                created_at=utc_now(),
                is_flow_scheduled=False,
            )
            menu_set = BotMenuSet(title="Rows", sort_order=1, employee_scope="employees")
            db.add_all([employee, menu_set])
            db.commit()
            first = BotMenuButton(menu_set_id=menu_set.id, label="First", sort_order=10, action_type="launch_scenario", scenario_key="test")
            second = BotMenuButton(menu_set_id=menu_set.id, label="Second", sort_order=20, action_type="launch_scenario", scenario_key="test")
            third = BotMenuButton(menu_set_id=menu_set.id, label="Third", sort_order=30, action_type="launch_scenario", scenario_key="test")
            db.add_all([first, second, third])
            db.commit()
            menu_set.button_rows = json.dumps([[second.id, first.id], [third.id]])
            employee.current_menu_set_id = menu_set.id
            employee.current_menu_path = str(menu_set.id)
            db.commit()

            rows = menu_button_option_rows(db, employee)

            self.assertEqual(
                rows[:2],
                [
                    [("Second", f"menu:button:{second.id}"), ("First", f"menu:button:{first.id}")],
                    [("Third", f"menu:button:{third.id}")],
                ],
            )
            self.assertTrue(rows[-1] == [("Главное меню", "menu:home")] or rows[-1] == rows[1])

    def test_disabled_and_unconfigured_buttons_are_hidden_and_stale_actions_ignored(self) -> None:
        chat_id = str(982000000000 + (uuid4().int % 100000000000))
        with SessionLocal() as db:
            employee = Employee(full_name="Hidden Button", telegram_user_id=chat_id, employee_stage="candidate", created_at=utc_now())
            menu_set = BotMenuSet(title="Visible root", employee_scope="candidates", sort_order=1)
            db.add_all([employee, menu_set])
            db.commit()
            menu_set.target_employee_ids = str(employee.id)
            settings = _get_or_create_hr_settings(db)
            settings.default_candidate_menu_set_id = menu_set.id
            visible = BotMenuButton(menu_set_id=menu_set.id, label="Visible", sort_order=10, action_type="launch_scenario", scenario_key="test")
            disabled = BotMenuButton(menu_set_id=menu_set.id, label="Disabled", sort_order=20, is_active=False, action_type="launch_scenario", scenario_key="test")
            unconfigured = BotMenuButton(menu_set_id=menu_set.id, label="Unconfigured", sort_order=30, action_type="inactive")
            db.add_all([visible, disabled, unconfigured])
            db.commit()
            menu_set.button_rows = json.dumps([[visible.id, disabled.id], [unconfigured.id]])
            db.commit()
            messenger = InlineMessenger()

            self.assertTrue(asyncio.run(show_main_menu(messenger, db, employee, "Fallback")))
            self.assertEqual(messenger.reply_menus[-1]["buttons"], [["Visible"]])
            self.assertFalse(asyncio.run(handle_root_menu_command(messenger, db, employee, "Disabled")))
            self.assertFalse(asyncio.run(handle_root_menu_command(messenger, db, employee, "Unconfigured")))
            self.assertEqual(asyncio.run(handle_menu_callback(messenger, db, chat_id, None, f"menu:button:{disabled.id}", None)), "ignored")

            response = self.client.post(
                f"/api/settings/menu-buttons/{visible.id}",
                json={"label": "Visible", "action_type": "launch_scenario", "scenario_key": "test", "is_active": False},
            )
            self.assertEqual(response.status_code, 200)
            db.refresh(visible)
            self.assertFalse(visible.is_active)
            self.assertFalse(next(button for menu in response.json()["menu_sets"] if menu["id"] == menu_set.id for button in menu["buttons"] if button["id"] == visible.id)["is_active"])

    def test_saved_root_rows_are_sent_on_targeted_refresh(self) -> None:
        chat_id = str(983000000000 + (uuid4().int % 100000000000))
        with SessionLocal() as db:
            employee = Employee(full_name="Rows Recipient", telegram_user_id=chat_id, employee_stage="candidate", created_at=utc_now())
            menu_set = BotMenuSet(title="Rows root", description="Выберите раздел", employee_scope="candidates", sort_order=1)
            db.add_all([employee, menu_set])
            db.commit()
            menu_set.target_employee_ids = str(employee.id)
            settings = _get_or_create_hr_settings(db)
            settings.default_candidate_menu_set_id = menu_set.id
            first = BotMenuButton(menu_set_id=menu_set.id, label="First", sort_order=10, action_type="launch_scenario", scenario_key="test")
            second = BotMenuButton(menu_set_id=menu_set.id, label="Second", sort_order=20, action_type="launch_scenario", scenario_key="test")
            db.add_all([first, second])
            db.commit()
            messenger = InlineMessenger()
            asyncio.run(show_main_menu(messenger, db, employee, "Fallback"))
            self.assertEqual(messenger.reply_menus[-1]["buttons"], ["First", "Second"])

            saved = self.client.post(
                f"/api/settings/menu-sets/{menu_set.id}",
                json={
                    "title": menu_set.title,
                    "menu_text": menu_set.description,
                    "employee_scope": "candidates",
                    "role_scope": "all",
                    "target_employee_ids": [employee.id],
                    "button_rows": [[first.id, second.id]],
                },
            )
            self.assertEqual(saved.status_code, 200)
            with patch("app.web.settings_routes.create_telegram_messenger", return_value=messenger), patch("app.web.settings_routes.settings.TELEGRAM_BOT_TOKEN", "test-token"):
                refreshed = self.client.post(f"/api/settings/menu-sets/{menu_set.id}/refresh")
            self.assertEqual(refreshed.status_code, 200)
            self.assertEqual(refreshed.json()["refreshed_count"], 1)
            self.assertEqual(messenger.reply_menus[-1]["buttons"], [["First", "Second"]])

    def test_deleting_menu_button_removes_it_from_saved_rows(self) -> None:
        with SessionLocal() as db:
            menu_set = BotMenuSet(title=f"Delete rows {uuid4().hex[:8]}", sort_order=1, employee_scope="employees")
            db.add(menu_set)
            db.commit()
            first = BotMenuButton(menu_set_id=menu_set.id, label="First", sort_order=10, action_type="inactive")
            second = BotMenuButton(menu_set_id=menu_set.id, label="Second", sort_order=20, action_type="inactive")
            db.add_all([first, second])
            db.commit()
            menu_set.button_rows = json.dumps([[first.id], [second.id]])
            db.commit()
            first_id, second_id, menu_set_id = first.id, second.id, menu_set.id

        response = self.client.delete(f"/api/settings/menu-buttons/{first_id}")
        self.assertEqual(response.status_code, 200)
        with SessionLocal() as db:
            menu_set = db.get(BotMenuSet, menu_set_id)
            self.assertEqual(json.loads(menu_set.button_rows), [[second_id]])

        response = self.client.delete(f"/api/settings/menu-buttons/{second_id}")
        self.assertEqual(response.status_code, 200)
        with SessionLocal() as db:
            menu_set = db.get(BotMenuSet, menu_set_id)
            self.assertIsNone(menu_set.button_rows)


if __name__ == "__main__":
    unittest.main()
