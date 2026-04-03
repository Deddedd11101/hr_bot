from __future__ import annotations

from typing import Optional

from ..models import Employee


def get_primary_chat_id(employee: Employee) -> Optional[str]:
    value = (employee.telegram_user_id or "").strip()
    return value or None


def set_primary_chat_id(employee: Employee, value: Optional[str]) -> None:
    normalized = (value or "").strip()
    employee.telegram_user_id = normalized or None


def get_public_chat_handle(employee: Employee) -> Optional[str]:
    value = (employee.telegram_username or "").strip()
    return value or None


def set_public_chat_handle(employee: Employee, value: Optional[str]) -> None:
    normalized = (value or "").strip()
    employee.telegram_username = normalized or None


def get_manager_chat_id(employee: Employee) -> Optional[str]:
    value = (employee.manager_telegram_id or "").strip()
    return value or None


def get_mentor_adaptation_chat_id(employee: Employee) -> Optional[str]:
    value = (employee.mentor_adaptation_telegram_id or "").strip()
    return value or None


def get_mentor_ipr_chat_id(employee: Employee) -> Optional[str]:
    value = (employee.mentor_ipr_telegram_id or "").strip()
    return value or None
