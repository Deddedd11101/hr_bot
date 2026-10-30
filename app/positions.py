from __future__ import annotations

import re
from datetime import datetime
from typing import Iterable, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import Employee, Position
from .time_utils import utc_now

ROLE_SCOPE_ALL = "all"

DEFAULT_POSITIONS = [
    {"title": "Дизайнер", "slug": "designer", "sort_order": 10},
    {"title": "Project manager", "slug": "project_manager", "sort_order": 20},
    {"title": "Аналитик", "slug": "analyst", "sort_order": 30},
]

_CYRILLIC_TRANSLIT = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "h",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "sch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}

_LEGACY_SCOPE_ALIASES = {
    "designer": "designer",
    "дизайнер": "designer",
    "project_manager": "project_manager",
    "project-manager": "project_manager",
    "project manager": "project_manager",
    "pm": "project_manager",
    "рм": "project_manager",
    "product_manager": "project_manager",
    "product manager": "project_manager",
    "analyst": "analyst",
    "аналитик": "analyst",
}

_LEGACY_SCOPE_TITLES = {
    "designer": "Дизайнер",
    "project_manager": "Project manager",
    "analyst": "Аналитик",
}


def _transliterate(value: str) -> str:
    result: list[str] = []
    for char in value.lower():
        result.append(_CYRILLIC_TRANSLIT.get(char, char))
    return "".join(result)


def normalize_position_slug(value: str) -> str:
    normalized = (value or "").strip().lower()
    if not normalized:
        return ""
    alias = _LEGACY_SCOPE_ALIASES.get(normalized)
    if alias:
        return alias
    transliterated = _transliterate(normalized)
    slug = re.sub(r"[^a-z0-9]+", "_", transliterated).strip("_")
    return slug[:128]


def canonical_position_title(value: str) -> str:
    normalized_slug = normalize_position_slug(value)
    if normalized_slug in _LEGACY_SCOPE_TITLES:
        return _LEGACY_SCOPE_TITLES[normalized_slug]
    return (value or "").strip()


def position_title_key(value: str) -> str:
    return " ".join((value or "").split()).casefold()


def canonical_project_lead_answer(db: Session, value: str) -> str:
    aliases = {"project_manager", "project manager", "руководитель проекта", "руководитель проектов",
               "rukovoditel_proekta", "rukovoditel_proektov"}
    if position_title_key(value) in aliases:
        position = db.query(Position).filter_by(slug="rukovoditel_proektov", is_active=True).first()
        if position is not None:
            return position.title
    return value


def _catalog(db: Session) -> list[tuple[int, str, str]]:
    cached = db.info.get("position_matching_catalog")
    changed = any(isinstance(row, Position) for row in (*db.new, *db.dirty, *db.deleted))
    if cached is None or cached[0] is not db.get_transaction() or changed:
        rows = [(row.id, row.title, row.slug) for row in db.query(Position).all()]
        cached = (db.get_transaction(), rows)
        db.info["position_matching_catalog"] = cached
    return cached[1]


def _catalog_scope(db: Session, value: str, *, scope: bool = False) -> str | None:
    rows = _catalog(db)
    key = position_title_key(value)
    slug = normalize_position_slug(value)
    if scope:
        direct = [row for row in rows if row[2] == slug]
        if direct:
            return direct[0][2] if len(direct) == 1 else None
    titles = [row for row in rows if position_title_key(row[1]) == key]
    if titles:
        return titles[0][2] if len(titles) == 1 else None
    direct = [row for row in rows if row[2] == slug]
    if direct:
        return direct[0][2] if len(direct) == 1 else None
    normalized = [row for row in rows if normalize_position_slug(row[1]) == slug]
    if normalized:
        return normalized[0][2] if len(normalized) == 1 else None
    return slug


def build_role_scope_labels(db: Session, *, include_inactive: bool = False) -> dict[str, str]:
    labels = {ROLE_SCOPE_ALL: "Для всех ролей"}
    query = db.query(Position)
    if not include_inactive:
        query = query.filter(Position.is_active.is_(True))
    positions = query.order_by(Position.sort_order.asc(), Position.id.asc()).all()
    for position in positions:
        labels[position.slug] = position.title
    return labels


def parse_role_scopes(value: str | Iterable[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_items = re.split(r"[,\n;]+", value)
    else:
        raw_items = [str(item) for item in value]
    scopes: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        normalized = resolve_scope_slug(item)
        if normalized == ROLE_SCOPE_ALL:
            continue
        if normalized and normalized not in seen:
            seen.add(normalized)
            scopes.append(normalized)
    return scopes


def serialize_role_scopes(value: str | Iterable[str] | None) -> str:
    scopes = parse_role_scopes(value)
    return ",".join(scopes) if scopes else ROLE_SCOPE_ALL


def role_scope_label(db: Session, value: str | Iterable[str] | None, *, include_inactive: bool = True) -> str:
    scopes = parse_role_scopes(value)
    if not scopes:
        return build_role_scope_labels(db, include_inactive=include_inactive)[ROLE_SCOPE_ALL]
    labels = build_role_scope_labels(db, include_inactive=include_inactive)
    return ", ".join(labels.get(scope, canonical_position_title(scope) or scope) for scope in scopes)


def position_options(db: Session, *, include_inactive: bool = False) -> list[Position]:
    query = db.query(Position)
    if not include_inactive:
        query = query.filter(Position.is_active.is_(True))
    return query.order_by(Position.sort_order.asc(), Position.id.asc()).all()


def employee_position_values(db: Session, *, current_value: str = "") -> list[str]:
    values = [position.title for position in position_options(db)]
    return values


def position_titles_for_scope(db: Session, role_scope: str) -> list[str]:
    normalized_scopes = parse_role_scopes(role_scope)
    if not normalized_scopes:
        return []
    titles = [title for _id, title, _slug in _catalog(db)]
    for normalized_scope in normalized_scopes:
        legacy_title = canonical_position_title(normalized_scope)
        if legacy_title and legacy_title not in titles:
            titles.append(legacy_title)
    # SQL targeting must include the same legacy/case variants accepted by runtime.
    titles.extend(value for (value,) in db.query(Employee.desired_position).distinct() if value)
    return list(dict.fromkeys(title for title in titles if position_matches_scope(title, role_scope, db=db)))


def resolve_scope_slug(value: str) -> str:
    normalized = normalize_position_slug(value)
    return normalized or ROLE_SCOPE_ALL


def position_matches_scope(employee_position: Optional[str], role_scope: Optional[str], *, db: Session | None = None) -> bool:
    normalized_scopes = parse_role_scopes(role_scope or "")
    if not normalized_scopes:
        return True
    if db is None:
        normalized_employee_scope = normalize_position_slug(employee_position or "")
        return bool(normalized_employee_scope) and normalized_employee_scope in set(normalized_scopes)
    employee_key = _catalog_scope(db, employee_position or "")
    scope_keys = {_catalog_scope(db, scope, scope=True) for scope in normalized_scopes}
    return bool(employee_key) and employee_key in scope_keys


def ensure_position_exists(
    db: Session,
    *,
    title: str,
    slug: str | None = None,
    is_active: bool = True,
    sort_order: int | None = None,
) -> Position:
    normalized_title = canonical_position_title(title)
    if not normalized_title:
        raise ValueError("Position title is required")
    normalized_slug = normalize_position_slug(slug or normalized_title)
    if not normalized_slug:
        raise ValueError("Position slug is required")

    position = db.query(Position).filter(Position.slug == normalized_slug).first()
    if position is None:
        position = (
            db.query(Position)
            .filter(func.lower(Position.title) == normalized_title.lower())
            .first()
        )
    if position is None:
        next_sort_order = sort_order
        if next_sort_order is None:
            max_sort_order = db.query(func.max(Position.sort_order)).scalar()
            next_sort_order = int(max_sort_order or 0) + 10
        position = Position(
            title=normalized_title,
            slug=normalized_slug,
            is_active=is_active,
            sort_order=next_sort_order,
            created_at=utc_now(),
        )
        db.add(position)
        db.flush()
        db.info.pop("position_matching_catalog", None)
        return position

    changed = False
    if position.title != normalized_title:
        position.title = normalized_title
        changed = True
    if is_active and not position.is_active:
        position.is_active = True
        changed = True
    if sort_order is not None and position.sort_order != sort_order:
        position.sort_order = sort_order
        changed = True
    if changed:
        db.flush()
        db.info.pop("position_matching_catalog", None)
    return position


def resolve_employee_position_value(db: Session, value: str) -> Optional[str]:
    normalized_value = (value or "").strip()
    if not normalized_value:
        return None

    rows = position_options(db)
    if normalized_value.isdigit():
        matches = [row for row in rows if row.id == int(normalized_value)]
    else:
        matches = [row for row in rows if position_title_key(row.title) == position_title_key(normalized_value)]
        if not matches:
            matches = [row for row in rows if row.slug == normalized_value]
    if len(matches) != 1:
        raise ValueError("Выберите активную должность из справочника")
    return matches[0].title


def seed_positions_catalog() -> None:
    with SessionLocal() as db:
        # A managed catalog is not a startup repair target.
        if db.query(Position.id).first() or db.query(Employee.id).first():
            return
        changed = False
        for item in DEFAULT_POSITIONS:
            before_count = db.query(Position).count()
            ensure_position_exists(
                db,
                title=item["title"],
                slug=item["slug"],
                sort_order=item["sort_order"],
            )
            if db.query(Position).count() != before_count:
                changed = True

        if changed:
            db.commit()
        else:
            db.rollback()
