import unittest
from datetime import datetime
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import CatalogGroup, CatalogMembership, Employee, ScenarioTemplate, ScenarioProgress
from app.web.catalog_groups import router, get_db


class CatalogGroupsTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        now = datetime(2026, 11, 9)
        self.db.add_all([Employee(id=1, full_name="Person", employee_stage="staff", created_at=now),
            ScenarioTemplate(id=1, scenario_key="group_test", title="Scenario", trigger_mode="manual_only", purpose="adaptation"),
            ScenarioProgress(employee_id=1, scenario_key="group_test", started_at=now, updated_at=now,
                waiting_for_response=True, is_completed=False, step_history="preserved")])
        self.db.commit()
        app = FastAPI()
        app.include_router(router)
        @app.middleware("http")
        async def user(request, call_next):
            if request.headers.get("x-test-user"):
                request.state.current_user = SimpleNamespace(id=int(request.headers["x-test-user"]), role="hr")
            return await call_next(request)
        def session():
            try:
                yield self.db
            finally:
                self.db.rollback()
        app.dependency_overrides[get_db] = session
        self.client = TestClient(app)
        self.headers = {"x-test-user": "1"}

    def tearDown(self):
        self.client.close()
        self.db.close()
        self.engine.dispose()

    def create(self, scope="people", name="Team"):
        response = self.client.post("/api/catalog-groups", headers=self.headers, json={"scope": scope, "name": name})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["created_group_id"]

    def move(self, scope, group, expected=None, object_id=1):
        return self.client.put("/api/catalog-group-membership", headers=self.headers,
            json={"scope": scope, "group_id": group, "object_id": object_id, "expected_group_id": expected})

    def test_auth_scope_and_name_validation(self):
        self.assertEqual(self.client.get("/api/catalog-groups?scope=people").status_code, 401)
        self.assertEqual(self.client.post("/api/catalog-groups", json={"scope": "people", "name": "One"}).status_code, 401)
        for name in (" ", "Все", "без группы"):
            self.assertEqual(self.client.post("/api/catalog-groups", headers=self.headers,
                json={"scope": "people", "name": name}).status_code, 422)
        self.assertEqual(self.client.get("/api/catalog-groups?scope=bad", headers=self.headers).status_code, 422)

    def test_common_groups_unique_names_and_rename_cas(self):
        group = self.create(name="  Team  Name ")
        duplicate = self.client.post("/api/catalog-groups", headers=self.headers, json={"scope": "people", "name": "team name"})
        self.assertEqual(duplicate.status_code, 409)
        other_user = self.client.get("/api/catalog-groups?scope=people", headers={"x-test-user": "2"}).json()
        self.assertEqual(other_user["groups"][0]["id"], group)
        url = f"/api/catalog-groups/{group}"
        self.assertEqual(self.client.patch(url, headers=self.headers, json={"scope": "people", "name": "Renamed", "expected_revision": 1}).status_code, 200)
        self.assertEqual(self.client.patch(url, headers=self.headers, json={"scope": "people", "name": "Stale", "expected_revision": 1}).status_code, 409)
        self.assertEqual(self.db.get(CatalogGroup, group).name, "Renamed")

    def test_move_is_single_group_and_checks_concurrent_membership(self):
        first, second = self.create(name="First"), self.create(name="Second")
        self.assertEqual(self.move("people", first).status_code, 200)
        self.assertEqual(self.move("people", second).status_code, 409)
        self.assertEqual(self.move("people", second, first).status_code, 200)
        self.assertEqual(self.db.query(CatalogMembership).count(), 1)
        self.assertEqual(self.move("people", None, second).status_code, 200)
        self.assertEqual(self.db.query(CatalogMembership).count(), 0)

    def test_cross_scope_and_unknown_record_are_rejected(self):
        group = self.create(scope="scenarios")
        self.assertEqual(self.move("people", group).status_code, 422)
        self.assertEqual(self.move("scenarios", group, object_id=99999).status_code, 404)
        self.assertEqual(self.db.query(CatalogMembership).count(), 0)

    def test_delete_group_preserves_records_runtime_and_scenario_configuration(self):
        group = self.create(scope="scenarios")
        self.assertEqual(self.move("scenarios", group).status_code, 200)
        url = f"/api/catalog-groups/{group}?scope=scenarios&expected_revision=1"
        self.assertEqual(self.client.delete(url, headers=self.headers).status_code, 200)
        self.assertIsNotNone(self.db.get(Employee, 1))
        scenario = self.db.get(ScenarioTemplate, 1)
        self.assertEqual((scenario.trigger_mode, scenario.purpose), ("manual_only", "adaptation"))
        progress = self.db.query(ScenarioProgress).one()
        self.assertTrue(progress.waiting_for_response)
        self.assertEqual(progress.step_history, "preserved")
        self.assertEqual(self.db.query(CatalogMembership).count(), 0)

    def test_scenario_delete_cleans_membership_to_prevent_id_reuse(self):
        from app.web.scenarios import _delete_template_entity
        group = self.create(scope="scenarios")
        self.assertEqual(self.move("scenarios", group).status_code, 200)
        _delete_template_entity(self.db, self.db.get(ScenarioTemplate, 1))
        self.db.commit()
        self.assertEqual(self.db.query(CatalogMembership).count(), 0)
        self.assertIsNotNone(self.db.get(CatalogGroup, group))

    def test_old_schema_bootstrap_adds_tables_without_rewriting_objects(self):
        engine = create_engine("sqlite://")
        Employee.__table__.create(engine)
        ScenarioTemplate.__table__.create(engine)
        with Session(engine) as db:
            db.add(Employee(id=5, full_name="Existing", created_at=datetime(2026, 1, 1)))
            db.commit()
        Base.metadata.create_all(engine)
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            self.assertEqual(db.get(Employee, 5).full_name, "Existing")
            self.assertEqual(db.query(CatalogGroup).count(), 0)
            self.assertEqual(db.execute(text("PRAGMA quick_check")).scalar(), "ok")
        engine.dispose()

    def test_deleted_group_id_is_not_reused_for_stale_drop_target(self):
        first = self.create(name="Old")
        self.assertEqual(self.client.delete(f"/api/catalog-groups/{first}?scope=people&expected_revision=1", headers=self.headers).status_code, 200)
        second = self.create(name="New")
        self.assertGreater(second, first)
        self.assertEqual(self.move("people", first).status_code, 422)
