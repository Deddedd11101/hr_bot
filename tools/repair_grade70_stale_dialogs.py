"""One-off explicitly approved repair, not a generic timeout policy."""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

EXPECTED = {
    127: ("custom_scenario_26921655a2b4", "mid_info_copy_30_1", "2026-10-14 20:59:05.307106"),
    128: ("custom_scenario_e52d98379e63", "mid_info_copy_30_1_copy_33_1", "2026-10-14 20:59:05.324421"),
}


def preview(db):
    rows = list(db.execute("SELECT * FROM scenario_progress WHERE id IN (127,128) ORDER BY id"))
    if len(rows) != 2:
        raise ValueError("Expected exactly two approved rows")
    for row in rows:
        if ((row["scenario_key"], row["current_step_key"], row["updated_at"]) != EXPECTED[row["id"]]
                or row["employee_id"] != 70 or row["recipient_employee_id"] != 70
                or any(row[key] for key in ("is_completed", "waiting_for_response", "interrupted_at",
                    "feedback_run_id", "survey_launch_id", "adaptation_plan_item_id"))):
            raise ValueError("Runtime snapshot changed; refusing repair")
    return [{"id": r["id"], "scenario_key": r["scenario_key"], "answer_run_id": r["answer_run_id"]} for r in rows]


def repair(path, apply=False):
    path = Path(path).resolve()
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as source:
        source.row_factory = sqlite3.Row
        plan = preview(source)
        if not apply:
            return {"mode": "dry_run", "plan": plan}
        directory = path.parent / "backups"
        directory.mkdir(exist_ok=True)
        backup = directory / f"hr_bot.before-grade70-repair.{datetime.now(timezone.utc):%Y%m%d-%H%M%S-%f}.db"
        with closing(sqlite3.connect(backup)) as target:
            source.backup(target)
            if target.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise ValueError("Backup verification failed")
    with closing(sqlite3.connect(path.as_uri() + "?mode=rw", uri=True, timeout=30)) as db:
        db.row_factory = sqlite3.Row
        try:
            db.execute("BEGIN IMMEDIATE")
            if preview(db) != plan:
                raise ValueError("Runtime changed after backup")
            now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat(sep=" ")
            for item in plan:
                db.execute("""UPDATE scenario_progress SET interrupted_at=?, completed_at=?, updated_at=?,
                    is_completed=1, waiting_for_response=0, pending_confirmation_value=NULL,
                    pending_confirmation_option_index=NULL, pending_confirmation_message_id=NULL WHERE id=?""",
                           (now, now, now, item["id"]))
                if item["answer_run_id"]:
                    db.execute("UPDATE scenario_answer_runs SET status='interrupted' WHERE id=? AND status='in_progress'",
                               (item["answer_run_id"],))
                db.execute("""UPDATE flow_launch_requests SET processed_at=? WHERE employee_id=70
                    AND flow_key=? AND processed_at IS NULL AND skip_step_key IS NOT NULL""",
                           (now, item["scenario_key"]))
            db.execute("""INSERT INTO onboarding_events (employee_id,event_key,scheduled_at,sent_at,message)
                VALUES (70,'scenario_queue_action',?,?,?)""", (now, now,
                "Approved repair: interrupted stale progress #127/#128; answers preserved; grade collection unchanged."))
            db.commit()
        except Exception:
            db.rollback()
            raise
    return {"mode": "applied", "plan": plan, "backup": str(backup)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(repair(args.db, args.apply), ensure_ascii=True))
