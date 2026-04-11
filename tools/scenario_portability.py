from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
from pathlib import Path
from typing import Any


SCENARIO_TEMPLATE_FIELDS = [
    "scenario_key",
    "title",
    "sort_order",
    "scenario_kind",
    "role_scope",
    "employee_scope",
    "trigger_mode",
    "target_employee_id",
    "description",
]

FLOW_STEP_FIELDS = [
    "step_key",
    "step_title",
    "sort_order",
    "default_text",
    "custom_text",
    "response_type",
    "button_options",
    "send_mode",
    "send_time",
    "day_offset_workdays",
    "target_field",
    "launch_scenario_key",
    "attachment_filename",
    "send_employee_card",
    "notify_on_send_text",
    "notify_on_send_recipient_ids",
    "notify_on_send_recipient_scope",
]

STEP_NOTIFICATION_FIELDS = [
    "option_index",
    "message_text",
    "recipient_ids",
    "recipient_scope",
]


def _dict_factory(cursor: sqlite3.Cursor, row: tuple[Any, ...]) -> dict[str, Any]:
    return {description[0]: row[index] for index, description in enumerate(cursor.description)}


def _connect(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(str(db_path))
    connection.row_factory = _dict_factory
    return connection


def _normalize_scenario_keys(raw_values: list[str]) -> list[str]:
    result: list[str] = []
    for raw_value in raw_values:
        for item in raw_value.split(","):
            normalized = item.strip()
            if normalized and normalized not in result:
                result.append(normalized)
    return result


def _load_scenario_row(connection: sqlite3.Connection, scenario_key: str) -> dict[str, Any]:
    row = connection.execute(
        """
        SELECT scenario_key, title, sort_order, scenario_kind, role_scope, employee_scope, trigger_mode, target_employee_id, description
        FROM scenario_templates
        WHERE scenario_key = ?
        """,
        (scenario_key,),
    ).fetchone()
    if not row:
        raise RuntimeError(f"Scenario '{scenario_key}' not found.")
    return row


def _load_step_rows(connection: sqlite3.Connection, scenario_key: str) -> list[dict[str, Any]]:
    return connection.execute(
        """
        SELECT
            id,
            flow_key,
            step_key,
            parent_step_id,
            branch_option_index,
            step_title,
            sort_order,
            default_text,
            custom_text,
            response_type,
            button_options,
            send_mode,
            send_time,
            day_offset_workdays,
            target_field,
            launch_scenario_key,
            attachment_path,
            attachment_filename,
            send_employee_card,
            notify_on_send_text,
            notify_on_send_recipient_ids,
            notify_on_send_recipient_scope
        FROM flow_step_templates
        WHERE flow_key = ?
        ORDER BY parent_step_id IS NOT NULL, parent_step_id, sort_order, id
        """,
        (scenario_key,),
    ).fetchall()


def _load_notifications(connection: sqlite3.Connection, flow_key: str) -> list[dict[str, Any]]:
    return connection.execute(
        """
        SELECT
            n.step_id,
            s.step_key,
            n.option_index,
            n.message_text,
            n.recipient_ids,
            n.recipient_scope
        FROM step_button_notifications n
        JOIN flow_step_templates s ON s.id = n.step_id
        WHERE n.flow_key = ?
        ORDER BY s.step_key, n.option_index, n.id
        """,
        (flow_key,),
    ).fetchall()


def _copy_attachment(source_path: str | None, export_assets_dir: Path, flow_key: str, step_key: str) -> dict[str, Any] | None:
    normalized_source = (source_path or "").strip()
    if not normalized_source:
        return None
    source = Path(normalized_source)
    if not source.exists():
        return {
            "missing": True,
            "original_path": normalized_source,
        }

    target_dir = export_assets_dir / flow_key
    target_dir.mkdir(parents=True, exist_ok=True)
    target_name = f"{step_key}_{source.name}"
    target_path = target_dir / target_name
    shutil.copy2(source, target_path)
    return {
        "missing": False,
        "original_path": normalized_source,
        "package_path": str(Path("assets") / flow_key / target_name).replace("\\", "/"),
        "original_name": source.name,
    }


def export_scenarios(db_path: Path, output_dir: Path, scenario_keys: list[str]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    assets_dir = output_dir / "assets"
    assets_dir.mkdir(exist_ok=True)

    with _connect(db_path) as connection:
        payload: dict[str, Any] = {
            "version": 1,
            "exported_from": str(db_path),
            "scenarios": [],
        }

        for scenario_key in scenario_keys:
            scenario_row = _load_scenario_row(connection, scenario_key)
            step_rows = _load_step_rows(connection, scenario_key)
            step_key_by_id = {row["id"]: row["step_key"] for row in step_rows}
            notifications = _load_notifications(connection, scenario_key)

            serialized_steps: list[dict[str, Any]] = []
            for row in step_rows:
                attachment = _copy_attachment(row.get("attachment_path"), assets_dir, scenario_key, row["step_key"])
                serialized_step = {
                    field: row.get(field) for field in FLOW_STEP_FIELDS
                }
                serialized_step["parent_step_key"] = step_key_by_id.get(row.get("parent_step_id"))
                serialized_step["branch_option_index"] = row.get("branch_option_index")
                serialized_step["attachment"] = attachment
                serialized_steps.append(serialized_step)

            serialized_notifications: list[dict[str, Any]] = []
            for notification in notifications:
                item = {field: notification.get(field) for field in STEP_NOTIFICATION_FIELDS}
                item["step_key"] = notification["step_key"]
                serialized_notifications.append(item)

            payload["scenarios"].append(
                {
                    "template": {field: scenario_row.get(field) for field in SCENARIO_TEMPLATE_FIELDS},
                    "steps": serialized_steps,
                    "button_notifications": serialized_notifications,
                }
            )

    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Exported {len(payload['scenarios'])} scenario(s) to {manifest_path}")


def _load_manifest(input_dir: Path) -> dict[str, Any]:
    manifest_path = input_dir / "manifest.json"
    if not manifest_path.exists():
        raise RuntimeError(f"Manifest not found: {manifest_path}")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _delete_existing_scenario(connection: sqlite3.Connection, scenario_key: str) -> None:
    step_rows = connection.execute(
        "SELECT id FROM flow_step_templates WHERE flow_key = ?",
        (scenario_key,),
    ).fetchall()
    step_ids = [row["id"] for row in step_rows]
    if step_ids:
        placeholders = ",".join("?" for _ in step_ids)
        connection.execute(
            f"DELETE FROM step_button_notifications WHERE step_id IN ({placeholders})",
            tuple(step_ids),
        )
    connection.execute("DELETE FROM flow_step_templates WHERE flow_key = ?", (scenario_key,))


def _upsert_scenario_template(connection: sqlite3.Connection, template: dict[str, Any]) -> None:
    template = {**template, "employee_scope": template.get("employee_scope") or "all"}
    existing = connection.execute(
        "SELECT id FROM scenario_templates WHERE scenario_key = ?",
        (template["scenario_key"],),
    ).fetchone()

    values = tuple(template.get(field) for field in SCENARIO_TEMPLATE_FIELDS)
    if existing:
        connection.execute(
            """
            UPDATE scenario_templates
            SET
                title = ?,
                sort_order = ?,
                scenario_kind = ?,
                role_scope = ?,
                employee_scope = ?,
                trigger_mode = ?,
                target_employee_id = ?,
                description = ?
            WHERE scenario_key = ?
            """,
            (
                template.get("title"),
                template.get("sort_order"),
                template.get("scenario_kind"),
                template.get("role_scope"),
                template.get("employee_scope") or "all",
                template.get("trigger_mode"),
                template.get("target_employee_id"),
                template.get("description"),
                template["scenario_key"],
            ),
        )
        return

    connection.execute(
        """
        INSERT INTO scenario_templates (
            scenario_key, title, sort_order, scenario_kind, role_scope, employee_scope, trigger_mode, target_employee_id, description
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        values,
    )


def _restore_attachment(
    package_dir: Path,
    storage_root: Path,
    flow_key: str,
    step_key: str,
    attachment: dict[str, Any] | None,
) -> tuple[str | None, str | None]:
    if not attachment or attachment.get("missing"):
        return None, None

    package_path = attachment.get("package_path")
    if not package_path:
        return None, None

    source = package_dir / package_path
    if not source.exists():
        raise RuntimeError(f"Attachment file is missing from package: {source}")

    target_dir = storage_root / flow_key
    target_dir.mkdir(parents=True, exist_ok=True)
    target_name = source.name
    if not target_name.startswith(f"{step_key}_"):
        target_name = f"{step_key}_{target_name}"
    target_path = target_dir / target_name
    shutil.copy2(source, target_path)
    return str(target_path.resolve()), attachment.get("original_name") or source.name


def import_scenarios(db_path: Path, input_dir: Path, storage_root: Path) -> None:
    payload = _load_manifest(input_dir)
    imported = 0

    with _connect(db_path) as connection:
        for scenario_item in payload.get("scenarios", []):
            template = scenario_item["template"]
            scenario_key = template["scenario_key"]
            _upsert_scenario_template(connection, template)
            _delete_existing_scenario(connection, scenario_key)

            inserted_step_ids: dict[str, int] = {}
            pending_steps = list(scenario_item.get("steps", []))
            while pending_steps:
                progress_made = False
                next_pending: list[dict[str, Any]] = []
                for step in pending_steps:
                    parent_step_key = step.get("parent_step_key")
                    if parent_step_key and parent_step_key not in inserted_step_ids:
                        next_pending.append(step)
                        continue

                    attachment_path, attachment_filename = _restore_attachment(
                        input_dir,
                        storage_root,
                        scenario_key,
                        step["step_key"],
                        step.get("attachment"),
                    )
                    cursor = connection.execute(
                        """
                        INSERT INTO flow_step_templates (
                            flow_key,
                            step_key,
                            parent_step_id,
                            branch_option_index,
                            step_title,
                            sort_order,
                            default_text,
                            custom_text,
                            response_type,
                            button_options,
                            send_mode,
                            send_time,
                            day_offset_workdays,
                            target_field,
                            launch_scenario_key,
                            attachment_path,
                            attachment_filename,
                            send_employee_card,
                            notify_on_send_text,
                            notify_on_send_recipient_ids,
                            notify_on_send_recipient_scope
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            scenario_key,
                            step["step_key"],
                            inserted_step_ids.get(parent_step_key),
                            step.get("branch_option_index"),
                            step.get("step_title"),
                            step.get("sort_order"),
                            step.get("default_text") or "",
                            step.get("custom_text"),
                            step.get("response_type"),
                            step.get("button_options"),
                            step.get("send_mode"),
                            step.get("send_time"),
                            step.get("day_offset_workdays"),
                            step.get("target_field"),
                            step.get("launch_scenario_key"),
                            attachment_path,
                            attachment_filename,
                            int(bool(step.get("send_employee_card"))),
                            step.get("notify_on_send_text"),
                            step.get("notify_on_send_recipient_ids"),
                            step.get("notify_on_send_recipient_scope"),
                        ),
                    )
                    inserted_step_ids[step["step_key"]] = int(cursor.lastrowid)
                    progress_made = True

                if not progress_made and next_pending:
                    unresolved = ", ".join(step["step_key"] for step in next_pending)
                    raise RuntimeError(f"Could not resolve parent step references for: {unresolved}")
                pending_steps = next_pending

            for notification in scenario_item.get("button_notifications", []):
                step_id = inserted_step_ids.get(notification["step_key"])
                if not step_id:
                    raise RuntimeError(
                        f"Button notification refers to unknown step_key: {notification['step_key']}"
                    )
                connection.execute(
                    """
                    INSERT INTO step_button_notifications (
                        flow_key, step_id, option_index, message_text, recipient_ids, recipient_scope
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        scenario_key,
                        step_id,
                        notification.get("option_index"),
                        notification.get("message_text"),
                        notification.get("recipient_ids"),
                        notification.get("recipient_scope"),
                    ),
                )

            imported += 1

        connection.commit()

    print(f"Imported {imported} scenario(s) into {db_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export/import editable scenarios, steps, button notifications, and step attachments."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    export_parser = subparsers.add_parser("export", help="Export scenarios into a portable package directory.")
    export_parser.add_argument("--db", required=True, help="Path to source SQLite database.")
    export_parser.add_argument("--out", required=True, help="Output directory for the export package.")
    export_parser.add_argument(
        "--scenario-key",
        action="append",
        required=True,
        help="Scenario key to export. Can be passed multiple times or as a comma-separated list.",
    )

    import_parser = subparsers.add_parser("import", help="Import scenarios from a portable package directory.")
    import_parser.add_argument("--db", required=True, help="Path to target SQLite database.")
    import_parser.add_argument("--in", dest="input_dir", required=True, help="Input export package directory.")
    import_parser.add_argument(
        "--storage-root",
        default="storage/scenario_step_files",
        help="Root directory for imported step attachments.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "export":
        export_scenarios(
            db_path=Path(args.db).resolve(),
            output_dir=Path(args.out).resolve(),
            scenario_keys=_normalize_scenario_keys(args.scenario_key),
        )
        return

    if args.command == "import":
        import_scenarios(
            db_path=Path(args.db).resolve(),
            input_dir=Path(args.input_dir).resolve(),
            storage_root=Path(args.storage_root).resolve(),
        )
        return

    raise RuntimeError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
