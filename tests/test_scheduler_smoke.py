import unittest
from datetime import UTC, date, datetime
from unittest.mock import patch
from uuid import uuid4

from app.config import settings
from app.database import SessionLocal, init_db
from app.messaging.identity import set_primary_chat_id
from app.models import Employee, EmployeeMessengerAccount, FlowLaunchRequest, FlowStepTemplate, MassMessageAction, MassScenarioAction, OnboardingEvent, ScenarioProgress, ScenarioTemplate
from app.scheduler import _load_pending_flow_requests, _load_pending_mass_message_actions, _load_pending_mass_scenario_actions, run_scheduled_step, schedule_all_employees, schedule_employee_scenario
from app.scenario_engine import SINGLE_STEP_REQUEST_PREFIX, send_step


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
            db.query(MassScenarioAction).filter(MassScenarioAction.flow_key == self.scenario_key).delete(synchronize_session=False)
            db.query(MassMessageAction).filter(MassMessageAction.message_text == self.scenario_key).delete(synchronize_session=False)
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

    async def test_scheduled_queues_use_moscow_time_while_internal_requests_use_utc(self) -> None:
        self._create_scenario_with_employee()
        utc_instant = datetime(2026, 10, 16, 9, 5)
        scheduled_due = datetime(2026, 10, 16, 12, 0)
        scheduled_future = datetime(2026, 10, 16, 12, 10)
        with SessionLocal() as db:
            requests = [
                FlowLaunchRequest(employee_id=self.employee_id, flow_key=self.scenario_key, requested_at=scheduled_due, launch_type="scheduled"),
                FlowLaunchRequest(employee_id=self.employee_id, flow_key=self.scenario_key, requested_at=scheduled_future, launch_type="scheduled"),
                FlowLaunchRequest(employee_id=self.employee_id, flow_key=self.scenario_key, requested_at=datetime(2026, 10, 16, 9, 0), launch_type="trigger"),
                FlowLaunchRequest(employee_id=self.employee_id, flow_key=self.scenario_key, requested_at=datetime(2026, 10, 16, 9, 10), launch_type="trigger"),
                FlowLaunchRequest(employee_id=self.employee_id, flow_key=self.scenario_key, requested_at=datetime(2026, 10, 16, 9, 0), launch_type="scheduled", skip_step_key=f"{SINGLE_STEP_REQUEST_PREFIX}first_step"),
                FlowLaunchRequest(employee_id=self.employee_id, flow_key=self.scenario_key, requested_at=datetime(2026, 10, 16, 9, 10), launch_type="scheduled", skip_step_key=f"{SINGLE_STEP_REQUEST_PREFIX}second_step"),
            ]
            scenario_actions = [
                MassScenarioAction(flow_key=self.scenario_key, scenario_kind="scenario", requested_at=value, launch_type="scheduled", created_at=utc_instant)
                for value in (scheduled_due, scheduled_future)
            ]
            message_actions = [
                MassMessageAction(message_text=self.scenario_key, requested_at=value, launch_type="scheduled", created_at=utc_instant)
                for value in (scheduled_due, scheduled_future)
            ]
            db.add_all([*requests, *scenario_actions, *message_actions])
            db.commit()

            with patch.object(settings, "TIMEZONE", "Europe/Moscow"), patch("app.scheduler.datetime") as scheduler_datetime, patch("app.scheduler.utc_now", return_value=utc_instant):
                scheduler_datetime.now.side_effect = lambda tz=None: utc_instant.replace(tzinfo=UTC).astimezone(tz) if tz else utc_instant
                due_request_ids = {item.id for item in _load_pending_flow_requests(db)}
                due_scenario_ids = {item.id for item in _load_pending_mass_scenario_actions(db)}
                due_message_ids = {item.id for item in _load_pending_mass_message_actions(db)}

            self.assertIn(requests[0].id, due_request_ids)
            self.assertNotIn(requests[1].id, due_request_ids)
            self.assertIn(requests[2].id, due_request_ids)
            self.assertNotIn(requests[3].id, due_request_ids)
            self.assertIn(requests[4].id, due_request_ids)
            self.assertNotIn(requests[5].id, due_request_ids)
            self.assertIn(scenario_actions[0].id, due_scenario_ids)
            self.assertNotIn(scenario_actions[1].id, due_scenario_ids)
            self.assertIn(message_actions[0].id, due_message_ids)
            self.assertNotIn(message_actions[1].id, due_message_ids)

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

    async def test_explicit_scheduled_launch_without_first_workday_is_queued(self) -> None:
        employee, scenario = self._create_scenario_with_employee()
        scheduler = _FakeScheduler()
        with SessionLocal() as db:
            db_employee = db.get(Employee, employee.id)
            assert db_employee is not None
            db_employee.first_workday = None
            request = FlowLaunchRequest(
                employee_id=employee.id,
                flow_key=scenario.scenario_key,
                requested_at=datetime(2025, 1, 1, 12, 0),
                launch_type="scheduled",
            )
            db.add(request)
            db.commit()
            request_id = request.id

        with patch.object(settings, "DEMO_MODE", False), patch("app.scheduler._load_all_employees", return_value=[]), patch("app.scheduler._load_scenarios", return_value=[]):
            await schedule_all_employees(scheduler, bot=None)

        first_job = scheduler.get_job(f"employee-{employee.id}-{scenario.scenario_key}-first_step")
        self.assertIsNotNone(first_job)
        with SessionLocal() as db:
            self.assertIsNotNone(db.get(FlowLaunchRequest, request_id).processed_at)
            db_employee = db.get(Employee, employee.id)
            db_scenario = db.query(ScenarioTemplate).filter(ScenarioTemplate.scenario_key == scenario.scenario_key).one()
            automatic_scheduler = _FakeScheduler()
            schedule_employee_scenario(db, automatic_scheduler, None, db_employee, db_scenario, set(), manual=False)
            self.assertEqual(automatic_scheduler.jobs, {})

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

    async def test_run_scheduled_step_skips_stale_scenario_after_employee_stage_changed(self) -> None:
        employee, scenario = self._create_scenario_with_employee()
        messenger = _FakeMessenger()

        with SessionLocal() as db:
            existing_event_ids = {
                row.id
                for row in db.query(OnboardingEvent.id).filter(OnboardingEvent.employee_id == employee.id).all()
            }

        with SessionLocal() as db:
            db_employee = db.get(Employee, employee.id)
            assert db_employee is not None
            db_employee.employee_stage = "candidate"
            db.commit()

        await run_scheduled_step(
            messenger,
            employee.id,
            self.scenario_key,
            "second_step",
            datetime(2026, 7, 8, 11, 30),
        )

        with SessionLocal() as db:
            sent_event_ids = {
                row.id
                for row in db.query(OnboardingEvent.id).filter(OnboardingEvent.employee_id == employee.id).all()
            }

        self.assertEqual(messenger.sent_texts, [])
        self.assertEqual(sent_event_ids, existing_event_ids)

    async def test_pending_trigger_request_marks_processed_and_records_delivery_error_for_missing_manager(self) -> None:
        now = datetime.now(UTC).replace(tzinfo=None)
        scenario_key = f"trigger_missing_manager_{self.unique_tag}"
        scheduler = _FakeScheduler()
        messenger = _FakeMessenger()

        with SessionLocal() as db:
            employee = Employee(
                full_name=f"Trigger Subject {self.unique_tag}",
                telegram_user_id="800001",
                telegram_username=None,
                first_workday=date(2026, 7, 8),
                created_at=now,
                is_flow_scheduled=False,
                candidate_status="new",
                employee_stage="adaptation",
            )
            scenario = ScenarioTemplate(
                scenario_key=scenario_key,
                title=f"Trigger scenario {self.unique_tag}",
                role_scope="all",
                employee_scope="employees",
                scenario_kind="scenario",
                sort_order=0,
                trigger_mode="manager_assigned_adaptation",
                recipient_mode="manager",
            )
            step = FlowStepTemplate(
                flow_key=scenario_key,
                step_key="first_step",
                step_title="Первый шаг",
                sort_order=10,
                default_text="Назначь наставника",
                response_type="text",
                send_mode="immediate",
                day_offset_workdays=0,
            )
            db.add_all([employee, scenario, step])
            db.flush()
            self.employee_id = employee.id
            set_primary_chat_id(employee, "800001", db=db)
            db.add(
                FlowLaunchRequest(
                    employee_id=employee.id,
                    flow_key=scenario_key,
                    requested_at=now,
                    processed_at=None,
                    launch_type="trigger",
                    skip_step_key=None,
                )
            )
            db.commit()

        await schedule_all_employees(scheduler, messenger)

        with SessionLocal() as db:
            request_row = (
                db.query(FlowLaunchRequest)
                .filter(
                    FlowLaunchRequest.employee_id == self.employee_id,
                    FlowLaunchRequest.flow_key == scenario_key,
                    FlowLaunchRequest.launch_type == "trigger",
                )
                .first()
            )
            self.assertIsNotNone(request_row)
            self.assertIsNotNone(request_row.processed_at)

        job = scheduler.get_job(f"employee-{self.employee_id}-{scenario_key}-first_step")
        self.assertIsNotNone(job)
        await job["func"](*job["args"])

        with SessionLocal() as db:
            progress = (
                db.query(ScenarioProgress)
                .filter(
                    ScenarioProgress.employee_id == self.employee_id,
                    ScenarioProgress.scenario_key == scenario_key,
                )
                .first()
            )
            self.assertIsNotNone(progress)
            self.assertIn("не назначен", progress.last_delivery_error or "")

        self.assertEqual(messenger.sent_texts, [])

    async def test_pending_candidate_hr_stage_request_starts_without_first_workday(self) -> None:
        now = datetime.now(UTC).replace(tzinfo=None)
        scheduler = _FakeScheduler()
        messenger = _FakeMessenger()

        with SessionLocal() as db:
            employee = Employee(
                full_name=f"Candidate Trigger {self.unique_tag}",
                telegram_user_id=None,
                telegram_username=None,
                first_workday=None,
                created_at=now,
                is_flow_scheduled=False,
                candidate_status="new",
                employee_stage="candidate",
                candidate_work_stage="offer",
            )
            scenario = ScenarioTemplate(
                scenario_key=self.scenario_key,
                title=f"Scheduler smoke {self.unique_tag}",
                role_scope="all",
                employee_scope="candidates",
                scenario_kind="scenario",
                sort_order=0,
                trigger_mode="candidate_hr_stage",
                candidate_work_stage_trigger="offer",
            )
            step = FlowStepTemplate(
                flow_key=self.scenario_key,
                step_key="first_step",
                step_title="Первый шаг",
                sort_order=10,
                default_text="Оффер",
                response_type="none",
                send_mode="immediate",
                day_offset_workdays=0,
            )
            db.add_all([employee, scenario, step])
            db.flush()
            self.employee_id = employee.id
            set_primary_chat_id(employee, "800002", db=db)
            db.add(
                FlowLaunchRequest(
                    employee_id=employee.id,
                    flow_key=self.scenario_key,
                    requested_at=now,
                    processed_at=None,
                    launch_type="status_transition",
                    skip_step_key=None,
                )
            )
            db.commit()

        with patch("app.scheduler.start_scenario", return_value=True) as mocked_start:
            await schedule_all_employees(scheduler, messenger)

        mocked_start.assert_awaited_once()
        with SessionLocal() as db:
            request_row = (
                db.query(FlowLaunchRequest)
                .filter(
                    FlowLaunchRequest.employee_id == self.employee_id,
                    FlowLaunchRequest.flow_key == self.scenario_key,
                    FlowLaunchRequest.launch_type == "status_transition",
                )
                .one()
            )
            self.assertIsNotNone(request_row.processed_at)

    async def test_pending_candidate_hr_stage_request_skips_stale_status(self) -> None:
        now = datetime.now(UTC).replace(tzinfo=None)
        scheduler = _FakeScheduler()
        messenger = _FakeMessenger()

        with SessionLocal() as db:
            employee = Employee(
                full_name=f"Candidate Trigger {self.unique_tag}",
                telegram_user_id=None,
                telegram_username=None,
                first_workday=None,
                created_at=now,
                is_flow_scheduled=False,
                candidate_status="new",
                employee_stage="candidate",
                candidate_work_stage="testing",
            )
            scenario = ScenarioTemplate(
                scenario_key=self.scenario_key,
                title=f"Scheduler smoke {self.unique_tag}",
                role_scope="all",
                employee_scope="candidates",
                scenario_kind="scenario",
                sort_order=0,
                trigger_mode="candidate_hr_stage",
                candidate_work_stage_trigger="offer",
            )
            db.add_all([employee, scenario])
            db.flush()
            self.employee_id = employee.id
            set_primary_chat_id(employee, "800003", db=db)
            db.add(
                FlowLaunchRequest(
                    employee_id=employee.id,
                    flow_key=self.scenario_key,
                    requested_at=now,
                    processed_at=None,
                    launch_type="status_transition",
                    skip_step_key=None,
                )
            )
            db.commit()

        with patch("app.scheduler.start_scenario", return_value=True) as mocked_start:
            await schedule_all_employees(scheduler, messenger)

        mocked_start.assert_not_awaited()
        with SessionLocal() as db:
            request_row = (
                db.query(FlowLaunchRequest)
                .filter(
                    FlowLaunchRequest.employee_id == self.employee_id,
                    FlowLaunchRequest.flow_key == self.scenario_key,
                    FlowLaunchRequest.launch_type == "status_transition",
                )
                .one()
            )
            self.assertIsNotNone(request_row.processed_at)
