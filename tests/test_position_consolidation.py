from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Employee, Position, ScenarioTemplate, MassMessageAction, GradeSpecialization
from app.position_consolidation import CANONICAL, TITLES, apply, preview
from app.positions import resolve_employee_position_value


class PositionConsolidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.path = Path(self.temp.name) / "fixture.db"
        self.engine = create_engine("sqlite:///" + str(self.path))
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        now = datetime(2026, 10, 30)
        for key, title in TITLES.items():
            self.db.add(Position(title=title, slug=key, is_active=True, created_at=now))
            self.db.add(Employee(full_name="Private fixture", desired_position=title, created_at=now))
        self.db.add(ScenarioTemplate(title="Fixture", scenario_key="fixture", role_scope=",".join(TITLES)))
        self.db.add(MassMessageAction(message_text="Private message", requested_at=now, created_at=now,
            target_role_scopes='["project_manager","rukovoditel_proekta","rukovoditel_proektov"]'))
        self.db.add(MassMessageAction(message_text="Private history", requested_at=now, created_at=now,
            processed_at=now, target_role_scope="project_manager"))
        self.db.add(GradeSpecialization(slug="fixture", name="Fixture", position_slug="project_manager"))
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        self.temp.cleanup()

    def test_preview_read_only_apply_backup_and_idempotency(self):
        before = self.path.read_bytes()
        plan = preview(self.db)
        self.assertEqual(before, self.path.read_bytes())
        self.assertNotIn("Private", str(plan))
        self.assertEqual(plan["audience_deltas"], [])
        result = apply(self.db, plan["fingerprint"])
        self.assertTrue(Path(result["backup"]).is_file())
        self.assertEqual(preview(self.db)["changes"], [])
        self.assertEqual({e.desired_position for e in self.db.query(Employee)}, {TITLES[CANONICAL]})
        self.assertEqual([p.slug for p in self.db.query(Position).filter_by(is_active=True)], [CANONICAL])
        self.assertEqual(self.db.query(ScenarioTemplate).one().role_scope, CANONICAL)
        self.assertEqual(self.db.query(MassMessageAction).filter(MassMessageAction.processed_at.is_(None)).one().target_role_scopes,
                         '["rukovoditel_proektov"]')
        self.assertEqual(self.db.query(MassMessageAction).filter(MassMessageAction.processed_at.is_not(None)).one().target_role_scope,
                         "project_manager")
        self.assertEqual(self.db.query(GradeSpecialization).one().position_slug, CANONICAL)

    def test_stale_plan_and_audience_expansion_are_rejected_without_writes(self):
        plan = preview(self.db)
        self.db.query(ScenarioTemplate).one().role_scope = "project_manager"
        self.db.commit()
        with self.assertRaisesRegex(ValueError, "изменились"):
            apply(self.db, plan["fingerprint"])
        plan = preview(self.db)
        self.assertTrue(plan["audience_deltas"])
        with self.assertRaisesRegex(ValueError, "аудитории"):
            apply(self.db, plan["fingerprint"])
        self.assertEqual(self.db.query(Position).filter_by(is_active=True).count(), 3)

    def test_card_save_catalog_only_no_creation_and_no_inactive_selection(self):
        for value in ("Unknown free text", "9999"):
            with self.assertRaises(ValueError):
                resolve_employee_position_value(self.db, value)
        self.assertEqual(self.db.query(Position).count(), 3)
        position = self.db.query(Position).filter_by(slug="project_manager").one()
        position.is_active = False
        self.db.commit()
        for value in (position.title, position.slug, str(position.id)):
            with self.assertRaises(ValueError):
                resolve_employee_position_value(self.db, value)
        self.assertEqual(resolve_employee_position_value(self.db, CANONICAL), TITLES[CANONICAL])

    def test_maintenance_routes_require_admin_and_same_origin(self):
        from fastapi import HTTPException
        from types import SimpleNamespace
        from app.web.settings_routes import apply_project_lead_positions, preview_project_lead_positions
        request = SimpleNamespace(state=SimpleNamespace(current_user=SimpleNamespace(role="hr")), headers={})
        with self.assertRaises(HTTPException) as caught:
            preview_project_lead_positions(request, self.db)
        self.assertEqual(caught.exception.status_code, 403)
        request.state.current_user.role = "admin"
        request.headers = {"origin": "https://other.example", "host": "testserver"}
        with self.assertRaises(HTTPException) as caught:
            apply_project_lead_positions(request, "invalid", self.db)
        self.assertEqual(caught.exception.status_code, 403)
