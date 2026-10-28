import concurrent.futures
import asyncio
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch, AsyncMock, MagicMock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app import flow_templates
from app.models import Employee, FlowStepTemplate, ScenarioBootstrapState, ScenarioTemplate


class ScenarioBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.engine = create_engine("sqlite:///" + str(Path(self.temp.name) / "bootstrap.db"),
                                    connect_args={"check_same_thread": False, "timeout": 30})
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        self.patch = patch.object(flow_templates, "SessionLocal", self.sessions)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.engine.dispose()
        self.temp.cleanup()

    def test_fresh_bootstrap_and_deleted_scenario_never_resurrects(self):
        flow_templates.seed_flow_templates()
        with self.sessions() as db:
            self.assertEqual(db.query(ScenarioTemplate).count(), len(flow_templates.SCENARIO_DEFINITIONS))
            self.assertEqual(db.get(ScenarioBootstrapState, 1).mode, "fresh")
            db.query(FlowStepTemplate).filter_by(flow_key="first_day").delete()
            db.query(ScenarioTemplate).filter_by(scenario_key="first_day").delete()
            db.commit()
        flow_templates.seed_flow_templates()
        with self.sessions() as db:
            self.assertIsNone(db.query(ScenarioTemplate).filter_by(scenario_key="first_day").first())
            self.assertEqual(db.query(FlowStepTemplate).filter_by(flow_key="first_day").count(), 0)

    def test_existing_catalog_is_adopted_without_inserting_or_modifying(self):
        with self.sessions() as db:
            db.add(ScenarioTemplate(scenario_key="custom", title="Real workflow", employee_scope="all"))
            db.commit()
        flow_templates.seed_flow_templates()
        with self.sessions() as db:
            self.assertEqual(db.query(ScenarioTemplate).count(), 1)
            self.assertEqual(db.query(FlowStepTemplate).count(), 0)
            self.assertEqual(db.get(ScenarioBootstrapState, 1).mode, "existing")

    def test_existing_business_data_with_empty_catalog_is_not_reseeded(self):
        with self.sessions() as db:
            db.add(Employee(id=1, created_at=datetime(2026, 10, 28)))
            db.commit()
        flow_templates.seed_flow_templates()
        with self.sessions() as db:
            self.assertEqual(db.query(ScenarioTemplate).count(), 0)
            self.assertEqual(db.query(FlowStepTemplate).count(), 0)
            self.assertEqual(db.get(ScenarioBootstrapState, 1).mode, "existing")

    def test_removed_step_and_empty_catalog_remain_deleted(self):
        flow_templates.seed_flow_templates()
        with self.sessions() as db:
            db.query(FlowStepTemplate).filter_by(step_key="fill_form_11").delete()
            db.commit()
        flow_templates.seed_flow_templates()
        with self.sessions() as db:
            self.assertIsNone(db.query(FlowStepTemplate).filter_by(step_key="fill_form_11").first())
            db.query(FlowStepTemplate).delete()
            db.query(ScenarioTemplate).delete()
            db.commit()
        flow_templates.seed_flow_templates()
        with self.sessions() as db:
            self.assertEqual(db.query(ScenarioTemplate).count(), 0)
            self.assertEqual(db.query(FlowStepTemplate).count(), 0)

    def test_concurrent_web_worker_bootstrap_is_once_only(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda _: flow_templates.seed_flow_templates(), range(2)))
        with self.sessions() as db:
            self.assertEqual(db.query(ScenarioBootstrapState).count(), 1)
            self.assertEqual(db.query(ScenarioTemplate).count(), len(flow_templates.SCENARIO_DEFINITIONS))

    def test_orphan_steps_do_not_trigger_default_catalog_installation(self):
        with self.sessions() as db:
            db.add(FlowStepTemplate(flow_key="custom", step_key="custom-step", step_title="Step", default_text="Saved"))
            db.commit()
        flow_templates.seed_flow_templates()
        with self.sessions() as db:
            self.assertEqual(db.query(ScenarioTemplate).count(), 0)
            self.assertEqual(db.query(FlowStepTemplate).count(), 1)
            self.assertEqual(db.get(ScenarioBootstrapState, 1).mode, "existing")

    def test_stale_automatic_job_cannot_send_manual_only_scenario(self):
        from app import scheduler
        now = datetime(2026, 10, 28, 12)
        with self.sessions() as db:
            employee = Employee(id=1, created_at=now)
            scenario = ScenarioTemplate(scenario_key="custom", title="Scenario", trigger_mode="manual_only")
            db.add_all([employee, scenario, FlowStepTemplate(flow_key="custom", step_key="one", step_title="Step", default_text="Text")])
            db.commit()
            fake = MagicMock()
            fake.get_job.return_value = None
            scheduler.schedule_employee_scenario(db, fake, object(), employee, scenario, set(), manual=True, now=now)
            self.assertTrue(fake.add_job.call_args.kwargs["args"][-1])
        with patch.object(scheduler, "SessionLocal", self.sessions), patch.object(scheduler, "send_step", new_callable=AsyncMock) as send:
            asyncio.run(scheduler.run_scheduled_step(object(), 1, "custom", "one", now))
            send.assert_not_awaited()
            asyncio.run(scheduler.run_scheduled_step(object(), 1, "custom", "one", now, explicit=True))
            send.assert_awaited_once()
