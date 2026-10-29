from datetime import datetime
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app import positions
from app.mass_targeting import mass_target_employee_query
from app.messaging.service import menu_set_matches_employee
from app.models import BotMenuSet, Employee, Position, ScenarioTemplate
from app.scenario_engine import matches_role_scope


class PositionMatchingTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        self.db = self.sessions()
        self.position = Position(title="Руководитель проектов", slug="project_manager", is_active=True,
                                 created_at=datetime(2026, 10, 29), sort_order=10)
        self.db.add(self.position)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def employee(self, value):
        row = Employee(full_name="Fixture", desired_position=value, employee_stage="staff", created_at=datetime(2026, 10, 29))
        self.db.add(row)
        self.db.commit()
        return row

    def test_custom_slug_matches_card_scenario_menu_and_multi_target(self):
        first = self.employee("Руководитель проектов")
        second = self.employee("  РУКОВОДИТЕЛЬ   ПРОЕКТОВ ")
        other = self.employee("Дизайнер")
        scenario = ScenarioTemplate(scenario_key="test-position", title="Fixture", role_scope="project_manager")
        menu = BotMenuSet(title="Fixture", role_scope="project_manager")
        for employee in (first, second):
            self.assertTrue(matches_role_scope(employee, scenario))
            self.assertTrue(menu_set_matches_employee(employee, menu))
            self.assertEqual(positions.resolve_employee_position_value(self.db, employee.desired_position), self.position.title)
        self.assertFalse(matches_role_scope(other, scenario))
        query = mass_target_employee_query(self.db, target_all=False, target_employee_stages=[], target_candidate_stages=[],
                                           target_role_scopes=["project_manager"], target_employee_ids=[])
        self.assertEqual({row.id for row in query}, {first.id, second.id})
        single = mass_target_employee_query(self.db, target_all=True, target_employee_stages=[], target_candidate_stages=[],
                                            target_role_scope="project_manager")
        self.assertEqual({row.id for row in single}, {first.id, second.id})

    def test_exact_title_takes_precedence_over_legacy_alias(self):
        self.db.add(Position(title="Product manager", slug="product_lead", is_active=True, created_at=datetime(2026, 10, 29)))
        self.db.commit()
        self.assertFalse(positions.position_matches_scope("Product manager", "project_manager", db=self.db))
        self.assertTrue(positions.position_matches_scope("Product manager", "product_lead", db=self.db))

    def test_ambiguous_title_is_not_arbitrarily_resolved(self):
        self.db.add(Position(title="РУКОВОДИТЕЛЬ ПРОЕКТОВ", slug="another_pm", is_active=True, created_at=datetime(2026, 10, 29)))
        self.db.commit()
        self.assertFalse(positions.position_matches_scope("Руководитель проектов", "project_manager", db=self.db))

    def test_cache_refreshes_after_commit(self):
        self.assertTrue(positions.position_matches_scope(self.position.title, "project_manager", db=self.db))
        self.position.title = "Project lead"
        self.db.commit()
        self.assertTrue(positions.position_matches_scope("Project lead", "project_manager", db=self.db))

    def test_scope_slug_has_priority_over_another_position_title(self):
        self.db.add_all([
            Position(title="Developer", slug="engineer", is_active=True, created_at=datetime(2026, 10, 29)),
            Position(title="Engineer", slug="another_role", is_active=True, created_at=datetime(2026, 10, 29)),
        ])
        self.db.commit()
        self.assertTrue(positions.position_matches_scope("Developer", "engineer", db=self.db))
        self.assertFalse(positions.position_matches_scope("Engineer", "engineer", db=self.db))

    def test_api_rejects_duplicate_titles_without_mutating_catalog(self):
        from fastapi import HTTPException
        from app.web.settings_routes import create_position_api, update_position_api
        with patch("app.web.settings_routes.require_api_auth"):
            with self.assertRaises(HTTPException) as caught:
                create_position_api(None, {"title": "  РУКОВОДИТЕЛЬ   ПРОЕКТОВ ", "slug": "different_slug"}, self.db)
            self.assertEqual(caught.exception.status_code, 409)
            other = Position(title="Other", slug="other", is_active=True, created_at=datetime(2026, 10, 29))
            self.db.add(other)
            self.db.commit()
            with self.assertRaises(HTTPException) as caught:
                update_position_api(None, other.id, {"title": "Руководитель проектов"}, self.db)
            self.assertEqual(caught.exception.status_code, 409)
            self.assertEqual(other.title, "Other")

    def test_audit_is_read_only_and_reports_disagreement(self):
        from tools.audit_position_matching import build_report
        with TemporaryDirectory() as directory:
            path = Path(directory) / "audit.db"
            engine = create_engine("sqlite:///" + str(path))
            Base.metadata.create_all(engine)
            with sessionmaker(bind=engine)() as db:
                db.add(Position(title="Руководитель проектов", slug="project_manager", is_active=True, created_at=datetime(2026, 10, 29)))
                db.add(Employee(full_name="Must not be exported", desired_position="Руководитель проектов", created_at=datetime(2026, 10, 29)))
                db.add(ScenarioTemplate(scenario_key="audit", title="Fixture", role_scope="project_manager"))
                db.commit()
            engine.dispose()
            before = hashlib.sha256(path.read_bytes()).hexdigest()
            report = build_report(path)
            self.assertTrue(report["read_only"])
            self.assertEqual(len(report["role_matching_changes"]), 1)
            self.assertNotIn("Must not be exported", str(report))
            self.assertEqual(before, hashlib.sha256(path.read_bytes()).hexdigest())

    def test_startup_preserves_custom_title_inactive_and_deleted_defaults(self):
        self.position.is_active = False
        self.db.commit()
        with patch.object(positions, "SessionLocal", self.sessions):
            positions.seed_positions_catalog()
        self.db.expire_all()
        self.assertEqual(self.db.query(Position).count(), 1)
        self.assertEqual(self.position.title, "Руководитель проектов")
        self.assertFalse(self.position.is_active)

    def test_old_unknown_values_and_all_scope_remain_compatible(self):
        self.assertTrue(positions.position_matches_scope("Legacy specialist", "legacy_specialist", db=self.db))
        self.assertTrue(positions.position_matches_scope(None, "all", db=self.db))
        self.assertFalse(positions.position_matches_scope("Дизайнер", "project_manager", db=self.db))
