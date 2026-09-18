"""Reference numerical cases plus Python-port boundary regressions."""

import copy
import math
import unittest

from app.grades.calculations import (
    category_averages,
    clamp_level,
    gap_list,
    importance_weight,
    next_grade_progress,
    next_grade_slug,
    weighted_average,
)


def score(name, current, target, importance, category="cat"):
    return {
        "skillId": name,
        "skillName": name,
        "categoryId": category,
        "categoryName": "\u041a\u0430\u0442\u0435\u0433\u043e\u0440\u0438\u044f",
        "importance": importance,
        "currentLevel": current,
        "targetLevel": target,
    }


class GradeCalculationTests(unittest.TestCase):
    def test_reference_clamp(self):
        for value, expected in [(-1, 0), (2.4, 2), (2.6, 3), (9, 4), ("bad", 0)]:
            with self.subTest(value=value):
                self.assertEqual(clamp_level(value), expected)

    def test_js_rounding_and_number_conversion(self):
        cases = [
            (0.5, 1),
            (2.5, 3),
            (3.5, 4),
            (-0.5, 0),
            (math.nextafter(0.5, 0), 0),
            (None, 0),
            (True, 1),
            (False, 0),
            (" 2.5 ", 3),
            ("", 0),
            ("0x3", 3),
            ("0b10", 2),
            ("0o3", 3),
            ("0x" + "f" * 300, 0),
            ("1e0", 1),
            ("1_0", 0),
            ("+0x3", 0),
            ([], 0),
            ([2.5], 3),
            ([[3]], 3),
            ([1, 2], 0),
            ([True], 0),
            ({}, 0),
            (float("nan"), 0),
            (float("inf"), 0),
            (-float("inf"), 0),
        ]
        for value, expected in cases:
            with self.subTest(value=value):
                self.assertEqual(clamp_level(value), expected)
                self.assertIs(type(clamp_level(value)), int)

    def test_reference_importance(self):
        for value, expected in [(0, 1), (1, 1), (2, 1.5), (3, 2), (4, 2), (-1, 1)]:
            self.assertEqual(importance_weight(value), expected)

    def test_reference_weighted_average(self):
        items = [
            {"value": 4, "weight": importance_weight(0)},
            {"value": 2, "weight": 1},
            {"value": 4, "weight": 2},
        ]
        self.assertAlmostEqual(
            weighted_average(items, lambda i: i["value"], lambda i: i["weight"]), 14 / 4
        )

    def test_nonpositive_weights_are_skipped_before_reading_value(self):
        items = [{"weight": 0}, {"weight": -1}, {"value": 2.5, "weight": 2}]
        self.assertEqual(
            weighted_average(iter(items), lambda i: i["value"], lambda i: i["weight"]),
            3,
        )
        self.assertEqual(weighted_average([], lambda i: i, lambda i: i), 0)
        self.assertEqual(weighted_average([0, -1], lambda i: i, lambda i: i), 0)

    def test_reference_progress(self):
        scores = [score("a", 2, 3, 3), score("b", 1, 2, 2), score("c", 4, 4, 0)]
        self.assertAlmostEqual(
            next_grade_progress(scores), (2 * 2 + 1 * 1.5 + 4) / (3 * 2 + 2 * 1.5 + 4)
        )

    def test_reference_zero_requirement(self):
        scores = [score("required", 1, 2, 3), score("none", 4, 0, 3)]
        self.assertEqual(next_grade_progress(scores), 0.5)
        self.assertEqual([i["skillName"] for i in gap_list(scores)], ["required"])

    def test_progress_caps_each_skill_and_handles_empty_targets(self):
        self.assertEqual(
            next_grade_progress([score("a", 4, 1, 1), score("b", 0, 1, 1)]), 0.5
        )
        self.assertEqual(next_grade_progress([score("a", 9, 2, 1)]), 1)
        self.assertEqual(next_grade_progress([score("a", 4, 0, 3)]), 0)
        self.assertEqual(next_grade_progress([]), 0)

    def test_reference_gaps_and_no_mutation(self):
        scores = [score("a", 2, 4, 1), score("b", 1, 3, 3), score("c", 0, 4, 0)]
        before = copy.deepcopy(scores)
        gaps = gap_list(scores)
        self.assertEqual([i["skillName"] for i in gaps], ["b", "c", "a"])
        self.assertEqual([i["gap"] for i in gaps], [2, 4, 2])
        self.assertEqual([i["weightedGap"] for i in gaps], [4, 4, 2])
        self.assertEqual(scores, before)
        self.assertTrue(
            all(all(item is not source for source in scores) for item in gaps)
        )

    def test_gap_ties_use_documented_unicode_order_and_stable_duplicates(self):
        scores = [score("b", 0, 2.5, 2), score("a", 0, 3, 2), score("a", 0, 3, 2)]
        scores[1]["skillId"] = 1
        scores[2]["skillId"] = 2
        self.assertEqual([i["skillId"] for i in gap_list(scores)], [1, 2, "b"])
        names = ["\u0451", "\u044f", "\u0430", "\u0411"]
        self.assertEqual(
            [i["skillName"] for i in gap_list([score(n, 0, 1, 1) for n in names])],
            sorted(names),
        )
        self.assertEqual(gap_list([score("done", 4, 2, 3)]), [])

    def test_category_averages_preserve_order_and_identifier_types(self):
        scores = [
            score("a", 2, 3, 3, 7),
            score("b", 1, 2, 2, "7"),
            score("c", 4, 4, 0, 7),
        ]
        scores[0]["categoryName"] = "First"
        scores[2]["categoryName"] = "Ignored"
        before = copy.deepcopy(scores)
        result = category_averages(scores)
        self.assertEqual([i["categoryId"] for i in result], [7, "7"])
        self.assertEqual(result[0]["categoryName"], "First")
        self.assertAlmostEqual(result[0]["current"], 8 / 3)
        self.assertAlmostEqual(result[0]["target"], 10 / 3)
        self.assertEqual(result[1]["current"], 1)
        self.assertEqual(scores, before)
        self.assertEqual(category_averages([]), [])

    def test_category_name_nullish_fallback(self):
        item = score("a", 0, 0, 1)
        item["categoryName"] = None
        self.assertEqual(
            category_averages([item])[0]["categoryName"],
            "\u041a\u0430\u0442\u0435\u0433\u043e\u0440\u0438\u044f",
        )
        item["categoryName"] = ""
        self.assertEqual(category_averages([item])[0]["categoryName"], "")

    def test_next_grade_slug(self):
        for rank, expected in [
            (-1, "middle"),
            (1, "middle"),
            (2, "senior"),
            (3, "lead"),
            (4, "lead"),
        ]:
            self.assertEqual(next_grade_slug(rank), expected)
