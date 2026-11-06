import sqlite3
from contextlib import closing
import tempfile
import unittest
from pathlib import Path

from tools.repair_grade70_stale_dialogs import EXPECTED, repair


class StaleRepairTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "test.db"
        with closing(sqlite3.connect(self.path)) as db:
            db.executescript("""
                CREATE TABLE scenario_progress(id INTEGER PRIMARY KEY, employee_id, recipient_employee_id,
                    scenario_key, current_step_key, updated_at, is_completed DEFAULT 0,
                    waiting_for_response DEFAULT 0, interrupted_at, feedback_run_id, survey_launch_id,
                    adaptation_plan_item_id, answer_run_id, completed_at, pending_confirmation_value,
                    pending_confirmation_option_index, pending_confirmation_message_id, step_history);
                CREATE TABLE scenario_answer_runs(id PRIMARY KEY, status);
                CREATE TABLE flow_launch_requests(employee_id, flow_key, processed_at, skip_step_key);
                CREATE TABLE onboarding_events(employee_id,event_key,scheduled_at,sent_at,message);
                CREATE TABLE answers(value);
                INSERT INTO answers VALUES ('preserved');
            """)
            for key, (scenario, step, stamp) in EXPECTED.items():
                db.execute("""INSERT INTO scenario_progress(id, employee_id, recipient_employee_id,
                    scenario_key,current_step_key,updated_at,answer_run_id,step_history)
                    VALUES (?,70,70,?,?,?,?,?)""", (key, scenario, step, stamp, key, '["old"]'))
                db.execute("INSERT INTO scenario_answer_runs VALUES (?,'in_progress')", (key,))
                db.execute("INSERT INTO flow_launch_requests VALUES (70,?,NULL,'next')", (scenario,))
                db.execute("INSERT INTO flow_launch_requests VALUES (70,?,NULL,NULL)", (scenario,))
            db.commit()

    def tearDown(self):
        self.tmp.cleanup()

    def test_preview_readonly_and_apply_preserves_data(self):
        before = self.path.read_bytes()
        self.assertEqual(repair(self.path)["mode"], "dry_run")
        self.assertEqual(before, self.path.read_bytes())
        result = repair(self.path, True)
        self.assertTrue(Path(result["backup"]).exists())
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT SUM(is_completed) FROM scenario_progress").fetchone()[0], 2)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM scenario_progress WHERE step_history=?", ('["old"]',)).fetchone()[0], 2)
            self.assertEqual(db.execute("SELECT value FROM answers").fetchone()[0], "preserved")
            self.assertEqual(db.execute("SELECT COUNT(*) FROM flow_launch_requests WHERE processed_at IS NULL").fetchone()[0], 2)
        with self.assertRaises(ValueError):
            repair(self.path, True)

    def test_changed_or_waiting_runtime_refused(self):
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("UPDATE scenario_progress SET waiting_for_response=1 WHERE id=127")
            db.commit()
        with self.assertRaises(ValueError):
            repair(self.path, True)
        self.assertFalse((self.path.parent / "backups").exists())
