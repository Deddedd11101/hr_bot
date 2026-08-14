"""Read-only audit for scenario delivery state in a SQLite database."""

from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit scenario/message delivery state without modifying the database."
    )
    parser.add_argument("--db", required=True, type=Path, help="Path to SQLite DB copy")
    parser.add_argument(
        "--stale-minutes",
        type=int,
        default=60,
        help="Age threshold for stale pending flow_launch_requests",
    )
    parser.add_argument(
        "--recent-minutes",
        type=int,
        default=10,
        help="Window for repeated onboarding_events with the same employee/event_key",
    )
    parser.add_argument("--limit", type=int, default=50, help="Rows to print per section")
    return parser.parse_args()


def connect_read_only(db_path: Path) -> sqlite3.Connection:
    resolved = db_path.resolve()
    if not resolved.exists():
        raise SystemExit(f"DB file not found: {resolved}")
    conn = sqlite3.connect(f"file:{resolved.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    return conn


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "select 1 from sqlite_master where type = 'table' and name = ?", (table,)
    ).fetchone()
    return row is not None


def columns(conn: sqlite3.Connection, table: str) -> set[str]:
    if not table_exists(conn, table):
        return set()
    return {row["name"] for row in conn.execute(f"pragma table_info({table})")}


def can_run(conn: sqlite3.Connection, table: str, required: set[str]) -> tuple[bool, str]:
    if not table_exists(conn, table):
        return False, f"skip: missing table {table}"
    missing = sorted(required - columns(conn, table))
    if missing:
        return False, f"skip: {table} missing columns {', '.join(missing)}"
    return True, ""


def print_rows(title: str, rows: list[sqlite3.Row], limit: int) -> None:
    print(f"\n## {title}")
    print(f"rows: {len(rows)}")
    if not rows:
        return
    names = rows[0].keys()
    for row in rows[:limit]:
        parts = [f"{name}={row[name]!r}" for name in names]
        print("- " + ", ".join(parts))
    if len(rows) > limit:
        print(f"... truncated, printed {limit} of {len(rows)}")


def fetch_all(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
    return list(conn.execute(sql, params))


def audit_multiple_waiting(conn: sqlite3.Connection, limit: int) -> None:
    ok, reason = can_run(
        conn,
        "scenario_progress",
        {
            "id",
            "employee_id",
            "scenario_key",
            "current_step_key",
            "waiting_for_response",
            "is_completed",
            "updated_at",
        },
    )
    if not ok:
        print(f"\n## Multiple active waiting progress\n{reason}")
        return
    recipient_expr = (
        "coalesce(recipient_employee_id, employee_id)"
        if "recipient_employee_id" in columns(conn, "scenario_progress")
        else "employee_id"
    )
    rows = fetch_all(
        conn,
        f"""
        with active_waiting as (
            select id, employee_id, scenario_key, current_step_key, updated_at,
                   {recipient_expr} as effective_recipient_id
            from scenario_progress
            where waiting_for_response = 1
              and is_completed = 0
        ),
        grouped as (
            select effective_recipient_id, count(*) as cnt
            from active_waiting
            group by effective_recipient_id
            having count(*) > 1
        )
        select g.effective_recipient_id, g.cnt,
               aw.id as progress_id, aw.employee_id, aw.scenario_key,
               aw.current_step_key, aw.updated_at
        from grouped g
        join active_waiting aw on aw.effective_recipient_id = g.effective_recipient_id
        order by g.cnt desc, g.effective_recipient_id, aw.updated_at desc
        """
    )
    print_rows("Multiple active waiting progress per effective recipient", rows, limit)

    if "recipient_chat_id" not in columns(conn, "scenario_progress"):
        return
    chat_rows = fetch_all(
        conn,
        """
        with active_waiting as (
            select id, employee_id, scenario_key, current_step_key, updated_at,
                   recipient_mode, recipient_employee_id, recipient_chat_id
            from scenario_progress
            where waiting_for_response = 1
              and is_completed = 0
              and coalesce(recipient_chat_id, '') <> ''
        ),
        grouped as (
            select recipient_chat_id, count(*) as cnt
            from active_waiting
            group by recipient_chat_id
            having count(*) > 1
        )
        select g.recipient_chat_id, g.cnt,
               aw.id as progress_id, aw.employee_id, aw.scenario_key,
               aw.current_step_key, aw.recipient_mode, aw.recipient_employee_id,
               aw.updated_at
        from grouped g
        join active_waiting aw on aw.recipient_chat_id = g.recipient_chat_id
        order by g.cnt desc, g.recipient_chat_id, aw.updated_at desc
        """
    )
    print_rows("Multiple active waiting progress per recipient_chat_id", chat_rows, limit)


def audit_flow_requests(conn: sqlite3.Connection, stale_minutes: int, limit: int) -> None:
    ok, reason = can_run(
        conn,
        "flow_launch_requests",
        {"id", "employee_id", "flow_key", "requested_at", "processed_at", "skip_step_key"},
    )
    if not ok:
        print(f"\n## FlowLaunchRequest pending/stale/duplicates\n{reason}")
        return
    threshold = (datetime.now(timezone.utc) - timedelta(minutes=stale_minutes)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    stale_rows = fetch_all(
        conn,
        """
        select id, employee_id, flow_key, launch_type, requested_at, skip_step_key
        from flow_launch_requests
        where processed_at is null
          and requested_at <= ?
        order by requested_at asc, id asc
        """,
        (threshold,),
    )
    print_rows(f"Pending flow_launch_requests older than {stale_minutes} minutes", stale_rows, limit)

    dup_rows = fetch_all(
        conn,
        """
        select employee_id, flow_key, coalesce(skip_step_key, '') as skip_step_key,
               count(*) as cnt, group_concat(id) as request_ids,
               min(requested_at) as first_requested_at,
               max(requested_at) as last_requested_at
        from flow_launch_requests
        where processed_at is null
        group by employee_id, flow_key, coalesce(skip_step_key, '')
        having count(*) > 1
        order by cnt desc, last_requested_at desc
        """,
    )
    print_rows("Duplicate pending flow_launch_requests by employee/flow/skip_step", dup_rows, limit)


def audit_missing_steps(conn: sqlite3.Connection, limit: int) -> None:
    ok_progress, reason_progress = can_run(
        conn,
        "scenario_progress",
        {"id", "employee_id", "scenario_key", "current_step_key", "is_completed"},
    )
    ok_steps, reason_steps = can_run(
        conn, "flow_step_templates", {"id", "flow_key", "step_key"}
    )
    if not ok_progress or not ok_steps:
        print("\n## Progress current_step_key missing from templates")
        print(reason_progress if not ok_progress else reason_steps)
        return
    rows = fetch_all(
        conn,
        """
        select p.id as progress_id, p.employee_id, p.scenario_key, p.current_step_key,
               p.is_completed, p.updated_at
        from scenario_progress p
        left join flow_step_templates s
          on s.flow_key = p.scenario_key
         and s.step_key = p.current_step_key
        where coalesce(p.current_step_key, '') <> ''
          and s.id is null
        order by p.updated_at desc, p.id desc
        """,
    )
    print_rows("Progress current_step_key missing from templates", rows, limit)


def audit_repeated_events(conn: sqlite3.Connection, recent_minutes: int, limit: int) -> None:
    ok, reason = can_run(
        conn, "onboarding_events", {"id", "employee_id", "event_key", "sent_at"}
    )
    if not ok:
        print(f"\n## Repeated onboarding_events\n{reason}")
        return
    rows = fetch_all(
        conn,
        """
        with ordered as (
            select id, employee_id, event_key, sent_at,
                   lag(id) over (
                       partition by employee_id, event_key
                       order by sent_at, id
                   ) as previous_id,
                   lag(sent_at) over (
                       partition by employee_id, event_key
                       order by sent_at, id
                   ) as previous_sent_at
            from onboarding_events
            where sent_at is not null
        )
        select id, previous_id, employee_id, event_key, previous_sent_at, sent_at,
               round((julianday(sent_at) - julianday(previous_sent_at)) * 24 * 60, 2)
                   as minutes_between
        from ordered
        where previous_sent_at is not null
          and (julianday(sent_at) - julianday(previous_sent_at)) * 24 * 60 between 0 and ?
        order by sent_at desc, id desc
        """,
        (recent_minutes,),
    )
    print_rows(f"Repeated onboarding_events within {recent_minutes} minutes", rows, limit)


def audit_duplicate_step_keys(conn: sqlite3.Connection, limit: int) -> None:
    ok, reason = can_run(conn, "flow_step_templates", {"flow_key", "step_key"})
    if not ok:
        print(f"\n## Step keys reused across scenarios\n{reason}")
        return
    rows = fetch_all(
        conn,
        """
        select step_key, count(distinct flow_key) as scenario_count,
               count(*) as step_count,
               group_concat(distinct flow_key) as flow_keys
        from flow_step_templates
        where coalesce(step_key, '') <> ''
        group by step_key
        having count(distinct flow_key) > 1
        order by scenario_count desc, step_count desc, step_key
        """,
    )
    print_rows("Step keys reused across scenarios", rows, limit)


def main() -> None:
    args = parse_args()
    conn = connect_read_only(args.db)
    try:
        db_path = args.db.resolve()
        print("# Scenario Delivery State Audit")
        print(f"db={db_path}")
        print(f"generated_at_utc={datetime.now(timezone.utc).isoformat(timespec='seconds')}")
        print("mode=read-only sqlite uri + PRAGMA query_only")
        audit_multiple_waiting(conn, args.limit)
        audit_flow_requests(conn, args.stale_minutes, args.limit)
        audit_missing_steps(conn, args.limit)
        audit_repeated_events(conn, args.recent_minutes, args.limit)
        audit_duplicate_step_keys(conn, args.limit)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
