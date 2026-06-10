from __future__ import annotations

from pathlib import Path
import re

from sqlalchemy.orm import Session

from ..models import BotMenuButton, BotMenuSet, DocumentLibraryItem
from ..time_utils import utc_now


DOCUMENT_KIND_LABELS = {
    "file": "Файл",
    "link": "Ссылка",
}
_SYSTEM_TAG_SAFE_RE = re.compile(r"[^a-z0-9]+")


def _normalize_document_kind(value: str) -> str:
    normalized = (value or "").strip()
    return normalized if normalized in DOCUMENT_KIND_LABELS else "file"


def _document_items(db: Session) -> list[DocumentLibraryItem]:
    return db.query(DocumentLibraryItem).order_by(DocumentLibraryItem.sort_order, DocumentLibraryItem.id).all()


def _serialize_document_item(item: DocumentLibraryItem) -> dict:
    is_file = (item.item_kind or "").strip() == "file"
    filename = (item.original_filename or "").strip()
    return {
        "id": item.id,
        "title": item.title,
        "description": item.description or "",
        "category": item.category or "",
        "item_kind": item.item_kind,
        "item_kind_label": DOCUMENT_KIND_LABELS.get(item.item_kind, item.item_kind),
        "external_url": item.external_url or "",
        "original_filename": filename,
        "mime_type": item.mime_type or "",
        "file_size": item.file_size,
        "is_active": bool(item.is_active),
        "sort_order": item.sort_order,
        "download_url": f"/documents/{item.id}/download" if is_file else "",
        "created_at_label": item.created_at.strftime("%d.%m.%Y %H:%M") if item.created_at else "—",
        "updated_at_label": item.updated_at.strftime("%d.%m.%Y %H:%M") if item.updated_at else "—",
    }


def _document_option(item: DocumentLibraryItem) -> dict:
    suffix = DOCUMENT_KIND_LABELS.get(item.item_kind, item.item_kind).lower()
    return {
        "value": str(item.id),
        "label": f"{item.title} · {suffix}",
    }


def _documents_workspace_payload(db: Session) -> dict:
    items = _document_items(db)
    return {
        "document_kind_labels": DOCUMENT_KIND_LABELS,
        "items": [_serialize_document_item(item) for item in items],
    }


def _apply_document_item_payload(item: DocumentLibraryItem, payload: dict) -> None:
    item.title = str(payload.get("title") or "").strip() or item.title
    item.description = str(payload.get("description") or "").strip() or None
    item.category = str(payload.get("category") or "").strip() or None
    item.is_active = bool(payload.get("is_active", True))
    item.item_kind = _normalize_document_kind(str(payload.get("item_kind") or item.item_kind or "file"))
    if item.item_kind == "link":
        item.external_url = str(payload.get("external_url") or "").strip() or None
        item.original_filename = None
        item.stored_path = None
        item.mime_type = None
        item.file_size = None
    else:
        item.external_url = None
    item.updated_at = utc_now()


def _delete_document_library_file(item: DocumentLibraryItem) -> None:
    path_value = (item.stored_path or "").strip()
    if not path_value:
        return
    path = Path(path_value)
    try:
        if path.exists():
            path.unlink()
    except OSError:
        pass


def _document_scaffold_tag(root_title: str) -> str:
    normalized = _SYSTEM_TAG_SAFE_RE.sub("-", (root_title or "").strip().lower()).strip("-")
    return f"documents_scaffold:{normalized or 'documents'}"


def _delete_document_scaffold_sets(db: Session, system_tag: str) -> None:
    menu_set_ids = [
        menu_set_id
        for (menu_set_id,) in db.query(BotMenuSet.id).filter(BotMenuSet.system_tag == system_tag).all()
    ]
    if not menu_set_ids:
        return
    db.query(BotMenuButton).filter(BotMenuButton.menu_set_id.in_(menu_set_ids)).delete(synchronize_session=False)
    db.query(BotMenuButton).filter(BotMenuButton.target_menu_set_id.in_(menu_set_ids)).update(
        {
            BotMenuButton.action_type: "inactive",
            BotMenuButton.target_menu_set_id: None,
            BotMenuButton.document_item_id: None,
        },
        synchronize_session=False,
    )
    db.query(BotMenuSet).filter(BotMenuSet.id.in_(menu_set_ids)).delete(synchronize_session=False)
    db.flush()


def _build_document_menu_scaffold(db: Session, root_title: str, *, replace_existing: bool = False) -> BotMenuSet:
    items = (
        db.query(DocumentLibraryItem)
        .filter(DocumentLibraryItem.is_active.is_(True))
        .order_by(DocumentLibraryItem.category, DocumentLibraryItem.sort_order, DocumentLibraryItem.id)
        .all()
    )
    if not items:
        raise ValueError("Нет активных документов для сборки меню")

    grouped: dict[str, list[DocumentLibraryItem]] = {}
    for item in items:
        category = (item.category or "").strip() or "Без категории"
        grouped.setdefault(category, []).append(item)
    system_tag = _document_scaffold_tag(root_title)
    if replace_existing:
        _delete_document_scaffold_sets(db, system_tag)
    elif db.query(BotMenuSet).filter(BotMenuSet.system_tag == system_tag).first() is not None:
        raise ValueError("Раздел с таким именем уже был сгенерирован. Используйте пересборку.")

    last_set = db.query(BotMenuSet).order_by(BotMenuSet.sort_order.desc(), BotMenuSet.id.desc()).first()
    next_set_order = (last_set.sort_order + 10) if last_set else 10
    root_menu = BotMenuSet(
        title=root_title.strip() or "Документы",
        description="Каталог документов",
        sort_order=next_set_order,
        role_scope="all",
        employee_scope="all",
        target_employee_id=None,
        target_employee_ids=None,
        target_employee_stages=None,
        target_candidate_stages=None,
        system_tag=system_tag,
    )
    db.add(root_menu)
    db.flush()

    root_button_order = 10
    child_set_order = next_set_order + 10
    for category, category_items in grouped.items():
        child_menu = BotMenuSet(
            title=f"{root_menu.title} · {category}",
            description=category,
            sort_order=child_set_order,
            role_scope="all",
            employee_scope="all",
            target_employee_id=None,
            target_employee_ids=None,
            target_employee_stages=None,
            target_candidate_stages=None,
            system_tag=system_tag,
        )
        db.add(child_menu)
        db.flush()

        db.add(
            BotMenuButton(
                menu_set_id=root_menu.id,
                label=category,
                sort_order=root_button_order,
                action_type="open_set",
                scenario_key=None,
                target_menu_set_id=child_menu.id,
                document_item_id=None,
            )
        )
        root_button_order += 10

        button_order = 10
        for item in category_items:
            db.add(
                BotMenuButton(
                    menu_set_id=child_menu.id,
                    label=item.title,
                    sort_order=button_order,
                    action_type="send_document",
                    scenario_key=None,
                    target_menu_set_id=None,
                    document_item_id=item.id,
                )
            )
            button_order += 10
        child_set_order += 10

    db.flush()
    root_menu.description = f"Собрано {len(grouped)} разделов · {len(items)} документов"
    db.commit()
    db.refresh(root_menu)
    return root_menu
