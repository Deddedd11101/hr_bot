import unittest
from datetime import date
from fractions import Fraction

from app.vacation_accrual import MonthEndPolicy, accrue_annual, preview_accrual
from app.vacation_accounting import LeaveKind
from app.vacation_ledger import read_balance
from tests import test_vacation_ledger as ledger_tests


class AccrualPreviewTests(unittest.TestCase):
    def preview(self, **kwargs):
        values = dict(hired_on=date(2027, 2, 5), opening_through=date(2027, 2, 5),
                      through=date(2027, 3, 19), no_exclusions_confirmed=True)
        values.update(kwargs)
        return preview_accrual(**values)

    def test_fifteenth_day_and_month_close(self):
        self.assertEqual(self.preview(through=date(2027, 2, 18)), [])
        self.assertEqual([item.earned_on for item in self.preview()],
                         [date(2027, 2, 19), date(2027, 3, 19)])
        self.assertEqual(len(self.preview(through=date(2027, 3, 4))), 1)

    def test_opening_is_inclusive(self):
        self.assertEqual([item.earned_on for item in self.preview(opening_through=date(2027, 2, 19))],
                         [date(2027, 3, 19)])

    def test_twelve_months_exact(self):
        plan = self.preview(through=date(2028, 2, 4))
        self.assertEqual(len(plan), 12)
        self.assertEqual(sum(item.amount for item in plan), 28)

    def test_explicit_month_end_and_no_anchor_drift(self):
        args = dict(hired_on=date(2027, 1, 31), opening_through=date(2027, 1, 31),
                    through=date(2027, 4, 15))
        with self.assertRaises(ValueError):
            self.preview(**args)
        plan = self.preview(**args, month_end_policy=MonthEndPolicy.CLAMP_TO_LAST_DAY)
        self.assertEqual([item.month_start for item in plan],
                         [date(2027, 1, 31), date(2027, 2, 28), date(2027, 3, 31)])

    def test_leap_day(self):
        plan = self.preview(hired_on=date(2024, 2, 29), opening_through=date(2025, 1, 31),
            through=date(2025, 3, 15), month_end_policy=MonthEndPolicy.CLAMP_TO_LAST_DAY)
        self.assertEqual([item.month_start for item in plan],
                         [date(2025, 1, 29), date(2025, 2, 28)])

    def test_no_automatic_assumptions(self):
        for args in ({"no_exclusions_confirmed": False},
                     {"hired_on": None}, {"month_end_policy": "clamp"},
                     {"opening_through": date(2027, 4, 1)}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                self.preview(**args)


class AccrualLedgerTests(unittest.TestCase):
    setUp = ledger_tests.VacationLedgerTests.setUp
    tearDown = ledger_tests.VacationLedgerTests.tearDown
    record = ledger_tests.VacationLedgerTests.record

    def accrue(self, **kwargs):
        values = dict(employee_id=1, contract_key="contract-a", hired_on=date(2026, 2, 5),
                      through=date(2027, 3, 19), no_exclusions_confirmed=True)
        values.update(kwargs)
        return accrue_annual(self.db, **values)

    def test_apply_and_retry(self):
        self.record(amount="2.34")  # Includes everything through 01.01.2027.
        plan = self.accrue()
        self.assertEqual(len(plan), 3)
        self.assertEqual(self.accrue(), [])
        self.assertEqual(read_balance(self.db, 1, "contract-a", LeaveKind.ANNUAL).available,
                         Fraction("2.34") + 7)
        self.assertEqual(len(self.accrue(through=date(2027, 4, 19))), 1)

    def test_requires_opening_and_verified_inputs(self):
        with self.assertRaises(ValueError):
            self.accrue()
        self.record()
        with self.assertRaises(ValueError):
            self.accrue(no_exclusions_confirmed=False)

    def test_changed_anchor_is_not_a_second_grant(self):
        self.record()
        self.accrue()
        with self.assertRaises(ValueError):
            self.accrue(hired_on=date(2026, 2, 6))
        with self.assertRaises(ValueError):
            self.accrue(through=date(2027, 1, 19))


if __name__ == "__main__":
    unittest.main()
