import unittest
from datetime import UTC, datetime
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.auth import authenticate_account, create_admin_session_token
from app.config import settings
from app.database import SessionLocal, init_db
from app.main import AUTH_COOKIE_NAME, app
from app.models import Employee, Position
from app.web.integrations import bearer_token_matches

SYNC_TOKEN = "test-pulse-sync-token-" + uuid4().hex


class PulseIntegrationApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        init_db()
        cls.client = TestClient(app)

    def setUp(self) -> None:
        self.tag = uuid4().hex[:10]
        self.employee_ids: dict[str, int] = {}
        with SessionLocal() as db:
            position = Position(
                title=f"Старший дизайнер {self.tag}",
                slug=f"starshiy_dizayner_{self.tag}",
                is_active=True,
                sort_order=999,
                created_at=datetime.now(UTC).replace(tzinfo=None),
            )
            db.add(position)
            db.flush()
            self.position_id = position.id
            rows = {
                "staff": dict(employee_stage="staff", desired_position=position.title, work_email=" staff@example.com "),
                "adaptation": dict(employee_stage="adaptation", desired_position="Аналитик"),
                "ipr": dict(employee_stage="ipr", desired_position=None, is_manager=True),
                "candidate": dict(employee_stage="candidate", candidate_status="new"),
                "blocked": dict(employee_stage="staff", is_bot_blocked=True),
                "no_stage": dict(employee_stage=None),
            }
            for key, fields in rows.items():
                employee = Employee(
                    full_name=f"Pulse {key} {self.tag}",
                    first_name=key.capitalize(),
                    created_at=datetime.now(UTC).replace(tzinfo=None),
                    is_flow_scheduled=False,
                    **fields,
                )
                db.add(employee)
                db.flush()
                self.employee_ids[key] = employee.id
            db.commit()

    def tearDown(self) -> None:
        with SessionLocal() as db:
            db.query(Employee).filter(Employee.id.in_(list(self.employee_ids.values()))).delete(synchronize_session=False)
            db.query(Position).filter(Position.id == self.position_id).delete(synchronize_session=False)
            db.commit()

    def _get(self, token: str | None = None, **kwargs):
        headers = dict(kwargs.pop("headers", {}) or {})
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        return self.client.get("/api/integrations/pulse/employees", headers=headers, **kwargs)

    def _own_rows(self, payload: dict) -> dict[str, dict]:
        by_id = {row["id"]: row for row in payload["employees"]}
        return {key: by_id[employee_id] for key, employee_id in self.employee_ids.items() if employee_id in by_id}

    def test_returns_503_when_token_is_not_configured(self) -> None:
        with patch.object(settings, "PULSE_SYNC_TOKEN", ""):
            response = self._get(token=SYNC_TOKEN)
        self.assertEqual(response.status_code, 503)
        self.assertIn("PULSE_SYNC_TOKEN", response.json()["detail"])

    def test_rejects_missing_or_wrong_bearer_token(self) -> None:
        with patch.object(settings, "PULSE_SYNC_TOKEN", SYNC_TOKEN):
            missing = self._get()
            wrong = self._get(token="not-" + SYNC_TOKEN)
            basic = self._get(headers={"Authorization": f"Basic {SYNC_TOKEN}"})
        for response in (missing, wrong, basic):
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.headers.get("www-authenticate"), "Bearer")
            self.assertEqual(response.json(), {"detail": "Требуется авторизация"})

    def test_admin_session_cookie_does_not_replace_bearer_token(self) -> None:
        with SessionLocal() as db:
            account = authenticate_account(db, "admin", "admin123")
        self.assertIsNotNone(account)
        client = TestClient(app)
        client.cookies.set(AUTH_COOKIE_NAME, create_admin_session_token(account.id))
        with patch.object(settings, "PULSE_SYNC_TOKEN", SYNC_TOKEN):
            response = client.get("/api/integrations/pulse/employees")
        self.assertEqual(response.status_code, 401)

    def test_exports_only_working_stages_with_position_fields(self) -> None:
        with patch.object(settings, "PULSE_SYNC_TOKEN", SYNC_TOKEN):
            response = self._get(token=SYNC_TOKEN)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["source"], "hrbot")
        self.assertEqual(payload["employee_stages"], ["staff", "adaptation", "ipr"])
        self.assertTrue(payload["generated_at"].endswith("Z"))

        rows = self._own_rows(payload)
        self.assertEqual(set(rows), {"staff", "adaptation", "ipr"})

        staff = rows["staff"]
        self.assertEqual(staff["full_name"], f"Pulse staff {self.tag}")
        self.assertEqual(staff["first_name"], "Staff")
        self.assertEqual(staff["position_slug"], f"starshiy_dizayner_{self.tag}")
        self.assertEqual(staff["position_title"], f"Старший дизайнер {self.tag}")
        self.assertEqual(staff["employee_stage"], "staff")
        self.assertEqual(staff["work_email"], "staff@example.com")
        self.assertFalse(staff["is_manager"])
        self.assertFalse(staff["is_mentor"])

        adaptation = rows["adaptation"]
        self.assertEqual(adaptation["position_slug"], "analyst")
        self.assertEqual(adaptation["position_title"], "Аналитик")
        self.assertIsNone(adaptation["work_email"])

        ipr = rows["ipr"]
        self.assertIsNone(ipr["position_slug"])
        self.assertIsNone(ipr["position_title"])
        self.assertTrue(ipr["is_manager"])

        ids = [row["id"] for row in payload["employees"]]
        self.assertEqual(ids, sorted(ids))
        for row in payload["employees"]:
            self.assertEqual(
                set(row),
                {
                    "id",
                    "full_name",
                    "first_name",
                    "position_slug",
                    "position_title",
                    "employee_stage",
                    "work_email",
                    "is_manager",
                    "is_mentor",
                },
            )

    def test_bearer_token_matching_is_strict(self) -> None:
        self.assertTrue(bearer_token_matches("Bearer abc", "abc"))
        self.assertTrue(bearer_token_matches("bearer abc", "abc"))
        self.assertFalse(bearer_token_matches("Bearer abc ", "abc "))
        self.assertFalse(bearer_token_matches("Bearer ab", "abc"))
        self.assertFalse(bearer_token_matches("Bearer", "abc"))
        self.assertFalse(bearer_token_matches("Token abc", "abc"))
        self.assertFalse(bearer_token_matches(None, "abc"))
        self.assertFalse(bearer_token_matches("Bearer ", ""))

    def test_route_is_in_openapi_schema_with_integrations_tag(self) -> None:
        schema = app.openapi()
        operation = schema["paths"]["/api/integrations/pulse/employees"]["get"]
        self.assertEqual(operation["tags"], ["Integrations"])


if __name__ == "__main__":
    unittest.main()
