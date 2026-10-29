from datetime import datetime
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient

from app.auth import authenticate_account, create_admin_session_token
from app.database import SessionLocal, init_db
from app.main import AUTH_COOKIE_NAME, app
from app.models import Employee, EmployeeDocumentLink, EmployeeFile
from app.web.upload_limits import read_web_upload


class UploadReadTests(unittest.IsolatedAsyncioTestCase):
    async def test_exact_limit_and_unknown_size(self):
        with patch("app.web.upload_limits.settings.WEB_UPLOAD_MAX_BYTES", 8):
            self.assertEqual(await read_web_upload(UploadFile(BytesIO(b"12345678"), filename="data.bin")), b"12345678")

    async def test_reported_oversize_is_rejected_before_read(self):
        upload = UploadFile(BytesIO(b"x"), filename="data.bin", size=9)
        upload.read = AsyncMock()
        with patch("app.web.upload_limits.settings.WEB_UPLOAD_MAX_BYTES", 8):
            with self.assertRaises(HTTPException) as caught:
                await read_web_upload(upload)
            self.assertEqual(caught.exception.status_code, 413)
            upload.read.assert_not_awaited()

    async def test_underreported_size_does_not_bypass_bounded_read(self):
        upload = UploadFile(BytesIO(b"123456789"), filename="data.bin", size=1)
        with patch("app.web.upload_limits.settings.WEB_UPLOAD_MAX_BYTES", 8):
            with self.assertRaises(HTTPException) as caught:
                await read_web_upload(upload)
            self.assertEqual(caught.exception.status_code, 413)
            self.assertEqual(upload.file.tell(), 9)

    async def test_invalid_limit_fails_closed(self):
        with patch("app.web.upload_limits.settings.WEB_UPLOAD_MAX_BYTES", 0):
            with self.assertRaises(HTTPException) as caught:
                await read_web_upload(UploadFile(BytesIO(b"x"), filename="data.bin"))
            self.assertEqual(caught.exception.status_code, 503)

    async def test_oversized_step_attachment_preserves_previous_file(self):
        from app.web.scenarios import _save_step_attachment
        with TemporaryDirectory() as directory:
            old = Path(directory) / "old.pdf"
            old.write_bytes(b"old")
            step = SimpleNamespace(flow_key="fixture", step_key="file", attachment_path=str(old), attachment_filename="old.pdf")
            with patch("app.web.upload_limits.settings.WEB_UPLOAD_MAX_BYTES", 8), patch(
                "app.config.settings.FILE_STORAGE_DIR", str(Path(directory) / "files")
            ), patch("app.web.scenarios._delete_step_attachment_file") as remove:
                with self.assertRaises(HTTPException) as caught:
                    await _save_step_attachment(step, UploadFile(BytesIO(b"123456789"), filename="new.pdf"))
                self.assertEqual(caught.exception.status_code, 413)
                remove.assert_not_called()
            self.assertEqual(step.attachment_path, str(old))
            self.assertEqual(old.read_bytes(), b"old")


class UploadEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)
        with SessionLocal() as db:
            account = authenticate_account(db, "admin", "admin123")
            cls.client.cookies.set(AUTH_COOKIE_NAME, create_admin_session_token(account.id))

    def setUp(self):
        self.storage = TemporaryDirectory()
        self.storage_patch = patch("app.config.settings.FILE_STORAGE_DIR", str(Path(self.storage.name) / "files"))
        self.storage_patch.start()
        with SessionLocal() as db:
            employee = Employee(full_name="Upload fixture", created_at=datetime(2026, 10, 29))
            db.add(employee)
            db.commit()
            self.employee_id = employee.id

    def tearDown(self):
        self.storage_patch.stop()
        self.storage.cleanup()

    def test_oversized_replacement_preserves_resume_and_storage(self):
        url = f"/api/employees/{self.employee_id}/document-slots/resume/file"
        with patch("app.web.upload_limits.settings.WEB_UPLOAD_MAX_BYTES", 8):
            first = self.client.post(url, files={"upload": ("resume.pdf", b"%PDF-1", "application/pdf")})
            self.assertEqual(first.status_code, 200)
            with SessionLocal() as db:
                old_id = db.query(EmployeeDocumentLink).filter_by(employee_id=self.employee_id, slot_key="resume").one().employee_file_id
                old_path = Path(db.get(EmployeeFile, old_id).stored_path)
            before = set(Path(self.storage.name).rglob("*"))
            response = self.client.post(url, files={"upload": ("new.pdf", b"123456789", "application/pdf")})
            self.assertEqual(response.status_code, 413)
            with SessionLocal() as db:
                self.assertEqual(db.query(EmployeeDocumentLink).filter_by(employee_id=self.employee_id, slot_key="resume").one().employee_file_id, old_id)
                self.assertEqual(db.query(EmployeeFile).filter_by(employee_id=self.employee_id).count(), 1)
            self.assertEqual(old_path.read_bytes(), b"%PDF-1")
            self.assertEqual(before, set(Path(self.storage.name).rglob("*")))

    def test_generic_library_and_profile_reject_oversized_uploads(self):
        urls = [f"/employees/{self.employee_id}/files", f"/employees/{self.employee_id}/profile-photo", "/api/documents/files"]
        with patch("app.web.upload_limits.settings.WEB_UPLOAD_MAX_BYTES", 8):
            for url in urls:
                response = self.client.post(url, files={"upload": ("large.bin", b"123456789", "application/octet-stream")})
                self.assertEqual(response.status_code, 413, url)
        self.assertFalse(any(path.is_file() for path in Path(self.storage.name).rglob("*")))

    def test_download_is_attachment_with_nosniff_even_for_html(self):
        response = self.client.post(f"/employees/{self.employee_id}/files", files={"upload": ("example.html", b"<p>file</p>", "text/html")})
        self.assertEqual(response.status_code, 200)
        with SessionLocal() as db:
            file_id = db.query(EmployeeFile).filter_by(employee_id=self.employee_id).one().id
        downloaded = self.client.get(f"/employees/{self.employee_id}/files/{file_id}/download")
        self.assertEqual(downloaded.status_code, 200)
        self.assertEqual(downloaded.headers["x-content-type-options"], "nosniff")
        self.assertTrue(downloaded.headers["content-disposition"].startswith("attachment;"))
