import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

import app.database as database
from app.models import EmployeeFeedbackRecipient, EmployeeFeedbackRun


class FeedbackQueueSchemaTests(unittest.TestCase):
    def test_legacy_runs_stay_unqueued_without_recipient_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = create_engine("sqlite:///" + str(Path(directory) / "legacy.db"))
            try:
                database.Base.metadata.create_all(engine)
                with Session(engine) as db:
                    run = EmployeeFeedbackRun(subject_employee_id=1, scenario_key="legacy", created_at=datetime(2026, 1, 1))
                    db.add(run)
                    db.flush()
                    db.add(EmployeeFeedbackRecipient(run_id=run.id, respondent_employee_id=2))
                    db.commit()
                    run_id = run.id
                with engine.begin() as conn:
                    conn.execute(text("ALTER TABLE employee_feedback_runs DROP COLUMN queued_delivery"))
                with patch.object(database, "engine", engine):
                    database._ensure_sqlite_schema()
                    database._ensure_sqlite_schema()
                with Session(engine) as db:
                    self.assertFalse(db.get(EmployeeFeedbackRun, run_id).queued_delivery)
                    self.assertEqual(db.query(EmployeeFeedbackRecipient).one().delivery_status, "pending")
            finally:
                engine.dispose()
