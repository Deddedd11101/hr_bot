import hashlib
import hmac
import json
import time
import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlencode

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.web import employee_cabinet as cabinet


class EmployeeCabinetTests(unittest.TestCase):
    @staticmethod
    def signed(now, user_id=123):
        fields = {"auth_date": str(now), "user": json.dumps({"id": user_id}), "signature": "opaque"}
        key = hmac.digest(b"WebAppData", b"test-token", hashlib.sha256)
        payload = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
        fields["hash"] = hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()
        return urlencode(fields)

    def test_signed_user_expiry_tampering_and_duplicate_fields(self):
        now = int(time.time())
        raw = self.signed(now)
        self.assertEqual(cabinet.signed_telegram_id(raw, "test-token", now), "123")
        self.assertIsNone(cabinet.signed_telegram_id(raw.replace("123", "124"), "test-token", now))
        self.assertIsNone(cabinet.signed_telegram_id(raw, "test-token", now + 1801))
        self.assertIsNone(cabinet.signed_telegram_id(raw + "&auth_date=0", "test-token", now))

    def test_pilot_requires_current_verified_binding_and_exact_card(self):
        employee = SimpleNamespace(id=70, employee_stage="staff", is_bot_blocked=False)
        with patch.object(cabinet.settings, "EMPLOYEE_CABINET_URL", "https://example.test/employee-cabinet"), \
                patch.object(cabinet, "find_employees_by_channel_user_id", return_value=[employee]), \
                patch.object(cabinet, "verification_required", return_value=True), \
                patch.object(cabinet, "is_verified", return_value=True) as verified, \
                patch.object(cabinet, "get_primary_chat_id", return_value="123"):
            self.assertIs(cabinet.pilot_employee(None, "123"), employee)
            self.assertIsNone(cabinet.pilot_employee(None, "456"))
            employee.id = 80
            self.assertIs(cabinet.pilot_employee(None, "123"), employee)
            employee.id = 84
            self.assertIs(cabinet.pilot_employee(None, "123"), employee)
            employee.id = 71
            self.assertIsNone(cabinet.pilot_employee(None, "123"))
            employee.id = 70
            verified.return_value = False
            self.assertIsNone(cabinet.pilot_employee(None, "123"))

    def test_public_shell_has_no_data_and_download_requires_auth(self):
        app = FastAPI()
        app.include_router(cabinet.router)
        with TestClient(app) as client:
            self.assertEqual(client.get("/employee-cabinet").status_code, 200)
            for path in ("profile", "files/1"):
                response = client.get(f"/employee-cabinet/{path}")
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.headers["cache-control"], "no-store")

    def test_download_enforces_owner_direction_and_storage_path(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            engine = create_engine(f"sqlite:///{(root / 'test.db').as_posix()}")
            cabinet.EmployeeFile.__table__.create(engine)
            sessions = sessionmaker(bind=engine)
            own = root / "70" / "own.txt"
            own.parent.mkdir()
            own.write_text("own file", encoding="utf-8")
            outside = root / "outside.txt"
            outside.write_text("outside", encoding="utf-8")
            with sessions() as db:
                for file_id, employee_id, direction, path in (
                    (1, 70, "inbound", own), (2, 71, "inbound", own),
                    (3, 70, "outbound", own), (4, 70, "inbound", outside),
                ):
                    db.add(cabinet.EmployeeFile(id=file_id, employee_id=employee_id, direction=direction,
                        category="file", original_filename=path.name, stored_path=str(path), created_at=datetime.now()))
                db.commit()
            app = FastAPI()
            app.include_router(cabinet.router)
            with patch.object(cabinet, "get_session", sessions), \
                    patch.object(cabinet.settings, "FILE_STORAGE_DIR", directory), \
                    patch.object(cabinet, "authorize", return_value=SimpleNamespace(id=70)), TestClient(app) as client:
                response = client.get("/employee-cabinet/files/1")
                self.assertEqual(response.content, b"own file")
                self.assertIn("attachment", response.headers["content-disposition"])
                for file_id in (2, 3, 4):
                    self.assertEqual(client.get(f"/employee-cabinet/files/{file_id}").status_code, 404)
            engine.dispose()
