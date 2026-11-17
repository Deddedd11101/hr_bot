from contextlib import closing
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from tools.repair_roman_stale_dialogs import EXPECTED, repair


class RomanRepairTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / "test.db"
        with closing(sqlite3.connect(self.path)) as db, db:
            db.executescript("""
                CREATE TABLE scenario_progress (id INTEGER PRIMARY KEY, employee_id, recipient_employee_id,
                    scenario_key, current_step_key, updated_at, started_at, answer_run_id, feedback_run_id,
                    survey_launch_id, adaptation_plan_item_id, is_completed DEFAULT 0,
                    waiting_for_response DEFAULT 0, interrupted_at, completed_at, pending_confirmation_value,
                    pending_confirmation_option_index, pending_confirmation_message_id);
                CREATE TABLE scenario_step_deliveries (progress_id, status);
                CREATE TABLE flow_launch_requests (employee_id, flow_key, processed_at, skip_step_key);
                CREATE TABLE scenario_answer_runs (id, status, answer);
                CREATE TABLE onboarding_events (employee_id, event_key, scheduled_at, sent_at, message);
                INSERT INTO scenario_answer_runs VALUES (1, 'in_progress', 'preserve me');
            """)
            for row_id, (recipient, key, step, updated) in EXPECTED.items():
                db.execute("""INSERT INTO scenario_progress
                    (id, employee_id, recipient_employee_id, scenario_key, current_step_key, updated_at, answer_run_id)
                    VALUES (?,44,?,?,?,?,?)""", (row_id, recipient, key, step, updated, 1 if row_id == 30 else None))
            db.execute("INSERT INTO scenario_progress (id,employee_id) VALUES (1000,70)")
            db.execute("INSERT INTO flow_launch_requests VALUES (44,?,NULL,NULL)", (EXPECTED[30][1],))

    def test_backup_and_apply_preserve_history_pilot_and_independent_requests(self):
        self.assertEqual(repair(self.path)["dialog_ids"], list(EXPECTED))
        result = repair(self.path, apply=True)
        with closing(sqlite3.connect(result["backup"])) as backup:
            self.assertEqual(backup.execute("SELECT sum(is_completed) FROM scenario_progress").fetchone()[0], 0)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT sum(is_completed) FROM scenario_progress WHERE employee_id=44").fetchone()[0], 4)
            self.assertEqual(db.execute("SELECT is_completed FROM scenario_progress WHERE employee_id=70").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT status,answer FROM scenario_answer_runs").fetchone(), ("interrupted", "preserve me"))
            self.assertIsNone(db.execute("SELECT processed_at FROM flow_launch_requests").fetchone()[0])

    def test_refuses_claimed_step_without_backup_or_write(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("INSERT INTO scenario_step_deliveries VALUES (30,'starting')")
        with self.assertRaisesRegex(ValueError, "claimed step"):
            repair(self.path, apply=True)
        self.assertFalse((self.path.parent / "backups").exists())
