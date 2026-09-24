from pathlib import Path
from contextlib import closing
import sqlite3
import tempfile
import unittest

from tools.repair_candidate_answer_steps import REPAIRS, repair


class CandidateAnswerRepairTests(unittest.TestCase):
    def test_readonly_apply_backup_and_idempotency(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "source.db"
            backup = Path(directory) / "backup.db"
            with closing(sqlite3.connect(db_path)) as db:
                db.execute("CREATE TABLE flow_step_templates(flow_key TEXT, step_key TEXT, response_type TEXT, target_field TEXT)")
                db.executemany("INSERT INTO flow_step_templates VALUES(?,?,?,'candidate_file')", REPAIRS)
                db.commit()
            before = db_path.read_bytes()
            self.assertTrue(all(item["changed"] for item in repair(db_path)))
            self.assertEqual(before, db_path.read_bytes())
            repair(db_path, apply=True, backup=backup)
            with closing(sqlite3.connect(backup)) as db:
                self.assertEqual(db.execute("SELECT DISTINCT target_field FROM flow_step_templates").fetchall(), [("candidate_file",)])
            self.assertFalse(any(item["changed"] for item in repair(db_path, apply=True, backup=backup)))

    def test_changed_configuration_prevents_partial_repair(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "source.db"
            backup = Path(directory) / "backup.db"
            with closing(sqlite3.connect(db_path)) as db:
                db.execute("CREATE TABLE flow_step_templates(flow_key TEXT, step_key TEXT, response_type TEXT, target_field TEXT)")
                db.executemany("INSERT INTO flow_step_templates VALUES(?,?,?,'candidate_file')", REPAIRS)
                db.execute("UPDATE flow_step_templates SET target_field='resume' WHERE flow_key=?", (REPAIRS[-1][0],))
                db.commit()
            before = db_path.read_bytes()
            with self.assertRaises(ValueError):
                repair(db_path, apply=True, backup=backup)
            self.assertEqual(before, db_path.read_bytes())
            self.assertFalse(backup.exists())
