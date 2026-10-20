"""Dry-run first; repair only the reviewed adaptation/Pulse scenario configuration."""

import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3


FIRST_DAY = "scenario_e77a50f331d4"
ORGANIZATION = "scenario_6c14bc1720c2"
PULSE = "scenario_aae666a4c5bc"


def build_plan(db: sqlite3.Connection) -> list[dict]:
    plan = []
    for key in (FIRST_DAY, ORGANIZATION, PULSE):
        rows = db.execute("SELECT scenario_kind FROM scenario_templates WHERE scenario_key=?", (key,)).fetchall()
        if rows != [("scenario",)]:
            raise ValueError(f"Missing or changed scenario: {key}")
    rows = db.execute("SELECT id, step_key FROM flow_step_templates WHERE flow_key=? AND id IN (256,257) ORDER BY id", (FIRST_DAY,)).fetchall()
    old = f"{FIRST_DAY}_step_1783414191"
    new = f"{old}_id257"
    if rows not in ([(256, old), (257, old)], [(256, old), (257, new)]):
        raise ValueError("First-day step keys changed; review before repair")
    if rows[1][1] != new:
        if db.execute("SELECT 1 FROM flow_step_templates WHERE flow_key=? AND step_key=?", (FIRST_DAY, new)).fetchone():
            raise ValueError("Replacement step key already exists")
        plan.append(dict(id=257, flow_key=FIRST_DAY, field="step_key", old=old, new=new))
    row = db.execute("SELECT response_type, target_field FROM flow_step_templates WHERE id=254 AND flow_key=?", (ORGANIZATION,)).fetchone()
    if not row or row[0] != "file" or (row[1] or "") not in {"", "adaptation_tasks_url"}:
        raise ValueError("Plan upload step changed; review before repair")
    if row[1] != "adaptation_tasks_url":
        plan.append(dict(id=254, flow_key=ORGANIZATION, field="target_field", old=row[1], new="adaptation_tasks_url"))
    pulse_steps = db.execute("SELECT id, target_field FROM flow_step_templates WHERE flow_key=? AND response_type IN ('text','buttons','branching','date','file') AND id!=434 ORDER BY id", (PULSE,)).fetchall()
    if len(pulse_steps) < 10:
        raise ValueError("Pulse questions are missing; review before repair")
    for step_id, target in pulse_steps:
        if (target or "") not in {"", "survey_answer"}:
            raise ValueError(f"Pulse step {step_id} already saves another field")
        if target != "survey_answer":
            plan.append(dict(id=step_id, flow_key=PULSE, field="target_field", old=target, new="survey_answer"))
    return plan


def repair(path: Path, *, apply: bool = False, backup: Path | None = None, expected_plan_sha256: str | None = None) -> list[dict]:
    path = path.resolve(strict=True)
    if apply and (backup is None or backup.exists() or not backup.parent.exists()):
        raise ValueError("Apply requires a new --backup path in an existing directory")
    with closing(sqlite3.connect(path.as_uri() + ("?mode=rw" if apply else "?mode=ro"), uri=True)) as db:
        try:
            db.execute("BEGIN IMMEDIATE" if apply else "BEGIN")
            plan = build_plan(db)
            if expected_plan_sha256 is not None:
                actual = hashlib.sha256((json.dumps(plan, indent=2) + "\n").encode("utf-8")).hexdigest()
                if actual != expected_plan_sha256:
                    raise ValueError("Plan changed inside transaction; no changes applied")
            if apply and plan:
                with backup.open("xb"):
                    pass
                with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as source, closing(sqlite3.connect(backup)) as destination:
                    source.backup(destination)
                    if destination.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                        raise ValueError("Backup integrity check failed")
                for item in plan:
                    field = item["field"]
                    if field not in {"step_key", "target_field"}:
                        raise ValueError("Unexpected repair field")
                    result = db.execute(f"UPDATE flow_step_templates SET {field}=? WHERE id=? AND flow_key=? AND {field} IS ?", (item["new"], item["id"], item["flow_key"], item["old"]))
                    if result.rowcount != 1:
                        raise ValueError("Conditional update failed")
                db.commit()
            return plan
        finally:
            if db.in_transaction:
                db.rollback()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--expected-plan-sha256")
    args = parser.parse_args()
    print(json.dumps(repair(args.db, apply=args.apply, backup=args.backup, expected_plan_sha256=args.expected_plan_sha256), indent=2))
