from datetime import timedelta
from pathlib import Path

from app.database import SessionLocal
from app.models import Employee, EmployeeFeedbackRun, SurveyAnswer
from app.scenario_engine import format_message, send_tagged_employee_documents
from app.time_utils import utc_now
from tests import test_adaptation_pulse_files as fixtures
from tests.test_scenario_engine_smoke import FakeMessenger


class FeedbackDocumentTagsTests(fixtures.AdaptationPulseFilesTests):
    def tearDown(self):
        with SessionLocal() as db:
            ids = [r.id for r in db.query(EmployeeFeedbackRun).filter_by(subject_employee_id=self.ids[0])]
            db.query(SurveyAnswer).filter(SurveyAnswer.feedback_run_id.in_(ids)).delete(synchronize_session=False)
            db.query(EmployeeFeedbackRun).filter_by(subject_employee_id=self.ids[0]).delete(synchronize_session=False)
            db.commit()
        super().tearDown()

    async def test_latest_run_empty_does_not_attach_previous_answers(self):
        with SessionLocal() as db:
            subject = db.get(Employee, self.ids[0])
            old = EmployeeFeedbackRun(subject_employee_id=subject.id, scenario_key=self.key, created_at=utc_now() - timedelta(days=1))
            db.add(old)
            db.flush()
            db.add(SurveyAnswer(employee_id=self.ids[1], scenario_key=self.key, step_key="q", feedback_run_id=old.id, answer_value="old", answered_at=utc_now()))
            latest = EmployeeFeedbackRun(subject_employee_id=subject.id, scenario_key=self.key, created_at=utc_now())
            db.add(latest)
            db.commit()
            messenger = FakeMessenger()
            await send_tagged_employee_documents(messenger, db, "123", "{ос}", subject)
            self.assertEqual(messenger.documents, [])
            self.assertEqual(format_message(db, "Text {ос}", subject, utc_now().date(), None).strip(), "Text")
            db.add(SurveyAnswer(employee_id=self.ids[1], scenario_key=self.key, step_key="q", feedback_run_id=latest.id, answer_value="new", answered_at=utc_now()))
            db.commit()
            captured = []
            async def capture(chat_id, path, filename=None, **kwargs):
                captured.append((Path(path).read_bytes(), filename, str(path)))
            messenger.send_document_path = capture
            await send_tagged_employee_documents(messenger, db, "123", "{ос} {colleague_feedback}", subject)
            self.assertEqual(len(captured), 1)
            self.assertIn(f"run_{latest.id}", captured[0][1])
            self.assertFalse(Path(captured[0][2]).exists())
