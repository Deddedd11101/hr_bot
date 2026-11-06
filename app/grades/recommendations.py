"""Explain frozen-matrix coverage; never apply a personnel grade decision."""

from .calculations import importance_weight


def matrix_coverage(catalog, specialization_id, scores):
    expectations = {(row["grade_id"], row["skill_id"]): row["level"]
                    for row in catalog["expectations"] if row["specialization_id"] == specialization_id}
    levels = []
    for grade in sorted(catalog["grades"], key=lambda row: (row["rank"], row["id"])):
        if not grade.get("active", True):
            continue
        required_total = covered_total = 0.0
        missing = unassessed = unmet = 0
        for score in scores:
            required = expectations.get((grade["id"], score["skillId"]))
            if required is None:
                missing += 1
                continue
            if required == 0:
                continue
            weight = importance_weight(score["importance"])
            required_total += required * weight
            if not score.get("assessed", True):
                unassessed += 1
                continue
            covered_total += min(score["currentLevel"], required) * weight
            if score["currentLevel"] < required:
                unmet += 1
        fully_met = required_total > 0 and not (missing or unassessed or unmet)
        levels.append(dict(grade_id=grade["id"], name=grade["name"], fully_met=fully_met,
                           coverage_percent=covered_total / required_total * 100 if required_total else None,
                           missing_requirements=missing, unassessed=unassessed, unmet=unmet))
    supported = [row for row in levels if row["fully_met"]]
    return dict(method="highest_fully_met_frozen_matrix", grade_id=supported[-1]["grade_id"] if supported else None,
                name=supported[-1]["name"] if supported else None, levels=levels)
