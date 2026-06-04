import unittest
from datetime import UTC, datetime
from uuid import uuid4

from app.database import SessionLocal, init_db
from app.mass_targeting import deserialize_target_values, mass_target_employee_query
from app.messaging.identity import set_primary_chat_id
from app.messaging.service import resolve_inbound_access, save_incoming_file, handle_text_event
from app.models import Employee, EmployeeFile, EmployeeMessengerAccount


class _FakeMessenger:
    async def send_text(self, *args, **kwargs):
        return None


class P0BehaviourTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        init_db()

    def setUp(self) -> None:
        self.employee_ids: list[int] = []
        unique_suffix = uuid4().hex[:8]
        self.candidate_chat_id = f"tg-{unique_suffix}"
        self.blocked_chat_id = f"blocked-{unique_suffix}"
        with SessionLocal() as db:
            candidate_testing = Employee(
                full_name=f"Candidate Testing {unique_suffix}",
                telegram_user_id=None,
                telegram_username=None,
                first_workday=None,
                created_at=datetime.now(UTC).replace(tzinfo=None),
                is_flow_scheduled=False,
                candidate_status="new",
                employee_stage="candidate",
                candidate_work_stage="testing",
            )
            candidate_offer = Employee(
                full_name=f"Candidate Offer {unique_suffix}",
                telegram_user_id=None,
                telegram_username=None,
                first_workday=None,
                created_at=datetime.now(UTC).replace(tzinfo=None),
                is_flow_scheduled=False,
                candidate_status="new",
                employee_stage="candidate",
                candidate_work_stage="offer",
            )
            employee_staff = Employee(
                full_name=f"Employee Staff {unique_suffix}",
                telegram_user_id=None,
                telegram_username=None,
                first_workday=None,
                created_at=datetime.now(UTC).replace(tzinfo=None),
                is_flow_scheduled=False,
                candidate_status="new",
                employee_stage="staff",
                desired_position="Аналитик",
            )
            blocked_employee = Employee(
                full_name=f"Blocked Employee {unique_suffix}",
                telegram_user_id=None,
                telegram_username=None,
                first_workday=None,
                created_at=datetime.now(UTC).replace(tzinfo=None),
                is_flow_scheduled=False,
                is_bot_blocked=True,
                candidate_status="new",
                employee_stage="staff",
                desired_position="Аналитик",
            )
            db.add_all([candidate_testing, candidate_offer, employee_staff, blocked_employee])
            db.commit()
            db.refresh(candidate_testing)
            db.refresh(candidate_offer)
            db.refresh(employee_staff)
            db.refresh(blocked_employee)
            set_primary_chat_id(candidate_testing, self.candidate_chat_id, db=db)
            set_primary_chat_id(blocked_employee, self.blocked_chat_id, db=db)
            db.commit()
            self.employee_ids = [candidate_testing.id, candidate_offer.id, employee_staff.id, blocked_employee.id]
            self.candidate_testing_id = candidate_testing.id
            self.candidate_offer_id = candidate_offer.id
            self.employee_staff_id = employee_staff.id
            self.blocked_employee_id = blocked_employee.id

    def tearDown(self) -> None:
        with SessionLocal() as db:
            db.query(EmployeeFile).filter(EmployeeFile.employee_id.in_(self.employee_ids)).delete(synchronize_session=False)
            db.query(EmployeeMessengerAccount).filter(EmployeeMessengerAccount.employee_id.in_(self.employee_ids)).delete(synchronize_session=False)
            for employee_id in self.employee_ids:
                employee = db.get(Employee, employee_id)
                if employee is not None:
                    db.delete(employee)
            db.commit()

    def test_mass_targeting_uses_candidate_stage_split(self) -> None:
        with SessionLocal() as db:
            rows = (
                mass_target_employee_query(
                    db,
                    target_all=False,
                    target_employee_stages=[],
                    target_candidate_stages=["testing"],
                )
                .order_by(Employee.id.asc())
                .all()
            )

        matched_ids = [row.id for row in rows if row.id in self.employee_ids]
        self.assertEqual(matched_ids, [self.candidate_testing_id])

    def test_mass_targeting_reads_legacy_candidate_status(self) -> None:
        with SessionLocal() as db:
            rows = (
                mass_target_employee_query(
                    db,
                    target_all=False,
                    target_employee_stages=[],
                    target_candidate_stages=[],
                    legacy_target_statuses=deserialize_target_values("candidate", kind="legacy"),
                )
                .order_by(Employee.id.asc())
                .all()
            )

        matched_ids = [row.id for row in rows if row.id in self.employee_ids]
        self.assertEqual(matched_ids, [self.candidate_testing_id, self.candidate_offer_id])

    def test_resolve_inbound_access_marks_unknown_and_blocked(self) -> None:
        with SessionLocal() as db:
            unknown_access = resolve_inbound_access(db, "unknown-user", "nobody")
            blocked_access = resolve_inbound_access(db, self.blocked_chat_id, None)

        self.assertEqual(unknown_access.state, "unknown")
        self.assertIsNone(unknown_access.employee)
        self.assertEqual(blocked_access.state, "blocked")

    async def test_handle_text_event_ignores_stray_text_for_known_employee(self) -> None:
        with SessionLocal() as db:
            result = await handle_text_event(_FakeMessenger(), db, self.candidate_chat_id, None, "лишний текст")

        self.assertEqual(result, "ignored")

    async def test_save_incoming_file_rejects_unknown_user(self) -> None:
        with SessionLocal() as db:
            before_count = db.query(EmployeeFile).count()
            employee, db_file, state = await save_incoming_file(
                db,
                "unknown-file-user",
                None,
                original_name="resume.pdf",
                stored_path="D:/tmp/resume.pdf",
                category="resume",
                mime_type="application/pdf",
                file_size=123,
            )
            after_count = db.query(EmployeeFile).count()

        self.assertEqual(state, "unknown")
        self.assertIsNone(employee)
        self.assertIsNone(db_file)
        self.assertEqual(before_count, after_count)

    async def test_save_incoming_file_accepts_known_user(self) -> None:
        with SessionLocal() as db:
            employee, db_file, state = await save_incoming_file(
                db,
                self.candidate_chat_id,
                None,
                original_name="portfolio.pdf",
                stored_path="D:/tmp/portfolio.pdf",
                category="candidate_file",
                mime_type="application/pdf",
                file_size=456,
            )

        self.assertEqual(state, "saved")
        self.assertIsNotNone(employee)
        self.assertIsNotNone(db_file)

