import unittest
from datetime import date, timedelta
from decimal import Decimal
from fractions import Fraction

from app.vacation_accounting import (
    CalendarDayKind, LeaveBalance, LeaveKind, annual_accrual, annual_charge,
    display_amount, exact_amount, month_is_credited,
)


class VacationAccountingTests(unittest.TestCase):
    def test_exact_year_and_display(self):
        self.assertEqual(annual_accrual(12), 28)
        self.assertEqual(sum(annual_accrual(1) for _ in range(12)), 28)
        self.assertEqual(display_amount(annual_accrual(1)), "2.33")
        self.assertEqual(display_amount(annual_accrual(2)), "4.67")

    def test_fifteenth_day_threshold(self):
        self.assertFalse(month_is_credited(14))
        self.assertTrue(month_is_credited(15))
        self.assertTrue(month_is_credited(31))
        for value in (-1, 32, True, 15.0):
            with self.subTest(value=value), self.assertRaises(ValueError):
                month_is_credited(value)

    def test_bad_accrual_inputs(self):
        for value in (-1, True, 1.5):
            with self.subTest(value=value), self.assertRaises(ValueError):
                annual_accrual(value)
        with self.assertRaises(ValueError):
            annual_accrual(1, 0)

    def test_exact_import_numbers(self):
        self.assertEqual(exact_amount("2.34"), Fraction(117, 50))
        self.assertEqual(exact_amount(Decimal("-10")), -10)
        for value in (2.33, True, "NaN", Decimal("Infinity")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                exact_amount(value)

    def test_unknown_is_not_zero(self):
        unknown = LeaveBalance(LeaveKind.ANNUAL, None, accrued=annual_accrual(1))
        self.assertIsNone(unknown.available)
        self.assertEqual(LeaveBalance(LeaveKind.ANNUAL, 0).available, 0)

    def test_balance_and_advance(self):
        balance = LeaveBalance(LeaveKind.ANNUAL, "2.34", accrued=annual_accrual(1),
                               used=1, reserved=7)
        self.assertEqual(balance.available, Fraction(117, 50) + Fraction(7, 3) - 8)
        self.assertLess(balance.available, 0)

    def test_completion_does_not_double_charge(self):
        before = LeaveBalance(LeaveKind.ANNUAL, 28, used=7, reserved=14)
        after = LeaveBalance(LeaveKind.ANNUAL, 28, used=21, reserved=0)
        cancelled = LeaveBalance(LeaveKind.ANNUAL, 28, used=7, reserved=0)
        self.assertEqual(before.available, after.available)
        self.assertEqual(cancelled.available - before.available, 14)

    def test_units_are_separate(self):
        self.assertEqual(LeaveBalance(LeaveKind.DAY_OFF, "1.5").unit, "hours")
        self.assertEqual(LeaveBalance(LeaveKind.FORCE_MAJEURE, 5).unit, "days")
        self.assertEqual(LeaveBalance(LeaveKind.ANNUAL, 28).unit, "days")
        with self.assertRaises(ValueError):
            LeaveBalance("annual", 28)

    def test_negative_usage_is_invalid(self):
        for kwargs in ({"used": -1}, {"reserved": -1}, {"accrued": -1}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                LeaveBalance(LeaveKind.ANNUAL, 0, **kwargs)

    def test_weekends_charge_holidays_do_not(self):
        start = date(2027, 5, 1)
        calendar = {start: CalendarDayKind.HOLIDAY,
                    start + timedelta(days=1): CalendarDayKind.WEEKEND,
                    start + timedelta(days=2): CalendarDayKind.WORKDAY}
        end = start + timedelta(days=2)
        self.assertEqual(annual_charge(start, end, calendar), 2)
        self.assertEqual(end, date(2027, 5, 3))
        self.assertEqual(annual_charge(start, start, calendar), 0)

    def test_calendar_must_be_explicit(self):
        day = date(2027, 1, 1)
        for calendar in ({}, {day: False}, {day: "holiday"}):
            with self.subTest(calendar=calendar), self.assertRaises(ValueError):
                annual_charge(day, day, calendar)
        with self.assertRaises(ValueError):
            annual_charge(day, day - timedelta(days=1), {})


if __name__ == "__main__":
    unittest.main()
