from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_session
from .integrations import bearer_token_matches, build_pulse_employees_payload

router = APIRouter()


def require_pulse_token(request: Request) -> None:
    """Server-to-server auth для Pulse: bearer из env, без admin cookie-сессии."""
    expected = (settings.PULSE_SYNC_TOKEN or "").strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Интеграция Pulse не настроена: задайте PULSE_SYNC_TOKEN",
        )
    if not bearer_token_matches(request.headers.get("authorization"), expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется авторизация",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_pulse_db(request: Request):
    require_pulse_token(request)
    with get_session() as db:
        yield db


@router.get("/api/integrations/pulse/employees")
def api_pulse_employees(db: Session = Depends(get_pulse_db)):
    return build_pulse_employees_payload(db)
