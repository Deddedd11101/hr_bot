"""Disposable loopback preview with synthetic data; never starts a bot worker."""

import os
import secrets
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
directory = Path(tempfile.mkdtemp(prefix="hrbot-vacation-preview-"))
os.environ.update(DATABASE_URL=f"sqlite:///{directory / 'preview.db'}",
                  TELEGRAM_BOT_TOKEN="123456:local-preview-no-delivery",
                  ADMIN_SESSION_SECRET=secrets.token_hex(32),
                  DEFAULT_ADMIN_LOGIN="preview", DEFAULT_ADMIN_PASSWORD="Local-preview-vacation-only!",
                  DEFAULT_HR_PASSWORD="Local-preview-hr-only!", STAFF_EMAIL_OTP_ENABLED="false",
                  FILE_STORAGE_DIR=str(directory / "files"), ADMIN_SESSION_COOKIE_SECURE="false",
                  DOTENV_OVERRIDE="false")

from app.database import SessionLocal, init_db  # noqa: E402
from app.models import Employee, AdminAccount  # noqa: E402
from app.time_utils import utc_now  # noqa: E402
from app.vacation import BalanceInput, save_balance  # noqa: E402
from app.vacation_accounts import AccountInput, save_account, today  # noqa: E402
from app.vacation_accounting import LeaveKind  # noqa: E402
from app.vacation_ledger import append_operation  # noqa: E402

init_db()
with SessionLocal() as db:
    account = db.query(AdminAccount).filter_by(login="preview").one()
    db.add(Employee(id=1, full_name="Тестовый сотрудник", desired_position="Системный аналитик",
                    first_workday=date(2026, 11, 9), created_at=utc_now(), employee_stage="staff"))
    db.flush()
    save_account(db, 1, account.id, AccountInput(contract_key="demo-contract",
        employed_on=date(2025, 4, 17), reviewed_through=today(), revision=0,
        reason="Синтетические данные локального предпросмотра"))
    for kind, amount in ((LeaveKind.ANNUAL, "28"), (LeaveKind.FORCE_MAJEURE, "5"), (LeaveKind.DAY_OFF, "8.5")):
        append_operation(db, employee_id=1, contract_key="demo-contract", kind=kind,
            operation="opening", operation_key="opening", amount=amount,
            effective_on=date(2026, 9, 30), actor="local-preview", reason="Тестовый входящий остаток")
    append_operation(db, employee_id=1, contract_key="demo-contract", kind=LeaveKind.ANNUAL,
        operation="reserve", operation_key="demo-reserve", amount=7, reservation_key="demo-request:v1",
        effective_on=date(2026, 11, 1), actor="local-preview", reason="Тестовый резерв")
    save_balance(db, 1, account.id, BalanceInput(year=today().year, used_days=7, remaining_days=21))
    db.commit()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8046)
