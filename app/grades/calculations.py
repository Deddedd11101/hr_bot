"""Port of Grade calculations.ts at a360e5083b6608dbeceb1038769c5280936fe7c0.

Records retain Grade's camelCase keys; identifiers can be strings or integers.
Gap ties use Unicode code-point order, not JavaScript's ICU Russian collation.
Thus case, punctuation, and Cyrillic (notably yo) ties can differ from Grade.
No process-global locale is changed and no third-party dependency is required.
"""

import math
import re
from collections.abc import Callable, Iterable, Mapping
from typing import Any, TypeVar

MAX_LEVEL = 4
T = TypeVar("T")


def _js_number(value: Any) -> float:
    # JSON arrays undergo JS Array.toString before Number conversion.
    if isinstance(value, (list, tuple)):

        def element_text(item: Any) -> str:
            if item is None:
                return ""
            if isinstance(item, (list, tuple)):
                return ",".join(element_text(child) for child in item)
            if isinstance(item, bool):
                return "true" if item else "false"
            return str(item)

        value = ",".join(element_text(item) for item in value)
    if value is None:
        return 0.0
    if isinstance(value, str):
        value = value.strip().strip("\ufeff").strip()
        if not value:
            return 0.0
        if re.fullmatch(r"0(?:[xX][0-9a-fA-F]+|[bB][01]+|[oO][0-7]+)", value):
            try:
                return float(int(value, 0))
            except OverflowError:
                return math.inf
        if not re.fullmatch(
            r"[+-]?(?:(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?|Infinity)", value
        ):
            return math.nan
    elif not isinstance(value, (int, float)):
        return math.nan
    try:
        return float(value)
    except (ValueError, OverflowError):
        return math.nan


def clamp_level(value: Any) -> int:
    """Coerce JSON-like values using JS Number, then round ties toward +infinity."""
    numeric = _js_number(value)
    if not math.isfinite(numeric) or numeric <= 0:
        return 0
    if numeric >= MAX_LEVEL:
        return MAX_LEVEL
    integer = math.floor(numeric)
    return integer + (numeric - integer >= 0.5)


def importance_weight(importance: float) -> float:
    if importance >= 3:
        return 2
    if importance == 2:
        return 1.5
    return 1


def weighted_average(
    items: Iterable[T],
    value_for_item: Callable[[T], Any],
    weight_for_item: Callable[[T], float],
) -> float:
    total = weight_total = 0.0
    for item in items:
        weight = weight_for_item(item)
        if weight <= 0:
            continue
        total += clamp_level(value_for_item(item)) * weight
        weight_total += weight
    return total / weight_total if weight_total > 0 else 0


def category_averages(scores: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str | int, list[Mapping[str, Any]]] = {}
    for score in scores:
        buckets.setdefault(score["categoryId"], []).append(score)
    return [
        {
            "categoryId": category_id,
            "categoryName": items[0].get("categoryName")
            if items[0].get("categoryName") is not None
            else "\u041a\u0430\u0442\u0435\u0433\u043e\u0440\u0438\u044f",
            "current": weighted_average(
                items,
                lambda item: item["currentLevel"],
                lambda item: importance_weight(item["importance"]),
            ),
            "target": weighted_average(
                items,
                lambda item: item["targetLevel"],
                lambda item: importance_weight(item["importance"]),
            ),
        }
        for category_id, items in buckets.items()
    ]


def next_grade_progress(scores: Iterable[Mapping[str, Any]]) -> float:
    current = target = 0.0
    for score in scores:
        weight = importance_weight(score["importance"])
        required = clamp_level(score["targetLevel"])
        current += min(clamp_level(score["currentLevel"]), required) * weight
        target += required * weight
    return current / target if target > 0 else 0


def gap_list(scores: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Return new records, ordered by weighted gap, importance, then Unicode name."""
    gaps = []
    for score in scores:
        gap = max(
            0, clamp_level(score["targetLevel"]) - clamp_level(score["currentLevel"])
        )
        if gap:
            gaps.append(
                {
                    **score,
                    "gap": gap,
                    "weightedGap": gap * importance_weight(score["importance"]),
                }
            )
    return sorted(
        gaps,
        key=lambda score: (
            -score["weightedGap"],
            -score["importance"],
            score["skillName"],
        ),
    )


def next_grade_slug(current_rank: float) -> str:
    if current_rank <= 1:
        return "middle"
    if current_rank == 2:
        return "senior"
    return "lead"
