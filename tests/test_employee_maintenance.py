import unittest
from datetime import UTC, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, _ensure_sqlite_schema
from app.config import settings
from app.employee_activity import employee_activity, utc_datetime
from app.models import (
    AdminAccount, Employee, EmployeeAssignmentHistory, EmployeeFile, EmployeeHrNote,
    EmployeeManualBotMessage, FlowLaunchRequest, GradeAssessment, OnboardingEvent,
)
from app.web.employee_routes import get_db, router
from app.web.employees import (
    _serialize_employee_file, _serialize_hr_notes_history,
    _serialize_manual_bot_message_history, _sync_hr_note_history,
)


class EmployeeMaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.at = datetime(2026, 10, 27, 10)
        self.db.add_all([
            Employee(id=1, full_name="One", created_at=self.at),
            Employee(id=2, full_name="Two", created_at=self.at),
            AdminAccount(id=1, login="operator", password_hash="unused", role="hr",
                         created_at=self.at, updated_at=self.at),
        ])
        self.db.commit()
        api = FastAPI()
        api.include_router(router)

        @api.middleware("http")
        async def auth(request, call_next):
            if request.headers.get("x-test-auth"):
                request.state.current_user = SimpleNamespace(id=1, role="hr")
            return await call_next(request)

        def session():
            yield self.db

        api.dependency_overrides[get_db] = session
        self.client = TestClient(api)
        self.auth = {"x-test-auth": "yes"}

    def tearDown(self):
        self.client.close()
        self.db.close()
        self.engine.dispose()

    def seed_records(self, count=1):
        for index in range(count):
            self.db.add(EmployeeHrNote(employee_id=1, note_text=f"private-note-{index}",
                                       author_account_id=1, created_at=self.at))
            self.db.add(EmployeeManualBotMessage(employee_id=1, message_text=f"private-message-{index}",
                       sender_account_id=1, status="sent", error_text="private-error", sent_at=self.at, created_at=self.at))
        self.db.commit()

    def test_auth_employee_bound_and_idempotent_deletion(self):
        self.seed_records()
        for resource in ("hr-notes", "bot-messages"):
            path = f"/api/employees/1/{resource}"
            self.assertEqual(self.client.get(path).status_code, 401)
            self.assertEqual(self.client.delete(path + "/1").status_code, 401)
            self.assertEqual(self.client.delete(f"/api/employees/2/{resource}/1", headers=self.auth).status_code, 404)
            self.assertEqual(self.client.delete(f"/api/employees/999/{resource}/1", headers=self.auth).status_code, 404)
            self.assertEqual(self.client.delete(path + "/1", headers=self.auth).json(), {"success": True})
            model = EmployeeHrNote if resource == "hr-notes" else EmployeeManualBotMessage
            self.db.expire_all()
            first = self.db.get(model, 1).deleted_at
            self.client.delete(path + "/1", headers=self.auth)
            self.db.expire_all()
            row = self.db.get(model, 1)
            self.assertEqual(row.deleted_at, first)
            self.assertEqual(row.deleted_by_account_id, 1)
            self.assertEqual(self.client.get(path, headers=self.auth).json()["total"], 0)
        message = self.db.get(EmployeeManualBotMessage, 1)
        self.assertEqual(message.message_text, "")
        self.assertIsNone(message.error_text)
        self.assertEqual(message.status, "sent")
        self.assertEqual(message.sent_at, self.at)
        self.assertEqual(self.db.get(EmployeeHrNote, 1).note_text, "")
        self.assertEqual(_serialize_hr_notes_history(self.db, 1), [])
        self.assertEqual(_serialize_manual_bot_message_history(self.db, 1), [])
        history = self.client.get("/api/employees/1/activity", headers=self.auth).json()
        self.assertEqual(history["total"], 4)
        self.assertNotIn("private-", str(history))
        self.assertEqual(sum(item["id"].endswith(":deleted") for item in history["items"]), 2)
        self.assertTrue(all(item["actor"] == "operator" for item in history["items"]))

    def test_pagination_defaults_bounds_and_order(self):
        self.seed_records(23)
        for resource, size in (("hr-notes", 10), ("bot-messages", 20)):
            path = f"/api/employees/1/{resource}"
            first = self.client.get(path, headers=self.auth).json()
            self.assertEqual((first["total"], first["page"], first["page_size"], first["pages"]),
                             (23, 1, size, (23 + size - 1) // size))
            self.assertEqual([item["id"] for item in first["items"]], list(range(23, 23 - size, -1)))
            second = self.client.get(path + "?page=2&page_size=10", headers=self.auth).json()
            self.assertEqual([item["id"] for item in second["items"]], list(range(13, 3, -1)))
            self.assertEqual(self.client.get(path + "?page=50", headers=self.auth).json()["items"], [])
            for query in ("page=0", "page_size=0", "page_size=101"):
                self.assertEqual(self.client.get(path + "?" + query, headers=self.auth).status_code, 422)
        self.assertEqual(self.client.get("/api/employees/2/hr-notes", headers=self.auth).json()["pages"], 0)

    def test_activity_only_stored_facts_and_stable_sort(self):
        self.seed_records(2)
        self.db.add_all([
            EmployeeFile(employee_id=1, direction="inbound", category="resume", original_filename="cv.pdf",
                         stored_path="unused", created_at=self.at),
            FlowLaunchRequest(employee_id=1, flow_key="future", requested_at=self.at + timedelta(days=10)),
            FlowLaunchRequest(employee_id=1, flow_key="processed", requested_at=self.at, processed_at=self.at),
            OnboardingEvent(employee_id=1, event_key="pending", scheduled_at=self.at, message="unused"),
            OnboardingEvent(employee_id=1, event_key="sent", scheduled_at=self.at, sent_at=self.at, message="unused"),
        ])
        self.db.commit()
        path = "/api/employees/1/activity"
        self.assertEqual(self.client.get(path).status_code, 401)
        self.assertEqual(self.client.get(path + "?kind=unknown", headers=self.auth).status_code, 422)
        first = self.client.get(path, headers=self.auth).json()
        self.assertEqual(first, self.client.get(path, headers=self.auth).json())
        self.assertEqual(first["total"], 7)
        self.assertTrue(all(item["occurred_at"].endswith("+00:00") for item in first["items"]))
        self.assertEqual([item["id"] for item in first["items"]], sorted((item["id"] for item in first["items"]), reverse=True))
        self.assertTrue(all(item["actor"] is None for item in first["items"] if item["kind"] in ("file", "launch", "onboarding")))
        self.assertNotIn("future", str(first))
        filtered = self.client.get(path + "?kind=note&page_size=1&page=2", headers=self.auth).json()
        self.assertEqual((filtered["total"], filtered["pages"], len(filtered["items"])), (2, 2, 1))
        self.assertEqual(employee_activity(self.db, 2, 1, 20, "all")["items"], [])

    def test_timezone_normalization(self):
        self.assertEqual(utc_datetime(self.at), self.at.replace(tzinfo=UTC))
        self.assertEqual(utc_datetime(self.at.replace(tzinfo=timezone(timedelta(hours=3)))),
                         (self.at - timedelta(hours=3)).replace(tzinfo=UTC))

    def test_file_metadata_is_additive_and_utc(self):
        row = EmployeeFile(id=7, employee_id=1, direction="inbound", category="resume",
                           original_filename="cv.pdf", created_at=self.at, mime_type="application/pdf", file_size=123)
        payload = _serialize_employee_file(row, 1, False)
        self.assertEqual(payload["created_at"], "2026-10-27T10:00:00+00:00")
        self.assertEqual(payload["mime_type"], "application/pdf")
        self.assertEqual(payload["file_size"], 123)
        self.assertIn("created_at_label", payload)
        self.assertEqual(payload["download_url"], "/employees/1/files/7/download")

    def test_note_delete_clears_matching_projection_without_recreation(self):
        self.seed_records(2)
        employee = self.db.get(Employee, 1)
        employee.notes = "private-note-1"
        self.db.commit()
        self.client.delete("/api/employees/1/hr-notes/1", headers=self.auth)
        self.db.refresh(employee)
        self.assertEqual(employee.notes, "private-note-1")
        self.client.delete("/api/employees/1/hr-notes/2", headers=self.auth)
        self.db.refresh(employee)
        self.assertIsNone(employee.notes)
        _sync_hr_note_history(self.db, employee=employee, previous_notes=employee.notes,
                             next_notes=employee.notes, author_account_id=1)
        self.db.commit()
        self.assertEqual(self.db.query(EmployeeHrNote).count(), 2)
        self.assertEqual(_serialize_hr_notes_history(self.db, 1), [])
        self.assertIn("all", [item["value"] for item in employee_activity(self.db, 1, 1, 20, "all")["kinds"]])

    def test_stale_profile_save_does_not_resurrect_deleted_note(self):
        self.seed_records()
        employee = self.db.get(Employee, 1)
        employee.notes = "private-note-0"
        self.db.commit()
        old_revision = self.client.get("/api/employees/1", headers=self.auth).json()["employee"]["notes_revision"]
        stale_payload = {"full_name": "Updated", "notes": "  private-note-0  ", "employee_stage": "candidate"}
        self.assertEqual(self.client.delete("/api/employees/1/hr-notes/1", headers=self.auth).status_code, 200)
        response = self.client.post("/api/employees/1", headers=self.auth, json=stale_payload)
        self.assertEqual(response.status_code, 200, response.text)
        self.db.refresh(employee)
        self.assertIsNone(employee.notes)
        self.assertEqual(employee.full_name, "Updated")
        self.assertEqual(self.db.query(EmployeeHrNote).count(), 1)
        row = self.db.get(EmployeeHrNote, 1)
        self.assertEqual(row.note_text, "")
        self.assertNotIn("deleted_text_digest", EmployeeHrNote.__table__.columns)
        deleted_revision = response.json()["employee"]["notes_revision"]
        self.assertNotEqual(old_revision, deleted_revision)
        with patch.object(settings, "ADMIN_SESSION_SECRET", "rotated-test-secret"):
            stale_payload["expected_notes_revision"] = old_revision
            response = self.client.post("/api/employees/1", headers=self.auth, json=stale_payload)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["employee"]["notes_revision"], deleted_revision)
            self.assertEqual(response.json()["employee"]["notes"], "")
        # A stale deleted value must also not overwrite a newer projection.
        employee.notes = "new current note"
        self.db.commit()
        response = self.client.post("/api/employees/1", headers=self.auth, json=stale_payload)
        self.assertEqual(response.status_code, 200, response.text)
        self.db.refresh(employee)
        self.assertEqual(employee.notes, "new current note")
        self.assertEqual(self.db.query(EmployeeHrNote).count(), 1)

    def test_matching_revision_allows_legacy_change_and_explicit_draft_bypasses_stale(self):
        self.seed_records()
        self.client.delete("/api/employees/1/hr-notes/1", headers=self.auth)
        revision = self.client.get("/api/employees/1", headers=self.auth).json()["employee"]["notes_revision"]
        response = self.client.post("/api/employees/1", headers=self.auth, json={
            "full_name": "One", "notes": "fresh note", "expected_notes_revision": revision})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["employee"]["notes"], "fresh note")
        self.assertNotEqual(response.json()["employee"]["notes_revision"], revision)
        response = self.client.post("/api/employees/1", headers=self.auth, json={
            "full_name": "One", "notes": "stale", "expected_notes_revision": revision,
            "hr_note_draft": "private-note-0"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["employee"]["notes"], "private-note-0")
        self.assertEqual(self.db.query(EmployeeHrNote).count(), 3)

    def test_list_timestamps_are_explicit_utc(self):
        self.seed_records()
        for resource in ("hr-notes", "bot-messages"):
            item = self.client.get(f"/api/employees/1/{resource}", headers=self.auth).json()["items"][0]
            self.assertEqual(item["created_at"], "2026-10-27T10:00:00+00:00")
            if resource == "bot-messages":
                self.assertEqual(item["sent_at"], "2026-10-27T10:00:00+00:00")

    def test_assignment_and_grade_events_do_not_invent_actors(self):
        self.db.add_all([
            EmployeeAssignmentHistory(subject_employee_id=1, assigned_employee_id=2,
                assignment_role="manager", assigned_by_account_id=1, started_at=self.at,
                ended_at=self.at + timedelta(days=1), created_at=self.at),
            GradeAssessment(employee_id=1, specialization_id=1, assessor_admin_account_id=1,
                status="final", created_at=self.at, updated_at=self.at,
                finalized_at=self.at + timedelta(days=1), archived_at=self.at + timedelta(days=2)),
        ])
        self.db.commit()
        history = employee_activity(self.db, 1, 1, 20, "all")
        self.assertEqual(history["total"], 5)
        self.assertEqual(history["items"][0]["id"], "grade:1:archived")
        for item in history["items"]:
            self.assertEqual(item["actor"], None if item["id"].endswith((":ended", ":finalized", ":archived")) else "operator")
        self.assertEqual(employee_activity(self.db, 1, 1, 20, "grade")["total"], 3)

    def test_legacy_schema_adds_nullable_deletion_columns_idempotently(self):
        self.seed_records()
        self.db.close()
        with self.engine.begin() as conn:
            for table in ("employee_hr_notes", "employee_manual_bot_messages"):
                for column in ("deleted_at", "deleted_by_account_id"):
                    conn.execute(text(f"ALTER TABLE {table} DROP COLUMN {column}"))
        with patch("app.database.engine", self.engine):
            _ensure_sqlite_schema()
            _ensure_sqlite_schema()
        for model in (EmployeeHrNote, EmployeeManualBotMessage):
            row = self.db.get(model, 1)
            self.assertIsNone(row.deleted_at)
            self.assertIsNone(row.deleted_by_account_id)
        self.assertEqual(self.db.get(EmployeeHrNote, 1).note_text, "private-note-0")
