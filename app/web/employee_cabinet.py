import hashlib
import hmac
import json
import time
from pathlib import Path
from urllib.parse import parse_qsl

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

from ..config import settings
from ..database import get_session
from ..messaging.identity import find_employees_by_channel_user_id, get_primary_chat_id
from ..models import Employee, EmployeeFile
from ..staff_email_verification import is_verified, verification_required

router = APIRouter(prefix="/employee-cabinet")
PILOT_EMPLOYEE_ID = 70
PRIVATE_HEADERS = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}


def signed_telegram_id(raw, token, now):
    if not raw or len(raw) > 8192 or not token:
        return None
    try:
        pairs = parse_qsl(raw, keep_blank_values=True, strict_parsing=True, max_num_fields=32)
        fields = dict(pairs)
        if len(pairs) != len(fields):
            return None
        signature = fields.pop("hash")
        secret = hmac.digest(b"WebAppData", token.encode(), hashlib.sha256)
        check = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
        if not hmac.compare_digest(hmac.new(secret, check.encode(), hashlib.sha256).hexdigest(), signature):
            return None
        if not -30 <= now - int(fields["auth_date"]) <= 1800:
            return None
        user_id = json.loads(fields["user"])["id"]
        return str(user_id) if type(user_id) is int and 0 < user_id < 2**52 else None
    except (KeyError, ValueError, TypeError):
        return None


def pilot_employee(db, telegram_id):
    if not telegram_id or not settings.EMPLOYEE_CABINET_URL:
        return None
    matches = find_employees_by_channel_user_id(db, channel="telegram", external_user_id=telegram_id)
    if len(matches) != 1:
        return None
    person = matches[0]
    if (person.id == PILOT_EMPLOYEE_ID and person.employee_stage in {"staff", "adaptation", "ipr"}
            and not person.is_bot_blocked and verification_required(person)
            and is_verified(db, person, telegram_id) and get_primary_chat_id(person, db=db) == telegram_id):
        return person
    return None


def authorize(db, request):
    telegram_id = signed_telegram_id(request.headers.get("X-Telegram-Init-Data"), settings.TELEGRAM_BOT_TOKEN, time.time())
    employee = pilot_employee(db, telegram_id)
    if not employee:
        raise HTTPException(403, "Кабинет доступен только через Telegram пилота.", headers=PRIVATE_HEADERS)
    return employee


def own_files(db, employee):
    return db.query(EmployeeFile).filter_by(employee_id=employee.id, direction="inbound")


@router.get("", include_in_schema=False)
def cabinet_page():
    return FileResponse(Path(__file__).resolve().parents[1] / "static" / "employee-cabinet.html", headers=PRIVATE_HEADERS)


@router.get("/profile")
def profile(request: Request):
    with get_session() as db:
        employee = authorize(db, request)

        def name(employee_id):
            related = db.get(Employee, employee_id) if employee_id else None
            return related.full_name if related else None

        return JSONResponse({
            "name": employee.full_name, "position": employee.desired_position,
            "email": employee.work_email, "hours": employee.work_hours,
            "first_workday": employee.first_workday.isoformat() if employee.first_workday else None,
            "manager": name(employee.manager_employee_id), "adaptation_mentor": name(employee.mentor_adaptation_employee_id),
            "development_mentor": name(employee.mentor_ipr_employee_id),
            "files": [{"id": item.id, "name": item.original_filename, "size": item.file_size}
                      for item in own_files(db, employee).order_by(EmployeeFile.id.desc())],
        }, headers=PRIVATE_HEADERS)


@router.get("/files/{file_id}")
def download(file_id: int, request: Request):
    with get_session() as db:
        employee = authorize(db, request)
        item = own_files(db, employee).filter_by(id=file_id).first()
        if not item:
            raise HTTPException(404, headers=PRIVATE_HEADERS)
        root = Path(settings.FILE_STORAGE_DIR).expanduser().resolve() / str(employee.id)
        path = Path(item.stored_path).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise HTTPException(404, headers=PRIVATE_HEADERS)
        return FileResponse(path, filename=item.original_filename, media_type="application/octet-stream", headers=PRIVATE_HEADERS)
