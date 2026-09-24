"""Dry-run by default; repair reviewed answer destinations, never candidate data."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3


# Scenario keys, not database-local IDs. Loom's separate answer needs product review.
REPAIRS = (
    ("scenario_79dff913f06d", "scenario_79dff913f06d_step_1786983499", "text"),
    ("custom_scenario_1a59cad6b7a2", "scenario_79dff913f06d_step_1786983499_copy_45_5", "file"),
    ("custom_scenario_9493d363cba1", "scenario_79dff913f06d_step_1786983499_copy_45_5_copy_46_4", "text"),
)


def repair(db_path: Path, *, apply: bool = False, backup: Path | None = None) -> list[dict]:
    db_path = db_path.resolve(strict=True)
    if apply and (backup is None or backup.resolve() == db_path):
        raise ValueError("Apply requires a separate, new --backup path")
    uri = db_path.as_uri() + ("?mode=rw" if apply else "?mode=ro")
    with closing(sqlite3.connect(uri, uri=True)) as db:
        try:
            db.execute("BEGIN IMMEDIATE" if apply else "BEGIN")
            plan = []
            for flow_key, step_key, expected_response in REPAIRS:
                rows = db.execute(
                    "SELECT response_type, target_field FROM flow_step_templates WHERE flow_key=? AND step_key=?",
                    (flow_key, step_key),
                ).fetchall()
                if len(rows) != 1:
                    raise ValueError(f"Missing or ambiguous step: {flow_key}/{step_key}")
                response, target = rows[0]
                if response != expected_response or target not in {"candidate_file", "test_task_result"}:
                    raise ValueError(f"Configuration changed: {flow_key}/{step_key}; no changes applied")
                plan.append(dict(flow_key=flow_key, step_key=step_key, response_type=response,
                                 old_target=target, new_target="test_task_result", changed=target != "test_task_result"))
            if apply and any(item["changed"] for item in plan):
                # Hold the write lock while taking a consistent SQLite backup via a second reader.
                with backup.open("xb"):
                    pass
                with closing(sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True)) as source:
                    with closing(sqlite3.connect(backup)) as destination:
                        source.backup(destination)
                        if destination.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                            raise ValueError("Backup integrity check failed")
                for item in plan:
                    if item["changed"]:
                        result = db.execute(
                            "UPDATE flow_step_templates SET target_field=? WHERE flow_key=? AND step_key=? AND response_type=? AND target_field=?",
                            (item["new_target"], item["flow_key"], item["step_key"], item["response_type"], item["old_target"]),
                        )
                        if result.rowcount != 1:
                            raise ValueError("Conditional update failed")
                db.commit()
            else:
                db.rollback()
            return plan
        finally:
            if db.in_transaction:
                db.rollback()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup", type=Path)
    args = parser.parse_args()
    print(json.dumps(repair(args.db, apply=args.apply, backup=args.backup), indent=2))


if __name__ == "__main__":
    main()
