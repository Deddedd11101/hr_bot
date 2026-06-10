from fastapi import APIRouter, Depends, Request
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
