from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..database import get_session
from ..file_storage import build_document_library_file_path
from ..models import DocumentLibraryItem
from ..time_utils import utc_now
from .documents import (
    _apply_document_item_payload,
    _build_document_menu_scaffold,
    _delete_document_library_file,
    _documents_workspace_payload,
    _normalize_document_kind,
)
from .support import render_template, require_api_auth, require_auth

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def get_db():
    with get_session() as db:
        yield db


@router.get("/documents")
def documents_page(request: Request):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    return RedirectResponse(url="/app/documents", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/app/documents")
def react_documents_page(request: Request):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    return render_template(
        request,
        templates,
        "react_documents.html",
        {
            "active_tab": "documents",
            "react_api_url": "/api/documents/workspace",
        },
    )


@router.get("/api/documents/workspace")
def documents_workspace_api(request: Request, db: Session = Depends(get_db)):
    require_api_auth(request)
    return _documents_workspace_payload(db)


@router.post("/api/documents/links")
def create_document_link_api(
    request: Request,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    require_api_auth(request)
    title = str(payload.get("title") or "").strip()
    external_url = str(payload.get("external_url") or "").strip()
    if not title:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Укажите название документа")
    if not external_url:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Укажите ссылку")
    last_item = db.query(DocumentLibraryItem).order_by(DocumentLibraryItem.sort_order.desc(), DocumentLibraryItem.id.desc()).first()
    next_order = (last_item.sort_order + 10) if last_item else 10
    now = utc_now()
    item = DocumentLibraryItem(
        title=title,
        description=str(payload.get("description") or "").strip() or None,
        category=str(payload.get("category") or "").strip() or None,
        item_kind="link",
        external_url=external_url,
        original_filename=None,
        stored_path=None,
        mime_type=None,
        file_size=None,
        is_active=bool(payload.get("is_active", True)),
        sort_order=next_order,
        created_at=now,
        updated_at=now,
    )
    db.add(item)
    db.commit()
    return _documents_workspace_payload(db)


@router.post("/api/documents/menu-scaffold")
def create_document_menu_scaffold_api(
    request: Request,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    require_api_auth(request)
    replace_existing = str(payload.get("mode") or "").strip() == "rebuild"
    try:
        root_menu = _build_document_menu_scaffold(
            db,
            str(payload.get("root_title") or "Документы"),
            replace_existing=replace_existing,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return {
        "workspace": _documents_workspace_payload(db),
        "created_root_menu_set_id": root_menu.id,
        "created_root_menu_title": root_menu.title,
        "bot_menu_url": "/app/bot-menu",
    }


@router.post("/api/documents/files")
async def create_document_file_api(
    request: Request,
    title: str = Form(""),
    description: str = Form(""),
    category: str = Form(""),
    is_active: str = Form("true"),
    upload: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    require_api_auth(request)
    normalized_title = title.strip()
    filename = (upload.filename or "").strip()
    if not filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Выберите файл")
    destination = build_document_library_file_path(filename)
    content = await upload.read()
    destination.write_bytes(content)
    last_item = db.query(DocumentLibraryItem).order_by(DocumentLibraryItem.sort_order.desc(), DocumentLibraryItem.id.desc()).first()
    next_order = (last_item.sort_order + 10) if last_item else 10
    now = utc_now()
    item = DocumentLibraryItem(
        title=normalized_title or filename,
        description=description.strip() or None,
        category=category.strip() or None,
        item_kind="file",
        external_url=None,
        original_filename=filename,
        stored_path=str(destination),
        mime_type=upload.content_type,
        file_size=len(content),
        is_active=is_active == "true",
        sort_order=next_order,
        created_at=now,
        updated_at=now,
    )
    db.add(item)
    db.commit()
    return _documents_workspace_payload(db)


@router.post("/api/documents/{item_id}")
def update_document_item_api(
    request: Request,
    item_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    require_api_auth(request)
    item = db.get(DocumentLibraryItem, item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Документ не найден")
    title = str(payload.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Укажите название документа")
    normalized_kind = _normalize_document_kind(str(payload.get("item_kind") or item.item_kind))
    if normalized_kind == "link" and (item.item_kind or "").strip() == "file":
        _delete_document_library_file(item)
    if normalized_kind == "link" and not str(payload.get("external_url") or "").strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Укажите ссылку")
    if normalized_kind == "file" and not (item.stored_path or "").strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Файл документа не найден в хранилище")
    _apply_document_item_payload(item, payload)
    db.commit()
    return _documents_workspace_payload(db)


@router.delete("/api/documents/{item_id}")
def delete_document_item_api(
    request: Request,
    item_id: int,
    db: Session = Depends(get_db),
):
    require_api_auth(request)
    item = db.get(DocumentLibraryItem, item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Документ не найден")
    _delete_document_library_file(item)
    db.delete(item)
    db.commit()
    return _documents_workspace_payload(db)


@router.get("/documents/{item_id}/download")
def download_document_item(
    request: Request,
    item_id: int,
    db: Session = Depends(get_db),
):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    item = db.get(DocumentLibraryItem, item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Документ не найден")
    if (item.item_kind or "").strip() != "file":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Скачивание доступно только для файлов")
    path = Path(item.stored_path or "")
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Файл не найден в хранилище")
    return FileResponse(path, filename=item.original_filename or path.name)
