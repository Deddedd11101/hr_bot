import unittest
from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Employee, EmployeeDocumentLink, EmployeeFile
from app.scenario_engine import format_message, resolve_tagged_employee_documents
from app.web.employees import _set_employee_ipr_link
from app.time_utils import utc_now


class NotificationDocumentTagsTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.employee = Employee(full_name="Иванов Иван Иванович", first_workday=date(2026, 10, 1), created_at=utc_now())
        self.db.add(self.employee)
        self.db.flush()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def render(self, text):
        return format_message(self.db, text, self.employee, date(2026, 10, 1), None)

    def test_notification_links_use_employee_sources_and_escape_html(self):
        _set_employee_ipr_link(self.db, self.employee.id, 'https://example.com/ipr?a=1&b="x"')
        self.employee.adaptation_tasks_url = "https://example.com/plan"
        self.employee.adaptation_feedback_url = "https://example.com/feedback"
        self.db.flush()
        text = self.render("{ipr} {probation_plan} {colleague_feedback} {first_workday}")
        self.assertIn('href="https://example.com/ipr?a=1&amp;b=&quot;x&quot;"', text)
        self.assertIn('<a href="https://example.com/plan">План испытательного срока</a>', text)
        self.assertIn('<a href="https://example.com/feedback">Обратная связь коллег</a>', text)
        self.assertIn("01.10.2026", text)
        self.assertEqual(self.render("{adaptation_tasks_url}"), self.render("{probation_plan}"))
        self.assertEqual(resolve_tagged_employee_documents(self.db, "{ipr} {probation_plan}", self.employee, include_resume=True), [])

    def test_missing_or_unsafe_links_are_not_active_and_never_use_other_employee(self):
        other = Employee(full_name="Другой сотрудник", created_at=utc_now())
        self.db.add(other)
        self.db.flush()
        _set_employee_ipr_link(self.db, other.id, "https://example.com/private")
        for value in (None, "javascript:alert(1)", "https://user:pass@example.com", "https://example.com:bad", "https://", "https://example.com/\nsecret"):
            with self.subTest(value=value):
                self.employee.adaptation_tasks_url = value
                self.assertEqual(self.render("{probation_plan}"), "План испытательного срока: ссылка не указана")
        self.assertEqual(self.render("{ipr}"), "ИПР: ссылка не указана")
        self.assertEqual(self.render("{colleague_feedback}"), "Обратная связь коллег: ссылка не указана")

    def test_ipr_replace_clear_preserve_files_and_other_slots(self):
        file = EmployeeFile(employee_id=self.employee.id, direction="outbound", category="hr_file", stored_path="unused.pdf", original_filename="old.pdf", created_at=utc_now())
        self.db.add(file)
        self.db.flush()
        ipr = EmployeeDocumentLink(employee_id=self.employee.id, slot_key="ipr", title="ИПР", item_kind="file", employee_file_id=file.id, url="", created_at=utc_now())
        offer = EmployeeDocumentLink(employee_id=self.employee.id, slot_key="offer", title="Оффер", item_kind="link", url="https://example.com/offer", created_at=utc_now())
        self.db.add_all([ipr, offer])
        self.db.flush()
        _set_employee_ipr_link(self.db, self.employee.id, "https://example.com/new")
        self.db.flush()
        self.assertIsNone(ipr.employee_file_id)
        _set_employee_ipr_link(self.db, self.employee.id, "")
        self.db.flush()
        self.assertIsNotNone(self.db.get(EmployeeFile, file.id))
        self.assertIsNotNone(self.db.get(EmployeeDocumentLink, offer.id))
        self.assertEqual(self.db.query(EmployeeDocumentLink).filter_by(slot_key="ipr").count(), 0)

    def test_ipr_invalid_update_does_not_replace_existing_link(self):
        _set_employee_ipr_link(self.db, self.employee.id, "https://example.com/valid")
        self.db.flush()
        for value in ("javascript:alert(1)", "https://user:pass@example.com", "not a url"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                _set_employee_ipr_link(self.db, self.employee.id, value)
        self.assertIn("https://example.com/valid", self.render("{ipr}"))
