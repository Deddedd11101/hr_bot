import hashlib
import hmac
import json
import time
import unittest
from datetime import date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from urllib.parse import urlencode

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.web import employee_cabinet as cabinet


class VacationDeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_notices_sent_once_and_in_order(self):
        from app.models import EmployeeVacationRequest, HrSettings
        from app.vacation_delivery import deliver_pending

        engine = create_engine("sqlite://")
        self.addCleanup(engine.dispose)
        for model in (cabinet.Employee, EmployeeVacationRequest, HrSettings):
            model.__table__.create(engine)
        session = sessionmaker(bind=engine)
        with session() as db:
            db.add(cabinet.Employee(id=70, full_name="Employee", created_at=datetime.now()))
            db.add(HrSettings(id=1, telegram_user_id="456", created_at=datetime.now(), updated_at=datetime.now()))
            db.add(EmployeeVacationRequest(id=1, employee_id=70, starts_on=date(2090, 1, 2),
                                          ends_on=date(2090, 1, 3), workdays=2, created_at=datetime.now()))
            db.commit()
        bot = SimpleNamespace(send_message=AsyncMock())
        with patch("app.vacation_delivery.SessionLocal", session), patch(
            "app.vacation_delivery.manager_chat", return_value="123"
        ), patch("app.vacation_delivery.chat_id_allowed", return_value=True):
            await deliver_pending(bot)
            await deliver_pending(bot)
            self.assertEqual([call.args[0] for call in bot.send_message.await_args_list], [123])
            with session() as db:
                row = db.get(EmployeeVacationRequest, 1)
                self.assertEqual(row.manager_notice, "sent")
                row.status = "pending_hr"
                db.commit()
            await deliver_pending(bot)
            await deliver_pending(bot)
        self.assertEqual([call.args[0] for call in bot.send_message.await_args_list], [123, 456])


class EmployeeCabinetTests(unittest.TestCase):
    def test_vacation_request_preview_duplicate_and_owner(self):
        from app.adaptation_planning import CalendarDates
        from app.models import EmployeeVacationRequest
        from app.vacation import VacationPeriod, calendar_month, decide, preview, requests_for, route_to_current_manager, submit

        engine = create_engine("sqlite://")
        cabinet.Employee.__table__.create(engine)
        EmployeeVacationRequest.__table__.create(engine)
        period = VacationPeriod(starts_on=date(2090, 1, 1), ends_on=date(2090, 1, 3))
        with sessionmaker(bind=engine)() as db:
            db.add(cabinet.Employee(id=70, full_name="Employee", created_at=datetime.now()))
            db.commit()
            with patch.object(CalendarDates, "working", side_effect=lambda day: day.day != 2):
                month = calendar_month(db, "2090-01")
                self.assertEqual(month["days"][1], {"date": "2090-01-02", "workday": False})
                self.assertEqual(len(month["days"]), 31)
                self.assertEqual(preview(db, period), dict(calendar_days=3, workdays=2, non_workdays=1))
                first = submit(db, 70, period)
                self.assertEqual(submit(db, 70, period), first)
                with self.assertRaisesRegex(ValueError, "уже есть заявка"):
                    submit(db, 70, VacationPeriod(starts_on=period.ends_on, ends_on=period.ends_on))
                self.assertEqual(requests_for(db, 70), [first])
                self.assertEqual(requests_for(db, 80), [])
                row_id = first["id"]
                with self.assertRaises(LookupError):
                    decide(db, row_id, approved=True, employee_id=80, hr_account_id=1)
                with self.assertRaises(ValueError):
                    decide(db, row_id, approved=True, employee_id=70, hr_account_id=1)
                self.assertIn("не назначен", requests_for(db, 70, for_hr=True)[0]["manager_issue"])
                self.assertNotIn("manager_issue", requests_for(db, 70)[0])
                db.get(cabinet.Employee, 70).manager_employee_id = 71
                db.flush()
                self.assertTrue(requests_for(db, 70, for_hr=True)[0]["can_route"])
                with patch("app.vacation_delivery.manager_contact", return_value=("123", None)):
                    self.assertEqual(route_to_current_manager(db, 70, row_id)["manager_notice"], "pending")
                    with self.assertRaises(ValueError):
                        route_to_current_manager(db, 70, row_id)
                with patch("app.vacation_delivery.manager_chat", return_value="123"):
                    with self.assertRaisesRegex(ValueError, "устарела"):
                        decide(db, row_id, approved=True, telegram_id="123", manager_revision=1)
                    with self.assertRaises(PermissionError):
                        decide(db, row_id, approved=True, telegram_id="456", manager_revision=2)
                    self.assertEqual(decide(db, row_id, approved=True, telegram_id="123", manager_revision=2)["status"], "pending_hr")
                    with self.assertRaises(ValueError):
                        decide(db, row_id, approved=False, telegram_id="123", manager_revision=2)
                self.assertEqual(decide(db, row_id, approved=True, employee_id=70, hr_account_id=1)["status"], "approved")
                self.assertEqual(db.get(EmployeeVacationRequest, row_id).hr_account_id, 1)
        engine.dispose()

    def test_vacation_balance_preserves_zero_and_is_scoped_by_employee_and_year(self):
        from app.models import EmployeeVacationBalance
        from app.vacation import BalanceInput, balance, save_balance
        from app import vacation

        engine = create_engine("sqlite://")
        cabinet.Employee.__table__.create(engine)
        EmployeeVacationBalance.__table__.create(engine)
        with sessionmaker(bind=engine)() as db:
            db.add(cabinet.Employee(id=70, full_name="Employee", created_at=datetime.now()))
            db.commit()
            with patch.object(vacation, "current_year", return_value=2026):
                self.assertIsNone(balance(db, 70)["used_days"])
                save_balance(db, 70, 1, BalanceInput(year=2026, used_days=0, remaining_days=12))
                self.assertEqual(balance(db, 70), dict(year=2026, used_days=0, remaining_days=12))
                self.assertIsNone(balance(db, 80)["remaining_days"])
            with patch.object(vacation, "current_year", return_value=2027):
                self.assertIsNone(balance(db, 70)["remaining_days"])
        engine.dispose()

    @staticmethod
    def signed(now, user_id=123):
        fields = {"auth_date": str(now), "user": json.dumps({"id": user_id}), "signature": "opaque"}
        key = hmac.digest(b"WebAppData", b"test-token", hashlib.sha256)
        payload = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
        fields["hash"] = hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()
        return urlencode(fields)

    def test_signed_user_expiry_tampering_and_duplicate_fields(self):
        now = int(time.time())
        raw = self.signed(now)
        self.assertEqual(cabinet.signed_telegram_id(raw, "test-token", now), "123")
        self.assertIsNone(cabinet.signed_telegram_id(raw.replace("123", "124"), "test-token", now))
        self.assertIsNone(cabinet.signed_telegram_id(raw, "test-token", now + 1801))
        self.assertIsNone(cabinet.signed_telegram_id(raw + "&auth_date=0", "test-token", now))

    def test_pilot_requires_current_verified_binding_and_exact_card(self):
        employee = SimpleNamespace(id=70, employee_stage="staff", is_bot_blocked=False)
        with patch.object(cabinet.settings, "EMPLOYEE_CABINET_URL", "https://example.test/employee-cabinet"), \
                patch.object(cabinet, "find_employees_by_channel_user_id", return_value=[employee]), \
                patch.object(cabinet, "verification_required", return_value=True), \
                patch.object(cabinet, "is_verified", return_value=True) as verified, \
                patch.object(cabinet, "get_primary_chat_id", return_value="123"):
            self.assertIs(cabinet.pilot_employee(None, "123"), employee)
            self.assertIsNone(cabinet.pilot_employee(None, "456"))
            employee.id = 80
            self.assertIs(cabinet.pilot_employee(None, "123"), employee)
            employee.id = 84
            self.assertIs(cabinet.pilot_employee(None, "123"), employee)
            employee.id = 71
            self.assertIsNone(cabinet.pilot_employee(None, "123"))
            employee.id = 70
            verified.return_value = False
            self.assertIsNone(cabinet.pilot_employee(None, "123"))

    def test_public_shell_has_no_data_and_download_requires_auth(self):
        app = FastAPI()
        app.include_router(cabinet.router)
        with TestClient(app) as client:
            self.assertEqual(client.get("/employee-cabinet").status_code, 200)
            self.assertIn("Использовано в этом году", client.get("/employee-cabinet").text)
            for path in ("profile", "files/1", "vacation/requests", "vacation/calendar", "colleagues", "colleagues/71/avatar", "knowledge"):
                response = client.get(f"/employee-cabinet/{path}")
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.headers["cache-control"], "no-store")

    def test_knowledge_only_exports_visible_active_links_and_breaks_cycles(self):
        from app.models import BotMenuButton, BotMenuSet

        engine = create_engine("sqlite://")
        self.addCleanup(engine.dispose)
        for model in (BotMenuSet, BotMenuButton):
            model.__table__.create(engine)
        with sessionmaker(bind=engine)() as db:
            db.add_all([
                BotMenuSet(id=1, title="Root"), BotMenuSet(id=2, title="Section"),
                BotMenuSet(id=3, title="Private", target_employee_ids="80"),
                BotMenuSet(id=4, title="Wrong stage", target_employee_stages="adaptation"),
                BotMenuButton(menu_set_id=1, label="Guides", action_type="open_set", target_menu_set_id=2, is_active=True),
                BotMenuButton(menu_set_id=1, label="Private", action_type="open_set", target_menu_set_id=3, is_active=True),
                BotMenuButton(menu_set_id=1, label="Other stage", action_type="open_set", target_menu_set_id=4, is_active=True),
                BotMenuButton(menu_set_id=2, label="Back", action_type="open_set", target_menu_set_id=1, is_active=True),
                BotMenuButton(menu_set_id=2, label="Read", action_type="open_url", url="https://example.com/guide", is_active=True),
                BotMenuButton(menu_set_id=2, label="Unsafe", action_type="open_url", url="javascript:alert(1)", is_active=True),
                BotMenuButton(menu_set_id=2, label="Hidden", action_type="open_url", url="https://example.com/hidden", is_active=False),
                BotMenuButton(menu_set_id=2, label="Run", action_type="launch_scenario", is_active=True),
                BotMenuButton(menu_set_id=3, label="Hidden", action_type="open_url", url="https://example.com/private", is_active=True),
                BotMenuButton(menu_set_id=4, label="Hidden", action_type="open_url", url="https://example.com/other", is_active=True),
            ])
            db.commit()
            employee = cabinet.Employee(id=70, employee_stage="staff")
            self.assertEqual(cabinet.knowledge_links(db, employee, 1), [
                {"label": "Guides", "children": [{"label": "Read", "url": "https://example.com/guide"}]},
            ])

    def test_colleagues_exposes_only_work_directory_fields(self):
        from app.models import CatalogGroup, CatalogMembership

        with TemporaryDirectory() as directory:
            engine = create_engine(f"sqlite:///{(Path(directory) / 'directory.db').as_posix()}", poolclass=NullPool)
            self.addCleanup(engine.dispose)
            for model in (cabinet.Employee, CatalogGroup, CatalogMembership):
                model.__table__.create(engine)
            sessions = sessionmaker(bind=engine)
            with sessions() as db:
                for person_id, name, stage, username in (
                    (70, "Viewer", "staff", None), (71, "Analyst", "ipr", "@analyst_1"),
                    (72, "Candidate", "candidate", "@candidate_1"), (73, "Designer", "adaptation", "bad/path"),
                    (74, "Former", "dismissed", "@former_1"), (75, "PM", "staff", "@pm_person"),
                ):
                    db.add(cabinet.Employee(id=person_id, full_name=name, employee_stage=stage,
                                            telegram_username=username, created_at=datetime.now()))
                db.add(CatalogGroup(id=10, scope="people", name="Analytics", normalized_name="analytics"))
                db.add(CatalogMembership(scope="people", group_id=10, object_id=71))
                db.commit()
            app = FastAPI()
            app.include_router(cabinet.router)
            with patch.object(cabinet, "get_session", sessions), patch.object(
                cabinet, "authorize", return_value=SimpleNamespace(id=70)
            ), patch.object(cabinet, "get_primary_chat_id", side_effect=lambda person, **_: "123" if person.id == 71 else None), patch.object(
                cabinet, "find_employees_by_channel_user_id", return_value=[SimpleNamespace(id=71)],
            ), patch("app.cabinet_avatars.telegram_avatar", new_callable=AsyncMock, return_value=b"\xff\xd8\xff") as avatar:
                with TestClient(app) as client:
                    response = client.get("/employee-cabinet/colleagues")
                    photo = client.get("/employee-cabinet/colleagues/71/avatar")
                    self.assertEqual(photo.status_code, 200)
                    self.assertEqual(photo.headers["content-type"], "image/jpeg")
                    self.assertEqual(photo.headers["cache-control"], "no-store")
                    for excluded in (70, 72, 74, 75, 999):
                        self.assertEqual(client.get(f"/employee-cabinet/colleagues/{excluded}/avatar").status_code, 404)
                    avatar.assert_awaited_once_with("123")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["cache-control"], "no-store")
            rows = {row["name"]: row for row in response.json()}
            self.assertEqual(set(rows), {"Analyst", "Designer", "PM"})
            self.assertEqual(rows["Analyst"], {"name": "Analyst", "position": None, "username": "analyst_1",
                                               "avatar_id": 71, "group_id": 10, "group_name": "Analytics"})
            self.assertIsNone(rows["Designer"]["group_name"])
            self.assertIsNone(rows["Designer"]["username"])
            self.assertIsNone(rows["PM"]["username"])

    def test_download_enforces_owner_direction_and_storage_path(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            engine = create_engine(f"sqlite:///{(root / 'test.db').as_posix()}")
            cabinet.EmployeeFile.__table__.create(engine)
            sessions = sessionmaker(bind=engine)
            own = root / "70" / "own.txt"
            own.parent.mkdir()
            own.write_text("own file", encoding="utf-8")
            outside = root / "outside.txt"
            outside.write_text("outside", encoding="utf-8")
            with sessions() as db:
                for file_id, employee_id, direction, path in (
                    (1, 70, "inbound", own), (2, 71, "inbound", own),
                    (3, 70, "outbound", own), (4, 70, "inbound", outside),
                ):
                    db.add(cabinet.EmployeeFile(id=file_id, employee_id=employee_id, direction=direction,
                        category="file", original_filename=path.name, stored_path=str(path), created_at=datetime.now()))
                db.commit()
            app = FastAPI()
            app.include_router(cabinet.router)
            with patch.object(cabinet, "get_session", sessions), \
                    patch.object(cabinet.settings, "FILE_STORAGE_DIR", directory), \
                    patch.object(cabinet, "authorize", return_value=SimpleNamespace(id=70)), TestClient(app) as client:
                response = client.get("/employee-cabinet/files/1")
                self.assertEqual(response.content, b"own file")
                self.assertIn("attachment", response.headers["content-disposition"])
                for file_id in (2, 3, 4):
                    self.assertEqual(client.get(f"/employee-cabinet/files/{file_id}").status_code, 404)
            engine.dispose()
