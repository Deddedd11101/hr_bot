from fastapi import APIRouter, Depends, Request, Query, HTTPException
from typing import Literal
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..database import get_session
from .dashboard import dashboard_workspace_payload
from .support import render_template, require_api_auth, require_auth

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def get_db():
    with get_session() as db:
        yield db


@router.get("/app/vacation-schedule")
def vacation_schedule_page(request: Request):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    return render_template(request, templates, "react_vacation_schedule.html", {"active_tab": "vacations"})


@router.get("/api/vacation-schedule")
def vacation_schedule_api(request: Request, month: str | None = Query(None, pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$"),
    search: str = Query("", max_length=200), group_id: int | None = Query(None, ge=0),
    page: int = Query(1, ge=1, le=10000), db: Session = Depends(get_db)):
    require_api_auth(request)
    from ..vacation_schedule import schedule
    try:
        return schedule(db, month=month, search=search, group_id=group_id, page=page)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/app/dashboard")
def react_dashboard_page(request: Request):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    return render_template(
        request,
        templates,
        "react_dashboard.html",
        {
            "active_tab": "dashboard",
            "react_api_url": "/api/dashboard/workspace",
        },
    )


@router.get("/api/dashboard/workspace")
def dashboard_workspace_api(request: Request, db: Session = Depends(get_db)):
    require_api_auth(request)
    return dashboard_workspace_payload(db)


@router.get("/app/scenario-queue")
def scenario_queue_page(request: Request):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    return render_template(request, templates, "react_dashboard.html", {
        "active_tab": "flows", "react_api_url": "/api/scenario-queue", "queue_page": True})


@router.get("/api/scenario-queue")
def scenario_queue_api(request: Request,
    state: Literal["all", "attention", "blocked", "waiting", "scheduled", "queued", "active"] = "all",
    search: str = Query("", max_length=200), page: int = Query(1, ge=1, le=10000), db: Session = Depends(get_db)):
    require_api_auth(request)
    from .operational_queue import queue_payload
    return queue_payload(db, state=state, search=search, page=page)


@router.get("/api/dashboard/history")
def dashboard_history_api(request: Request,
    kind: Literal["all", "steps", "surveys", "messages", "launches"] = "all",
    page: int = Query(1, ge=1, le=100), db: Session = Depends(get_db)):
    require_api_auth(request)
    from .operational_history import history_payload
    return history_payload(db, kind=kind, page=page)
