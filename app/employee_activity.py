"""Read-only employee timeline built from persisted facts, never inferred delivery."""

from datetime import UTC, datetime
import hashlib

from sqlalchemy.orm import Session
from sqlalchemy import text


from .models import (
    AdminAccount, Employee, EmployeeAssignmentHistory, EmployeeFile, EmployeeHrNote,
    EmployeeManualBotMessage, FlowLaunchRequest, GradeAssessment, OnboardingEvent,
)


KINDS = [
    {"value": "all", "label": "Все события"},
    {"value": "note", "label": "HR-заметки"},
    {"value": "message", "label": "Ручные сообщения"},
    {"value": "file", "label": "Файлы"},
    {"value": "launch", "label": "Запросы запуска"},
    {"value": "onboarding", "label": "Онбординг"},
    {"value": "assignment", "label": "Назначения"},
    {"value": "grade", "label": "Grade"},
]


def notes_revision(db: Session, employee_id: int) -> str:
    rows = db.query(EmployeeHrNote.id, EmployeeHrNote.deleted_at).filter_by(
        employee_id=employee_id).order_by(EmployeeHrNote.id).all()
    metadata = ";".join(f"{row.id}:{utc_datetime(row.deleted_at).isoformat() if row.deleted_at else ''}" for row in rows)
    return hashlib.sha256(f"notes-v1:{employee_id}:{metadata}".encode()).hexdigest()


def lock_note_projection(db: Session, employee_id: int) -> None:
    """Serialize legacy-note saves with deletion before either reads the projection."""
    if db.get_bind().dialect.name == "sqlite":
        connection = db.connection()
        if not connection.connection.driver_connection.in_transaction:
            connection.execute(text("BEGIN IMMEDIATE"))
    else:
        db.query(Employee).filter_by(id=employee_id).with_for_update().first()


def utc_datetime(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def page_payload(items: list, total: int, page: int, page_size: int) -> dict:
    return {"items": items, "total": total, "page": page, "page_size": page_size,
            "pages": (total + page_size - 1) // page_size}


def employee_activity(db: Session, employee_id: int, page: int, page_size: int, kind: str) -> dict:
    events = []
    actors = {}

    def actor(account_id):
        if account_id is None:
            return None
        if account_id not in actors:
            account = db.get(AdminAccount, account_id)
            actors[account_id] = (account.login or None) if account else None
        return actors[account_id]

    def add(source, row, at, event_kind, label, detail=None, account_id=None, suffix=""):
        if at is not None:
            events.append({"id": f"{source}:{row.id}{suffix}", "occurred_at": utc_datetime(at).isoformat(),
                           "kind": event_kind, "label": label, "detail": detail, "actor": actor(account_id)})

    def rows(model, column=None):
        return db.query(model).filter((column if column is not None else model.employee_id) == employee_id).all()

    if kind in ("all", "note", "message"):
        for model, event_kind, text_field, account_field, source in (
            (EmployeeHrNote, "note", "note_text", "author_account_id", "note"),
            (EmployeeManualBotMessage, "message", "message_text", "sender_account_id", "message"),
        ):
            if kind not in ("all", event_kind):
                continue
            for row in rows(model):
                deleted = row.deleted_at is not None
                label = "HR-заметка" if event_kind == "note" else f"Ручное сообщение: {row.status}"
                add(source, row, row.created_at, event_kind, label,
                    "Текст удалён" if deleted else getattr(row, text_field), getattr(row, account_field))
                if deleted:
                    add(source, row, row.deleted_at, event_kind,
                        "HR-заметка удалена" if event_kind == "note" else "Запись сообщения удалена",
                        None, row.deleted_by_account_id, ":deleted")
    if kind in ("all", "file"):
        for row in rows(EmployeeFile):
            add("file", row, row.created_at, "file", "Файл добавлен", row.original_filename)
    if kind in ("all", "launch"):
        for row in rows(FlowLaunchRequest):
            # requested_at is a scheduled target, not a creation timestamp.
            if row.processed_at:
                add("launch", row, row.processed_at, "launch", "Запрос запуска обработан", row.flow_key)
    if kind in ("all", "onboarding"):
        for row in rows(OnboardingEvent):
            if row.sent_at:
                add("onboarding", row, row.sent_at, "onboarding", "Событие онбординга отправлено", row.event_key)
    if kind in ("all", "assignment"):
        for row in rows(EmployeeAssignmentHistory, EmployeeAssignmentHistory.subject_employee_id):
            detail = f"{row.assignment_role}: #{row.assigned_employee_id}"
            add("assignment", row, row.started_at, "assignment", "Назначение начато", detail, row.assigned_by_account_id)
            add("assignment", row, row.ended_at, "assignment", "Назначение завершено", detail, suffix=":ended")
    if kind in ("all", "grade"):
        for row in rows(GradeAssessment):
            add("grade", row, row.created_at, "grade", "Оценка Grade создана", account_id=row.assessor_admin_account_id)
            add("grade", row, row.finalized_at, "grade", "Оценка Grade завершена", suffix=":finalized")
            add("grade", row, row.archived_at, "grade", "Оценка Grade архивирована", suffix=":archived")
    events.sort(key=lambda event: (event["occurred_at"], event["id"]), reverse=True)
    start = (page - 1) * page_size
    return {**page_payload(events[start:start + page_size], len(events), page, page_size), "kinds": KINDS}
