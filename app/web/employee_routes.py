from datetime import datetime
from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_session
from ..employee_card import render_employee_card_png
from ..file_storage import build_employee_file_path
from ..file_storage import build_employee_profile_photo_path
from ..messaging.identity import EmployeeIdentityConflictError, get_primary_chat_id
from ..models import Employee, EmployeeDocumentLink, EmployeeFile, FlowLaunchRequest
from ..time_utils import utc_now
from .employees import (
    CANDIDATE_WORK_STAGE_VALUES,
    EMPLOYEE_STAGE_VALUES,
    _apply_employee_update,
    _build_employee_detail_payload,
    _build_employee_views,
    _create_employee_record,
    _delete_employee_document_link,
    _delete_employee_record,
    _employee_display_name,
    _employee_identity_conflict_detail,
    _employee_identity_integrity_detail,
    _employee_list_kind,
    _employee_list_meta,
    _is_employee_identity_integrity_error,
    _launch_employee_flow_now,
    _promote_candidate_to_adaptation,
    _reset_employee_bot_linkage,
    _save_offer_document_file,
    _save_offer_document_link,
    _schedule_employee_flow_request,
    _send_file_to_telegram,
    _send_manual_bot_message,
    _serialize_document_link,
    _serialize_employee_view,
)
from .support import render_template, require_api_auth, require_auth

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def get_db():
    with get_session() as db:
        yield db


def _employee_edit_redirect(employee_id: int, flash_message: str | None = None, flash_type: str = "success") -> RedirectResponse:
    url = f"/app/employees/{employee_id}"
    if flash_message:
        from urllib.parse import urlencode

        url = f"{url}?{urlencode({'flash_message': flash_message, 'flash_type': flash_type})}"
    return RedirectResponse(url=url, status_code=status.HTTP_303_SEE_OTHER)


def _delete_employee_profile_photo(employee: Employee) -> None:
    profile_photo_path = (getattr(employee, "profile_photo_path", None) or "").strip()
    if profile_photo_path:
        path = Path(profile_photo_path)
        try:
            if path.exists():
                path.unlink()
        except OSError:
            pass
    employee.profile_photo_path = None
    employee.profile_photo_filename = None


@router.get("/candidates")
def candidates_page(request: Request):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    return RedirectResponse(url="/app/employees?list_kind=candidates", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/employees")
def employees_page(request: Request):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    return RedirectResponse(url="/app/employees", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/employees/{employee_id}/edit")
def edit_employee_form(
    request: Request,
    employee_id: int,
    db: Session = Depends(get_db),
):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    employee = db.get(Employee, employee_id)
    if not employee:
        return RedirectResponse(url="/employees", status_code=status.HTTP_303_SEE_OTHER)
    return _employee_edit_redirect(
        employee_id,
        flash_message=request.query_params.get("flash_message"),
        flash_type=request.query_params.get("flash_type", "success"),
    )


@router.post("/employees/{employee_id}")
def update_employee(
    request: Request,
    employee_id: int,
    full_name: str = Form(""),
    telegram_user_id: str = Form(""),
    telegram_username: str = Form(""),
    first_workday: str = Form(""),
    desired_position: str = Form(""),
    birth_date: str = Form(""),
    work_email: str = Form(""),
    work_hours: str = Form(""),
    is_manager: str = Form("false"),
    is_mentor: str = Form("false"),
    manager_employee_id: str = Form(""),
    mentor_adaptation_employee_id: str = Form(""),
    mentor_ipr_employee_id: str = Form(""),
    adaptation_tasks_url: str = Form(""),
    adaptation_feedback_url: str = Form(""),
    adaptation_midpoint: str = Form(""),
    adaptation_end: str = Form(""),
    employee_stage: str = Form(""),
    candidate_work_stage: str = Form(""),
    salary_expectation: str = Form(""),
    personal_data_consent: str = Form("false"),
    employee_data_consent: str = Form("false"),
    is_bot_blocked: str = Form("false"),
    test_task_due_at: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    current_user = getattr(request.state, "current_user", None)
    employee = db.get(Employee, employee_id)
    if not employee:
        return RedirectResponse(url="/employees", status_code=status.HTTP_303_SEE_OTHER)
    try:
        employee = _apply_employee_update(
            db,
            employee,
            full_name=full_name,
            chat_id=telegram_user_id,
            chat_handle=telegram_username,
            first_workday=first_workday,
            desired_position=desired_position,
            birth_date=birth_date,
            work_email=work_email,
            work_hours=work_hours,
            is_manager=is_manager == "true",
            is_mentor=is_mentor == "true",
            manager_employee_id=manager_employee_id,
            mentor_adaptation_employee_id=mentor_adaptation_employee_id,
            mentor_ipr_employee_id=mentor_ipr_employee_id,
            adaptation_tasks_url=adaptation_tasks_url,
            adaptation_feedback_url=adaptation_feedback_url,
            adaptation_midpoint=adaptation_midpoint,
            adaptation_end=adaptation_end,
            employee_stage=employee_stage,
            candidate_work_stage=candidate_work_stage,
            salary_expectation=salary_expectation,
            personal_data_consent=personal_data_consent == "true",
            employee_data_consent=employee_data_consent == "true",
            is_bot_blocked=is_bot_blocked == "true",
            test_task_due_at=test_task_due_at,
            notes=notes,
            assigned_by_account_id=getattr(current_user, "id", None),
        )
    except EmployeeIdentityConflictError as exc:
        db.rollback()
        return _employee_edit_redirect(employee_id, _employee_identity_conflict_detail(exc), "error")
    except IntegrityError as exc:
        db.rollback()
        if _is_employee_identity_integrity_error(exc):
            return _employee_edit_redirect(employee_id, _employee_identity_integrity_detail(telegram_user_id), "error")
        raise
    except ValueError as exc:
        db.rollback()
        return _employee_edit_redirect(employee_id, str(exc), "error")
    return RedirectResponse(
        url="/candidates" if _employee_list_kind(employee) == "candidates" else "/employees",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/employees/{employee_id}/profile-photo")
async def upload_employee_profile_photo(
    request: Request,
    employee_id: int,
    upload: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    employee = db.get(Employee, employee_id)
    if not employee:
        return RedirectResponse(url="/employees", status_code=status.HTTP_303_SEE_OTHER)
    filename = (upload.filename or "").strip()
    if not filename:
        return _employee_edit_redirect(employee_id, "Выберите файл фотографии.", "error")
    destination = build_employee_profile_photo_path(employee_id, filename)
    content = await upload.read()
    destination.write_bytes(content)
    _delete_employee_profile_photo(employee)
    employee.profile_photo_path = str(destination)
    employee.profile_photo_filename = filename
    db.commit()
    return _employee_edit_redirect(employee_id, "Фотография сотрудника сохранена.", "success")


@router.post("/employees/{employee_id}/profile-photo/delete")
def delete_employee_profile_photo(
    request: Request,
    employee_id: int,
    db: Session = Depends(get_db),
):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    employee = db.get(Employee, employee_id)
    if not employee:
        return RedirectResponse(url="/employees", status_code=status.HTTP_303_SEE_OTHER)
    _delete_employee_profile_photo(employee)
    db.commit()
    return _employee_edit_redirect(employee_id, "Фотография сотрудника удалена.", "success")


@router.get("/employees/{employee_id}/card-image")
def employee_card_image(
    request: Request,
    employee_id: int,
    db: Session = Depends(get_db),
):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    employee = db.get(Employee, employee_id)
    if not employee:
        return RedirectResponse(url="/employees", status_code=status.HTTP_303_SEE_OTHER)
    try:
        image_bytes = render_employee_card_png(employee)
    except ImportError:
        return _employee_edit_redirect(employee_id, "Не удалось собрать PNG карточки сотрудника.", "error")
    return StreamingResponse(BytesIO(image_bytes), media_type="image/png")


@router.post("/employees/{employee_id}/delete")
def delete_employee(
    request: Request,
    employee_id: int,
    db: Session = Depends(get_db),
):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    employee = db.get(Employee, employee_id)
    if employee:
        redirect_url = _delete_employee_record(db, employee)
        return RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)
    return RedirectResponse(url="/employees", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/employees")
def create_employee(
    request: Request,
    full_name: str = Form(""),
    telegram_user_id: str = Form(""),
    telegram_username: str = Form(""),
    first_workday: str = Form(""),
    employee_stage: str = Form(""),
    candidate_work_stage: str = Form(""),
    db: Session = Depends(get_db),
):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    list_kind = "candidates" if (employee_stage or "").strip() == "candidate" else "employees"
    try:
        employee = _create_employee_record(
            db,
            full_name=full_name,
            chat_id=telegram_user_id,
            chat_handle=telegram_username,
            first_workday=first_workday,
            employee_stage=employee_stage,
            candidate_work_stage=candidate_work_stage,
            list_kind=list_kind,
        )
    except EmployeeIdentityConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_employee_identity_conflict_detail(exc))
    except IntegrityError as exc:
        db.rollback()
        if _is_employee_identity_integrity_error(exc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=_employee_identity_integrity_detail(telegram_user_id),
            )
        raise

    return RedirectResponse(
        url="/candidates" if _employee_list_kind(employee) == "candidates" else "/employees",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/employees/{employee_id}/launch")
async def launch_flow(
    request: Request,
    employee_id: int,
    flow_key: str = Form(...),
    db: Session = Depends(get_db),
):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    employee = db.get(Employee, employee_id)
    if not employee:
        return RedirectResponse(url="/employees", status_code=status.HTTP_303_SEE_OTHER)
    error_message = await _launch_employee_flow_now(db, employee, flow_key=flow_key)
    if error_message:
        return _employee_edit_redirect(employee_id, error_message, "error")
    return _employee_edit_redirect(employee_id, "Сценарий успешно запущен.", "success")


@router.post("/employees/{employee_id}/schedule")
def schedule_flow(
    request: Request,
    employee_id: int,
    flow_key: str = Form(""),
    requested_at: str = Form(""),
    db: Session = Depends(get_db),
):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    employee = db.get(Employee, employee_id)
    if not employee:
        return RedirectResponse(url="/employees", status_code=status.HTTP_303_SEE_OTHER)
    error_message = _schedule_employee_flow_request(
        db,
        employee,
        flow_key=flow_key,
        requested_at=requested_at,
    )
    if error_message:
        return _employee_edit_redirect(employee_id, error_message, "error")
    return _employee_edit_redirect(employee_id, "Сценарий запланирован.", "success")


@router.post("/employees/{employee_id}/schedule/{launch_request_id}/delete")
def delete_scheduled_flow(
    request: Request,
    employee_id: int,
    launch_request_id: int,
    db: Session = Depends(get_db),
):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    launch_request = db.get(FlowLaunchRequest, launch_request_id)
    if (
        not launch_request
        or launch_request.employee_id != employee_id
        or launch_request.launch_type != "scheduled"
        or launch_request.processed_at is not None
        or launch_request.processing_status != "pending"
    ):
        return _employee_edit_redirect(employee_id, "Запланированный сценарий не найден.", "error")
    db.delete(launch_request)
    db.commit()
    return _employee_edit_redirect(employee_id, "Запланированная отправка удалена.", "success")


@router.post("/employees/{employee_id}/files")
async def upload_employee_file(
    request: Request,
    employee_id: int,
    upload: UploadFile = File(...),
    category: str = Form("hr_file"),
    send_to_telegram: str = Form("false"),
    db: Session = Depends(get_db),
):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
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
        created_at=utc_now(),
    )
    db.add(db_file)
    db.commit()

    chat_id = get_primary_chat_id(employee, db=db)
    if send_to_telegram == "true" and chat_id and settings.TELEGRAM_BOT_TOKEN:
        await _send_file_to_telegram(chat_id, destination, filename)

    return _employee_edit_redirect(employee_id, "Файл загружен.", "success")


@router.get("/employees/{employee_id}/files/{file_id}/download")
def download_employee_file(
    request: Request,
    employee_id: int,
    file_id: int,
    db: Session = Depends(get_db),
):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    db_file = db.get(EmployeeFile, file_id)
    if not db_file or db_file.employee_id != employee_id:
        return RedirectResponse(url="/employees", status_code=status.HTTP_303_SEE_OTHER)
    path = Path(db_file.stored_path)
    if not path.exists():
        return _employee_edit_redirect(employee_id, "Файл не найден в хранилище.", "error")
    return FileResponse(
        path=str(path),
        filename=db_file.original_filename,
        media_type=db_file.mime_type or "application/octet-stream",
    )


@router.post("/employees/{employee_id}/files/{file_id}/send")
async def send_employee_file(
    request: Request,
    employee_id: int,
    file_id: int,
    db: Session = Depends(get_db),
):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    employee = db.get(Employee, employee_id)
    db_file = db.get(EmployeeFile, file_id)
    if not employee or not db_file or db_file.employee_id != employee_id:
        return RedirectResponse(url="/employees", status_code=status.HTTP_303_SEE_OTHER)
    chat_id = get_primary_chat_id(employee, db=db)
    if not chat_id or not settings.TELEGRAM_BOT_TOKEN:
        return _employee_edit_redirect(employee_id, "Нельзя отправить файл: нет Telegram-привязки или токена бота.", "error")

    path = Path(db_file.stored_path)
    if path.exists():
        await _send_file_to_telegram(chat_id, path, db_file.original_filename)
        return _employee_edit_redirect(employee_id, "Файл отправлен в Telegram.", "success")
    return _employee_edit_redirect(employee_id, "Файл не найден в хранилище.", "error")


@router.post("/employees/{employee_id}/document-links")
def create_employee_document_link(
    request: Request,
    employee_id: int,
    url: str = Form(""),
    db: Session = Depends(get_db),
):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    employee = db.get(Employee, employee_id)
    if not employee:
        return RedirectResponse(url="/employees", status_code=status.HTTP_303_SEE_OTHER)
    _, error_message = _save_offer_document_link(db, employee_id, url)
    if error_message:
        return _employee_edit_redirect(employee_id, error_message, "error")
    return _employee_edit_redirect(employee_id, "Ссылка на оффер сохранена.", "success")


@router.post("/employees/{employee_id}/document-links/{link_id}/delete")
def delete_employee_document_link(
    request: Request,
    employee_id: int,
    link_id: int,
    db: Session = Depends(get_db),
):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    link_row = db.get(EmployeeDocumentLink, link_id)
    if not link_row or link_row.employee_id != employee_id:
        return _employee_edit_redirect(employee_id, "Ссылка на документ не найдена.", "error")
    _delete_employee_document_link(db, link_row)
    return _employee_edit_redirect(employee_id, "Ссылка на документ удалена.", "success")


@router.get("/api/employees")
def employees_api(
    request: Request,
    list_kind: str = "employees",
    db: Session = Depends(get_db),
):
    require_api_auth(request)
    normalized_kind = "candidates" if list_kind == "candidates" else "employees"
    employee_views = _build_employee_views(normalized_kind, db)
    return {
        "meta": {
            **_employee_list_meta(normalized_kind),
            "list_kind": normalized_kind,
            "classic_page_url": "/candidates" if normalized_kind == "candidates" else "/employees",
        },
        "items": [_serialize_employee_view(item, normalized_kind) for item in employee_views],
    }


@router.post("/api/employees")
def create_employee_api(
    request: Request,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    require_api_auth(request)
    list_kind = "candidates" if (payload.get("list_kind") or "").strip() == "candidates" else "employees"
    try:
        employee = _create_employee_record(
            db,
            full_name=str(payload.get("full_name") or ""),
            chat_id=str(payload.get("chat_id") or ""),
            chat_handle=str(payload.get("chat_handle") or ""),
            first_workday=str(payload.get("first_workday") or ""),
            employee_stage=str(payload.get("employee_stage") or ""),
            candidate_work_stage=str(payload.get("candidate_work_stage") or ""),
            list_kind=list_kind,
        )
    except EmployeeIdentityConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_employee_identity_conflict_detail(exc))
    except IntegrityError as exc:
        db.rollback()
        if _is_employee_identity_integrity_error(exc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=_employee_identity_integrity_detail(str(payload.get("chat_id") or "")),
            )
        raise
    views = _build_employee_views(list_kind, db)
    item = next((row for row in views if row["employee"].id == employee.id), None)
    return {
        "meta": {
            **_employee_list_meta(list_kind),
            "list_kind": list_kind,
            "classic_page_url": "/candidates" if list_kind == "candidates" else "/employees",
        },
        "item": _serialize_employee_view(item, list_kind) if item else None,
    }


@router.get("/api/employees/{employee_id}")
def employee_detail_api(
    request: Request,
    employee_id: int,
    db: Session = Depends(get_db),
):
    require_api_auth(request)
    employee = db.get(Employee, employee_id)
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сотрудник не найден")
    return _build_employee_detail_payload(db, employee)


@router.post("/api/employees/{employee_id}")
def update_employee_api(
    request: Request,
    employee_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    current_user = require_api_auth(request)
    employee = db.get(Employee, employee_id)
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сотрудник не найден")
    try:
        employee = _apply_employee_update(
            db,
            employee,
            full_name=str(payload.get("full_name") or ""),
            chat_id=str(payload.get("chat_id") or get_primary_chat_id(employee, db=db) or ""),
            chat_handle=str(payload.get("chat_handle") or ""),
            first_workday=str(payload.get("first_workday") or ""),
            desired_position=str(payload.get("desired_position") or ""),
            birth_date=str(payload.get("birth_date") or ""),
            work_email=str(payload.get("work_email") or ""),
            work_hours=str(payload.get("work_hours") or ""),
            is_manager=bool(payload.get("is_manager")),
            is_mentor=bool(payload.get("is_mentor")),
            manager_employee_id=str(payload.get("manager_employee_id") or ""),
            mentor_adaptation_employee_id=str(payload.get("mentor_adaptation_employee_id") or ""),
            mentor_ipr_employee_id=str(payload.get("mentor_ipr_employee_id") or ""),
            adaptation_tasks_url=str(payload.get("adaptation_tasks_url") or ""),
            adaptation_feedback_url=str(payload.get("adaptation_feedback_url") or ""),
            adaptation_midpoint=str(payload.get("adaptation_midpoint") or ""),
            adaptation_end=str(payload.get("adaptation_end") or ""),
            employee_stage=str(payload.get("employee_stage") or ""),
            candidate_work_stage=str(payload.get("candidate_work_stage") or ""),
            salary_expectation=str(payload.get("salary_expectation") or ""),
            personal_data_consent=bool(payload.get("personal_data_consent")),
            employee_data_consent=bool(payload.get("employee_data_consent")),
            is_bot_blocked=bool(payload.get("is_bot_blocked")),
            test_task_due_at=str(payload.get("test_task_due_at") or ""),
            notes=str(payload.get("notes") or ""),
            assigned_by_account_id=getattr(current_user, "id", None),
        )
    except EmployeeIdentityConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_employee_identity_conflict_detail(exc))
    except IntegrityError as exc:
        db.rollback()
        if _is_employee_identity_integrity_error(exc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=_employee_identity_integrity_detail(str(payload.get("chat_id") or "")),
            )
        raise
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return _build_employee_detail_payload(db, employee)


@router.post("/api/employees/{employee_id}/bot-message")
async def send_manual_bot_message_api(
    request: Request,
    employee_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    current_user = require_api_auth(request)
    employee = db.get(Employee, employee_id)
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сотрудник не найден")
    error_message = await _send_manual_bot_message(
        db,
        employee,
        text=str(payload.get("text") or ""),
        sender_account_id=getattr(current_user, "id", None),
    )
    if error_message:
        status_code = status.HTTP_409_CONFLICT if employee.is_bot_blocked else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=error_message)
    return _build_employee_detail_payload(db, employee)


@router.post("/api/employees/{employee_id}/document-links")
def create_employee_document_link_api(
    request: Request,
    employee_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    require_api_auth(request)
    employee = db.get(Employee, employee_id)
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сотрудник не найден")
    link_row, error_message = _save_offer_document_link(db, employee_id, str(payload.get("url") or ""))
    if error_message:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_message)
    return {
        "item": _serialize_document_link(link_row, employee_id),
        "payload": _build_employee_detail_payload(db, employee),
    }


@router.post("/api/employees/{employee_id}/document-slots/offer/file")
async def upload_offer_document_file_api(
    request: Request,
    employee_id: int,
    upload: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    require_api_auth(request)
    employee = db.get(Employee, employee_id)
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сотрудник не найден")
    filename = (upload.filename or "").strip() or "offer.bin"
    content = await upload.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Выберите файл оффера.")
    link_row = _save_offer_document_file(
        db,
        employee,
        filename=filename,
        content=content,
        mime_type=upload.content_type,
    )
    return {
        "item": _serialize_document_link(link_row, employee_id),
        "payload": _build_employee_detail_payload(db, employee),
    }


@router.delete("/api/employees/{employee_id}/document-links/{link_id}")
def delete_employee_document_link_api(
    request: Request,
    employee_id: int,
    link_id: int,
    db: Session = Depends(get_db),
):
    require_api_auth(request)
    employee = db.get(Employee, employee_id)
    link_row = db.get(EmployeeDocumentLink, link_id)
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сотрудник не найден")
    if not link_row or link_row.employee_id != employee_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ссылка на документ не найдена")
    _delete_employee_document_link(db, link_row)
    return _build_employee_detail_payload(db, employee)


@router.post("/api/employees/{employee_id}/schedule")
def schedule_employee_flow_api(
    request: Request,
    employee_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    require_api_auth(request)
    employee = db.get(Employee, employee_id)
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сотрудник не найден")
    error_message = _schedule_employee_flow_request(
        db,
        employee,
        flow_key=str(payload.get("flow_key") or ""),
        requested_at=str(payload.get("requested_at") or ""),
    )
    if error_message:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_message)
    return _build_employee_detail_payload(db, employee)


@router.delete("/api/employees/{employee_id}/schedule/{launch_request_id}")
def delete_scheduled_flow_api(
    request: Request,
    employee_id: int,
    launch_request_id: int,
    db: Session = Depends(get_db),
):
    require_api_auth(request)
    employee = db.get(Employee, employee_id)
    launch_request = db.get(FlowLaunchRequest, launch_request_id)
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сотрудник не найден")
    if (
        not launch_request
        or launch_request.employee_id != employee_id
        or launch_request.launch_type != "scheduled"
        or launch_request.processed_at is not None
        or launch_request.processing_status != "pending"
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Запланированный сценарий не найден")
    db.delete(launch_request)
    db.commit()
    return _build_employee_detail_payload(db, employee)


@router.post("/api/employees/{employee_id}/launch")
async def launch_flow_api(
    request: Request,
    employee_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    require_api_auth(request)
    employee = db.get(Employee, employee_id)
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сотрудник не найден")
    error_message = await _launch_employee_flow_now(
        db,
        employee,
        flow_key=str(payload.get("flow_key") or ""),
    )
    if error_message:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_message)
    return _build_employee_detail_payload(db, employee)


@router.post("/api/employees/{employee_id}/promote-to-adaptation")
def promote_employee_to_adaptation_api(
    request: Request,
    employee_id: int,
    db: Session = Depends(get_db),
):
    require_api_auth(request)
    employee = db.get(Employee, employee_id)
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сотрудник не найден")
    try:
        employee = _promote_candidate_to_adaptation(db, employee)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return _build_employee_detail_payload(db, employee)


@router.post("/api/employees/{employee_id}/bot-link/reset")
def reset_employee_bot_linkage_api(
    request: Request,
    employee_id: int,
    db: Session = Depends(get_db),
):
    require_api_auth(request)
    employee = db.get(Employee, employee_id)
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сотрудник не найден")
    employee = _reset_employee_bot_linkage(db, employee)
    return _build_employee_detail_payload(db, employee)


@router.post("/api/employees/{employee_id}/files")
async def upload_employee_file_api(
    request: Request,
    employee_id: int,
    upload: UploadFile = File(...),
    category: str = Form("hr_file"),
    send_to_channel: str = Form("false"),
    db: Session = Depends(get_db),
):
    require_api_auth(request)
    employee = db.get(Employee, employee_id)
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сотрудник не найден")

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
        created_at=utc_now(),
    )
    db.add(db_file)
    db.commit()

    chat_id = get_primary_chat_id(employee, db=db)
    if send_to_channel == "true" and chat_id and settings.TELEGRAM_BOT_TOKEN:
        await _send_file_to_telegram(chat_id, destination, filename)

    return _build_employee_detail_payload(db, employee)


@router.post("/api/employees/{employee_id}/files/{file_id}/send")
async def send_employee_file_api(
    request: Request,
    employee_id: int,
    file_id: int,
    db: Session = Depends(get_db),
):
    require_api_auth(request)
    employee = db.get(Employee, employee_id)
    db_file = db.get(EmployeeFile, file_id)
    if not employee or not db_file or db_file.employee_id != employee_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Файл не найден")
    chat_id = get_primary_chat_id(employee, db=db)
    if not chat_id or not settings.TELEGRAM_BOT_TOKEN:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="У сотрудника не настроен канал для отправки")

    path = Path(db_file.stored_path)
    if path.exists():
        await _send_file_to_telegram(chat_id, path, db_file.original_filename)
    return _build_employee_detail_payload(db, employee)


@router.delete("/api/employees/{employee_id}/files/{file_id}")
def delete_employee_file_api(
    request: Request,
    employee_id: int,
    file_id: int,
    db: Session = Depends(get_db),
):
    require_api_auth(request)
    employee = db.get(Employee, employee_id)
    db_file = db.get(EmployeeFile, file_id)
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сотрудник не найден")
    if not db_file or db_file.employee_id != employee_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Файл не найден")

    path = Path(db_file.stored_path)
    try:
        if path.exists():
            path.unlink()
    except OSError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Не удалось удалить файл из хранилища")

    db.delete(db_file)
    db.commit()
    return _build_employee_detail_payload(db, employee)


@router.delete("/api/employees/{employee_id}")
def delete_employee_api(
    request: Request,
    employee_id: int,
    db: Session = Depends(get_db),
):
    require_api_auth(request)
    employee = db.get(Employee, employee_id)
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сотрудник не найден")
    redirect_url = _delete_employee_record(db, employee)
    return {"redirect_url": redirect_url}


@router.get("/app/employees")
def react_employees_page(
    request: Request,
    list_kind: str = "employees",
):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    normalized_kind = "candidates" if list_kind == "candidates" else "employees"
    return render_template(
        request,
        templates,
        "react_employees.html",
        {
            "active_tab": normalized_kind,
            "react_page_title": "Список сотрудников 2.0",
            "react_api_url": f"/api/employees?list_kind={normalized_kind}",
            "react_create_url": "/api/employees",
            "react_default_list_kind": normalized_kind,
            "classic_page_url": "/candidates" if normalized_kind == "candidates" else "/employees",
        },
    )


@router.get("/app/employees/{employee_id}")
def react_employee_edit_page(
    request: Request,
    employee_id: int,
    db: Session = Depends(get_db),
):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    employee = db.get(Employee, employee_id)
    if not employee:
        return RedirectResponse(url="/employees", status_code=status.HTTP_303_SEE_OTHER)
    list_kind = _employee_list_kind(employee)
    return render_template(
        request,
        templates,
        "react_employee_edit.html",
        {
            "active_tab": list_kind,
            "employee_id": employee_id,
            "react_api_url": f"/api/employees/{employee_id}",
            "react_save_url": f"/api/employees/{employee_id}",
            "list_url": "/app/employees?list_kind=candidates" if list_kind == "candidates" else "/app/employees",
        },
    )
