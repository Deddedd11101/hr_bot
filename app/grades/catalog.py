"""Catalog validation and persistence. The caller owns commit/rollback."""
from __future__ import annotations

import math
import re

from sqlalchemy import select

from app.models import (
    Grade, GradeSpecialization, GradeSkillCategory, GradeSkill,
    GradeSkillImportance, GradeSkillExpectation, Position,
)
from app.positions import normalize_position_slug

KINDS = {"grades": Grade, "specializations": GradeSpecialization,
         "categories": GradeSkillCategory, "skills": GradeSkill}


def integer(value, low, high, field):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{field} must be an integer from {low} to {high}")
    return value


def name(value):
    if not isinstance(value, str) or not 2 <= len(value.strip()) <= 255:
        raise ValueError("name must contain 2..255 characters")
    return value.strip()


def record(value):
    if not isinstance(value, dict):
        raise ValueError("Expected an object")
    return value


def items(value, field, nonempty=False):
    if not isinstance(value, list) or (nonempty and not value):
        raise ValueError(f"{field} must be {'a nonempty' if nonempty else 'an'} array")
    return value


def row(item):
    return {column.name: getattr(item, column.name) for column in item.__table__.columns}


def require(db, model, item_id, active=False):
    integer(item_id, 1, 2**63 - 1, "id")
    item = db.get(model, item_id)
    if item is None:
        raise LookupError(f"{model.__name__} {item_id} not found")
    if active and not item.active:
        raise ValueError(f"{model.__name__} {item_id} is archived")
    return item


def _all(db, model):
    return list(db.scalars(select(model).order_by(model.id)))


def workspace_payload(db):
    result = {key: [row(item) for item in _all(db, model)] for key, model in KINDS.items()}
    result["grades"].sort(key=lambda item: (item["rank"], item["id"]))
    for key in ("specializations", "categories", "skills"):
        result[key].sort(key=lambda item: (item["sort_order"], item["name"], item["id"]))
    result["importances"] = [row(item) for item in _all(db, GradeSkillImportance)]
    result["expectations"] = [row(item) for item in _all(db, GradeSkillExpectation)]
    result["positions"] = [{"id": p.id, "slug": p.slug, "title": p.title,
                            "active": p.is_active, "sort_order": p.sort_order}
                           for p in _all(db, Position)]
    return result


def seed_grades(db):
    existing = _all(db, Grade)
    # Bootstrap only: subsequent catalog edits must survive application startup.
    if existing:
        return
    for rank, slug in enumerate(("junior", "middle", "senior", "lead"), 1):
        db.add(Grade(slug=slug, name=slug.title(), rank=rank, sort_order=rank, active=True))
    db.flush()


def ensure_defaults(db):
    db.flush()
    skills = _all(db, GradeSkill)
    specs = _all(db, GradeSpecialization)
    grades = _all(db, Grade)
    importance_keys = {(i.skill_id, i.specialization_id) for i in _all(db, GradeSkillImportance)}
    expectation_keys = {(e.skill_id, e.grade_id, e.specialization_id)
                        for e in _all(db, GradeSkillExpectation)}
    for skill in skills:
        for spec in specs:
            if (skill.id, spec.id) not in importance_keys:
                db.add(GradeSkillImportance(skill_id=skill.id, specialization_id=spec.id, importance=1))
            for grade in grades:
                if (skill.id, grade.id, spec.id) not in expectation_keys:
                    db.add(GradeSkillExpectation(skill_id=skill.id, grade_id=grade.id,
                                                specialization_id=spec.id, level=0))
    db.flush()


def _slug(value, existing):
    base = normalize_position_slug(value).replace("_", "-")[:90] or "specialization"
    used = {item.slug for item in existing}
    slug, index = base, 2
    while slug in used:
        slug, index = f"{base}-{index}", index + 1
    return slug


def _complexity(value):
    if type(value) not in (int, float) or not math.isfinite(value) or not 1 <= value <= 2:
        raise ValueError("complexity must be a number from 1 to 2")
    return value


def save_catalog_item(db, kind, payload, item_id=None):
    if kind not in KINDS:
        raise ValueError("Unknown catalog kind")
    payload = record(payload)
    model = KINDS[kind]
    existing = _all(db, model)
    item = require(db, model, item_id) if item_id is not None else model()
    allowed = {c.name for c in model.__table__.columns} - {"id"}
    if set(payload) - allowed:
        raise ValueError("Unknown catalog fields")
    data = {key: getattr(item, key) for key in allowed} if item_id is not None else {
        "active": True, "sort_order": 0}
    data.update(payload)
    data["name"] = name(data.get("name"))
    if type(data["active"]) is not bool:
        raise ValueError("active must be boolean")
    integer(data["sort_order"], 0, 2**31 - 1, "sort_order")
    if kind in ("grades", "specializations"):
        data.setdefault("slug", _slug(data["name"], existing))
        if not isinstance(data["slug"], str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,99}", data["slug"]):
            raise ValueError("Invalid slug")
        if any(x.id != item_id and x.slug == data["slug"] for x in existing):
            raise ValueError("Slug already exists")
    if kind == "grades":
        integer(data.get("rank"), 1, 2**31 - 1, "rank")
        if any(x.id != item_id and x.rank == data["rank"] for x in existing):
            raise ValueError("Rank already exists")
    if kind == "specializations":
        description = data.get("description")
        if description is not None and not isinstance(description, str):
            raise ValueError("description must be text or null")
        position = data.get("position_slug")
        if position is not None:
            if not isinstance(position, str):
                raise ValueError("position_slug must be text or null")
            position = normalize_position_slug(position)
            if not db.scalar(select(Position.id).where(Position.slug == position, Position.is_active.is_(True))):
                raise ValueError("Unknown active position slug")
            data["position_slug"] = position
    if kind == "skills":
        require(db, GradeSkillCategory, data.get("category_id"), active=True)
        data["complexity"] = _complexity(data.get("complexity", 1))
    if kind in ("categories", "skills") and any(
        x.id != item_id and x.name.strip().lower() == data["name"].lower()
        and (kind == "categories" or x.category_id == data["category_id"]) for x in existing
    ):
        raise ValueError("Name already exists")
    for key, value in data.items():
        setattr(item, key, value)
    db.add(item)
    db.flush()
    ensure_defaults(db)
    return row(item)


def archive_catalog_item(db, kind, item_id):
    if kind not in KINDS:
        raise ValueError("Unknown catalog kind")
    item = require(db, KINDS[kind], item_id)
    item.active = False
    db.flush()
    return row(item)


def save_matrix(db, payload):
    payload = record(payload)
    spec = require(db, GradeSpecialization, payload.get("specialization_id"), active=True)
    grades = {g.slug: g for g in _all(db, Grade) if g.active}
    categories = {c.id for c in _all(db, GradeSkillCategory) if c.active}
    skills = {s.id for s in _all(db, GradeSkill) if s.active and s.category_id in categories}
    validated, seen = [], set()
    for entry in items(payload.get("rows"), "rows"):
        entry = record(entry)
        skill_id = integer(entry.get("skill_id"), 1, 2**63 - 1, "skill_id")
        if skill_id not in skills or skill_id in seen:
            raise ValueError("Unknown, archived or duplicate skill")
        seen.add(skill_id)
        importance = integer(entry.get("importance"), 1, 3, "importance")
        levels = record(entry.get("levels"))
        for slug, level in levels.items():
            if slug not in grades:
                raise ValueError(f"Unknown active grade: {slug}")
            integer(level, 0, 4, "level")
        validated.append((skill_id, importance, levels))
    importances = {(i.skill_id, i.specialization_id): i for i in _all(db, GradeSkillImportance)}
    expectations = {(e.skill_id, e.grade_id, e.specialization_id): e for e in _all(db, GradeSkillExpectation)}
    for skill_id, importance, levels in validated:
        key = (skill_id, spec.id)
        item = importances.get(key)
        if item is None:
            item = GradeSkillImportance(skill_id=skill_id, specialization_id=spec.id)
            db.add(item)
        item.importance = importance
        for slug, level in levels.items():
            key = (skill_id, grades[slug].id, spec.id)
            item = expectations.get(key)
            if item is None:
                item = GradeSkillExpectation(skill_id=skill_id, grade_id=grades[slug].id, specialization_id=spec.id)
                db.add(item)
            item.level = level
    db.flush()
    return workspace_payload(db)


def _import_number(value, low, high, aliases, field):
    if isinstance(value, str):
        value = value.strip().lower()
        if value in aliases:
            value = aliases[value]
        else:
            try:
                number = float(value or "0")
                value = int(number) if math.isfinite(number) and number.is_integer() else None
            except ValueError:
                value = None
    elif type(value) is float and math.isfinite(value) and value.is_integer():
        value = int(value)
    return integer(value, low, high, field)


def _normalize_import(value, grade_slugs):
    value = record(value)
    result = {"specialization": {"name": name(record(value.get("specialization")).get("name"))}, "categories": []}
    names = set()
    for category in items(value.get("categories"), "categories", True):
        category = record(category)
        category_name = name(category.get("name"))
        if category_name.lower() in names:
            raise ValueError("Duplicate category name")
        names.add(category_name.lower())
        output = {"name": category_name, "skills": []}
        skill_names = set()
        for skill in items(category.get("skills"), "skills", True):
            skill = record(skill)
            skill_name = name(skill.get("name"))
            if skill_name.lower() in skill_names:
                raise ValueError("Duplicate skill name")
            skill_names.add(skill_name.lower())
            levels = record(skill.get("levels"))
            output["skills"].append({
                "name": skill_name, "complexity": _complexity(skill.get("complexity", 1)),
                "importance": _import_number(skill.get("importance"), 1, 3,
                                             {"ordinary": 1, "key": 2, "critical": 3}, "importance"),
                "levels": {slug: _import_number(levels.get(slug), 0, 4,
                                                {"none": 0, "\u043d\u0435\u0442": 0}, "level")
                           for slug in grade_slugs},
            })
        result["categories"].append(output)
    return result


def import_catalog(db, payload):
    # In particular, a preview must not trigger Session autoflush of pending work.
    with db.no_autoflush:
        return _import_catalog(db, payload)


def _import_catalog(db, payload):
    payload = record(payload)
    if type(payload.get("dryRun")) is not bool or payload.get("mode") not in (
        "create-specialization", "update-specialization"
    ):
        raise ValueError("dryRun boolean and valid mode are required")
    grades = [g for g in _all(db, Grade) if g.active]
    if not grades:
        raise ValueError("Seed active grades before importing")
    catalog = _normalize_import(payload.get("catalog"), [g.slug for g in grades])
    specs = _all(db, GradeSpecialization)
    cats = {c.name.strip().lower(): c for c in _all(db, GradeSkillCategory)}
    skills = {(s.category_id, s.name.strip().lower()): s for s in _all(db, GradeSkill)}
    spec_name = catalog["specialization"]["name"]
    if payload["mode"] == "update-specialization":
        if payload.get("targetSpecializationId") is None:
            raise ValueError("targetSpecializationId is required")
        spec = require(db, GradeSpecialization, payload["targetSpecializationId"], active=True)
    else:
        spec = next((s for s in specs if s.name.strip().lower() == spec_name.lower()), None)
    counts = dict(categories=len(catalog["categories"]), skills=0,
                  createCategories=0, updateCategories=0, createSkills=0, updateSkills=0)
    for cat_input in catalog["categories"]:
        cat = cats.get(cat_input["name"].lower())
        counts["updateCategories" if cat and cat.active else "createCategories"] += 1
        for skill_input in cat_input["skills"]:
            skill = skills.get((cat.id, skill_input["name"].lower())) if cat else None
            counts["skills"] += 1
            counts["updateSkills" if skill and skill.active else "createSkills"] += 1
    preview = {"specialization": {"name": spec_name, "slug": spec.slug if spec else _slug(spec_name, specs),
                                  "action": "update" if spec and spec.active else "create"},
               "counts": counts, "errors": []}
    if payload["dryRun"]:
        return preview
    if spec is None:
        spec = GradeSpecialization(name=spec_name, slug=preview["specialization"]["slug"],
                                   sort_order=len([s for s in specs if s.active]) + 1)
        db.add(spec)
    elif not spec.active:
        spec.name = spec_name
        spec.sort_order = len([s for s in specs if s.active]) + 1
    spec.active = True
    db.flush()
    matrix_rows = []
    for index, cat_input in enumerate(catalog["categories"], 1):
        cat = cats.get(cat_input["name"].lower())
        if cat is None:
            cat = GradeSkillCategory()
            db.add(cat)
        cat.name, cat.sort_order, cat.active = cat_input["name"], index, True
        db.flush()
        for skill_index, skill_input in enumerate(cat_input["skills"], 1):
            skill = skills.get((cat.id, skill_input["name"].lower()))
            if skill is None:
                skill = GradeSkill(category_id=cat.id, complexity=skill_input["complexity"])
                db.add(skill)
            # Reference import preserves complexity for an existing skill.
            skill.name, skill.sort_order, skill.active = skill_input["name"], skill_index, True
            db.flush()
            matrix_rows.append({"skill_id": skill.id, "importance": skill_input["importance"],
                                "levels": skill_input["levels"]})
    ensure_defaults(db)
    save_matrix(db, {"specialization_id": spec.id, "rows": matrix_rows})
    preview["specialization"].update(id=spec.id, name=spec.name)
    return preview
