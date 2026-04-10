import argparse
import os
import sys
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LOCAL_SITE_PACKAGES = REPO_ROOT / ".venv" / "Lib" / "site-packages"
if str(LOCAL_SITE_PACKAGES) not in sys.path:
    sys.path.insert(0, str(LOCAL_SITE_PACKAGES))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sqlalchemy import create_engine, inspect


REQUIRED_SCHEMA = {
    "employees": [
        "id",
        "full_name",
        "telegram_user_id",
        "telegram_username",
        "first_workday",
        "birth_date",
        "desired_position",
        "work_email",
        "work_hours",
        "salary_expectation",
        "candidate_work_stage",
        "employee_stage",
        "manager_telegram_id",
        "mentor_adaptation_telegram_id",
        "mentor_ipr_telegram_id",
        "personal_data_consent",
        "employee_data_consent",
        "test_task_due_at",
        "notes",
        "is_flow_scheduled",
        "created_at",
    ],
    "employee_messenger_accounts": [
        "id",
        "employee_id",
        "channel",
        "external_user_id",
        "external_username",
        "is_primary",
        "is_active",
        "created_at",
        "updated_at",
    ],
    "employee_files": [
        "id",
        "employee_id",
        "direction",
        "original_filename",
        "created_at",
    ],
    "employee_document_links": [
        "id",
        "employee_id",
        "title",
        "url",
        "created_at",
    ],
    "flow_launch_requests": [
        "id",
        "employee_id",
        "flow_key",
        "requested_at",
        "processed_at",
        "launch_type",
    ],
    "scenario_templates": [
        "id",
        "scenario_key",
        "title",
        "scenario_kind",
    ],
}


def _build_engine(database_url: str):
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, connect_args=connect_args)


def _check_schema(database_url: str) -> int:
    issues = 0
    engine = _build_engine(database_url)
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    print(f"[schema] database_url={database_url}")
    for table_name, required_columns in REQUIRED_SCHEMA.items():
        if table_name not in tables:
            issues += 1
            print(f"[missing-table] {table_name}")
            continue

        actual_columns = {column["name"] for column in inspector.get_columns(table_name)}
        missing_columns = [column for column in required_columns if column not in actual_columns]
        if missing_columns:
            issues += 1
            print(f"[missing-columns] {table_name}: {', '.join(missing_columns)}")
        else:
            print(f"[ok] {table_name}")

    return issues


def _probe_payload(database_url: str, employee_ids: list[int]) -> int:
    os.environ.setdefault("TELEGRAM_BOT_TOKEN", "debug-dummy-token")
    os.environ["DATABASE_URL"] = database_url

    from app.database import get_session  # noqa: WPS433
    from app.main import _build_employee_detail_payload  # noqa: WPS433
    from app.models import Employee  # noqa: WPS433

    failures = 0
    with get_session() as db:
        if not employee_ids:
            employee_ids = [row[0] for row in db.query(Employee.id).order_by(Employee.id.asc()).all()]

    print(f"[probe] employee_ids={employee_ids}")
    for employee_id in employee_ids:
        try:
            with get_session() as db:
                employee = db.get(Employee, employee_id)
                if not employee:
                    print(f"[missing-employee] {employee_id}")
                    failures += 1
                    continue
                payload = _build_employee_detail_payload(db, employee)
                print(
                    "[ok-payload] "
                    f"id={employee_id} "
                    f"files={len(payload['files'])} "
                    f"links={len(payload['document_links'])} "
                    f"scheduled={len(payload['scheduled_launches'])} "
                    f"history={len(payload['manual_launch_history'])}"
                )
        except Exception as exc:  # pragma: no cover - debugging entrypoint
            failures += 1
            print(f"[payload-error] id={employee_id} type={type(exc).__name__} error={exc}")
            traceback.print_exc()

    return failures


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check DB compatibility for GET /api/employees/{id} and optionally probe payload building."
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL", "sqlite:///./hr_bot.db"),
        help="SQLAlchemy database URL. Defaults to DATABASE_URL or sqlite:///./hr_bot.db",
    )
    parser.add_argument(
        "--probe-payload",
        action="store_true",
        help="Import app code and run _build_employee_detail_payload for selected employees.",
    )
    parser.add_argument(
        "--employee-id",
        action="append",
        dest="employee_ids",
        type=int,
        default=[],
        help="Employee id to probe. Can be passed multiple times. If omitted with --probe-payload, all employees are checked.",
    )
    args = parser.parse_args()

    issues = _check_schema(args.database_url)
    if args.probe_payload:
        issues += _probe_payload(args.database_url, args.employee_ids)

    if issues:
        print(f"[result] issues={issues}")
        return 1

    print("[result] ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
