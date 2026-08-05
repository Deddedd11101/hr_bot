from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

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


def build_role_scope_labels(db: Session, *, include_inactive: bool = False) -> dict[str, str]:
    labels = {ROLE_SCOPE_ALL: "Для всех ролей"}
    query = db.query(Position)
    if not include_inactive:
        query = query.filter(Position.is_active.is_(True))
    positions = query.order_by(Position.sort_order.asc(), Position.id.asc()).all()
    for position in positions:
        labels[position.slug] = position.title
    return labels


def position_options(db: Session, *, include_inactive: bool = False) -> list[Position]:
    query = db.query(Position)
    if not include_inactive:
        query = query.filter(Position.is_active.is_(True))
    return query.order_by(Position.sort_order.asc(), Position.id.asc()).all()


def employee_position_values(db: Session, *, current_value: str = "") -> list[str]:
    values = [position.title for position in position_options(db)]
    normalized_current = canonical_position_title(current_value)
    if normalized_current and normalized_current not in values:
        values.append(normalized_current)
    return values


def position_titles_for_scope(db: Session, role_scope: str) -> list[str]:
    normalized_scope = resolve_scope_slug(role_scope)
    if normalized_scope == ROLE_SCOPE_ALL:
        return []
    positions = db.query(Position).filter(Position.slug == normalized_scope).all()
    titles = [position.title for position in positions if (position.title or "").strip()]
    legacy_title = canonical_position_title(normalized_scope)
    if legacy_title and legacy_title not in titles:
        titles.append(legacy_title)
    return titles


def resolve_scope_slug(value: str) -> str:
    normalized = normalize_position_slug(value)
    return normalized or ROLE_SCOPE_ALL


def position_matches_scope(employee_position: Optional[str], role_scope: Optional[str]) -> bool:
    normalized_scope = resolve_scope_slug(role_scope or "")
    if normalized_scope == ROLE_SCOPE_ALL:
        return True
    normalized_employee_scope = normalize_position_slug(employee_position or "")
    return bool(normalized_employee_scope) and normalized_employee_scope == normalized_scope


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
    return position


def resolve_employee_position_value(db: Session, value: str) -> Optional[str]:
    normalized_value = (value or "").strip()
    if not normalized_value:
        return None

    if normalized_value.isdigit():
        position = db.get(Position, int(normalized_value))
        if position is not None:
            return position.title

    normalized_slug = normalize_position_slug(normalized_value)
    if normalized_slug:
        position = db.query(Position).filter(Position.slug == normalized_slug).first()
        if position is not None:
            return position.title

    position = (
        db.query(Position)
        .filter(func.lower(Position.title) == normalized_value.lower())
        .first()
    )
    if position is not None:
        return position.title

    ensure_position_exists(db, title=normalized_value, slug=normalized_slug or None)
    return canonical_position_title(normalized_value)


def seed_positions_catalog() -> None:
    with SessionLocal() as db:
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

        distinct_titles = [
            (row[0] or "").strip()
            for row in db.query(Employee.desired_position).distinct().all()
            if (row[0] or "").strip()
        ]
        for index, title in enumerate(distinct_titles, start=1):
            slug = normalize_position_slug(title)
            existing = db.query(Position).filter(Position.slug == slug).first() if slug else None
            if existing is None:
                ensure_position_exists(db, title=title, slug=slug or None, sort_order=1000 + index)
                changed = True

        if changed:
            db.commit()
        else:
            db.rollback()
