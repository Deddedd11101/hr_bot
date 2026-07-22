from __future__ import annotations

import argparse
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CYRILLIC_TRANSLIT = {
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

LEGACY_SCOPE_ALIASES = {
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

LEGACY_SCOPE_TITLES = {
    "designer": "Дизайнер",
    "project_manager": "Project manager",
    "analyst": "Аналитик",
}

EMPLOYEE_DEFAULTS: dict[str, Any] = {
    "telegram_user_id": None,
    "current_menu_set_id": None,
    "current_menu_path": None,
    "first_workday": None,
    "birth_date": None,
    "is_flow_scheduled": 0,
    "is_bot_blocked": 0,
    "work_hours": None,
    "is_manager": 0,
    "is_mentor": 0,
    "profile_photo_path": None,
    "profile_photo_filename": None,
    "salary_expectation": None,
    "candidate_status": None,
    "candidate_work_stage": None,
    "employee_stage": "staff",
    "manager_employee_id": None,
    "mentor_adaptation_employee_id": None,
    "mentor_ipr_employee_id": None,
    "manager_telegram_id": None,
    "mentor_adaptation_telegram_id": None,
    "mentor_ipr_telegram_id": None,
    "adaptation_tasks_url": None,
    "adaptation_feedback_url": None,
    "adaptation_midpoint": None,
    "adaptation_end": None,
    "personal_data_consent": 0,
    "employee_data_consent": 0,
    "test_task_link": None,
    "test_task_due_at": None,
    "notes": None,
}


def transliterate(value: str) -> str:
    return "".join(CYRILLIC_TRANSLIT.get(char, char) for char in value.lower())


def normalize_position_slug(value: str) -> str:
    normalized = (value or "").strip().lower()
    if not normalized:
        return ""
    alias = LEGACY_SCOPE_ALIASES.get(normalized)
    if alias:
        return alias
    return re.sub(r"[^a-z0-9]+", "_", transliterate(normalized)).strip("_")[:128]


def canonical_position_title(value: str) -> str:
    slug = normalize_position_slug(value)
    return LEGACY_SCOPE_TITLES.get(slug, (value or "").strip())


def normalize_email(value: str) -> str:
    return (value or "").strip().lower()


def normalize_username(value: str) -> tuple[str, str | None]:
    normalized = (value or "").strip().lstrip("@")
    if not normalized:
        return "", None
    if not re.fullmatch(r"[A-Za-z0-9_]{5,32}", normalized):
        return "", f"invalid telegram_username skipped: {value}"
    return normalized, None


def load_records(path: Path) -> list[dict[str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = payload.get("employees", payload if isinstance(payload, list) else [])
    if not isinstance(records, list):
        raise SystemExit("Payload must be a list or an object with employees list.")
    result: list[dict[str, str]] = []
    for index, row in enumerate(records, start=1):
        if not isinstance(row, dict):
            raise SystemExit(f"Employee row #{index} is not an object.")
        item = {
            "full_name": str(row.get("full_name") or "").strip(),
            "telegram_username": str(row.get("telegram_username") or "").strip(),
            "work_email": str(row.get("work_email") or "").strip(),
            "desired_position": str(row.get("desired_position") or "").strip(),
            "_source_row": str(row.get("_row") or index),
        }
        if any(item[key] for key in ("full_name", "telegram_username", "work_email", "desired_position")):
            result.append(item)
    return result


def table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in connection.execute(f'PRAGMA table_info("{table}")').fetchall()}


def ensure_position(
    connection: sqlite3.Connection,
    *,
    title: str,
    sort_order: int | None,
    dry_run: bool,
) -> tuple[str, bool]:
    canonical_title = canonical_position_title(title)
    slug = normalize_position_slug(canonical_title)
    if not canonical_title or not slug:
        raise SystemExit(f"Invalid position title: {title!r}")

    row = connection.execute(
        "SELECT id, title, is_active, sort_order FROM positions WHERE slug = ? OR lower(title) = lower(?) ORDER BY id LIMIT 1",
        (slug, canonical_title),
    ).fetchone()
    if row:
        position_id, current_title, is_active, current_sort_order = row
        updates: dict[str, Any] = {}
        if current_title != canonical_title:
            updates["title"] = canonical_title
        if not is_active:
            updates["is_active"] = 1
        if sort_order is not None and current_sort_order != sort_order:
            updates["sort_order"] = sort_order
        if updates and not dry_run:
            assignments = ", ".join(f"{column} = ?" for column in updates)
            connection.execute(
                f"UPDATE positions SET {assignments} WHERE id = ?",
                (*updates.values(), position_id),
            )
        return canonical_title, False

    if sort_order is None:
        max_sort_order = connection.execute("SELECT max(sort_order) FROM positions").fetchone()[0]
        sort_order = int(max_sort_order or 0) + 10
    if not dry_run:
        connection.execute(
            "INSERT INTO positions (title, slug, is_active, sort_order, created_at) VALUES (?, ?, 1, ?, ?)",
            (canonical_title, slug, sort_order, datetime.now(timezone.utc).replace(tzinfo=None).isoformat(sep=" ")),
        )
    return canonical_title, True


def find_employee(connection: sqlite3.Connection, *, email: str, username: str, full_name: str) -> tuple[int, str] | None:
    if email:
        row = connection.execute(
            "SELECT id FROM employees WHERE lower(coalesce(work_email, '')) = lower(?) ORDER BY id LIMIT 1",
            (email,),
        ).fetchone()
        if row:
            return int(row[0]), "work_email"
    if username:
        row = connection.execute(
            "SELECT id FROM employees WHERE lower(trim(replace(coalesce(telegram_username, ''), '@', ''))) = lower(?) ORDER BY id LIMIT 1",
            (username,),
        ).fetchone()
        if row:
            return int(row[0]), "telegram_username"
    if full_name:
        row = connection.execute(
            "SELECT id FROM employees WHERE lower(trim(coalesce(full_name, ''))) = lower(?) ORDER BY id LIMIT 1",
            (full_name,),
        ).fetchone()
        if row:
            return int(row[0]), "full_name"
    return None


def upsert_employee(
    connection: sqlite3.Connection,
    *,
    columns: set[str],
    record: dict[str, str],
    dry_run: bool,
) -> tuple[str, str | None]:
    full_name = record["full_name"]
    email = normalize_email(record["work_email"])
    username, warning = normalize_username(record["telegram_username"])
    position = canonical_position_title(record["desired_position"])
    if not full_name:
        raise SystemExit(f"Row {record['_source_row']}: full_name is required.")
    if not position:
        raise SystemExit(f"Row {record['_source_row']}: desired_position is required.")

    existing = find_employee(connection, email=email, username=username, full_name=full_name)
    update_values = {
        "full_name": full_name,
        "telegram_username": username or None,
        "work_email": email or None,
        "desired_position": position,
        "employee_stage": "staff",
        "candidate_work_stage": None,
    }
    if existing:
        employee_id, matched_by = existing
        writable = {key: value for key, value in update_values.items() if key in columns}
        if not dry_run:
            assignments = ", ".join(f"{column} = ?" for column in writable)
            connection.execute(
                f"UPDATE employees SET {assignments} WHERE id = ?",
                (*writable.values(), employee_id),
            )
        return f"updated employee #{employee_id} by {matched_by}: {full_name}", warning

    values: dict[str, Any] = dict(EMPLOYEE_DEFAULTS)
    values.update(update_values)
    values["created_at"] = datetime.now(timezone.utc).replace(tzinfo=None).isoformat(sep=" ")
    insert_values = {key: value for key, value in values.items() if key in columns}
    if not dry_run:
        column_names = list(insert_values)
        placeholders = ", ".join("?" for _ in column_names)
        connection.execute(
            f"INSERT INTO employees ({', '.join(column_names)}) VALUES ({placeholders})",
            tuple(insert_values[column] for column in column_names),
        )
    return f"created employee: {full_name}", warning


def run(database_path: Path, input_path: Path, *, dry_run: bool) -> dict[str, Any]:
    records = load_records(input_path)
    if not records:
        raise SystemExit("No employee records found.")

    connection = sqlite3.connect(database_path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        employee_columns = table_columns(connection, "employees")
        position_columns = table_columns(connection, "positions")
        required_position_columns = {"title", "slug", "is_active", "sort_order", "created_at"}
        if not required_position_columns <= position_columns:
            missing = sorted(required_position_columns - position_columns)
            raise SystemExit(f"positions table is missing columns: {missing}")

        position_titles = []
        created_positions = []
        seen_positions = set()
        for record in records:
            title = canonical_position_title(record["desired_position"])
            if title and title.lower() not in seen_positions:
                seen_positions.add(title.lower())
                position_titles.append(title)
        for index, title in enumerate(sorted(position_titles, key=str.lower), start=1):
            canonical_title, created = ensure_position(
                connection,
                title=title,
                sort_order=index * 10,
                dry_run=dry_run,
            )
            if created:
                created_positions.append(canonical_title)

        actions = []
        warnings = []
        for record in records:
            action, warning = upsert_employee(
                connection,
                columns=employee_columns,
                record=record,
                dry_run=dry_run,
            )
            actions.append(action)
            if warning:
                warnings.append({"row": record["_source_row"], "full_name": record["full_name"], "warning": warning})

        if dry_run:
            connection.rollback()
        else:
            connection.commit()

        return {
            "mode": "dry_run" if dry_run else "import",
            "employees_seen": len(records),
            "positions_seen": len(position_titles),
            "positions_created": created_positions,
            "employees_created": sum(1 for action in actions if action.startswith("created ")),
            "employees_updated": sum(1 for action in actions if action.startswith("updated ")),
            "warnings": warnings,
            "actions": actions,
        }
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Import staff employees into stage SQLite database.")
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--mode", choices=("dry_run", "import"), default="dry_run")
    args = parser.parse_args()
    summary = run(args.db, args.input, dry_run=args.mode == "dry_run")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
