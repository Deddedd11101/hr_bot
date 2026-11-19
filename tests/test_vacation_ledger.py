import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from fractions import Fraction
from pathlib import Path
from threading import Barrier

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Employee, EmployeeLeaveOperation, EmployeeVacationBalance
from app.time_utils import utc_now
from app.vacation_accounting import LeaveKind
from app.vacation_ledger import append_operation, read_balance


class VacationLedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_engine(f"sqlite:///{Path(self.temp.name) / 'test.db'}")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine, autoflush=False)
        self.db.add(Employee(id=1, full_name="Test", created_at=utc_now()))
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        self.temp.cleanup()

    def record(self, operation="opening", key="opening", amount=28, **kwargs):
        values = dict(employee_id=1, contract_key="contract-a", kind=LeaveKind.ANNUAL,
                      operation=operation, operation_key=key, amount=amount,
                      effective_on=date(2027, 1, 1), actor="hr:1", reason="Test entry")
        values.update(kwargs)
        return append_operation(self.db, **values)

    def balance(self, contract="contract-a", kind=LeaveKind.ANNUAL):
        return read_balance(self.db, 1, contract, kind)

    def test_unknown_then_exact_opening_and_accrual(self):
        self.assertIsNone(self.balance().available)
        self.record(amount="2.34")
        for month in range(12):
            self.record("accrual", f"month-{month}", Fraction(28, 12))
        self.assertEqual(self.balance().available, Fraction("30.34"))

    def test_same_key_is_idempotent_and_conflicting_payload_rejected(self):
        first = self.record()
        self.assertEqual(self.record().id, first.id)
        with self.assertRaises(ValueError):
            self.record(amount=29)
        self.assertEqual(len(self.db.scalars(select(EmployeeLeaveOperation)).all()), 1)

    def test_idempotency_survives_new_connection(self):
        first_id = self.record().id
        self.db.commit()
        with Session(self.engine) as other:
            row = append_operation(other, employee_id=1, contract_key="contract-a",
                kind=LeaveKind.ANNUAL, operation="opening", operation_key="opening",
                amount=28, effective_on=date(2027, 1, 1), actor="hr:1", reason="Test entry")
            self.assertEqual(row.id, first_id)
            other.commit()
        self.assertEqual(self.balance().available, 28)

    def test_contracts_and_units_do_not_mix(self):
        self.record()
        self.record(amount=7, contract_key="contract-b")
        self.record(amount="1.5", kind=LeaveKind.DAY_OFF)
        self.assertEqual(self.balance().available, 28)
        self.assertEqual(self.balance("contract-b").available, 7)
        self.assertEqual(self.balance(kind=LeaveKind.DAY_OFF).available, Fraction(3, 2))

    def test_concurrent_duplicate_records_once(self):
        gate = Barrier(2)

        def write():
            with Session(self.engine) as db:
                gate.wait(timeout=5)
                row = append_operation(db, employee_id=1, contract_key="contract-a",
                    kind=LeaveKind.ANNUAL, operation="opening", operation_key="opening",
                    amount=28, effective_on=date(2027, 1, 1), actor="hr:1", reason="Test entry")
                row_id = row.id
                db.commit()
                return row_id

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: write(), range(2)))
        self.assertEqual(results[0], results[1])
        self.assertEqual(self.balance().available, 28)

    def test_reserve_completion_and_cancel(self):
        self.record()
        self.record("reserve", "request-1-reserve", 14, reservation_key="request:1:v1")
        self.record("reserve", "request-2-reserve", 7, reservation_key="request:2:v1")
        self.assertEqual(self.balance().available, 7)
        self.record("consume", "request-1-complete", 14, reservation_key="request:1:v1")
        self.assertEqual(self.balance().available, 7)
        self.assertEqual(self.balance().used, 14)
        self.record("release", "request-2-cancel", 7, reservation_key="request:2:v1")
        self.assertEqual(self.balance().available, 14)

    def test_cannot_release_another_requests_reserve(self):
        self.record()
        self.record("reserve", "r1", 7, reservation_key="request:1:v1")
        for operation in ("release", "consume"):
            with self.subTest(operation=operation), self.assertRaises(ValueError):
                self.record(operation, operation, 1, reservation_key="request:2:v1")
        with self.assertRaises(ValueError):
            self.record("release", "too-much", 8, reservation_key="request:1:v1")

    def test_advance_only_for_annual(self):
        self.record(amount=0)
        self.record("reserve", "advance", 14, reservation_key="request:1:v1")
        self.assertEqual(self.balance().available, -14)
        for kind in (LeaveKind.DAY_OFF, LeaveKind.FORCE_MAJEURE):
            self.record(amount=0, kind=kind)
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                self.record("reserve", "advance", 1, reservation_key="request:1:v1", kind=kind)

    def test_rollback_and_legacy_balance_unchanged(self):
        self.db.add(EmployeeVacationBalance(employee_id=1, year=2027, used_days=3,
                    remaining_days=25, updated_at=utc_now(), updated_by_account_id=1))
        self.db.commit()
        self.record()
        self.db.rollback()
        self.assertIsNone(self.balance().available)
        self.assertEqual(self.db.get(EmployeeVacationBalance, (1, 2027)).remaining_days, 25)

    def test_actor_reason_opening_and_employee_required(self):
        for kwargs in ({"employee_id": 999}, {"reason": ""}, {"actor": ""},
                       {"contract_key": ""}, {"amount": 2.33},
                       {"operation": "accrual", "key": "a"}):
            with self.subTest(kwargs=kwargs), self.assertRaises((ValueError, LookupError)):
                self.record(**kwargs)

    def test_deletion_block_preserves_journal(self):
        from fastapi import HTTPException
        from app.web.employees import _delete_employee_record

        self.record()
        self.db.commit()
        with self.assertRaises(HTTPException) as caught:
            _delete_employee_record(self.db, self.db.get(Employee, 1))
        self.assertEqual(caught.exception.status_code, 409)
        self.db.rollback()
        self.assertEqual(self.balance().available, 28)


if __name__ == "__main__":
    unittest.main()
