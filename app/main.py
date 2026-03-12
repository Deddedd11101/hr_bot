from datetime import datetime, date, timedelta
from pathlib import Path
import shutil
from typing import Optional

from aiogram import Bot
from aiogram.types import FSInputFile
from fastapi import Depends, FastAPI, File, Form, Request, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .config import settings
from .database import get_session, init_db
from .file_storage import build_employee_file_path
from .models import Employee, EmployeeFile, FlowLaunchRequest, FlowStepTemplate, HrSettings
from .recruitment_flow import RECRUITMENT_FLOW_KEY


app = FastAPI(title="HR Bot Admin")

templates = Jinja2Templates(directory="app/templates")

app.mount("/static", StaticFiles(directory="app/static"), name="static")


def get_db():
    with get_session() as db:
        yield db


def _is_workday(d: date) -> bool:
    return d.weekday() < 5


def _workdays_between(start: Optional[date], end: date) -> int:
    if not start:
        return 0
    if end <= start:
        return 0
    days = 0
    current = start
    while current < end:
        if _is_workday(current):
            days += 1
        current += timedelta(days=1)
    return days


def _stage_label(first_workday: Optional[date], today: date) -> str:
    if not first_workday:
        return "Не задан"
    if today < first_workday:
        return "До первого рабочего дня"
    workdays = _workdays_between(first_workday, today)
    if workdays < 1:
        return "Первый рабочий день"
    if workdays < 5:
        return "Первая рабочая неделя"
    if workdays < settings.PROBATION_WORKDAYS // 2:
        return "Испытательный срок (первая половина)"
    if workdays < settings.PROBATION_WORKDAYS:
        return "Испытательный срок (вторая половина)"
    return "Испытательный срок завершён"


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/")
def index():
    return RedirectResponse(url="/employees", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/employees")
def employees_page(request: Request, db: Session = Depends(get_db)):
    employees = db.query(Employee).order_by(Employee.id.desc()).all()
    today = datetime.now().date()
    employee_views = [
        {
            "employee": emp,
            "stage": _stage_label(emp.first_workday, today),
            "workdays": _workdays_between(emp.first_workday, today),
        }
        for emp in employees
    ]
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "active_tab": "employees",
            "employee_views": employee_views,
        },
    )


@app.get("/employees/{employee_id}/edit")
def edit_employee_form(
    request: Request,
    employee_id: int,
    db: Session = Depends(get_db),
):
    employee = db.get(Employee, employee_id)
    if not employee:
        return RedirectResponse(url="/employees", status_code=status.HTTP_303_SEE_OTHER)
    employee_files = (
        db.query(EmployeeFile)
        .filter(EmployeeFile.employee_id == employee.id)
        .order_by(EmployeeFile.id.desc())
        .all()
    )
    today = datetime.now().date()
    return templates.TemplateResponse(
        "employee_edit.html",
        {
            "request": request,
            "active_tab": "employees",
            "employee": employee,
            "employee_files": employee_files,
            "stage": _stage_label(employee.first_workday, today),
            "workdays": _workdays_between(employee.first_workday, today),
        },
    )


@app.post("/employees/{employee_id}")
def update_employee(
    employee_id: int,
    full_name: str = Form(""),
    telegram_user_id: str = Form(""),
    first_workday: str = Form(""),
    desired_position: str = Form(""),
    salary_expectation: str = Form(""),
    candidate_status: str = Form(""),
    personal_data_consent: str = Form("false"),
    employee_data_consent: str = Form("false"),
    test_task_link: str = Form(""),
    test_task_due_at: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    employee = db.get(Employee, employee_id)
    if not employee:
        return RedirectResponse(url="/employees", status_code=status.HTTP_303_SEE_OTHER)
    first_day = datetime.strptime(first_workday, "%Y-%m-%d").date() if first_workday else None
    employee.full_name = full_name.strip() or None
    employee.telegram_user_id = (telegram_user_id or "").strip() or None
    employee.first_workday = first_day
    employee.desired_position = desired_position.strip() or None
    employee.salary_expectation = salary_expectation.strip() or None
    employee.candidate_status = candidate_status.strip() or None
    employee.personal_data_consent = personal_data_consent == "true"
    employee.employee_data_consent = employee_data_consent == "true"
    employee.test_task_link = test_task_link.strip() or None
    employee.test_task_due_at = (
        datetime.strptime(test_task_due_at, "%Y-%m-%dT%H:%M")
        if (test_task_due_at or "").strip()
        else None
    )
    employee.notes = notes.strip() or None
    db.commit()
    return RedirectResponse(url="/employees", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/employees/{employee_id}/delete")
def delete_employee(
    employee_id: int,
    db: Session = Depends(get_db),
):
    employee = db.get(Employee, employee_id)
    if employee:
        # Удаляем связанные файлы из БД и с диска.
        employee_files = db.query(EmployeeFile).filter(EmployeeFile.employee_id == employee_id).all()
        for file_row in employee_files:
            path = Path(file_row.stored_path)
            try:
                if path.exists():
                    path.unlink()
            except OSError:
                pass
            db.delete(file_row)

        employee_dir = Path(settings.FILE_STORAGE_DIR).expanduser().resolve() / str(employee_id)
        if employee_dir.exists():
            shutil.rmtree(employee_dir, ignore_errors=True)

        db.delete(employee)
        db.commit()
    return RedirectResponse(url="/employees", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/employees")
def create_employee(
    request: Request,
    full_name: str = Form(""),
    telegram_user_id: str = Form(""),
    first_workday: str = Form(""),
    db: Session = Depends(get_db),
):
    first_day = datetime.strptime(first_workday, "%Y-%m-%d").date() if first_workday else None

    employee = Employee(
        full_name=full_name.strip() or None,
        telegram_user_id=str(telegram_user_id).strip() or None,
        first_workday=first_day,
        created_at=datetime.utcnow(),
        is_flow_scheduled=False,
        candidate_status="new",
    )
    db.add(employee)
    db.flush()
    db.add(
        FlowLaunchRequest(
            employee_id=employee.id,
            flow_key=RECRUITMENT_FLOW_KEY,
            requested_at=datetime.utcnow(),
            processed_at=None,
        )
    )
    db.commit()

    return RedirectResponse(url="/employees", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/employees/{employee_id}/launch")
def launch_flow(
    employee_id: int,
    flow_key: str = Form(...),
    db: Session = Depends(get_db),
):
    employee = db.get(Employee, employee_id)
    if not employee:
        return RedirectResponse(url="/employees", status_code=status.HTTP_303_SEE_OTHER)
    db.add(
        FlowLaunchRequest(
            employee_id=employee.id,
            flow_key=flow_key,
            requested_at=datetime.utcnow(),
            processed_at=None,
        )
    )
    db.commit()
    return RedirectResponse(
        url=f"/employees/{employee_id}/edit",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@app.post("/employees/{employee_id}/files")
async def upload_employee_file(
    employee_id: int,
    upload: UploadFile = File(...),
    category: str = Form("hr_file"),
    send_to_telegram: str = Form("false"),
    db: Session = Depends(get_db),
):
    employee = db.get(Employee, employee_id)
    if not employee:
        return RedirectResponse(url="/employees", status_code=status.HTTP_303_SEE_OTHER)

    filename = upload.filename or "file.bin"
    destination = build_employee_file_path(employee_id, filename)
    content = await upload.read()
    destination.write_bytes(content)

    db_file = EmployeeFile(
        employee_id=employee_id,
        direction="outbound",
        category=(category or "hr_file").strip(),
        telegram_file_id=None,
        telegram_file_unique_id=None,
        original_filename=filename,
        stored_path=str(destination),
        mime_type=upload.content_type,
        file_size=len(content),
        created_at=datetime.utcnow(),
    )
    db.add(db_file)
    db.commit()

    if send_to_telegram == "true" and employee.telegram_user_id and settings.TELEGRAM_BOT_TOKEN:
        await _send_file_to_telegram(employee.telegram_user_id, destination, filename)

    return RedirectResponse(
        url=f"/employees/{employee_id}/edit",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@app.get("/employees/{employee_id}/files/{file_id}/download")
def download_employee_file(
    employee_id: int,
    file_id: int,
    db: Session = Depends(get_db),
):
    db_file = db.get(EmployeeFile, file_id)
    if not db_file or db_file.employee_id != employee_id:
        return RedirectResponse(url="/employees", status_code=status.HTTP_303_SEE_OTHER)
    path = Path(db_file.stored_path)
    if not path.exists():
        return RedirectResponse(url=f"/employees/{employee_id}/edit", status_code=status.HTTP_303_SEE_OTHER)
    return FileResponse(
        path=str(path),
        filename=db_file.original_filename,
        media_type=db_file.mime_type or "application/octet-stream",
    )


@app.post("/employees/{employee_id}/files/{file_id}/send")
async def send_employee_file(
    employee_id: int,
    file_id: int,
    db: Session = Depends(get_db),
):
    employee = db.get(Employee, employee_id)
    db_file = db.get(EmployeeFile, file_id)
    if not employee or not db_file or db_file.employee_id != employee_id:
        return RedirectResponse(url="/employees", status_code=status.HTTP_303_SEE_OTHER)
    if not employee.telegram_user_id or not settings.TELEGRAM_BOT_TOKEN:
        return RedirectResponse(url=f"/employees/{employee_id}/edit", status_code=status.HTTP_303_SEE_OTHER)

    path = Path(db_file.stored_path)
    if path.exists():
        await _send_file_to_telegram(employee.telegram_user_id, path, db_file.original_filename)
    return RedirectResponse(url=f"/employees/{employee_id}/edit", status_code=status.HTTP_303_SEE_OTHER)


async def _send_file_to_telegram(chat_id: str, path: Path, filename: str) -> None:
    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    try:
        await bot.send_document(chat_id=chat_id, document=FSInputFile(str(path), filename=filename))
    finally:
        await bot.session.close()


@app.get("/flows")
def flows_page(request: Request, db: Session = Depends(get_db)):
    flow_steps = db.query(FlowStepTemplate).order_by(FlowStepTemplate.flow_key, FlowStepTemplate.sort_order).all()
    return templates.TemplateResponse(
        "flows.html",
        {
            "request": request,
            "active_tab": "flows",
            "flow_steps": flow_steps,
        },
    )


@app.post("/flows/{step_id}")
def update_flow_step(
    step_id: int,
    custom_text: str = Form(""),
    db: Session = Depends(get_db),
):
    step = db.get(FlowStepTemplate, step_id)
    if step:
        step.custom_text = custom_text.strip() or None
        db.commit()
    return RedirectResponse(url="/flows", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/flows/{step_id}/reset")
def reset_flow_step(
    step_id: int,
    db: Session = Depends(get_db),
):
    step = db.get(FlowStepTemplate, step_id)
    if step:
        step.custom_text = None
        db.commit()
    return RedirectResponse(url="/flows", status_code=status.HTTP_303_SEE_OTHER)


def _get_or_create_hr_settings(db: Session) -> HrSettings:
    settings_row = db.get(HrSettings, 1)
    if settings_row:
        return settings_row
    now = datetime.utcnow()
    settings_row = HrSettings(
        id=1,
        hr_name=None,
        telegram_user_id=None,
        created_at=now,
        updated_at=now,
    )
    db.add(settings_row)
    db.commit()
    db.refresh(settings_row)
    return settings_row


@app.get("/settings")
def settings_page(request: Request, db: Session = Depends(get_db)):
    hr_settings = _get_or_create_hr_settings(db)
    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "active_tab": "settings",
            "hr_settings": hr_settings,
        },
    )


@app.post("/settings")
def update_settings(
    hr_name: str = Form(""),
    telegram_user_id: str = Form(""),
    db: Session = Depends(get_db),
):
    hr_settings = _get_or_create_hr_settings(db)
    hr_settings.hr_name = hr_name.strip() or None
    hr_settings.telegram_user_id = telegram_user_id.strip() or None
    hr_settings.updated_at = datetime.utcnow()
    db.commit()
    return RedirectResponse(url="/settings", status_code=status.HTTP_303_SEE_OTHER)
