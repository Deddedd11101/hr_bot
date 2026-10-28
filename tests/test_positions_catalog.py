from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from app.models import Position
from app.positions import (
    CANONICAL_POSITION_TITLES,
    DEFAULT_POSITIONS,
    normalize_position_slug,
    resolve_employee_position_value,
)


ROOT = Path(__file__).resolve().parents[1]


class PositionCatalogTests(unittest.TestCase):
    def test_unknown_employee_value_does_not_create_catalog_row(self) -> None:
        class EmptyQuery:
            def filter(self, *_args, **_kwargs):
                return self

            def first(self):
                return None

        class EmptyDb:
            def query(self, model):
                assert model is Position
                return EmptyQuery()

            def get(self, *_args):
                return None

        self.assertEqual(resolve_employee_position_value(EmptyDb(), "QA engineer"), "QA engineer")

    def test_default_catalog_is_exactly_the_curated_unique_list(self) -> None:
        self.assertEqual([item["title"] for item in DEFAULT_POSITIONS], list(CANONICAL_POSITION_TITLES))
        self.assertEqual(len({item["title"] for item in DEFAULT_POSITIONS}), len(DEFAULT_POSITIONS))
        self.assertEqual(len({item["slug"] for item in DEFAULT_POSITIONS}), len(DEFAULT_POSITIONS))
        self.assertEqual(
            DEFAULT_POSITIONS[-1]["slug"], normalize_position_slug("Системный администратор")
        )

    def test_audit_is_read_only_and_reports_unambiguous_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database = Path(temp_dir) / "audit.db"
            with sqlite3.connect(database) as connection:
                connection.executescript(
                    """
                    CREATE TABLE employees (desired_position TEXT);
                    CREATE TABLE positions (id INTEGER, title TEXT, slug TEXT, is_active INTEGER, sort_order INTEGER);
                    INSERT INTO employees VALUES ('Аналитик'), ('Аналитик'), ('Project manager');
                    INSERT INTO positions VALUES (1, 'Аналитик', 'analyst', 1, 10);
                    """
                )
                connection.commit()
            connection.close()
            result = subprocess.run(
                [sys.executable, "tools/audit_positions.py", "--db", str(database), "--json"],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            report = json.loads(result.stdout)
            self.assertTrue(report["read_only"])
            values = {item["existing_value"]: item for item in report["employee_values"]}
            self.assertEqual(values["Аналитик"]["usage_count"], 2)
            self.assertEqual(values["Аналитик"]["proposed_mapping"], "Аналитик")
            self.assertIsNone(values["Project manager"]["proposed_mapping"])
            with sqlite3.connect(database) as connection:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM employees").fetchone()[0], 3)
            connection.close()

    def test_replacement_is_dry_run_by_default_and_updates_scopes_only_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            database = temp_path / "replace.db"
            backup_dir = temp_path / "backups"
            with sqlite3.connect(database) as connection:
                connection.executescript(
                    """
                    CREATE TABLE employees (id INTEGER PRIMARY KEY, desired_position TEXT);
                    CREATE TABLE scenario_templates (id INTEGER PRIMARY KEY, role_scope TEXT);
                    INSERT INTO employees VALUES (1, 'Project manager');
                    INSERT INTO scenario_templates VALUES (1, 'project_manager');
                    """
                )
                connection.commit()
            connection.close()
            command = [
                sys.executable,
                "tools/replace_positions.py",
                "--db",
                str(database),
                "--mapping",
                "Project manager=Руководитель проектов",
                "--update-scopes",
            ]
            dry_run = subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)
            self.assertIn("Dry-run only", dry_run.stdout)
            with sqlite3.connect(database) as connection:
                self.assertEqual(connection.execute("SELECT desired_position FROM employees").fetchone()[0], "Project manager")
            connection.close()

            applied = subprocess.run(
                command + ["--apply", "--backup-dir", str(backup_dir)],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn("Applied successfully", applied.stdout)
            self.assertEqual(len(list(backup_dir.glob("*.db"))), 1)
            with sqlite3.connect(database) as connection:
                self.assertEqual(
                    connection.execute("SELECT desired_position FROM employees").fetchone()[0],
                    "Руководитель проектов",
                )
                self.assertEqual(
                    connection.execute("SELECT role_scope FROM scenario_templates").fetchone()[0],
                    "rukovoditel_proektov",
                )
            connection.close()


if __name__ == "__main__":
    unittest.main()
