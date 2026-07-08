import unittest
from datetime import UTC, date, datetime
from unittest.mock import patch
from uuid import uuid4

from app.config import settings
from app.database import SessionLocal, init_db
from app.messaging.identity import set_primary_chat_id
from app.models import Employee, EmployeeMessengerAccount, FlowLaunchRequest, FlowStepTemplate, OnboardingEvent, ScenarioProgress, ScenarioTemplate
from app.scheduler import schedule_employee_scenario
from app.scenario_engine import send_step


class _FakeScheduler:
    def __init__(self) -> None:
        self.jobs: dict[str, dict] = {}

    def get_job(self, job_id: str):
        return self.jobs.get(job_id)

    def add_job(self, func, trigger, run_date, args, id, replace_existing=False):
        if not replace_existing and id in self.jobs:
            return
        self.jobs[id] = {
            "func": func,
            "trigger": trigger,
            "run_date": run_date,
            "args": args,
            "id": id,
            "replace_existing": replace_existing,
        }


class _FakeMessenger:
    def __init__(self) -> None:
        self.sent_texts: list[tuple[str, str]] = []

    async def send_text(self, chat_id: str, text: str, reply_markup=None) -> None:
        self.sent_texts.append((chat_id, text))

    async def send_menu(self, chat_id: str, text: str, buttons: list[str]) -> None:
        self.sent_texts.append((chat_id, text))

    async def send_photo_path(self, chat_id: str, path, filename=None) -> None:
        return None

    async def send_photo_bytes(self, chat_id: str, data: bytes, filename: str) -> None:
        return None

    async def send_document_path(self, chat_id: str, path, filename=None) -> None:
        return None


class SchedulerSmokeTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        init_db()

    def setUp(self) -> None:
        self.unique_tag = uuid4().hex[:12]
        self.employee_id: int | None = None
        self.scenario_key = f"schedule_smoke_{self.unique_tag}"

    def tearDown(self) -> None:
        with SessionLocal() as db:
            if self.employee_id is not None:
                db.query(OnboardingEvent).filter(OnboardingEvent.employee_id == self.employee_id).delete(synchronize_session=False)
                db.query(FlowLaunchRequest).filter(FlowLaunchRequest.employee_id == self.employee_id).delete(synchronize_session=False)
                db.query(ScenarioProgress).filter(ScenarioProgress.employee_id == self.employee_id).delete(synchronize_session=False)
                db.query(EmployeeMessengerAccount).filter(EmployeeMessengerAccount.employee_id == self.employee_id).delete(synchronize_session=False)
                employee = db.get(Employee, self.employee_id)
                if employee is not None:
                    db.delete(employee)
            db.query(FlowStepTemplate).filter(FlowStepTemplate.flow_key == self.scenario_key).delete(synchronize_session=False)
            db.query(ScenarioTemplate).filter(ScenarioTemplate.scenario_key == self.scenario_key).delete(synchronize_session=False)
            db.commit()

    def _create_scenario_with_employee(self) -> tuple[Employee, ScenarioTemplate]:
        now = datetime.now(UTC).replace(tzinfo=None)
        with SessionLocal() as db:
            employee = Employee(
                full_name=f"Scheduler Smoke {self.unique_tag}",
                telegram_user_id=None,
                telegram_username=None,
                first_workday=date(2026, 7, 8),
                created_at=now,
                is_flow_scheduled=False,
                candidate_status="new",
                employee_stage="adaptation",
            )
            scenario = ScenarioTemplate(
                scenario_key=self.scenario_key,
                title=f"Scheduler smoke {self.unique_tag}",
                role_scope="all",
                employee_scope="employees",
                scenario_kind="scenario",
                sort_order=0,
                trigger_mode="first_workday",
            )
            db.add(employee)
            db.add(scenario)
            db.flush()
            self.employee_id = employee.id
            set_primary_chat_id(employee, "700000001", db=db)
            db.add_all(
                [
                    FlowStepTemplate(
                        flow_key=self.scenario_key,
                        step_key="first_step",
                        step_title="Первый шаг",
                        sort_order=10,
                        default_text="Первый шаг",
                        response_type="none",
                        send_mode="specific_time",
                        send_time="10:00",
                        day_offset_workdays=0,
                    ),
                    FlowStepTemplate(
                        flow_key=self.scenario_key,
                        step_key="second_step",
                        step_title="Второй шаг",
                        sort_order=20,
                        default_text="Второй шаг",
                        response_type="none",
                        send_mode="specific_time",
                        send_time="11:00",
                        day_offset_workdays=0,
                    ),
                ]
            )
            db.commit()
            db.refresh(employee)
            db.refresh(scenario)
            return employee, scenario

    def test_schedule_employee_scenario_catches_up_first_overdue_step_same_day(self) -> None:
        employee, scenario = self._create_scenario_with_employee()
        scheduler = _FakeScheduler()
        now = datetime.fromisoformat("2026-07-08T10:30:00+03:00")

        with patch.object(settings, "DEMO_MODE", False):
            with SessionLocal() as db:
                employee = db.get(Employee, employee.id)
                scenario = db.query(ScenarioTemplate).filter(ScenarioTemplate.scenario_key == self.scenario_key).first()
                assert employee is not None
                assert scenario is not None
                schedule_employee_scenario(
                    db,
                    scheduler,
                    bot=None,
                    employee=employee,
                    scenario=scenario,
                    sent_keys=set(),
                    manual=False,
                    now=now,
                )

        first_job = scheduler.get_job(f"employee-{employee.id}-{self.scenario_key}-first_step")
        second_job = scheduler.get_job(f"employee-{employee.id}-{self.scenario_key}-second_step")
        self.assertIsNotNone(first_job)
        self.assertIsNotNone(second_job)
        self.assertEqual(first_job["run_date"], now)
        self.assertEqual(second_job["run_date"], datetime.fromisoformat("2026-07-08T11:00:00+03:00"))

    def test_schedule_employee_scenario_does_not_catch_up_after_scenario_already_started(self) -> None:
        employee, scenario = self._create_scenario_with_employee()
        scheduler = _FakeScheduler()
        now = datetime.fromisoformat("2026-07-08T10:30:00+03:00")

        with patch.object(settings, "DEMO_MODE", False):
            with SessionLocal() as db:
                db.add(
                    OnboardingEvent(
                        employee_id=employee.id,
                        scheduled_at=datetime(2026, 7, 8, 10, 0),
                        sent_at=datetime(2026, 7, 8, 10, 0),
                        event_key="first_step",
                        message="Первый шаг",
                    )
                )
                db.commit()
                employee = db.get(Employee, employee.id)
                scenario = db.query(ScenarioTemplate).filter(ScenarioTemplate.scenario_key == self.scenario_key).first()
                assert employee is not None
                assert scenario is not None
                schedule_employee_scenario(
                    db,
                    scheduler,
                    bot=None,
                    employee=employee,
                    scenario=scenario,
                    sent_keys={"first_step"},
                    manual=False,
                    now=now,
                )

        self.assertIsNone(scheduler.get_job(f"employee-{employee.id}-{self.scenario_key}-first_step"))
        second_job = scheduler.get_job(f"employee-{employee.id}-{self.scenario_key}-second_step")
        self.assertIsNotNone(second_job)
        self.assertEqual(second_job["run_date"], datetime.fromisoformat("2026-07-08T11:00:00+03:00"))

    async def test_send_step_from_scheduler_does_not_enqueue_next_timed_step(self) -> None:
        employee, scenario = self._create_scenario_with_employee()
        messenger = _FakeMessenger()

        with SessionLocal() as db:
            employee = db.get(Employee, employee.id)
            scenario = db.query(ScenarioTemplate).filter(ScenarioTemplate.scenario_key == self.scenario_key).first()
            step = (
                db.query(FlowStepTemplate)
                .filter(
                    FlowStepTemplate.flow_key == self.scenario_key,
                    FlowStepTemplate.step_key == "first_step",
                )
                .first()
            )
            assert employee is not None
            assert scenario is not None
            assert step is not None

            await send_step(
                messenger,
                db,
                employee,
                scenario,
                step,
                scheduled_at=datetime(2026, 7, 8, 10, 0),
            )

            launch_requests = (
                db.query(FlowLaunchRequest)
                .filter(FlowLaunchRequest.employee_id == employee.id)
                .all()
            )
            sent_events = (
                db.query(OnboardingEvent)
                .filter(OnboardingEvent.employee_id == employee.id)
                .all()
            )

        self.assertEqual(messenger.sent_texts, [("700000001", "Первый шаг")])
        self.assertEqual(len(launch_requests), 0)
        self.assertEqual([event.event_key for event in sent_events], ["first_step"])
