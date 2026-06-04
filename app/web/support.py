from typing import Optional

from fastapi import HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from ..auth import ROLE_LABELS
from ..models import AdminAccount


def render_template(
    request: Request,
    templates: Jinja2Templates,
    template_name: str,
    context: dict,
):
    payload = dict(context)
    payload["request"] = request
    payload["current_user"] = getattr(request.state, "current_user", None)
    payload["role_labels"] = ROLE_LABELS
    return templates.TemplateResponse(request, template_name, payload)


def redirect_login() -> RedirectResponse:
    return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)


def require_auth(request: Request) -> Optional[RedirectResponse]:
    if getattr(request.state, "current_user", None):
        return None
    return redirect_login()


def require_api_auth(request: Request) -> AdminAccount:
    current_user = getattr(request.state, "current_user", None)
    if current_user:
        return current_user
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Требуется авторизация")


def require_api_admin(request: Request) -> AdminAccount:
    current_user = require_api_auth(request)
    if current_user.role == "admin":
        return current_user
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Требуются права администратора")


def require_admin(request: Request) -> Optional[RedirectResponse]:
    current_user = getattr(request.state, "current_user", None)
    if not current_user:
        return redirect_login()
    if current_user.role == "admin":
        return None
    return RedirectResponse(url="/settings", status_code=status.HTTP_303_SEE_OTHER)
