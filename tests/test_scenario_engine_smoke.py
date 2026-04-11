import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.scenario_engine import matches_role_scope, resolve_notification_recipients, send_step_attachment


class FakeBot:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def send_photo(self, **kwargs) -> None:
        self.calls.append(("photo", kwargs))

    async def send_document(self, **kwargs) -> None:
        self.calls.append(("document", kwargs))


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
            manager_telegram_id="manager-id",
            mentor_adaptation_telegram_id="mentor-id",
            mentor_ipr_telegram_id="mentor-id",
        )

        recipients = resolve_notification_recipients(
            employee,
            explicit_ids="hr-id, manager-id",
            recipient_scope="manager,mentor_adaptation,mentor_ipr",
        )

        self.assertEqual(recipients, ["hr-id", "manager-id", "mentor-id"])

    def test_matches_role_scope_respects_candidate_and_employee_scope(self) -> None:
        candidate = SimpleNamespace(id=1, employee_stage="candidate", desired_position="")
        employee = SimpleNamespace(id=2, employee_stage="staff", desired_position="")

        candidate_scenario = SimpleNamespace(employee_scope="candidates", target_employee_id=None, role_scope="all")
        employee_scenario = SimpleNamespace(employee_scope="employees", target_employee_id=None, role_scope="all")

        self.assertTrue(matches_role_scope(candidate, candidate_scenario))
        self.assertFalse(matches_role_scope(employee, candidate_scenario))
        self.assertTrue(matches_role_scope(employee, employee_scenario))
        self.assertFalse(matches_role_scope(candidate, employee_scenario))


if __name__ == "__main__":
    unittest.main()
