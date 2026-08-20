import json
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from tools.scenario_portability import export_scenarios, import_scenarios


def _create_portability_schema(db_path: Path) -> None:
    connection = sqlite3.connect(str(db_path))
    try:
        connection.executescript(
            """
            CREATE TABLE scenario_templates (
                id INTEGER PRIMARY KEY,
                scenario_key TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0,
                scenario_kind TEXT NOT NULL DEFAULT 'scenario',
                role_scope TEXT NOT NULL DEFAULT 'all',
                employee_scope TEXT NOT NULL DEFAULT 'all',
                recipient_mode TEXT NOT NULL DEFAULT 'self',
                trigger_mode TEXT NOT NULL DEFAULT 'manual_only',
                target_employee_id INTEGER,
                description TEXT
            );

            CREATE TABLE flow_step_templates (
                id INTEGER PRIMARY KEY,
                flow_key TEXT NOT NULL,
                step_key TEXT NOT NULL,
                parent_step_id INTEGER,
                branch_option_index INTEGER,
                step_title TEXT NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0,
                default_text TEXT NOT NULL,
                custom_text TEXT,
                response_type TEXT NOT NULL DEFAULT 'none',
                button_options TEXT,
                send_mode TEXT NOT NULL DEFAULT 'immediate',
                send_time TEXT,
                day_offset_workdays INTEGER NOT NULL DEFAULT 0,
                target_field TEXT,
                launch_scenario_key TEXT,
                attachment_path TEXT,
                attachment_filename TEXT,
                send_employee_card INTEGER NOT NULL DEFAULT 0,
                notify_on_send_text TEXT,
                notify_on_send_recipient_ids TEXT,
                notify_on_send_recipient_scope TEXT
            );

            CREATE TABLE step_button_notifications (
                id INTEGER PRIMARY KEY,
                flow_key TEXT NOT NULL,
                step_id INTEGER NOT NULL,
                option_index INTEGER NOT NULL,
                message_text TEXT,
                recipient_ids TEXT,
                recipient_scope TEXT
            );
            """
        )
        connection.commit()
    finally:
        connection.close()


def _add_attachment_document_schema(db_path: Path) -> None:
    connection = sqlite3.connect(str(db_path))
    try:
        connection.executescript(
            """
            ALTER TABLE flow_step_templates ADD COLUMN attachment_document_item_id INTEGER;

            CREATE TABLE document_library_items (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                category TEXT,
                item_kind TEXT NOT NULL,
                external_url TEXT,
                original_filename TEXT,
                stored_path TEXT,
                mime_type TEXT,
                file_size INTEGER,
                is_active INTEGER NOT NULL DEFAULT 1,
                sort_order INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        connection.commit()
    finally:
        connection.close()


def _insert_single_scenario_with_library_attachment(db_path: Path, document_id: int = 1) -> None:
    connection = sqlite3.connect(str(db_path))
    try:
        connection.execute(
            """
            INSERT INTO scenario_templates (
                scenario_key, title, sort_order, scenario_kind, role_scope, employee_scope, recipient_mode, trigger_mode, target_employee_id, description
            ) VALUES ('scenario_docs', 'Docs scenario', 10, 'scenario', 'all', 'employees', 'self', 'manual_only', NULL, 'docs')
            """
        )
        connection.execute(
            """
            INSERT INTO document_library_items (
                id, title, description, category, item_kind, external_url, original_filename, stored_path, mime_type, file_size, is_active, sort_order
            ) VALUES (?, 'Policy', 'Read it', 'Docs', 'link', 'https://example.com/policy', NULL, NULL, NULL, NULL, 1, 10)
            """,
            (document_id,),
        )
        connection.execute(
            """
            INSERT INTO flow_step_templates (
                flow_key, step_key, parent_step_id, branch_option_index, step_title, sort_order, default_text, custom_text, response_type, button_options,
                send_mode, send_time, day_offset_workdays, target_field, launch_scenario_key, attachment_document_item_id, attachment_path, attachment_filename,
                send_employee_card, notify_on_send_text, notify_on_send_recipient_ids, notify_on_send_recipient_scope
            ) VALUES ('scenario_docs', 'step_one', NULL, NULL, 'Step one', 10, 'Read doc', NULL, 'none', NULL, 'immediate', NULL, 0, NULL, NULL, ?, NULL, NULL, 0, NULL, NULL, NULL)
            """,
            (document_id,),
        )
        connection.commit()
    finally:
        connection.close()


def _insert_target_document(db_path: Path, *, document_id: int, external_url: str) -> None:
    connection = sqlite3.connect(str(db_path))
    try:
        connection.execute(
            """
            INSERT INTO document_library_items (
                id, title, description, category, item_kind, external_url, original_filename, stored_path, mime_type, file_size, is_active, sort_order
            ) VALUES (?, 'Policy', 'Read it', 'Docs', 'link', ?, NULL, NULL, NULL, NULL, 1, 10)
            """,
            (document_id, external_url),
        )
        connection.commit()
    finally:
        connection.close()


class ScenarioPortabilityTests(unittest.TestCase):
    def test_export_import_round_trip_preserves_recipient_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source_db = root / "source.db"
            target_db = root / "target.db"
            export_dir = root / "package"
            storage_root = root / "storage"

            _create_portability_schema(source_db)
            _create_portability_schema(target_db)

            source = sqlite3.connect(str(source_db))
            try:
                source.executemany(
                    """
                    INSERT INTO scenario_templates (
                        scenario_key, title, sort_order, scenario_kind, role_scope, employee_scope, recipient_mode, trigger_mode, target_employee_id, description
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        ("scenario_manager", "Manager scenario", 10, "scenario", "all", "employees", "manager", "manual_only", None, "manager"),
                        ("scenario_hr", "HR scenario", 20, "scenario", "all", "employees", "hr", "manual_only", None, "hr"),
                        ("scenario_mentor", "Mentor scenario", 30, "scenario", "all", "employees", "mentor_adaptation", "manual_only", None, "mentor"),
                    ],
                )
                source.executemany(
                    """
                    INSERT INTO flow_step_templates (
                        flow_key, step_key, parent_step_id, branch_option_index, step_title, sort_order, default_text, custom_text, response_type, button_options,
                        send_mode, send_time, day_offset_workdays, target_field, launch_scenario_key, attachment_path, attachment_filename, send_employee_card,
                        notify_on_send_text, notify_on_send_recipient_ids, notify_on_send_recipient_scope
                    ) VALUES (?, ?, NULL, NULL, ?, ?, ?, NULL, 'none', NULL, 'immediate', NULL, 0, NULL, NULL, NULL, NULL, 0, NULL, NULL, NULL)
                    """,
                    [
                        ("scenario_manager", "step_one", "Step one", 10, "Manager step"),
                        ("scenario_hr", "step_one", "Step one", 10, "HR step"),
                        ("scenario_mentor", "step_one", "Step one", 10, "Mentor step"),
                    ],
                )
                source.commit()
            finally:
                source.close()

            export_scenarios(source_db, export_dir, ["scenario_manager", "scenario_hr", "scenario_mentor"])

            manifest = json.loads((export_dir / "manifest.json").read_text(encoding="utf-8"))
            exported_modes = {
                item["template"]["scenario_key"]: item["template"]["recipient_mode"]
                for item in manifest["scenarios"]
            }
            self.assertEqual(
                exported_modes,
                {
                    "scenario_manager": "manager",
                    "scenario_hr": "hr",
                    "scenario_mentor": "mentor_adaptation",
                },
            )

            import_scenarios(target_db, export_dir, storage_root)

            target = sqlite3.connect(str(target_db))
            try:
                rows = target.execute(
                    """
                    SELECT scenario_key, recipient_mode
                    FROM scenario_templates
                    ORDER BY scenario_key
                    """
                ).fetchall()
            finally:
                target.close()

            self.assertEqual(
                rows,
                [
                    ("scenario_hr", "hr"),
                    ("scenario_manager", "manager"),
                    ("scenario_mentor", "mentor_adaptation"),
                ],
            )

    def test_export_from_old_db_without_attachment_document_column_does_not_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source_db = root / "source.db"
            export_dir = root / "package"

            _create_portability_schema(source_db)
            connection = sqlite3.connect(str(source_db))
            try:
                connection.execute(
                    """
                    INSERT INTO scenario_templates (
                        scenario_key, title, sort_order, scenario_kind, role_scope, employee_scope, recipient_mode, trigger_mode, target_employee_id, description
                    ) VALUES ('scenario_old', 'Old scenario', 10, 'scenario', 'all', 'employees', 'self', 'manual_only', NULL, NULL)
                    """
                )
                connection.execute(
                    """
                    INSERT INTO flow_step_templates (
                        flow_key, step_key, parent_step_id, branch_option_index, step_title, sort_order, default_text, custom_text, response_type, button_options,
                        send_mode, send_time, day_offset_workdays, target_field, launch_scenario_key, attachment_path, attachment_filename, send_employee_card,
                        notify_on_send_text, notify_on_send_recipient_ids, notify_on_send_recipient_scope
                    ) VALUES ('scenario_old', 'step_one', NULL, NULL, 'Step one', 10, 'Text', NULL, 'none', NULL, 'immediate', NULL, 0, NULL, NULL, NULL, NULL, 0, NULL, NULL, NULL)
                    """
                )
                connection.commit()
            finally:
                connection.close()

            export_scenarios(source_db, export_dir, ["scenario_old"])

            manifest = json.loads((export_dir / "manifest.json").read_text(encoding="utf-8"))
            step = manifest["scenarios"][0]["steps"][0]
            self.assertIsNone(step["attachment_document_item_id"])
            self.assertIsNone(step["attachment_document_item"])

    def test_import_clears_library_attachment_when_same_id_is_mismatched(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source_db = root / "source.db"
            target_db = root / "target.db"
            export_dir = root / "package"
            storage_root = root / "storage"

            _create_portability_schema(source_db)
            _create_portability_schema(target_db)
            _add_attachment_document_schema(source_db)
            _add_attachment_document_schema(target_db)
            _insert_single_scenario_with_library_attachment(source_db, document_id=1)
            _insert_target_document(target_db, document_id=1, external_url="https://example.com/different-policy")

            export_scenarios(source_db, export_dir, ["scenario_docs"])
            output = StringIO()
            with redirect_stdout(output):
                import_scenarios(target_db, export_dir, storage_root)

            target = sqlite3.connect(str(target_db))
            try:
                row = target.execute(
                    "SELECT attachment_document_item_id FROM flow_step_templates WHERE flow_key = 'scenario_docs'"
                ).fetchone()
            finally:
                target.close()

            self.assertIsNone(row[0])
            self.assertIn("WARNING: cleared attachment_document_item_id", output.getvalue())

    def test_import_preserves_library_attachment_for_exact_validated_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source_db = root / "source.db"
            target_db = root / "target.db"
            export_dir = root / "package"
            storage_root = root / "storage"

            _create_portability_schema(source_db)
            _create_portability_schema(target_db)
            _add_attachment_document_schema(source_db)
            _add_attachment_document_schema(target_db)
            _insert_single_scenario_with_library_attachment(source_db, document_id=1)
            _insert_target_document(target_db, document_id=7, external_url="https://example.com/policy")

            export_scenarios(source_db, export_dir, ["scenario_docs"])
            output = StringIO()
            with redirect_stdout(output):
                import_scenarios(target_db, export_dir, storage_root)

            target = sqlite3.connect(str(target_db))
            try:
                row = target.execute(
                    "SELECT attachment_document_item_id FROM flow_step_templates WHERE flow_key = 'scenario_docs'"
                ).fetchone()
            finally:
                target.close()

            self.assertEqual(row[0], 7)
            self.assertNotIn("WARNING: cleared attachment_document_item_id", output.getvalue())


if __name__ == "__main__":
    unittest.main()
