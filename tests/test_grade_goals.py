"""Grade goals.test.ts cases and pure goal-resolve validation cases."""

import copy
import unittest

from app.grades.goals import (
    GOAL_NONE,
    build_goal_options,
    goal_from_key,
    goal_key,
    goal_label,
    normalize_goal,
    resolve_goal,
)


def goal(grade=None, specialization=None):
    return {"targetGradeId": grade, "targetSpecializationId": specialization}


class GradeGoalTests(unittest.TestCase):
    def setUp(self):
        self.grades = [
            {"id": "g1", "name": "Junior", "rank": 1},
            {"id": "g2", "name": "Middle", "rank": 2},
            {"id": "g3", "name": "Senior", "rank": 3},
        ]
        self.specs = [
            {
                "id": "s1",
                "name": "\u041f\u0440\u043e\u0434\u0443\u043a\u0442\u043e\u0432\u044b\u0439 \u0434\u0438\u0437\u0430\u0439\u043d",
                "active": True,
            },
            {
                "id": "s2",
                "name": "\u0413\u0440\u0430\u0444\u0438\u0447\u0435\u0441\u043a\u0438\u0439 \u0434\u0438\u0437\u0430\u0439\u043d",
                "active": True,
            },
        ]
        self.context = {
            "grades": self.grades,
            "specializations": self.specs,
            "currentSpecializationId": "s1",
        }

    def test_reference_keys(self):
        for item, expected in [
            (goal(), GOAL_NONE),
            (goal("g2"), "grade:g2"),
            (goal("g2", "s2"), "spec:s2"),
        ]:
            self.assertEqual(goal_key(item), expected)

    def test_reference_decoding(self):
        context = {"currentGradeId": "g1"}
        for key, expected in [
            (GOAL_NONE, goal()),
            ("grade:g3", goal("g3")),
            ("spec:s2", goal("g1", "s2")),
            ("garbage", goal()),
        ]:
            self.assertEqual(goal_from_key(key, context), expected)
        self.assertEqual(
            goal_from_key("spec:s2", {"currentGradeId": "g1", "gradeId": "g3"}),
            goal("g3", "s2"),
        )

    def test_reference_options(self):
        options = build_goal_options(self.context)
        self.assertEqual(
            [i["value"] for i in options],
            [GOAL_NONE, "grade:g1", "grade:g2", "grade:g3", "spec:s2"],
        )
        self.assertEqual(options[0]["label"], "\u041d\u0435\u0442")
        self.assertEqual(options[4]["label"], "\u2192 " + self.specs[1]["name"])
        self.context["currentSpecializationId"] = None
        self.assertEqual(
            len(
                [
                    i
                    for i in build_goal_options(self.context)
                    if i["value"].startswith("spec:")
                ]
            ),
            2,
        )

    def test_reference_labels(self):
        self.assertEqual(goal_label(goal(), self.context), "\u041d\u0435\u0442")
        self.assertEqual(goal_label(goal("g2"), self.context), "Middle")
        self.assertEqual(
            goal_label(goal("g2", "s2"), self.context),
            "\u2192 " + self.specs[1]["name"] + " \u00b7 Middle",
        )

    def test_reference_normalization(self):
        for item, expected in [
            (goal("g2", "s1"), goal("g2")),
            (goal(None, "s2"), goal()),
            (goal("g2", "s2"), goal("g2", "s2")),
        ]:
            before = copy.deepcopy(item)
            self.assertEqual(normalize_goal(item, "s1"), expected)
            self.assertEqual(item, before)

    def test_unknown_references_and_empty_key_suffixes(self):
        self.assertEqual(goal_label(goal("missing"), self.context), "")
        self.assertEqual(
            goal_label(goal("missing", "missing"), self.context), "\u2192  \u00b7 "
        )
        self.assertEqual(goal_from_key("grade:", {"currentGradeId": "g1"}), goal(""))
        self.assertEqual(normalize_goal(goal("", "s2"), "s1"), goal())
        self.assertEqual(
            goal_from_key("spec:", {"currentGradeId": "g1", "gradeId": ""}),
            goal("g1", ""),
        )

    def test_integer_ids_including_zero_and_string_key_decoding(self):
        context = {
            "grades": [{"id": 0, "name": "Junior"}],
            "specializations": [{"id": 0, "name": "Design", "active": True}],
            "currentSpecializationId": 1,
        }
        self.assertEqual(goal_key(goal(0, 0)), "spec:0")
        self.assertEqual(normalize_goal(goal(0, 0), 0), goal(0))
        self.assertEqual(goal_label(goal(0), context), "Junior")
        self.assertEqual(goal_label(goal("0"), context), "")
        self.assertEqual(
            [i["value"] for i in build_goal_options(context)],
            ["none", "grade:0", "spec:0"],
        )
        self.assertEqual(
            goal_from_key("spec:0", {"currentGradeId": 1, "gradeId": 0}), goal(0, "0")
        )
        self.assertEqual(
            resolve_goal(
                goal(0, 0),
                1,
                grades=context["grades"],
                specializations=context["specializations"],
            ),
            {"goal": goal(0, 0)},
        )

    def resolve(self, item, current="s1"):
        return resolve_goal(
            item, current, grades=self.grades, specializations=self.specs
        )

    def test_resolve_none_grade_and_transition(self):
        for item in [goal(), goal("g2"), goal("g2", "s2")]:
            self.assertEqual(self.resolve(item), {"goal": item})

    def test_resolve_normalizes_before_validating(self):
        self.specs = []
        self.assertEqual(self.resolve(goal(None, "missing")), {"goal": goal()})
        self.assertEqual(self.resolve(goal("g2", "s1")), {"goal": goal("g2")})

    def test_resolve_missing_grade_takes_precedence(self):
        self.assertEqual(
            self.resolve(goal("missing", "missing")),
            {
                "error": "\u0413\u0440\u0435\u0439\u0434 \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d",
                "status": 404,
            },
        )

    def test_resolve_missing_or_inactive_specialization(self):
        expected = {
            "error": "\u0426\u0435\u043b\u0435\u0432\u0430\u044f \u0441\u043f\u0435\u0446\u0438\u0430\u043b\u0438\u0437\u0430\u0446\u0438\u044f \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u0430",
            "status": 404,
        }
        self.assertEqual(self.resolve(goal("g2", "missing")), expected)
        self.specs[1]["active"] = False
        self.assertEqual(self.resolve(goal("g2", "s2")), expected)
        del self.specs[1]["active"]
        self.assertEqual(self.resolve(goal("g2", "s2")), expected)

    def test_no_mutation_of_catalog_or_goal(self):
        item = goal("g2", "s2")
        before = copy.deepcopy((item, self.context))
        build_goal_options(self.context)
        goal_label(item, self.context)
        result = self.resolve(item)
        self.assertEqual((item, self.context), before)
        self.assertIsNot(result["goal"], item)
