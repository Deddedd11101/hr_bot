from datetime import datetime

from fastapi import APIRouter, Body, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_session
from ..messaging import create_telegram_messenger
from ..mass_targeting import build_legacy_target_statuses, serialize_target_values
from ..models import MassMessageAction, MassScenarioAction, MassScenarioRecipient, ScenarioTemplate
from ..time_utils import utc_now
from .bulk_actions import (
    _bulk_target_recipients,
    _bulk_workspace_payload,
    _ensure_confirmed,
    _mass_actions_redirect,
    _parse_bulk_run_at,
    _recipient_scope_label,
    _send_mass_message,
    _parse_multi_target_payload,
    _target_selection_storage,
)
from .employees import _scenario_matches_employee_role
from .support import render_template, require_api_auth, require_auth

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def get_db():
    with get_session() as db:
        yield db


async def _parse_classic_mass_action_payload(request: Request) -> dict:
    form = await request.form()
    return {
        "target_employee_stages": [str(value) for value in form.getlist("target_employee_stages")],
        "target_candidate_stages": [str(value) for value in form.getlist("target_candidate_stages")],
        "target_employee_id": str(form.get("target_employee_id", "") or "").strip(),
        "target_role_scope": str(form.get("target_role_scope", "") or "").strip(),
    }


async def _launch_queued_mass(db, scenario, payload, selection):
    target_all, employee_stages, candidate_stages, employee_id, role_scope, recipients = selection
    recipients = [person for person in recipients if _scenario_matches_employee_role(scenario, person)]
    if not recipients:
        raise HTTPException(400, "Нет получателей, подходящих сценарию.")
    action = MassScenarioAction(flow_key=scenario.scenario_key, scenario_kind=scenario.scenario_kind,
        requested_at=utc_now(), created_at=utc_now(), launch_type="manual", target_all=target_all,
        target_statuses=serialize_target_values(build_legacy_target_statuses(employee_stages, candidate_stages)),
        target_employee_stages=serialize_target_values(employee_stages), target_candidate_stages=serialize_target_values(candidate_stages),
        target_employee_id=employee_id, target_role_scope=role_scope, **_target_selection_storage(payload))
    db.add(action)
    db.flush()
    for person in recipients:
        db.add(MassScenarioRecipient(action_id=action.id, employee_id=person.id))
    db.commit()
    from ..mass_scenario_delivery import deliver_mass_action, delivery_counts
    messenger = create_telegram_messenger(settings.TELEGRAM_BOT_TOKEN)
    try:
        await deliver_mass_action(db, messenger, action.id, [person.id for person in recipients])
    finally:
        await messenger.close()
    counts = delivery_counts(db, action.id)
    return (f"Принято: {len(recipients)}. Начато: {counts.get('started', 0)}; "
        f"в очереди: {counts.get('pending', 0)}; проверить доставку: {counts.get('starting', 0)}; "
        f"ошибок: {counts.get('failed', 0)}.")


@router.get("/bulk-actions")
def bulk_actions_page(request: Request):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    return RedirectResponse(url="/app/messages", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/app/bulk-actions")
def react_bulk_actions_page(request: Request):
    """Прежний адрес страницы массовых действий: страница переименована."""
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    return RedirectResponse(url="/app/messages", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/app/messages")
def react_messages_page(request: Request):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    return render_template(
        request,
        templates,
        "react_messages.html",
        {
            "active_tab": "messages",
            "react_api_url": "/api/bulk-actions/workspace",
            "classic_page_url": "/bulk-actions",
        },
    )


@router.post("/bulk-actions/scenarios/schedule")
async def bulk_schedule_scenario(
    request: Request,
    flow_key: str = Form(""),
    requested_at: str = Form(""),
    db: Session = Depends(get_db),
):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    scenario = db.query(ScenarioTemplate).filter(ScenarioTemplate.scenario_key == flow_key).first()
    if not scenario:
        return _mass_actions_redirect("Сценарий не найден.", "error")
    payload = await _parse_classic_mass_action_payload(request)
    target_all, target_employee_stages, target_candidate_stages, target_employee_id, target_role_scope, recipients = _bulk_target_recipients(db, payload)
    if not recipients:
        return _mass_actions_redirect("Не найдено ни одного получателя для выбранных статусов.", "error")
    try:
        run_at = _parse_bulk_run_at(requested_at, "отправки сценария")
    except HTTPException as exc:
        return _mass_actions_redirect(exc.detail, "error")
    db.add(
        MassScenarioAction(
            flow_key=scenario.scenario_key,
            scenario_kind="scenario",
            requested_at=run_at,
            processed_at=None,
            launch_type="scheduled",
            target_all=target_all,
            target_statuses=serialize_target_values(build_legacy_target_statuses(target_employee_stages, target_candidate_stages)),
            target_employee_stages=serialize_target_values(target_employee_stages),
            target_candidate_stages=serialize_target_values(target_candidate_stages),
            target_role_scope=target_role_scope,
            target_employee_id=target_employee_id,
            recipient_count=len(recipients),
            created_at=utc_now(),
        )
    )
    db.commit()
    return _mass_actions_redirect("Массовый запуск сценария запланирован.", "success")


@router.post("/bulk-actions/surveys/schedule")
async def bulk_schedule_survey(
    request: Request,
    flow_key: str = Form(""),
    requested_at: str = Form(""),
    db: Session = Depends(get_db),
):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    scenario = (
        db.query(ScenarioTemplate)
        .filter(
            ScenarioTemplate.scenario_key == flow_key,
            ScenarioTemplate.scenario_kind == "survey",
        )
        .first()
    )
    if not scenario:
        return _mass_actions_redirect("Опрос не найден.", "error")
    payload = await _parse_classic_mass_action_payload(request)
    target_all, target_employee_stages, target_candidate_stages, target_employee_id, target_role_scope, recipients = _bulk_target_recipients(db, payload)
    if not recipients:
        return _mass_actions_redirect("Не найдено ни одного получателя для выбранных статусов.", "error")
    try:
        run_at = _parse_bulk_run_at(requested_at, "отправки опроса")
    except HTTPException as exc:
        return _mass_actions_redirect(exc.detail, "error")
    db.add(
        MassScenarioAction(
            flow_key=scenario.scenario_key,
            scenario_kind="survey",
            requested_at=run_at,
            processed_at=None,
            launch_type="scheduled",
            target_all=target_all,
            target_statuses=serialize_target_values(build_legacy_target_statuses(target_employee_stages, target_candidate_stages)),
            target_employee_stages=serialize_target_values(target_employee_stages),
            target_candidate_stages=serialize_target_values(target_candidate_stages),
            target_role_scope=target_role_scope,
            target_employee_id=target_employee_id,
            recipient_count=len(recipients),
            created_at=utc_now(),
        )
    )
    db.commit()
    return _mass_actions_redirect("Массовый запуск опроса запланирован.", "success")


@router.post("/bulk-actions/scenarios/launch")
async def bulk_launch_scenario(
    request: Request,
    flow_key: str = Form(""),
    db: Session = Depends(get_db),
):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    scenario = db.query(ScenarioTemplate).filter(ScenarioTemplate.scenario_key == flow_key).first()
    if not scenario:
        return _mass_actions_redirect("Сценарий не найден.", "error")
    payload = await _parse_classic_mass_action_payload(request)
    target_all, target_employee_stages, target_candidate_stages, target_employee_id, target_role_scope, recipients = _bulk_target_recipients(db, payload)
    if not recipients:
        return _mass_actions_redirect("Не найдено ни одного получателя для выбранных статусов.", "error")
    if not settings.TELEGRAM_BOT_TOKEN:
        return _mass_actions_redirect("Не задан TELEGRAM_BOT_TOKEN.", "error")
    try:
        message = await _launch_queued_mass(db, scenario, payload, (target_all, target_employee_stages,
            target_candidate_stages, target_employee_id, target_role_scope, recipients))
    except HTTPException as exc:
        return _mass_actions_redirect(exc.detail, "error")
    return _mass_actions_redirect(message, "success")


@router.post("/bulk-actions/surveys/launch")
async def bulk_launch_survey(
    request: Request,
    flow_key: str = Form(""),
    db: Session = Depends(get_db),
):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    scenario = (
        db.query(ScenarioTemplate)
        .filter(
            ScenarioTemplate.scenario_key == flow_key,
            ScenarioTemplate.scenario_kind == "survey",
        )
        .first()
    )
    if not scenario:
        return _mass_actions_redirect("Опрос не найден.", "error")
    payload = await _parse_classic_mass_action_payload(request)
    target_all, target_employee_stages, target_candidate_stages, target_employee_id, target_role_scope, recipients = _bulk_target_recipients(db, payload)
    if not recipients:
        return _mass_actions_redirect("Не найдено ни одного получателя для выбранных статусов.", "error")
    if not settings.TELEGRAM_BOT_TOKEN:
        return _mass_actions_redirect("Не задан TELEGRAM_BOT_TOKEN.", "error")
    try:
        message = await _launch_queued_mass(db, scenario, payload, (target_all, target_employee_stages,
            target_candidate_stages, target_employee_id, target_role_scope, recipients))
    except HTTPException as exc:
        return _mass_actions_redirect(exc.detail, "error")
    return _mass_actions_redirect(message, "success")


@router.post("/bulk-actions/messages/schedule")
async def bulk_schedule_message(
    request: Request,
    message_text: str = Form(""),
    requested_at: str = Form(""),
    db: Session = Depends(get_db),
):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    if not message_text.strip():
        return _mass_actions_redirect("Введите текст сообщения.", "error")
    payload = await _parse_classic_mass_action_payload(request)
    target_all, target_employee_stages, target_candidate_stages, target_employee_id, target_role_scope, recipients = _bulk_target_recipients(db, payload)
    if not recipients:
        return _mass_actions_redirect("Не найдено ни одного получателя для выбранных статусов.", "error")
    try:
        run_at = _parse_bulk_run_at(requested_at, "отправки сообщения")
    except HTTPException as exc:
        return _mass_actions_redirect(exc.detail, "error")
    db.add(
        MassMessageAction(
            message_text=message_text,
            requested_at=run_at,
            processed_at=None,
            launch_type="scheduled",
            target_all=target_all,
            target_statuses=serialize_target_values(build_legacy_target_statuses(target_employee_stages, target_candidate_stages)),
            target_employee_stages=serialize_target_values(target_employee_stages),
            target_candidate_stages=serialize_target_values(target_candidate_stages),
            target_role_scope=target_role_scope,
            target_employee_id=target_employee_id,
            recipient_count=len(recipients),
            created_at=utc_now(),
        )
    )
    db.commit()
    return _mass_actions_redirect("Массовая отправка сообщения запланирована.", "success")


@router.post("/bulk-actions/messages/send")
async def bulk_send_message(
    request: Request,
    message_text: str = Form(""),
    db: Session = Depends(get_db),
):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    if not message_text.strip():
        return _mass_actions_redirect("Введите текст сообщения.", "error")
    payload = await _parse_classic_mass_action_payload(request)
    target_all, target_employee_stages, target_candidate_stages, target_employee_id, target_role_scope, recipients = _bulk_target_recipients(db, payload)
    if not recipients:
        return _mass_actions_redirect("Не найдено ни одного получателя для выбранных статусов.", "error")
    if not settings.TELEGRAM_BOT_TOKEN:
        return _mass_actions_redirect("Не задан TELEGRAM_BOT_TOKEN.", "error")
    messenger = create_telegram_messenger(settings.TELEGRAM_BOT_TOKEN)
    sent_count = 0
    try:
        for employee in recipients:
            if await _send_mass_message(db, messenger, employee, message_text):
                sent_count += 1
        db.add(
            MassMessageAction(
                message_text=message_text,
                requested_at=utc_now(),
                processed_at=utc_now(),
                launch_type="manual",
                target_all=target_all,
                target_statuses=serialize_target_values(build_legacy_target_statuses(target_employee_stages, target_candidate_stages)),
                target_employee_stages=serialize_target_values(target_employee_stages),
                target_candidate_stages=serialize_target_values(target_candidate_stages),
                target_role_scope=target_role_scope,
                target_employee_id=target_employee_id,
                recipient_count=sent_count,
                created_at=utc_now(),
            )
        )
        db.commit()
    finally:
        await messenger.close()
    if not sent_count:
        return _mass_actions_redirect("Не удалось отправить сообщение ни одному получателю.", "error")
    return _mass_actions_redirect(f"Сообщение отправлено {sent_count} получателям.", "success")


@router.post("/bulk-actions/scenarios/{action_id}/delete")
def delete_bulk_scenario_action(
    request: Request,
    action_id: int,
    db: Session = Depends(get_db),
):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    action = db.get(MassScenarioAction, action_id)
    if not action or action.launch_type not in {"scheduled", "manual"} or action.processed_at is not None:
        return _mass_actions_redirect("Запланированный запуск не найден.", "error")
    from ..mass_scenario_delivery import delete_unstarted_action
    try:
        delete_unstarted_action(db, action_id)
    except ValueError as exc:
        db.rollback()
        return _mass_actions_redirect(str(exc), "error")
    db.commit()
    return _mass_actions_redirect("Запланированный запуск удалён.", "success")


@router.post("/bulk-actions/messages/{action_id}/delete")
def delete_bulk_message_action(
    request: Request,
    action_id: int,
    db: Session = Depends(get_db),
):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    action = db.get(MassMessageAction, action_id)
    if not action or action.launch_type != "scheduled" or action.processed_at is not None:
        return _mass_actions_redirect("Запланированная отправка не найдена.", "error")
    db.delete(action)
    db.commit()
    return _mass_actions_redirect("Запланированная отправка удалена.", "success")


@router.get("/api/bulk-actions/workspace")
def bulk_actions_workspace_api(request: Request, db: Session = Depends(get_db)):
    require_api_auth(request)
    return _bulk_workspace_payload(db)


@router.post("/api/bulk-actions/preview")
def bulk_actions_preview_api(
    request: Request,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    require_api_auth(request)
    target_all, target_employee_stages, target_candidate_stages, target_employee_id, target_role_scope, recipients = _bulk_target_recipients(db, payload)
    role_scopes, employee_ids = _parse_multi_target_payload(payload)
    return {
        "recipient_count": len(recipients),
        "recipient_scope": _recipient_scope_label(
            db,
            target_all,
            serialize_target_values(build_legacy_target_statuses(target_employee_stages, target_candidate_stages)),
            target_employee_id,
            target_role_scope,
            serialize_target_values(target_employee_stages),
            serialize_target_values(target_candidate_stages),
            role_scopes,
            employee_ids,
        ),
    }


@router.post("/api/bulk-actions/scenarios/schedule")
def bulk_schedule_scenario_api(
    request: Request,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    require_api_auth(request)
    scenario = (
        db.query(ScenarioTemplate)
        .filter(ScenarioTemplate.scenario_key == str(payload.get("flow_key") or ""), ScenarioTemplate.scenario_kind == "scenario")
        .first()
    )
    if not scenario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сценарий не найден")
    target_all, target_employee_stages, target_candidate_stages, target_employee_id, target_role_scope, recipients = _bulk_target_recipients(db, payload)
    if not recipients:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Не найдено ни одного получателя.")
    run_at = _parse_bulk_run_at(str(payload.get("requested_at") or ""), "отправки сценария")
    db.add(
        MassScenarioAction(
            flow_key=scenario.scenario_key,
            scenario_kind="scenario",
            requested_at=run_at,
            processed_at=None,
            launch_type="scheduled",
            target_all=target_all,
            target_statuses=serialize_target_values(build_legacy_target_statuses(target_employee_stages, target_candidate_stages)),
            target_employee_stages=serialize_target_values(target_employee_stages),
            target_candidate_stages=serialize_target_values(target_candidate_stages),
            target_role_scope=target_role_scope,
            target_employee_id=target_employee_id,
            recipient_count=len(recipients),
            **_target_selection_storage(payload),
            created_at=utc_now(),
        )
    )
    db.commit()
    return {"message": "Массовый запуск сценария запланирован.", "payload": _bulk_workspace_payload(db)}


@router.post("/api/bulk-actions/surveys/schedule")
def bulk_schedule_survey_api(
    request: Request,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    require_api_auth(request)
    scenario = (
        db.query(ScenarioTemplate)
        .filter(ScenarioTemplate.scenario_key == str(payload.get("flow_key") or ""), ScenarioTemplate.scenario_kind == "survey")
        .first()
    )
    if not scenario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Опрос не найден")
    target_all, target_employee_stages, target_candidate_stages, target_employee_id, target_role_scope, recipients = _bulk_target_recipients(db, payload)
    if not recipients:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Не найдено ни одного получателя.")
    run_at = _parse_bulk_run_at(str(payload.get("requested_at") or ""), "отправки опроса")
    db.add(
        MassScenarioAction(
            flow_key=scenario.scenario_key,
            scenario_kind="survey",
            requested_at=run_at,
            processed_at=None,
            launch_type="scheduled",
            target_all=target_all,
            target_statuses=serialize_target_values(build_legacy_target_statuses(target_employee_stages, target_candidate_stages)),
            target_employee_stages=serialize_target_values(target_employee_stages),
            target_candidate_stages=serialize_target_values(target_candidate_stages),
            target_role_scope=target_role_scope,
            target_employee_id=target_employee_id,
            recipient_count=len(recipients),
            **_target_selection_storage(payload),
            created_at=utc_now(),
        )
    )
    db.commit()
    return {"message": "Массовый запуск опроса запланирован.", "payload": _bulk_workspace_payload(db)}


@router.post("/api/bulk-actions/messages/schedule")
def bulk_schedule_message_api(
    request: Request,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    require_api_auth(request)
    message_text = str(payload.get("message_text") or "")
    if not message_text.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Введите текст сообщения.")
    target_all, target_employee_stages, target_candidate_stages, target_employee_id, target_role_scope, recipients = _bulk_target_recipients(db, payload)
    if not recipients:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Не найдено ни одного получателя.")
    run_at = _parse_bulk_run_at(str(payload.get("requested_at") or ""), "отправки сообщения")
    db.add(
        MassMessageAction(
            message_text=message_text,
            requested_at=run_at,
            processed_at=None,
            launch_type="scheduled",
            target_all=target_all,
            target_statuses=serialize_target_values(build_legacy_target_statuses(target_employee_stages, target_candidate_stages)),
            target_employee_stages=serialize_target_values(target_employee_stages),
            target_candidate_stages=serialize_target_values(target_candidate_stages),
            target_role_scope=target_role_scope,
            target_employee_id=target_employee_id,
            recipient_count=len(recipients),
            **_target_selection_storage(payload),
            created_at=utc_now(),
        )
    )
    db.commit()
    return {"message": "Массовая отправка сообщения запланирована.", "payload": _bulk_workspace_payload(db)}


@router.post("/api/bulk-actions/scenarios/launch")
async def bulk_launch_scenario_api(
    request: Request,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    require_api_auth(request)
    _ensure_confirmed(payload)
    scenario = (
        db.query(ScenarioTemplate)
        .filter(ScenarioTemplate.scenario_key == str(payload.get("flow_key") or ""), ScenarioTemplate.scenario_kind == "scenario")
        .first()
    )
    if not scenario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сценарий не найден")
    target_all, target_employee_stages, target_candidate_stages, target_employee_id, target_role_scope, recipients = _bulk_target_recipients(db, payload)
    if not recipients:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Не найдено ни одного получателя.")
    if not settings.TELEGRAM_BOT_TOKEN:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Не задан TELEGRAM_BOT_TOKEN.")
    message = await _launch_queued_mass(db, scenario, payload, (target_all, target_employee_stages,
        target_candidate_stages, target_employee_id, target_role_scope, recipients))
    return {"message": message, "payload": _bulk_workspace_payload(db)}


@router.post("/api/bulk-actions/surveys/launch")
async def bulk_launch_survey_api(
    request: Request,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    require_api_auth(request)
    _ensure_confirmed(payload)
    scenario = (
        db.query(ScenarioTemplate)
        .filter(ScenarioTemplate.scenario_key == str(payload.get("flow_key") or ""), ScenarioTemplate.scenario_kind == "survey")
        .first()
    )
    if not scenario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Опрос не найден")
    target_all, target_employee_stages, target_candidate_stages, target_employee_id, target_role_scope, recipients = _bulk_target_recipients(db, payload)
    if not recipients:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Не найдено ни одного получателя.")
    if not settings.TELEGRAM_BOT_TOKEN:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Не задан TELEGRAM_BOT_TOKEN.")
    message = await _launch_queued_mass(db, scenario, payload, (target_all, target_employee_stages,
        target_candidate_stages, target_employee_id, target_role_scope, recipients))
    return {"message": message, "payload": _bulk_workspace_payload(db)}


@router.post("/api/bulk-actions/messages/send")
async def bulk_send_message_api(
    request: Request,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    require_api_auth(request)
    _ensure_confirmed(payload)
    message_text = str(payload.get("message_text") or "")
    if not message_text.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Введите текст сообщения.")
    target_all, target_employee_stages, target_candidate_stages, target_employee_id, target_role_scope, recipients = _bulk_target_recipients(db, payload)
    if not recipients:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Не найдено ни одного получателя.")
    if not settings.TELEGRAM_BOT_TOKEN:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Не задан TELEGRAM_BOT_TOKEN.")
    messenger = create_telegram_messenger(settings.TELEGRAM_BOT_TOKEN)
    sent_count = 0
    try:
        for employee in recipients:
            if await _send_mass_message(db, messenger, employee, message_text):
                sent_count += 1
        db.add(
            MassMessageAction(
                message_text=message_text,
                requested_at=utc_now(),
                processed_at=utc_now(),
                launch_type="manual",
                target_all=target_all,
                target_statuses=serialize_target_values(build_legacy_target_statuses(target_employee_stages, target_candidate_stages)),
                target_employee_stages=serialize_target_values(target_employee_stages),
                target_candidate_stages=serialize_target_values(target_candidate_stages),
                target_role_scope=target_role_scope,
                target_employee_id=target_employee_id,
                recipient_count=sent_count,
                **_target_selection_storage(payload),
                created_at=utc_now(),
            )
        )
        db.commit()
    finally:
        await messenger.close()
    if not sent_count:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Не удалось отправить сообщение ни одному получателю.")
    return {"message": f"Сообщение отправлено {sent_count} получателям.", "payload": _bulk_workspace_payload(db)}


def _delete_scheduled_mass_scenario_action(
    request: Request,
    action_id: int,
    expected_kind: str | None,
    db: Session,
):
    require_api_auth(request)
    action = db.get(MassScenarioAction, action_id)
    if (
        not action
        or action.launch_type not in {"scheduled", "manual"}
        or action.processed_at is not None
        or (expected_kind and action.scenario_kind != expected_kind)
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Запланированный запуск не найден")
    from ..mass_scenario_delivery import delete_unstarted_action
    try:
        delete_unstarted_action(db, action_id)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from None
    db.commit()
    return {"message": "Запланированный запуск удален.", "payload": _bulk_workspace_payload(db)}


@router.delete("/api/bulk-actions/scenarios/{action_id}")
def delete_bulk_scenario_action_api(
    request: Request,
    action_id: int,
    db: Session = Depends(get_db),
):
    return _delete_scheduled_mass_scenario_action(request, action_id, "scenario", db)


@router.delete("/api/bulk-actions/surveys/{action_id}")
def delete_bulk_survey_action_api(
    request: Request,
    action_id: int,
    db: Session = Depends(get_db),
):
    return _delete_scheduled_mass_scenario_action(request, action_id, "survey", db)


@router.delete("/api/bulk-actions/messages/{action_id}")
def delete_bulk_message_action_api(
    request: Request,
    action_id: int,
    db: Session = Depends(get_db),
):
    require_api_auth(request)
    action = db.get(MassMessageAction, action_id)
    if not action or action.launch_type != "scheduled" or action.processed_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Запланированная отправка не найдена")
    db.delete(action)
    db.commit()
    return {"message": "Запланированная отправка удалена.", "payload": _bulk_workspace_payload(db)}

