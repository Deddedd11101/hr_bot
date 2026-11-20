import unittest
from datetime import date, datetime
from unittest.mock import patch, AsyncMock

from pydantic import ValidationError
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker

from app.adaptation_planning import CalendarDates
from app.database import Base
from app.models import Employee, EmployeeVacationRequest
from app.vacation import VacationPeriod, preview, submit, requests_for
from app.vacation_accounting import LeaveKind


class VacationRequestTypeTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        self.addCleanup(self.engine.dispose)
        Employee.__table__.create(self.engine)
        EmployeeVacationRequest.__table__.create(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.addCleanup(self.db.close)
        self.db.add(Employee(id=70, full_name="Local test", created_at=datetime.now()))
        self.db.commit()

    def test_types_comment_and_repeat(self):
        with patch.object(CalendarDates, "working", return_value=True):
            for day, kind in enumerate(("annual", "force_majeure", "day_off"), 1):
                period = VacationPeriod(starts_on=date(2090, 2, day), ends_on=date(2090, 2, day),
                                        kind=kind, employee_comment="  My reason  ")
                result = submit(self.db, 70, period)
                self.assertEqual(result["kind"], kind)
                self.assertEqual(result["employee_comment"], "My reason")
                self.assertEqual(submit(self.db, 70, period)["id"], result["id"])
            self.assertEqual(len(requests_for(self.db, 70)), 3)

    def test_legacy_defaults_and_kind_collision(self):
        with patch.object(CalendarDates, "working", return_value=True):
            period = VacationPeriod(starts_on=date(2090, 2, 1), ends_on=date(2090, 2, 1))
            self.assertEqual(submit(self.db, 70, period)["kind"], "annual")
            with self.assertRaises(ValueError):
                submit(self.db, 70, period.model_copy(update={"kind": LeaveKind.DAY_OFF}))

    def test_day_off_is_single_workday(self):
        with patch.object(CalendarDates, "working", return_value=True):
            with self.assertRaises(ValueError):
                preview(self.db, VacationPeriod(starts_on=date(2090, 2, 1), ends_on=date(2090, 2, 2), kind="day_off"))
        with patch.object(CalendarDates, "working", return_value=False):
            with self.assertRaises(ValueError):
                preview(self.db, VacationPeriod(starts_on=date(2090, 2, 1), ends_on=date(2090, 2, 1), kind="day_off"))

    def test_invalid_type_comment_and_unknown_units(self):
        for extra in ({"kind": "sick"}, {"employee_comment": "x" * 1025}, {"hours": 8}):
            with self.assertRaises(ValidationError):
                VacationPeriod(starts_on=date(2090, 2, 1), ends_on=date(2090, 2, 1), **extra)


class VacationRequestSchemaTests(unittest.TestCase):
    def test_existing_table_gains_safe_defaults(self):
        from app import database
        engine = create_engine("sqlite://")
        self.addCleanup(engine.dispose)
        Base.metadata.create_all(engine)
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE employee_vacation_requests DROP COLUMN kind"))
            conn.execute(text("ALTER TABLE employee_vacation_requests DROP COLUMN employee_comment"))
            conn.execute(text("INSERT INTO employee_vacation_requests (employee_id, starts_on, ends_on, workdays, status, created_at, manager_revision, manager_notice, hr_notice) VALUES (70,'2090-02-01','2090-02-01',1,'pending','2026-01-01',1,'pending','pending')"))
        with patch.object(database, "engine", engine):
            database._ensure_sqlite_schema()
            database._ensure_sqlite_schema()
        self.assertIn("kind", {row["name"] for row in inspect(engine).get_columns("employee_vacation_requests")})
        with engine.connect() as conn:
            self.assertEqual(conn.execute(text("SELECT kind,employee_comment FROM employee_vacation_requests")).one(), ("annual", ""))


class VacationTypeDeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_manager_gets_kind_and_escaped_comment_once(self):
        from app import vacation_delivery
        engine = create_engine("sqlite://")
        self.addCleanup(engine.dispose)
        Employee.__table__.create(engine)
        EmployeeVacationRequest.__table__.create(engine)
        sessions = sessionmaker(bind=engine)
        with sessions() as db:
            db.add(Employee(id=70, full_name="Local test", created_at=datetime.now()))
            db.add(EmployeeVacationRequest(employee_id=70, starts_on=date(2090, 2, 1),
                ends_on=date(2090, 2, 1), workdays=1, kind="day_off", employee_comment="<example>",
                status="pending", manager_id=71, created_at=datetime.now()))
            db.commit()
        bot = AsyncMock()
        with patch.object(vacation_delivery, "SessionLocal", sessions), patch.object(vacation_delivery, "manager_chat", return_value="123"):
            await vacation_delivery.deliver_pending(bot)
            await vacation_delivery.deliver_pending(bot)
        bot.send_message.assert_awaited_once()
        self.assertIn("Day off", bot.send_message.call_args.args[1])
        self.assertIn("&lt;example&gt;", bot.send_message.call_args.args[1])
