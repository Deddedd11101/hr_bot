"""Compare immutable review snapshots, never inferred target levels."""
import hashlib
import json


def matrix_version(catalog):
    return hashlib.sha256(json.dumps(catalog, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def compare_reviews(previous, current):
    if previous["employee_id"] != current["employee_id"]:
        raise ValueError("Reviews must belong to the same employee")
    if previous["status"] != "final" or current["status"] != "final":
        raise ValueError("Only finalized reviews can be compared")
    before = {score["skillId"]: score for score in previous["scores"]}
    after = {score["skillId"]: score for score in current["scores"]}
    previous_skills = {skill["id"]: skill for skill in previous["catalog"]["skills"]}
    current_skills = {skill["id"]: skill for skill in current["catalog"]["skills"]}
    result = []
    same_scale = previous.get("scale_version", "levels-0-4-v1") == current.get("scale_version", "levels-0-4-v1")
    for key in dict.fromkeys([*after, *before]):
        old, new = before.get(key), after.get(key)
        state = "added" if old is None else "removed" if new is None else "comparable"
        if old and new:
            legacy_changed = ("revision" not in previous_skills[key] or "revision" not in current_skills[key]) and any(previous_skills[key].get(field) != current_skills[key].get(field) for field in ("name", "category_id", "complexity", "description"))
            if not same_scale or legacy_changed or previous_skills[key].get("revision", 1) != current_skills[key].get("revision", 1) or old["categoryId"] != new["categoryId"]:
                state = "changed"
            elif not old.get("assessed", old["currentLevel"] != 0) or not new.get("assessed", new["currentLevel"] != 0):
                state = "unassessed"
        result.append({"skill_id": key, "name": (new or old)["skillName"], "category": (new or old)["categoryName"],
                       "state": state, "previous": old["currentLevel"] if old and old.get("assessed", True) else None,
                       "current": new["currentLevel"] if new and new.get("assessed", True) else None,
                       "delta": new["currentLevel"] - old["currentLevel"] if state == "comparable" else None})
    categories = {}
    for item in result:
        if item["state"] != "comparable":
            continue
        old = before[item["skill_id"]]
        weight = {1: 1, 2: 1.5, 3: 2}.get(old.get("importance"), 1)
        group = categories.setdefault(old["categoryId"], {"categoryId": old["categoryId"], "categoryName": item["category"], "current": 0, "target": 0, "weight": 0})
        group["current"] += item["current"] * weight
        group["target"] += item["previous"] * weight
        group["weight"] += weight
    paired = [{**group, "current": group["current"] / group["weight"], "target": group["target"] / group["weight"]} for group in categories.values()]
    return {"previous_id": previous["id"], "current_id": current["id"], "rows": result, "categories": paired}
