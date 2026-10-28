"""Plan or explicitly apply agreed employee position replacements.

The default mode is read-only. Apply mode creates a SQLite backup before the
transaction and updates only exact employee values named in the mapping.
Scenario and bulk-target role scopes are included only with --update-scopes.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow direct `python tools/replace_positions.py` execution from any checkout.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.positions import CANONICAL_POSITION_TITLES, normalize_position_slug


def _parse_mapping(values: list[str], mapping_file: Path | None) -> dict[str, str]:
    mapping: dict[str, str] = {}
    if mapping_file:
        loaded = json.loads(mapping_file.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise SystemExit("Mapping file must contain a JSON object: old value -> new value")
        mapping.update({str(key): str(value) for key, value in loaded.items()})
    for value in values:
        if "=" not in value:
            raise SystemExit(f"Invalid --mapping {value!r}; expected OLD=NEW")
        old, new = value.split("=", 1)
        mapping[old] = new
    cleaned = {old.strip(): new.strip() for old, new in mapping.items() if old.strip()}
    if not cleaned or any(not new for new in cleaned.values()):
        raise SystemExit("At least one non-empty OLD=NEW mapping is required")
    return cleaned


def _connect(database: Path) -> sqlite3.Connection:
    if not database.is_file():
        raise SystemExit(f"Database file does not exist: {database}")
    return sqlite3.connect(database)


def _backup_database(database: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup_path = backup_dir / f"{database.stem}.before-position-replace.{timestamp}.db"
    source = sqlite3.connect(database)
    target = sqlite3.connect(backup_path)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    return backup_path


def _scope_replacement(value: str | None, mapping: dict[str, str]) -> str | None:
    if not value or value.strip().lower() == "all":
        return value
    replacements = {
        normalize_position_slug(old): normalize_position_slug(new)
        for old, new in mapping.items()
        if normalize_position_slug(old) and normalize_position_slug(new)
    }
    parts = []
    for item in value.split(","):
        slug = normalize_position_slug(item)
        parts.append(replacements.get(slug, slug))
    result = []
    for item in parts:
        if item and item not in result:
            result.append(item)
    return ",".join(result) if result else "all"


def _plan(connection: sqlite3.Connection, mapping: dict[str, str], update_scopes: bool) -> dict[str, int]:
    employee_changes = 0
    for old, new in mapping.items():
        count = connection.execute(
            "SELECT COUNT(*) FROM employees WHERE desired_position = ?", (old,)
        ).fetchone()[0]
        employee_changes += count
        print(f"employees.desired_position: {old!r} -> {new!r}: {count} row(s)")

    scope_changes = 0
    if update_scopes:
        for table, column in (
            ("scenario_templates", "role_scope"),
            ("bot_menu_sets", "role_scope"),
            ("mass_scenario_actions", "target_role_scope"),
            ("mass_message_actions", "target_role_scope"),
        ):
            try:
                rows = connection.execute(f"SELECT id, {column} FROM {table}").fetchall()
            except sqlite3.OperationalError:
                continue
            for row_id, value in rows:
                replacement = _scope_replacement(value, mapping)
                if replacement != value:
                    scope_changes += 1
                    print(f"{table}.{column} #{row_id}: {value!r} -> {replacement!r}")
    return {"employee_changes": employee_changes, "scope_changes": scope_changes}


def _apply(connection: sqlite3.Connection, mapping: dict[str, str], update_scopes: bool) -> None:
    for old, new in mapping.items():
        connection.execute(
            "UPDATE employees SET desired_position = ? WHERE desired_position = ?", (new, old)
        )
    if update_scopes:
        for table, column in (
            ("scenario_templates", "role_scope"),
            ("bot_menu_sets", "role_scope"),
            ("mass_scenario_actions", "target_role_scope"),
            ("mass_message_actions", "target_role_scope"),
        ):
            try:
                rows = connection.execute(f"SELECT id, {column} FROM {table}").fetchall()
            except sqlite3.OperationalError:
                continue
            for row_id, value in rows:
                replacement = _scope_replacement(value, mapping)
                if replacement != value:
                    connection.execute(f"UPDATE {table} SET {column} = ? WHERE id = ?", (replacement, row_id))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True, help="SQLite database file")
    parser.add_argument("--mapping", action="append", default=[], help="Exact OLD=NEW replacement; repeatable")
    parser.add_argument("--mapping-file", type=Path, help="JSON object with exact OLD: NEW replacements")
    parser.add_argument("--update-scopes", action="store_true", help="Also replace matching role-scope slugs")
    parser.add_argument("--apply", action="store_true", help="Create backup and apply the dry-run plan")
    parser.add_argument("--backup-dir", type=Path, help="Required with --apply")
    args = parser.parse_args()

    mapping = _parse_mapping(args.mapping, args.mapping_file)
    canonical = {title.casefold() for title in CANONICAL_POSITION_TITLES}
    invalid_targets = [new for new in mapping.values() if new.casefold() not in canonical]
    if invalid_targets:
        raise SystemExit("Replacement targets must be canonical catalog titles: " + ", ".join(invalid_targets))

    if args.apply and not args.backup_dir:
        raise SystemExit("--apply requires --backup-dir")
    if args.apply:
        backup_path = _backup_database(args.db, args.backup_dir)
        print(f"Backup created: {backup_path}")

    connection = _connect(args.db)
    try:
        plan = _plan(connection, mapping, args.update_scopes)
        print(f"Plan: {plan['employee_changes']} employee row(s), {plan['scope_changes']} scope row(s)")
        if args.apply:
            _apply(connection, mapping, args.update_scopes)
            connection.commit()
            print("Applied successfully")
        else:
            print("Dry-run only; database was not modified")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
