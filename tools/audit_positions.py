"""Read-only audit of employee position values and catalog drift."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any

# Allow direct `python tools/audit_positions.py` execution from any checkout.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.positions import CANONICAL_POSITION_TITLES, normalize_position_slug


def _canonical_by_key() -> dict[str, str]:
    return {normalize_position_slug(title): title for title in CANONICAL_POSITION_TITLES}


def _proposed_mapping(value: str, canonical_by_key: dict[str, str]) -> tuple[str | None, str]:
    stripped = value.strip()
    if not stripped:
        return None, "empty"
    exact = next((title for title in CANONICAL_POSITION_TITLES if title.casefold() == stripped.casefold()), None)
    if exact:
        return exact, "already canonical"
    normalized = normalize_position_slug(stripped)
    canonical = canonical_by_key.get(normalized)
    if canonical:
        return canonical, "case/format normalization"
    return None, "requires explicit review; no unambiguous canonical match"


def _connect_read_only(database: Path) -> sqlite3.Connection:
    if not database.is_file():
        raise SystemExit(f"Database file does not exist: {database}")
    return sqlite3.connect(f"file:{database.resolve()}?mode=ro", uri=True)


def build_report(database: Path) -> dict[str, Any]:
    canonical_by_key = _canonical_by_key()
    connection = _connect_read_only(database)
    try:
        employee_rows = connection.execute(
            """
            SELECT COALESCE(TRIM(desired_position), ''), COUNT(*)
            FROM employees
            GROUP BY COALESCE(TRIM(desired_position), '')
            ORDER BY COUNT(*) DESC, COALESCE(TRIM(desired_position), '') COLLATE NOCASE
            """
        ).fetchall()
        catalog_rows = connection.execute(
            """
            SELECT id, title, slug, is_active, sort_order
            FROM positions
            ORDER BY sort_order, id
            """
        ).fetchall()
    finally:
        connection.close()

    employee_values = []
    for value, count in employee_rows:
        proposed, reason = _proposed_mapping(value, canonical_by_key)
        employee_values.append(
            {
                "existing_value": value,
                "usage_count": count,
                "proposed_mapping": proposed,
                "decision": reason,
            }
        )

    title_counts = Counter((str(row[1] or "").strip().casefold() for row in catalog_rows if str(row[1] or "").strip()))
    catalog = [
        {
            "id": row[0],
            "title": row[1],
            "slug": row[2],
            "is_active": bool(row[3]),
            "sort_order": row[4],
            "duplicate_title_count": title_counts[str(row[1] or "").strip().casefold()],
        }
        for row in catalog_rows
    ]
    return {
        "database": str(database),
        "read_only": True,
        "canonical_positions": list(CANONICAL_POSITION_TITLES),
        "employee_values": employee_values,
        "catalog_rows": catalog,
        "catalog_duplicate_titles": sorted(
            title for title, count in title_counts.items() if count > 1
        ),
    }


def _print_text(report: dict[str, Any]) -> None:
    print(f"Database: {report['database']} (read-only)")
    print("Employee values:")
    for item in report["employee_values"]:
        proposed = item["proposed_mapping"] or "<requires explicit review>"
        print(f"- {item['existing_value'] or '<empty>'}: {item['usage_count']} -> {proposed} [{item['decision']}]")
    print("Catalog rows:")
    for item in report["catalog_rows"]:
        state = "active" if item["is_active"] else "inactive"
        duplicate = f", duplicate title x{item['duplicate_title_count']}" if item["duplicate_title_count"] > 1 else ""
        print(f"- #{item['id']} {item['title']} ({item['slug']}, {state}{duplicate})")
    if report["catalog_duplicate_titles"]:
        print("Duplicate catalog titles: " + ", ".join(report["catalog_duplicate_titles"]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True, help="SQLite database file")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args()
    report = build_report(args.db)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_text(report)


if __name__ == "__main__":
    main()
