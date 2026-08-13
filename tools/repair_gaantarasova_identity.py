from __future__ import annotations

import argparse
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TARGET_EMPLOYEE_ID = 52
ORPHAN_ACCOUNT_ID = 4
CHANNEL = "telegram"
EXTERNAL_USER_ID = "1950649889"
EXTERNAL_USERNAME = "GaAnTarasova"


REQUIRED_COLUMNS = {
    "employees": {
        "id",
        "full_name",
        "telegram_user_id",
        "telegram_username",
        "employee_stage",
        "is_bot_blocked",
    },
    "employee_messenger_accounts": {
        "id",
        "employee_id",
        "channel",
        "external_user_id",
        "external_username",
        "is_primary",
        "is_active",
        "updated_at",
    },
}


@dataclass
class RepairPlan:
    actions: list[str]
    blockers: list[str]
    already_repaired: bool = False


def _connect(db_path: Path, *, read_only: bool) -> sqlite3.Connection:
    if read_only:
        connection = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    else:
        connection = sqlite3.connect(str(db_path))
    connection.row_factory = sqlite3.Row
    return connection


def _normalized_username(value: Any) -> str:
    return str(value or "").strip().lstrip("@").lower()


def _table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in connection.execute(f'PRAGMA table_info("{table}")').fetchall()}


def _require_schema(connection: sqlite3.Connection) -> list[str]:
    blockers: list[str] = []
    for table, required_columns in REQUIRED_COLUMNS.items():
        columns = _table_columns(connection, table)
        if not columns:
            blockers.append(f"missing table: {table}")
            continue
        missing = sorted(required_columns - columns)
        if missing:
            blockers.append(f"missing columns in {table}: {', '.join(missing)}")
    return blockers


def _row_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def load_state(connection: sqlite3.Connection) -> dict[str, Any]:
    employee = connection.execute(
        """
        SELECT id, full_name, telegram_user_id, telegram_username, employee_stage, is_bot_blocked
        FROM employees
        WHERE id = ?
        """,
        (TARGET_EMPLOYEE_ID,),
    ).fetchone()
    account = connection.execute(
        """
        SELECT id, employee_id, channel, external_user_id, external_username, is_primary, is_active
        FROM employee_messenger_accounts
        WHERE id = ?
        """,
        (ORPHAN_ACCOUNT_ID,),
    ).fetchone()
    account_employee = None
    if account is not None:
        account_employee = connection.execute(
            "SELECT id, full_name FROM employees WHERE id = ?",
            (account["employee_id"],),
        ).fetchone()
    conflicts = connection.execute(
        """
        SELECT id, employee_id, external_user_id, external_username, is_active
        FROM employee_messenger_accounts
        WHERE channel = ?
          AND external_user_id = ?
          AND id <> ?
        ORDER BY id
        """,
        (CHANNEL, EXTERNAL_USER_ID, ORPHAN_ACCOUNT_ID),
    ).fetchall()
    return {
        "employee": _row_dict(employee),
        "account": _row_dict(account),
        "account_employee": _row_dict(account_employee),
        "conflicts": [_row_dict(row) for row in conflicts],
    }


def build_plan(state: dict[str, Any]) -> RepairPlan:
    actions: list[str] = []
    blockers: list[str] = []
    employee = state["employee"]
    account = state["account"]
    account_employee = state["account_employee"]
    conflicts = state["conflicts"]

    if employee is None:
        blockers.append(f"target employee {TARGET_EMPLOYEE_ID} not found")
    else:
        if int(employee["is_bot_blocked"] or 0):
            blockers.append(f"target employee {TARGET_EMPLOYEE_ID} is bot-blocked")
        if _normalized_username(employee["telegram_username"]) != _normalized_username(EXTERNAL_USERNAME):
            blockers.append(
                "target employee username mismatch: "
                f"expected {EXTERNAL_USERNAME}, got {employee['telegram_username']!r}"
            )

    if account is None:
        blockers.append(f"messenger account {ORPHAN_ACCOUNT_ID} not found")
    else:
        if account["channel"] != CHANNEL:
            blockers.append(f"account {ORPHAN_ACCOUNT_ID} channel mismatch: {account['channel']!r}")
        if str(account["external_user_id"] or "") != EXTERNAL_USER_ID:
            blockers.append(
                f"account {ORPHAN_ACCOUNT_ID} external_user_id mismatch: {account['external_user_id']!r}"
            )
        if _normalized_username(account["external_username"]) != _normalized_username(EXTERNAL_USERNAME):
            blockers.append(
                "account username mismatch: "
                f"expected {EXTERNAL_USERNAME}, got {account['external_username']!r}"
            )

    if conflicts:
        blockers.append(
            "external_user_id is present on another account: "
            + ", ".join(f"id={row['id']} employee_id={row['employee_id']}" for row in conflicts)
        )

    if blockers:
        return RepairPlan(actions=actions, blockers=blockers)

    assert employee is not None
    assert account is not None

    already_repaired = (
        int(account["employee_id"]) == TARGET_EMPLOYEE_ID
        and int(account["is_active"] or 0) == 1
        and int(account["is_primary"] or 0) == 1
        and str(employee["telegram_user_id"] or "") == EXTERNAL_USER_ID
    )
    if already_repaired:
        return RepairPlan(actions=["no-op: identity already repaired"], blockers=[], already_repaired=True)

    if account_employee is not None and int(account_employee["id"]) != TARGET_EMPLOYEE_ID:
        blockers.append(
            f"account {ORPHAN_ACCOUNT_ID} is not orphan; it points to existing employee {account_employee['id']}"
        )
        return RepairPlan(actions=actions, blockers=blockers)

    if int(account["is_active"] or 0) != 1:
        blockers.append(f"account {ORPHAN_ACCOUNT_ID} is not active; refusing to infer a different repair")
        return RepairPlan(actions=actions, blockers=blockers)

    actions.append(
        f"move active orphan account id={ORPHAN_ACCOUNT_ID} to employee_id={TARGET_EMPLOYEE_ID}, "
        f"keep external_user_id={EXTERNAL_USER_ID}, set external_username={EXTERNAL_USERNAME}, primary active"
    )
    if str(employee["telegram_user_id"] or "") != EXTERNAL_USER_ID:
        actions.append(f"set employees.id={TARGET_EMPLOYEE_ID}.telegram_user_id={EXTERNAL_USER_ID}")
    return RepairPlan(actions=actions, blockers=[])


def create_backup(db_path: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup_path = backup_dir / f"{db_path.stem}.before-gaantarasova-identity-repair.{timestamp}.db"
    source = sqlite3.connect(str(db_path))
    backup = sqlite3.connect(str(backup_path))
    try:
        source.backup(backup)
        result = backup.execute("PRAGMA quick_check").fetchone()
        if not result or result[0] != "ok":
            backup_path.unlink(missing_ok=True)
            raise RuntimeError(f"SQLite backup integrity check failed: {result}")
    finally:
        backup.close()
        source.close()
    return backup_path


def apply_repair(connection: sqlite3.Connection) -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat(sep=" ", timespec="seconds")
    with connection:
        connection.execute(
            """
            UPDATE employee_messenger_accounts
            SET employee_id = ?,
                external_username = ?,
                is_primary = 1,
                is_active = 1,
                updated_at = ?
            WHERE id = ?
              AND channel = ?
              AND external_user_id = ?
            """,
            (TARGET_EMPLOYEE_ID, EXTERNAL_USERNAME, now, ORPHAN_ACCOUNT_ID, CHANNEL, EXTERNAL_USER_ID),
        )
        connection.execute(
            """
            UPDATE employees
            SET telegram_user_id = ?
            WHERE id = ?
            """,
            (EXTERNAL_USER_ID, TARGET_EMPLOYEE_ID),
        )


def verify(connection: sqlite3.Connection) -> list[str]:
    failures: list[str] = []
    employee = connection.execute(
        "SELECT telegram_user_id, is_bot_blocked FROM employees WHERE id = ?",
        (TARGET_EMPLOYEE_ID,),
    ).fetchone()
    if employee is None:
        failures.append(f"employee {TARGET_EMPLOYEE_ID} missing")
    else:
        if str(employee["telegram_user_id"] or "") != EXTERNAL_USER_ID:
            failures.append(f"employee {TARGET_EMPLOYEE_ID} telegram_user_id is not {EXTERNAL_USER_ID}")
        if int(employee["is_bot_blocked"] or 0):
            failures.append(f"employee {TARGET_EMPLOYEE_ID} is bot-blocked")

    account = connection.execute(
        """
        SELECT employee_id, external_user_id, external_username, is_primary, is_active
        FROM employee_messenger_accounts
        WHERE id = ?
        """,
        (ORPHAN_ACCOUNT_ID,),
    ).fetchone()
    if account is None:
        failures.append(f"account {ORPHAN_ACCOUNT_ID} missing")
    else:
        if int(account["employee_id"]) != TARGET_EMPLOYEE_ID:
            failures.append(f"account {ORPHAN_ACCOUNT_ID} employee_id is not {TARGET_EMPLOYEE_ID}")
        if str(account["external_user_id"] or "") != EXTERNAL_USER_ID:
            failures.append(f"account {ORPHAN_ACCOUNT_ID} external_user_id is not {EXTERNAL_USER_ID}")
        if _normalized_username(account["external_username"]) != _normalized_username(EXTERNAL_USERNAME):
            failures.append(f"account {ORPHAN_ACCOUNT_ID} external_username is not {EXTERNAL_USERNAME}")
        if int(account["is_primary"] or 0) != 1:
            failures.append(f"account {ORPHAN_ACCOUNT_ID} is not primary")
        if int(account["is_active"] or 0) != 1:
            failures.append(f"account {ORPHAN_ACCOUNT_ID} is not active")

    orphan = connection.execute(
        """
        SELECT a.id
        FROM employee_messenger_accounts a
        LEFT JOIN employees e ON e.id = a.employee_id
        WHERE a.id = ?
          AND a.channel = ?
          AND a.is_active = 1
          AND e.id IS NULL
        """,
        (ORPHAN_ACCOUNT_ID, CHANNEL),
    ).fetchone()
    if orphan is not None:
        failures.append(f"account {ORPHAN_ACCOUNT_ID} is still an active orphan")

    active_numeric_rows = connection.execute(
        """
        SELECT id, employee_id
        FROM employee_messenger_accounts
        WHERE channel = ?
          AND external_user_id = ?
          AND is_active = 1
        ORDER BY id
        """,
        (CHANNEL, EXTERNAL_USER_ID),
    ).fetchall()
    if len(active_numeric_rows) != 1 or int(active_numeric_rows[0]["employee_id"]) != TARGET_EMPLOYEE_ID:
        failures.append(
            "active numeric telegram account does not uniquely resolve to employee 52: "
            + ", ".join(f"id={row['id']} employee_id={row['employee_id']}" for row in active_numeric_rows)
        )
    return failures


def print_state(state: dict[str, Any]) -> None:
    print("target_employee:", state["employee"])
    print("account_4:", state["account"])
    print("account_4_employee:", state["account_employee"])
    print("external_user_id_conflicts:", state["conflicts"])


def run(db_path: Path, *, apply: bool, backup_dir: Path | None) -> int:
    if not db_path.exists():
        raise SystemExit(f"DB not found: {db_path}")

    connection = _connect(db_path, read_only=not apply)
    try:
        quick_check = connection.execute("PRAGMA quick_check").fetchone()[0]
        print(f"DB: {db_path}")
        print(f"quick_check: {quick_check}")
        if quick_check != "ok":
            raise SystemExit("Refusing to continue: SQLite quick_check failed.")

        schema_blockers = _require_schema(connection)
        state = load_state(connection)
        print_state(state)
        plan = build_plan(state)
        blockers = [*schema_blockers, *plan.blockers]
        print("mode:", "apply" if apply else "dry-run")
        print("plan:")
        if plan.actions:
            for action in plan.actions:
                print(f"- {action}")
        else:
            print("- no actions")
        if blockers:
            print("blockers:")
            for blocker in blockers:
                print(f"- {blocker}")
            return 2

        if not apply:
            print("dry-run: no changes written")
            return 0

        if plan.already_repaired:
            print("apply: no changes needed")
        else:
            backup_path = create_backup(db_path, backup_dir or db_path.parent / "backups")
            print(f"backup: {backup_path}")
            apply_repair(connection)
            print("apply: repair written")

        failures = verify(connection)
        print("verify:")
        if failures:
            for failure in failures:
                print(f"- failed: {failure}")
            return 3
        print("- passed: employee 52 has numeric telegram_user_id")
        print("- passed: account 4 is active primary and points to employee 52")
        print("- passed: account 4 is not an active orphan")
        print("- passed: external_user_id uniquely resolves to employee 52")
        return 0
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Narrow repair for stage orphan Telegram identity GaAnTarasova -> employee 52.",
    )
    parser.add_argument("--db", required=True, type=Path, help="Path to SQLite DB.")
    parser.add_argument("--backup-dir", type=Path, help="Backup directory for --apply. Defaults to <db>/../backups.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Analyze and print plan without writing. This is default.")
    mode.add_argument("--apply", action="store_true", help="Create backup, apply repair, and verify.")
    args = parser.parse_args()

    if args.backup_dir and not args.apply:
        print("warning: --backup-dir is ignored without --apply")
    return run(args.db, apply=bool(args.apply), backup_dir=args.backup_dir)


if __name__ == "__main__":
    raise SystemExit(main())
