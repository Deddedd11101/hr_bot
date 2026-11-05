import unittest

from app.grades.recommendations import matrix_coverage


class MatrixCoverageTests(unittest.TestCase):
    def setUp(self):
        self.catalog = dict(grades=[dict(id=i, name=name, rank=i, active=True) for i, name in ((1, "Junior"), (2, "Middle"), (3, "Senior"))],
            expectations=[dict(specialization_id=10, grade_id=grade, skill_id=skill, level=grade) for grade in (1, 2, 3) for skill in (11, 12)])
        self.scores = [dict(skillId=11, importance=1, assessed=True, currentLevel=3), dict(skillId=12, importance=3, assessed=True, currentLevel=2)]

    def test_highest_fully_met_not_majority_or_average(self):
        result = matrix_coverage(self.catalog, 10, self.scores)
        self.assertEqual(result["name"], "Middle")
        self.assertEqual(result["levels"][2]["unmet"], 1)
        self.scores[1]["currentLevel"] = 3
        self.assertEqual(matrix_coverage(self.catalog, 10, self.scores)["name"], "Senior")

    def test_missing_and_unassessed_are_not_zero_or_satisfied(self):
        self.scores[1]["assessed"] = False
        self.assertIsNone(matrix_coverage(self.catalog, 10, self.scores)["grade_id"])
        self.scores[1]["assessed"] = True
        self.catalog["expectations"] = []
        result = matrix_coverage(self.catalog, 10, self.scores)
        self.assertIsNone(result["grade_id"])
        self.assertEqual(result["levels"][0]["missing_requirements"], 2)

    def test_fractional_mean_and_zero_requirements(self):
        self.scores[1]["currentLevel"] = 1.5
        self.assertEqual(matrix_coverage(self.catalog, 10, self.scores)["name"], "Junior")
        self.catalog["expectations"] = [dict(specialization_id=10, grade_id=1, skill_id=skill, level=0) for skill in (11, 12)]
        self.assertIsNone(matrix_coverage(self.catalog, 10, self.scores)["grade_id"])
