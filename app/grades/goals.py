"""Pure port of Grade goals.ts and goal-resolve.ts at a360e508.

Records use camelCase. IDs retain their type (including integer zero); None and
empty strings mean absent. Encoded key suffixes decode to strings, as in Grade;
the caller must convert them when using an integer-ID catalog. Catalog equality
does not coerce strings to integers. Resolve catalogs must already be scoped to
the caller's accessible catalog; workspace/database access is intentionally absent.
"""

from collections.abc import Iterable, Mapping
from typing import Any

GOAL_NONE = "none"
Id = str | int


def _present(value: Id | None) -> bool:
    return value is not None and value != ""


def goal_key(goal: Mapping[str, Any]) -> str:
    if not _present(goal.get("targetGradeId")):
        return GOAL_NONE
    if _present(goal.get("targetSpecializationId")):
        return f"spec:{goal['targetSpecializationId']}"
    return f"grade:{goal['targetGradeId']}"


def goal_from_key(key: str, context: Mapping[str, Any]) -> dict[str, Id | None]:
    if key.startswith("grade:"):
        return {"targetGradeId": key[len("grade:") :], "targetSpecializationId": None}
    if key.startswith("spec:"):
        grade_id = context.get("gradeId")
        return {
            "targetGradeId": grade_id
            if _present(grade_id)
            else context["currentGradeId"],
            "targetSpecializationId": key[len("spec:") :],
        }
    return {"targetGradeId": None, "targetSpecializationId": None}


def normalize_goal(
    goal: Mapping[str, Any], current_specialization_id: Id | None
) -> dict[str, Id | None]:
    grade_id = goal.get("targetGradeId")
    specialization_id = goal.get("targetSpecializationId")
    if not _present(grade_id):
        return {"targetGradeId": None, "targetSpecializationId": None}
    if (
        not _present(specialization_id)
        or specialization_id == current_specialization_id
    ):
        specialization_id = None
    return {"targetGradeId": grade_id, "targetSpecializationId": specialization_id}


def build_goal_options(context: Mapping[str, Any]) -> list[dict[str, str]]:
    return [
        {"value": GOAL_NONE, "label": "\u041d\u0435\u0442"},
        *(
            {"value": f"grade:{grade['id']}", "label": grade["name"]}
            for grade in context["grades"]
        ),
        *(
            {
                "value": f"spec:{specialization['id']}",
                "label": f"\u2192 {specialization['name']}",
            }
            for specialization in context["specializations"]
            if specialization["id"] != context["currentSpecializationId"]
        ),
    ]


def goal_label(goal: Mapping[str, Any], context: Mapping[str, Any]) -> str:
    if not _present(goal.get("targetGradeId")):
        return "\u041d\u0435\u0442"
    grade_name = next(
        (
            grade.get("name") or ""
            for grade in context["grades"]
            if grade["id"] == goal["targetGradeId"]
        ),
        "",
    )
    if not _present(goal.get("targetSpecializationId")):
        return grade_name
    specialization_name = next(
        (
            spec.get("name") or ""
            for spec in context["specializations"]
            if spec["id"] == goal["targetSpecializationId"]
        ),
        "",
    )
    return f"\u2192 {specialization_name} \u00b7 {grade_name}"


def resolve_goal(
    input_goal: Mapping[str, Any],
    current_specialization_id: Id | None,
    *,
    grades: Iterable[Mapping[str, Any]],
    specializations: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Normalize and validate against pre-scoped catalogs; specializations need active=True."""
    goal = normalize_goal(input_goal, current_specialization_id)
    if _present(goal["targetGradeId"]) and not any(
        grade["id"] == goal["targetGradeId"] for grade in grades
    ):
        return {
            "error": "\u0413\u0440\u0435\u0439\u0434 \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d",
            "status": 404,
        }
    if _present(goal["targetSpecializationId"]) and not any(
        spec["id"] == goal["targetSpecializationId"] and spec.get("active") is True
        for spec in specializations
    ):
        return {
            "error": "\u0426\u0435\u043b\u0435\u0432\u0430\u044f \u0441\u043f\u0435\u0446\u0438\u0430\u043b\u0438\u0437\u0430\u0446\u0438\u044f \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u0430",
            "status": 404,
        }
    return {"goal": goal}
