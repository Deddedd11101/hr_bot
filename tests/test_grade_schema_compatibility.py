import unittest
from unittest.mock import patch
from sqlalchemy import create_engine, text
from app.database import Base
from app import models  # noqa: F401
import app.database as database


class GradeSchemaCompatibilityTests(unittest.TestCase):
    def test_optional_grade_rebuild_preserves_snapshots_values_and_indexes(self):
        from sqlalchemy.schema import CreateTable
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        with engine.begin() as db:
            db.execute(text("DROP TABLE grade_assessments"))
            ddl = str(CreateTable(Base.metadata.tables["grade_assessments"]).compile(engine))
            db.execute(text(ddl.replace("current_grade_id INTEGER,", "current_grade_id INTEGER NOT NULL,")))
            db.execute(text("CREATE INDEX ix_grade_assessments_employee_id ON grade_assessments(employee_id)"))
            db.execute(text("INSERT INTO grade_assessments (id,employee_id,specialization_id,current_grade_id,assessor_admin_account_id,status,catalog_snapshot,created_at,updated_at) VALUES (7,1,1,1,1,'final',:snapshot,'2026-01-01','2026-01-01')"), {"snapshot": '{"unchanged": true}'})
            db.execute(text("INSERT INTO grade_assessment_values (id,assessment_id,skill_id,level) VALUES (1,7,1,4)"))
            database._ensure_optional_assessment_grade(db)
            database._ensure_optional_assessment_grade(db)
            self.assertEqual(db.execute(text("SELECT catalog_snapshot FROM grade_assessments WHERE id=7")).scalar(), '{"unchanged": true}')
            self.assertEqual(db.execute(text("SELECT level FROM grade_assessment_values WHERE assessment_id=7")).scalar(), 4)
            self.assertFalse(next(row[3] for row in db.execute(text("PRAGMA table_info(grade_assessments)")) if row[1] == "current_grade_id"))
            self.assertIsNotNone(db.execute(text("SELECT name FROM sqlite_master WHERE name='ix_grade_assessments_employee_id'")).scalar())
        engine.dispose()

    def test_additive_patch_is_idempotent_and_keeps_final_snapshot(self):
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        with engine.begin() as db:
            db.execute(text("DROP INDEX uq_grade_assessment_employee_draft"))
            db.execute(text("ALTER TABLE grade_assessments DROP COLUMN archived_at"))
            db.execute(text("CREATE UNIQUE INDEX uq_grade_assessment_employee_draft ON grade_assessments(employee_id) WHERE status = 'draft'"))
            for statement in ("ALTER TABLE grade_skills DROP COLUMN revision", "ALTER TABLE grade_skills DROP COLUMN description", "ALTER TABLE grade_specializations DROP COLUMN skill_ids_json"):
                db.execute(text(statement))
            db.execute(text("INSERT INTO grade_skills (id,category_id,name,complexity,sort_order,active) VALUES (1,1,'Legacy',1,0,1)"))
            db.execute(text("INSERT INTO grade_assessments (id,employee_id,specialization_id,current_grade_id,assessor_admin_account_id,status,catalog_snapshot,created_at,updated_at) VALUES (1,1,1,1,1,'final',:snapshot,'2026-01-01','2026-01-01')"), {"snapshot": '{"legacy":"must remain byte-for-byte"}'})
        with patch.object(database, "engine", engine), patch.object(database.settings, "DATABASE_URL", "sqlite://"):
            database._ensure_sqlite_schema()
            database._ensure_sqlite_schema()
        with engine.connect() as db:
            self.assertEqual(db.execute(text("SELECT revision,description FROM grade_skills WHERE id=1")).one(), (1, None))
            self.assertEqual(db.execute(text("SELECT catalog_snapshot FROM grade_assessments WHERE id=1")).scalar(), '{"legacy":"must remain byte-for-byte"}')
            self.assertIn("skill_ids_json", {row[1] for row in db.execute(text("PRAGMA table_info(grade_specializations)"))})
            self.assertIn("archived_at", {row[1] for row in db.execute(text("PRAGMA table_info(grade_assessments)"))})
            self.assertIn("archived_at", db.execute(text("SELECT sql FROM sqlite_master WHERE name='uq_grade_assessment_employee_draft'")).scalar())
        engine.dispose()
