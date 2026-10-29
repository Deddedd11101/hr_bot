"""Preview catalog/runtime/SQL position matching without writes or personal names."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sqlite3
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models import Employee, Position, ScenarioTemplate
from app.positions import canonical_position_title, parse_role_scopes, position_matches_scope, position_title_key


def build_report(database: Path) -> dict:
    if not database.is_file():
        raise ValueError("Database must be an existing local file")
    uri = database.resolve().as_uri() + "?mode=ro"
    engine = create_engine("sqlite://", creator=lambda: sqlite3.connect(uri, uri=True))
    try:
        with Session(engine) as db:
            catalog = list(db.query(Position))
            employees = list(db.query(Employee.id, Employee.desired_position, Employee.employee_stage, Employee.is_bot_blocked))
            titles = Counter(employee.desired_position or "" for employee in employees)
            duplicates = [title for title, count in Counter(position_title_key(row.title) for row in catalog).items() if count > 1]
            changes = []
            for scenario in db.query(ScenarioTemplate):
                scopes = parse_role_scopes(scenario.role_scope)
                if not scopes:
                    continue
                old_sql_titles = {row.title for row in catalog if row.slug in scopes}
                old_sql_titles.update(canonical_position_title(scope) for scope in scopes)
                eligible = [employee for employee in employees if not employee.is_bot_blocked
                            and (not scenario.target_employee_id or scenario.target_employee_id == employee.id)
                            and (scenario.employee_scope != "candidates" or employee.employee_stage == "candidate")
                            and (scenario.employee_scope != "employees" or employee.employee_stage != "candidate")]
                old_runtime = {row.id for row in eligible if position_matches_scope(row.desired_position, scenario.role_scope)}
                old_sql = {row.id for row in eligible if row.desired_position in old_sql_titles}
                unified = {row.id for row in eligible if position_matches_scope(row.desired_position, scenario.role_scope, db=db)}
                if old_runtime != unified or old_sql != unified:
                    changes.append({"scenario_id": scenario.id, "scenario_key": scenario.scenario_key,
                                    "role_scope": scenario.role_scope,
                                    "old_runtime_ids": sorted(old_runtime), "old_role_sql_ids": sorted(old_sql),
                                    "unified_ids": sorted(unified)})
            return {"read_only": True, "position_count": len(catalog),
                    "inactive_count": sum(not row.is_active for row in catalog),
                    "duplicate_title_keys": duplicates,
                    "employee_position_counts": dict(sorted(titles.items())),
                    "role_matching_changes": changes,
                    "scope": "Position matching only; not a trigger, permission, or delivery simulation"}
    finally:
        engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build_report(args.db), ensure_ascii=False, indent=2))
