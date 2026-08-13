from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from tools.repair_gaantarasova_identity import run


def _create_schema(db_path: Path) -> None:
    connection = sqlite3.connect(str(db_path))
    try:
        connection.executescript(
            """
            CREATE TABLE employees (
                id INTEGER PRIMARY KEY,
                full_name TEXT,
                telegram_user_id TEXT,
                telegram_username TEXT,
                employee_stage TEXT,
                candidate_work_stage TEXT,
                is_bot_blocked INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE employee_messenger_accounts (
                id INTEGER PRIMARY KEY,
                employee_id INTEGER NOT NULL,
                channel TEXT NOT NULL,
                external_user_id TEXT NOT NULL,
                external_username TEXT,
                is_primary INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE UNIQUE INDEX uq_employee_messenger_accounts_channel_user
            ON employee_messenger_accounts (channel, external_user_id);
            """
        )
    finally:
        connection.close()


def _seed_drift(db_path: Path) -> None:
    connection = sqlite3.connect(str(db_path))
    try:
        connection.execute(
            """
            INSERT INTO employees (
                id, full_name, telegram_user_id, telegram_username, employee_stage, candidate_work_stage, is_bot_blocked
            ) VALUES (52, 'Тарасова Галина', NULL, '@GaAnTarasova', 'staff', NULL, 0)
            """
        )
        connection.execute(
            """
            INSERT INTO employee_messenger_accounts (
                id, employee_id, channel, external_user_id, external_username, is_primary, is_active, created_at, updated_at
            ) VALUES (4, 4, 'telegram', '1950649889', 'GaAnTarasova', 1, 1, '2026-08-01 00:00:00', '2026-08-01 00:00:00')
            """
        )
        connection.commit()
    finally:
        connection.close()


class RepairGaAnTarasovaIdentityTests(unittest.TestCase):
    def test_dry_run_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "hr_bot.db"
            _create_schema(db_path)
            _seed_drift(db_path)

            exit_code = run(db_path, apply=False, backup_dir=None)

            self.assertEqual(exit_code, 0)
            connection = sqlite3.connect(str(db_path))
            try:
                employee_user_id = connection.execute(
                    "SELECT telegram_user_id FROM employees WHERE id = 52"
                ).fetchone()[0]
                account_employee_id = connection.execute(
                    "SELECT employee_id FROM employee_messenger_accounts WHERE id = 4"
                ).fetchone()[0]
            finally:
                connection.close()
            self.assertIsNone(employee_user_id)
            self.assertEqual(account_employee_id, 4)

    def test_apply_moves_orphan_account_and_creates_backup(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_path = root / "hr_bot.db"
            backup_dir = root / "backups"
            _create_schema(db_path)
            _seed_drift(db_path)

            exit_code = run(db_path, apply=True, backup_dir=backup_dir)

            self.assertEqual(exit_code, 0)
            backups = list(backup_dir.glob("hr_bot.before-gaantarasova-identity-repair.*.db"))
            self.assertEqual(len(backups), 1)
            connection = sqlite3.connect(str(db_path))
            try:
                employee_user_id = connection.execute(
                    "SELECT telegram_user_id FROM employees WHERE id = 52"
                ).fetchone()[0]
                account = connection.execute(
                    """
                    SELECT employee_id, external_user_id, external_username, is_primary, is_active
                    FROM employee_messenger_accounts
                    WHERE id = 4
                    """
                ).fetchone()
            finally:
                connection.close()
            self.assertEqual(employee_user_id, "1950649889")
            self.assertEqual(account, (52, "1950649889", "GaAnTarasova", 1, 1))

    def test_apply_is_idempotent_after_repair(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_path = root / "hr_bot.db"
            backup_dir = root / "backups"
            _create_schema(db_path)
            _seed_drift(db_path)

            first_exit = run(db_path, apply=True, backup_dir=backup_dir)
            second_exit = run(db_path, apply=True, backup_dir=backup_dir)

            self.assertEqual(first_exit, 0)
            self.assertEqual(second_exit, 0)
            backups = list(backup_dir.glob("hr_bot.before-gaantarasova-identity-repair.*.db"))
            self.assertEqual(len(backups), 1)

    def test_apply_refuses_if_account_points_to_existing_other_employee(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "hr_bot.db"
            _create_schema(db_path)
            _seed_drift(db_path)
            connection = sqlite3.connect(str(db_path))
            try:
                connection.execute(
                    """
                    INSERT INTO employees (
                        id, full_name, telegram_user_id, telegram_username, employee_stage, candidate_work_stage, is_bot_blocked
                    ) VALUES (4, 'Other Employee', NULL, NULL, 'staff', NULL, 0)
                    """
                )
                connection.commit()
            finally:
                connection.close()

            exit_code = run(db_path, apply=True, backup_dir=Path(temp_dir) / "backups")

            self.assertEqual(exit_code, 2)


if __name__ == "__main__":
    unittest.main()
