import json
import unittest
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from fastapi.testclient import TestClient

from app.auth import authenticate_account, create_admin_session_token
from app.database import SessionLocal, init_db
from app.main import AUTH_COOKIE_NAME, app
from app.models import Employee, GradeAssessment, GradeSkill
from app.time_utils import utc_now


class GradesApiSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)
        with SessionLocal() as db:
            admin = authenticate_account(db, "admin", "admin123")
            cls.token = create_admin_session_token(admin.id)
        cls.client.cookies.set(AUTH_COOKIE_NAME, cls.token)

    def setUp(self):
        self.tag = uuid4().hex[:10]
        with SessionLocal() as db:
            employee = Employee(full_name=f"Grade test {self.tag}", created_at=utc_now(), employee_stage="staff")
            db.add(employee)
            db.commit()
            self.employee_id = employee.id

    def workspace(self):
        response = self.client.get("/api/grades/workspace")
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def create(self, kind, payload):
        response = self.client.post(f"/api/grades/{kind}", json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        return next(row for row in response.json()[kind] if row["name"] == payload["name"])

    def fixture(self):
        specialization = self.create("specializations", {"name": f"Design {self.tag}", "slug": f"design-{self.tag}"})
        category = self.create("categories", {"name": f"Category {self.tag}"})
        skill = self.create("skills", {"name": f"Skill {self.tag}", "category_id": category["id"]})
        grades = self.workspace()["grades"]
        junior = next(row for row in grades if row["slug"] == "junior")
        middle = next(row for row in grades if row["slug"] == "middle")
        result = self.client.put("/api/grades/matrix", json={
            "specialization_id": specialization["id"],
            "rows": [{"skill_id": skill["id"], "importance": 3, "levels": {row["slug"]: 3 for row in grades}}],
        })
        self.assertEqual(result.status_code, 200, result.text)
        result = self.client.put(f"/api/employees/{self.employee_id}/grade", json={
            "specialization_id": specialization["id"], "current_grade_id": junior["id"],
            "target_grade_id": middle["id"], "target_specialization_id": None,
        })
        self.assertEqual(result.status_code, 200, result.text)
        return specialization, category, skill

    def draft(self):
        response = self.client.post(f"/api/employees/{self.employee_id}/grade/assessments", json={})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_auth_and_route_contract(self):
        anon = TestClient(app)
        self.assertEqual(anon.get("/api/grades/workspace").status_code, 401)
        self.assertEqual(anon.put(f"/api/employees/{self.employee_id}/grade", json={}).status_code, 401)
        self.assertEqual(anon.post("/api/grade-assessments/1/finalize", json={}).status_code, 401)
        self.assertEqual(anon.get("/app/grades", follow_redirects=False).status_code, 303)
        self.assertEqual(self.client.get("/grades", follow_redirects=False).headers["location"], "/app/grades")
        paths = app.openapi()["paths"]
        for kind in ("grades", "specializations", "categories", "skills"):
            self.assertIn("post", paths[f"/api/grades/{kind}"])
            for method in ("put", "delete"):
                self.assertIn(method, paths[f"/api/grades/{kind}/{{item_id}}"])
        for path in ("/api/grades/matrix", "/api/grades/import", "/api/employees/{employee_id}/grade",
                     "/api/employees/{employee_id}/grade/assessments", "/api/grade-assessments/{assessment_id}",
                     "/api/grade-assessments/{assessment_id}/finalize"):
            self.assertIn(path, paths)

    def test_empty_profile_get_does_not_create_profile(self):
        response = self.client.get(f"/api/employees/{self.employee_id}/grade")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIsNone(response.json()["profile"])
        self.assertEqual(self.client.get("/api/employees/99999999/grade").status_code, 404)
        self.assertEqual(self.client.post(f"/api/employees/{self.employee_id}/grade/assessments", json={}).status_code, 422)

    def test_crud_defaults_and_validation(self):
        spec, _, skill = self.fixture()
        ws = self.workspace()
        importance = next(row for row in ws["importances"] if row["skill_id"] == skill["id"] and row["specialization_id"] == spec["id"])
        self.assertEqual(importance["importance"], 3)
        for level in (-1, 5, 1.5, True):
            result = self.client.put("/api/grades/matrix", json={"specialization_id": spec["id"], "rows": [
                {"skill_id": skill["id"], "importance": 2, "levels": {"junior": level}}]})
            self.assertEqual(result.status_code, 422, result.text)
        self.assertEqual(self.workspace()["importances"], ws["importances"])
        response = self.client.delete(f"/api/grades/skills/{skill['id']}")
        self.assertEqual(response.status_code, 200, response.text)
        with SessionLocal() as db:
            self.assertFalse(db.get(GradeSkill, skill["id"]).active)

    def test_assessment_finalize_is_immutable_and_reuses_values(self):
        _, _, skill = self.fixture()
        draft = self.draft()
        self.assertEqual(self.draft()["id"], draft["id"])
        url = f"/api/grade-assessments/{draft['id']}"
        result = self.client.patch(url, json={"values": [{"skill_id": skill["id"], "level": 2}]})
        self.assertEqual(result.status_code, 200, result.text)
        final = self.client.post(url + "/finalize", json={})
        self.assertEqual(final.status_code, 200, final.text)
        frozen = final.json()
        self.assertEqual(frozen["status"], "final")
        self.assertEqual(self.client.post(url + "/finalize", json={}).json(), frozen)
        self.assertIn(self.client.patch(url, json={"values": []}).status_code, (409, 422))
        rename = self.client.put(f"/api/grades/skills/{skill['id']}", json={"name": f"Renamed {self.tag}"})
        self.assertEqual(rename.status_code, 200, rename.text)
        self.assertEqual(self.client.get(url).json(), frozen)
        with SessionLocal() as db:
            self.assertIsInstance(json.loads(db.get(GradeAssessment, draft["id"]).catalog_snapshot), dict)
        next_draft = self.draft()
        self.assertNotEqual(next_draft["id"], draft["id"])
        self.assertEqual(next(score["currentLevel"] for score in next_draft["scores"] if score["skillId"] == skill["id"]), 2)

    def test_reject_foreign_skill_and_bad_levels(self):
        _, _, skill = self.fixture()
        draft = self.draft()
        url = f"/api/grade-assessments/{draft['id']}"
        for value in (-1, 5, 1.5, True):
            response = self.client.patch(url, json={"values": [{"skill_id": skill["id"], "level": value}]})
            self.assertEqual(response.status_code, 422, response.text)
        self.assertIn(self.client.patch(url, json={"values": [{"skill_id": 99999999, "level": 1}]}).status_code, (404, 422))

    def test_concurrent_draft_creation_returns_one_session(self):
        self.fixture()
        def create():
            with TestClient(app) as client:
                client.cookies.set(AUTH_COOKIE_NAME, self.token)
                return client.post(f"/api/employees/{self.employee_id}/grade/assessments", json={})
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: create(), range(2)))
        self.assertEqual([r.status_code for r in results], [200, 200])
        self.assertEqual(results[0].json()["id"], results[1].json()["id"])

    def test_import_dry_run_atomic_validation_and_apply(self):
        catalog = {"specialization": {"name": f"Import {self.tag}"}, "categories": [
            {"name": f"Imported category {self.tag}", "skills": [{"name": "Visual hierarchy", "importance": "critical",
             "levels": {row["slug"]: "2" for row in self.workspace()["grades"]}}]}]}
        request = {"dryRun": True, "mode": "create-specialization", "catalog": catalog}
        before = self.workspace()
        response = self.client.post("/api/grades/import", json=request)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.workspace(), before)
        request["dryRun"] = False
        response = self.client.post("/api/grades/import", json=request)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(any(row["name"] == catalog["specialization"]["name"] for row in self.workspace()["specializations"]))
        saved = self.workspace()
        catalog["categories"][0]["skills"][0]["levels"]["junior"] = 8
        response = self.client.post("/api/grades/import", json=request)
        self.assertIn(response.status_code, (200, 422))
        if response.status_code == 200:
            self.assertTrue(response.json().get("errors"))
        self.assertEqual(self.workspace(), saved)


if __name__ == "__main__":
    unittest.main()
