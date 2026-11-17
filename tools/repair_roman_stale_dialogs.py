"""One-time stage repair for the four reviewed stale dialogs of employee 44."""
import argparse
from contextlib import closing
from datetime import UTC, datetime
import json
from pathlib import Path
import sqlite3

EMPLOYEE_ID = 44
EXPECTED = {
    30: (44, "custom_scenario_bf4b01738d2c", "first_week_info_copy_35_1", "2026-08-07 20:59:28.440715"),
    102: (None, "custom_scenario_2f969c06b126", "scenario_6c14bc1720c2_step_1781188475_copy_48_1", "2026-09-25 20:59:36.476201"),
    103: (44, "custom_scenario_354a56ecf27a", "scenario_e77a50f331d4_step_1783414191_copy_49_1", "2026-09-25 20:59:36.483371"),
    104: (44, "custom_scenario_7f1b82a5166d", "scenario_6c14bc1720c2_step_1781188475_copy_48_1_copy_52_1", "2026-09-25 20:59:36.498326"),
}


def preview(db):
    rows = db.execute("""
        SELECT id, employee_id, recipient_employee_id, scenario_key, current_step_key, updated_at,
            started_at, answer_run_id, feedback_run_id, survey_launch_id, adaptation_plan_item_id,
            is_completed, waiting_for_response, interrupted_at
        FROM scenario_progress
        WHERE (employee_id = ? OR recipient_employee_id = ?) AND is_completed = 0 AND interrupted_at IS NULL
        ORDER BY id
    """, (EMPLOYEE_ID, EMPLOYEE_ID)).fetchall()
    if [r["id"] for r in rows] != list(EXPECTED):
        raise ValueError("Active dialog IDs have changed; refusing repair")
    for row in rows:
        observed = tuple(row[key] for key in ("recipient_employee_id", "scenario_key", "current_step_key", "updated_at"))
        if (row["employee_id"] != EMPLOYEE_ID or observed != EXPECTED[row["id"]]
                or any(row[key] is not None for key in ("adaptation_plan_item_id", "feedback_run_id", "survey_launch_id"))
                or row["waiting_for_response"]):
            raise ValueError("Dialog snapshot changed; refusing repair")
        if db.execute("""SELECT 1 FROM scenario_step_deliveries WHERE progress_id=?
                         AND status IN ('pending','starting') LIMIT 1""", (row["id"],)).fetchone():
            raise ValueError("Dialog has a pending or claimed step; refusing repair")
        if db.execute("""SELECT 1 FROM flow_launch_requests WHERE employee_id=? AND flow_key=?
                         AND processed_at IS NULL AND skip_step_key IS NOT NULL LIMIT 1""",
                      (EMPLOYEE_ID, row["scenario_key"])).fetchone():
            raise ValueError("Dialog has a queued continuation; refusing repair")
    return [dict(row) for row in rows]


def repair(path, apply=False):
    path = Path(path).resolve()
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as source:
        source.row_factory = sqlite3.Row
        plan = preview(source)
        if not apply:
            return {"mode": "dry_run", "employee_id": EMPLOYEE_ID, "dialog_ids": list(EXPECTED)}
        backup_dir = path.parent / "backups"
        backup_dir.mkdir(exist_ok=True)
        backup = backup_dir / f"hr_bot.before-roman-repair.{datetime.now(UTC):%Y%m%d-%H%M%S-%f}.db"
        backup.touch(mode=0o600, exist_ok=False)
        with closing(sqlite3.connect(backup)) as target:
            source.backup(target)
            if target.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise ValueError("Backup verification failed")
    with closing(sqlite3.connect(path.as_uri() + "?mode=rw", uri=True, timeout=15)) as db:
        db.row_factory = sqlite3.Row
        with db:
            db.execute("BEGIN IMMEDIATE")
            if preview(db) != plan:
                raise ValueError("Runtime changed after backup; refusing repair")
            now = datetime.now(UTC).replace(tzinfo=None).isoformat(sep=" ")
            for row in plan:
                db.execute("""UPDATE scenario_progress SET interrupted_at=?, completed_at=?, updated_at=?,
                    is_completed=1, waiting_for_response=0, pending_confirmation_value=NULL,
                    pending_confirmation_option_index=NULL, pending_confirmation_message_id=NULL WHERE id=?""",
                           (now, now, now, row["id"]))
                if row["answer_run_id"]:
                    db.execute("UPDATE scenario_answer_runs SET status='interrupted' WHERE id=? AND status='in_progress'",
                               (row["answer_run_id"],))
            db.execute("""INSERT INTO onboarding_events (employee_id,event_key,scheduled_at,sent_at,message)
                VALUES (?,'scenario_queue_action',?,?,?)""", (EMPLOYEE_ID, now, now,
                "Approved stage cleanup: interrupted stale dialogs #30/#102/#103/#104; answers preserved."))
    return {"mode": "applied", "employee_id": EMPLOYEE_ID, "dialog_ids": list(EXPECTED), "backup": str(backup)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(repair(args.db, args.apply)))
