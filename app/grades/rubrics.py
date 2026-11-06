"""Specialization-scoped behavioral anchors, frozen with each review."""
import json


def validate_rubric(value):
    if not isinstance(value, dict) or set(value) != {"levels", "na"}:
        raise ValueError("Rubric requires levels and na")
    levels = value["levels"]
    if not isinstance(levels, dict) or set(levels) != {"1", "2", "3", "4"}:
        raise ValueError("Rubric requires levels 1..4")
    texts = [*levels.values(), value["na"]]
    if any(not isinstance(t, str) or not 1 <= len(t.strip()) <= 600 for t in texts):
        raise ValueError("Rubric descriptions must contain 1..600 characters")
    return {"levels": {k: levels[k].strip() for k in ("1", "2", "3", "4")}, "na": value["na"].strip()}


def validate_questions(value):
    if not isinstance(value, list) or len(value) > 20 or any(
        not isinstance(q, str) or not 1 <= len(q.strip()) <= 2000 for q in value
    ):
        raise ValueError("Need at most 20 nonempty open questions")
    return [q.strip() for q in value]


def guidance(specialization):
    return json.loads(specialization.get("assessment_guidance_json") or "{}")
