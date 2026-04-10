import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.scenario_engine import resolve_branch_followup_step, step_has_sendable_content


class ScenarioEngineBranchingTests(unittest.TestCase):
    def test_step_has_sendable_content_returns_false_for_empty_shell(self) -> None:
        step = SimpleNamespace(
            custom_text="",
            default_text="",
            attachment_path="",
            send_employee_card=False,
            response_type="chain",
            button_options=None,
        )

        self.assertFalse(step_has_sendable_content(step))

    def test_resolve_branch_followup_step_returns_first_chain_step_for_chain_branch(self) -> None:
        branch_step = SimpleNamespace(id=42, response_type="chain")
        first_chain_step = SimpleNamespace(id=99, step_key="chain_step")

        with patch("app.scenario_engine.get_first_chain_step", return_value=first_chain_step), patch(
            "app.scenario_engine.resolve_followup_step", return_value=None
        ):
            result = resolve_branch_followup_step(None, "first_day", branch_step)

        self.assertIs(result, first_chain_step)

    def test_resolve_branch_followup_step_falls_through_when_chain_is_empty(self) -> None:
        branch_step = SimpleNamespace(id=42, response_type="chain")
        next_step = SimpleNamespace(id=100, step_key="next_step")

        with patch("app.scenario_engine.get_first_chain_step", return_value=None), patch(
            "app.scenario_engine.resolve_followup_step", return_value=next_step
        ):
            result = resolve_branch_followup_step(None, "first_day", branch_step)

        self.assertIs(result, next_step)


if __name__ == "__main__":
    unittest.main()
