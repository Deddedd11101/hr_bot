import sqlite3
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine, text

import app.database as database


def _create_non_employee_tables(engine) -> None:
    from app import models  # noqa: F401

    for table in database.Base.metadata.sorted_tables:
        if table.name != "employees":
            table.create(engine, checkfirst=True)


def _create_legacy_employees_table(path: Path, *, include_menu_state: bool) -> None:
    connection = sqlite3.connect(path)
    try:
        menu_columns = ""
        if include_menu_state:
            menu_columns = ", current_menu_path TEXT, current_menu_message_id INTEGER"
        connection.execute(
            f"""
            CREATE TABLE employees (
                id INTEGER PRIMARY KEY,
                full_name TEXT NOT NULL,
                telegram_user_id TEXT NOT NULL,
                telegram_username TEXT,
                current_menu_set_id INTEGER{menu_columns},
                first_workday DATE NOT NULL,
                birth_date DATE,
                created_at DATETIME NOT NULL,
                is_flow_scheduled BOOLEAN NOT NULL DEFAULT 0,
                is_bot_blocked BOOLEAN NOT NULL DEFAULT 0,
                desired_position TEXT,
                work_email TEXT,
                work_hours TEXT,
                is_manager BOOLEAN NOT NULL DEFAULT 0,
                is_mentor BOOLEAN NOT NULL DEFAULT 0,
                profile_photo_path TEXT,
                profile_photo_filename TEXT,
                salary_expectation TEXT,
                candidate_status TEXT,
                candidate_work_stage TEXT,
                employee_stage TEXT,
                manager_employee_id INTEGER,
                mentor_adaptation_employee_id INTEGER,
                mentor_ipr_employee_id INTEGER,
                manager_telegram_id TEXT,
                mentor_adaptation_telegram_id TEXT,
                mentor_ipr_telegram_id TEXT,
                adaptation_tasks_url TEXT,
                adaptation_feedback_url TEXT,
                adaptation_midpoint DATE,
                adaptation_end DATE,
                personal_data_consent BOOLEAN NOT NULL DEFAULT 0,
                employee_data_consent BOOLEAN NOT NULL DEFAULT 0,
                test_task_link TEXT,
                test_task_due_at DATETIME,
                notes TEXT
            )
            """
        )
        columns = [
            "id",
            "full_name",
            "telegram_user_id",
            "telegram_username",
            "current_menu_set_id",
            "first_workday",
            "created_at",
            "is_flow_scheduled",
            "employee_stage",
        ]
        values = [1, "Legacy employee", "12345", "legacy", 7, "2026-09-01", "2026-01-01", 0, "staff"]
        if include_menu_state:
            columns[5:5] = ["current_menu_path", "current_menu_message_id"]
            values[5:5] = ["7/9", 902]
        placeholders = ", ".join("?" for _ in values)
        connection.execute(
            f"INSERT INTO employees ({', '.join(columns)}) VALUES ({placeholders})",
            values,
        )
        connection.commit()
    finally:
        connection.close()


class DatabaseCompatibilityTests(unittest.TestCase):
    def test_employee_rebuild_preserves_existing_menu_state(self) -> None:
        self._assert_menu_state(include_menu_state=True, expected=("7/9", 902))

    def test_employee_rebuild_uses_null_for_missing_menu_state(self) -> None:
        self._assert_menu_state(include_menu_state=False, expected=(None, None))

    def _assert_menu_state(self, *, include_menu_state: bool, expected: tuple[str | None, int | None]) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "legacy.db"
            engine = create_engine(f"sqlite:///{path}")
            _create_non_employee_tables(engine)
            _create_legacy_employees_table(path, include_menu_state=include_menu_state)

            previous_engine = database.engine
            previous_url = database.settings.DATABASE_URL
            try:
                database.engine = engine
                database.settings.DATABASE_URL = f"sqlite:///{path}"
                database._ensure_sqlite_schema()
                with engine.connect() as connection:
                    row = connection.execute(
                        text("SELECT current_menu_path, current_menu_message_id FROM employees WHERE id = 1")
                    ).one()
                self.assertEqual((row[0], row[1]), expected)
            finally:
                database.engine = previous_engine
                database.settings.DATABASE_URL = previous_url
                engine.dispose()


if __name__ == "__main__":
    unittest.main()
