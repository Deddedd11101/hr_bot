"""Read-only экспорт данных HRBot для внешних систем (сейчас — Pulse).

HRBot остаётся master по составу штата и должностям; внешняя система сама
решает, как маппить эти данные на свою модель. Здесь только выборка и
сериализация, без записи.
"""

from __future__ import annotations

import hmac
from datetime import UTC, datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from ..models import Employee, Position
from ..positions import canonical_position_title, normalize_position_slug

# Стадии, в которых человек уже работает в компании. Кандидаты не экспортируются.
PULSE_EXPORT_EMPLOYEE_STAGES: tuple[str, ...] = ("staff", "adaptation", "ipr")


def bearer_token_matches(authorization_header: Optional[str], expected_token: str) -> bool:
    """Сравнить `Authorization: Bearer <token>` с ожидаемым токеном за константное время."""
    if not expected_token:
        return False
    if not authorization_header:
        return False
    scheme, _, presented = authorization_header.strip().partition(" ")
    if scheme.lower() != "bearer":
        return False
    presented = presented.strip()
    if not presented:
        return False
    return hmac.compare_digest(presented.encode("utf-8"), expected_token.encode("utf-8"))


def _position_fields(db_positions: dict[str, str], desired_position: Optional[str]) -> tuple[str, str]:
    raw = (desired_position or "").strip()
    if not raw:
        return "", ""
    slug = normalize_position_slug(raw)
    title = db_positions.get(slug) or canonical_position_title(raw)
    return slug, title


def serialize_pulse_employee(employee: Employee, db_positions: dict[str, str]) -> dict[str, Any]:
    position_slug, position_title = _position_fields(db_positions, employee.desired_position)
    return {
        "id": employee.id,
        "full_name": (employee.full_name or "").strip(),
        "first_name": (employee.first_name or "").strip() or None,
        "position_slug": position_slug or None,
        "position_title": position_title or None,
        "employee_stage": employee.employee_stage,
        "work_email": (employee.work_email or "").strip() or None,
        "is_manager": bool(employee.is_manager),
        "is_mentor": bool(employee.is_mentor),
    }


def build_pulse_employees_payload(db: Session) -> dict[str, Any]:
    """Штатные сотрудники для Pulse: только рабочие стадии и не заблокированные в боте."""
    db_positions = {position.slug: position.title for position in db.query(Position).all()}
    employees = (
        db.query(Employee)
        .filter(Employee.employee_stage.in_(PULSE_EXPORT_EMPLOYEE_STAGES))
        .filter(Employee.is_bot_blocked.is_(False))
        .order_by(Employee.id.asc())
        .all()
    )
    return {
        "source": "hrbot",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "employee_stages": list(PULSE_EXPORT_EMPLOYEE_STAGES),
        "employees": [serialize_pulse_employee(employee, db_positions) for employee in employees],
    }
