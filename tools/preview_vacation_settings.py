"""Disposable loopback preview with synthetic data; never starts a bot worker."""

import os
import secrets
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
directory = Path(tempfile.mkdtemp(prefix="hrbot-vacation-preview-"))
os.environ.update(DATABASE_URL=f"sqlite:///{directory / 'preview.db'}",
                  TELEGRAM_BOT_TOKEN="123456:local-preview-no-delivery",
                  ADMIN_SESSION_SECRET=secrets.token_hex(32),
                  DEFAULT_ADMIN_LOGIN="preview", DEFAULT_ADMIN_PASSWORD="Local-preview-vacation-only!",
                  DEFAULT_HR_PASSWORD="Local-preview-hr-only!", STAFF_EMAIL_OTP_ENABLED="true",
                  STAFF_EMAIL_SMTP_PASSWORD="", EMPLOYEE_CABINET_URL="http://127.0.0.1:8048/employee-cabinet",
                  FILE_STORAGE_DIR=str(directory / "files"), ADMIN_SESSION_COOKIE_SECURE="false",
                  DOTENV_OVERRIDE="false")

from app.database import SessionLocal, init_db  # noqa: E402
from app.models import Employee, AdminAccount, EmployeeVacationRequest, CatalogGroup, CatalogMembership, EmployeeTelegramEmailVerification  # noqa: E402
from app.messaging.identity import set_primary_chat_id  # noqa: E402
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
    db.add(CatalogGroup(id=1, scope="people", name="Аналитики", normalized_name="аналитики"))
    db.add(CatalogMembership(scope="people", object_id=1, group_id=1))
    db.add(Employee(id=2, full_name="Коллега для предпросмотра", employee_stage="staff", created_at=utc_now()))
    pilot = Employee(id=70, full_name="Пилотный сотрудник (демо)", work_email="preview@ze.studio",
                     employee_stage="staff", created_at=utc_now())
    db.add(pilot)
    db.flush()
    set_primary_chat_id(pilot, "123456789", db=db)
    db.add(EmployeeTelegramEmailVerification(employee_id=70, verified_at=utc_now(),
        verified_telegram_user_id="123456789", verified_work_email="preview@ze.studio"))
    for employee_id, offset in ((1, 0), (2, 3)):
        db.add(EmployeeVacationRequest(employee_id=employee_id, starts_on=today() + timedelta(days=offset),
            ends_on=today() + timedelta(days=offset + 7), workdays=5, status="approved", created_at=utc_now()))
    for employee_id, month in ((1, 4), (2, 7)):
        db.add(EmployeeVacationRequest(employee_id=employee_id, starts_on=date(today().year, month, 5),
            ends_on=date(today().year, month, 19), workdays=10, status="approved", created_at=utc_now()))
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
    import hashlib
    import hmac
    import json
    import time
    from urllib.parse import urlencode
    import uvicorn
    from fastapi.responses import HTMLResponse
    from app.main import app

    @app.get("/local-cabinet", include_in_schema=False)
    def local_cabinet():
        fields = {"auth_date": str(int(time.time())), "user": json.dumps({"id": 123456789})}
        secret = hmac.digest(b"WebAppData", os.environ["TELEGRAM_BOT_TOKEN"].encode(), hashlib.sha256)
        check = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
        fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
        html = (ROOT / "app/static/employee-cabinet.html").read_text(encoding="utf-8")
        bootstrap = '<script>window.Telegram={WebApp:{initData:' + json.dumps(urlencode(fields)) + ',platform:"web",ready(){},expand(){}}};</script>'
        return HTMLResponse(html.replace('<script src="https://telegram.org/js/telegram-web-app.js"></script>', bootstrap), headers={"Cache-Control": "no-store"})

    uvicorn.run(app, host="127.0.0.1", port=8048)
