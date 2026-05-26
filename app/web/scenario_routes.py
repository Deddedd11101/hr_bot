from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Body, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_session
from ..flow_templates import EMPLOYEE_SCOPE_LABELS, ROLE_SCOPE_LABELS, TRIGGER_MODE_LABELS
from ..models import FlowStepTemplate, ScenarioTemplate
from .scenarios import (
    _apply_workspace_step_update,
    _build_scenario_workspace_payload,
    _delete_step_attachment_file,
    _delete_step_subtree,
    _delete_template_entity,
    _generate_workspace_scenario_key,
    _get_workspace_scenario_by_flow_key,
    _normalize_workspace_kind,
    _save_step_attachment,
    _workspace_item_label,
    _workspace_node_kind,
    _copy_template_entity,
)
from .support import render_template, require_api_auth, require_auth

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def get_db():
    with get_session() as db:
        yield db


@router.post("/flows/reorder")
@router.post("/surveys/reorder")
async def reorder_templates(
    request: Request,
    db: Session = Depends(get_db),
):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    form = await request.form()
    scenario_ids = [int(value) for value in form.getlist("scenario_id") if str(value).isdigit()]
    if not scenario_ids:
        return RedirectResponse(url=request.url.path.rsplit("/", 1)[0], status_code=status.HTTP_303_SEE_OTHER)
    scenarios = db.query(ScenarioTemplate).filter(ScenarioTemplate.id.in_(scenario_ids)).all()
    scenario_map = {scenario.id: scenario for scenario in scenarios}
    for index, scenario_id in enumerate(scenario_ids):
        scenario = scenario_map.get(scenario_id)
        if scenario:
            scenario.sort_order = (index + 1) * 10
    db.commit()
    return RedirectResponse(url=request.url.path.rsplit("/", 1)[0], status_code=status.HTTP_303_SEE_OTHER)


@router.get("/flows")
def scenarios_page(request: Request):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    return RedirectResponse(url="/app/flows/workspace-v2", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/api/flows/workspace")
def scenario_workspace_api(
    request: Request,
    scenario_id: Optional[int] = None,
    kind: str = "scenario",
    db: Session = Depends(get_db),
):
    require_api_auth(request)
    return _build_scenario_workspace_payload(db, scenario_id, kind=kind)


@router.post("/api/flows/workspace/scenarios")
def create_workspace_scenario_api(
    request: Request,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    require_api_auth(request)
    try:
        kind = _normalize_workspace_kind(str(payload.get("kind") or "scenario"))
        item_label = _workspace_item_label(kind)
        title = str(payload.get("title") or "").strip() or f"Новый {item_label}"
        description = str(payload.get("description") or "").strip() or None

        last_scenario = (
            db.query(ScenarioTemplate)
            .filter(ScenarioTemplate.scenario_kind == kind)
            .order_by(ScenarioTemplate.sort_order.desc(), ScenarioTemplate.id.desc())
            .first()
        )
        next_order = ((last_scenario.sort_order or 0) + 10) if last_scenario else 10
        now = datetime.utcnow()
        scenario_key = _generate_workspace_scenario_key(kind)

        table_info = db.execute(text("PRAGMA table_info(scenario_templates)")).fetchall()
        table_columns = {row[1] for row in table_info}

        insert_values = {
            "scenario_key": scenario_key,
            "title": title,
            "sort_order": next_order,
            "scenario_kind": kind,
            "role_scope": "all",
            "employee_scope": "all",
            "trigger_mode": "manual_only",
            "target_employee_id": None,
            "description": description,
        }
        if "created_at" in table_columns:
            insert_values["created_at"] = now
        if "updated_at" in table_columns:
            insert_values["updated_at"] = now

        required_columns_without_default = {
            row[1]
            for row in table_info
            if row[5] == 0 and row[3] == 1 and row[4] is None
        }
        missing_required_columns = sorted(required_columns_without_default - set(insert_values.keys()))
        if missing_required_columns:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Не удалось создать {item_label}: в БД есть обязательные колонки без поддержки в UI ({', '.join(missing_required_columns)}).",
            )

        columns_sql = ", ".join(insert_values.keys())
        placeholders_sql = ", ".join(f":{key}" for key in insert_values.keys())
        db.execute(
            text(f"INSERT INTO scenario_templates ({columns_sql}) VALUES ({placeholders_sql})"),
            insert_values,
        )
        db.commit()
        scenario = db.query(ScenarioTemplate).filter(ScenarioTemplate.scenario_key == scenario_key).first()
        if not scenario:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Не удалось создать {item_label}: запись не найдена после сохранения.",
            )
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Не удалось создать элемент. Попробуй ещё раз.")
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Не удалось создать элемент.")

    return {
        "message": f"{item_label.capitalize()} создан",
        "scenario_id": scenario.id,
        "payload": _build_scenario_workspace_payload(db, scenario.id, kind=kind),
    }


@router.post("/api/flows/workspace/scenarios/{scenario_id}/settings")
def update_workspace_scenario_api(
    request: Request,
    scenario_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    require_api_auth(request)
    scenario = db.get(ScenarioTemplate, scenario_id)
    if not scenario or scenario.scenario_kind not in {"scenario", "survey"}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сценарий или опрос не найден")

    description = str(payload.get("description") or "").strip()
    role_scope = str(payload.get("role_scope") or "").strip()
    employee_scope = str(payload.get("employee_scope") or "").strip()
    trigger_mode = str(payload.get("trigger_mode") or "").strip()
    target_employee_id = str(payload.get("target_employee_id") or "").strip()

    scenario.description = description[:50] or None
    scenario.role_scope = role_scope if role_scope in ROLE_SCOPE_LABELS else "all"
    scenario.employee_scope = employee_scope if employee_scope in EMPLOYEE_SCOPE_LABELS else "all"
    scenario.trigger_mode = trigger_mode if trigger_mode in TRIGGER_MODE_LABELS else "manual_only"
    scenario.target_employee_id = int(target_employee_id) if target_employee_id.isdigit() else None
    db.commit()

    return {
        "message": "Настройки сохранены",
        "payload": _build_scenario_workspace_payload(db, scenario.id, kind=scenario.scenario_kind),
    }


@router.post("/api/flows/workspace/scenarios/reorder")
def reorder_workspace_scenarios_api(
    request: Request,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    require_api_auth(request)
    kind = _normalize_workspace_kind(str(payload.get("kind") or "scenario"))
    scenario_ids = [int(value) for value in (payload.get("scenario_ids") or []) if str(value).isdigit()]
    if not scenario_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Не передан порядок сценариев")

    scenarios = (
        db.query(ScenarioTemplate)
        .filter(
            ScenarioTemplate.id.in_(scenario_ids),
            ScenarioTemplate.scenario_kind == kind,
        )
        .all()
    )
    scenario_map = {scenario.id: scenario for scenario in scenarios}
    for index, scenario_id in enumerate(scenario_ids):
        scenario = scenario_map.get(scenario_id)
        if scenario:
            scenario.sort_order = (index + 1) * 10
    db.commit()

    selected_scenario_id = next((scenario_id for scenario_id in scenario_ids if scenario_id in scenario_map), None)
    return {
        "message": "Порядок обновлён",
        "payload": _build_scenario_workspace_payload(db, selected_scenario_id, kind=kind),
    }


@router.post("/api/flows/workspace/scenarios/bulk-copy")
def copy_workspace_scenarios_api(
    request: Request,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    require_api_auth(request)
    kind = _normalize_workspace_kind(str(payload.get("kind") or "scenario"))
    scenario_ids = [int(value) for value in (payload.get("scenario_ids") or []) if str(value).isdigit()]
    if not scenario_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Не выбраны сценарии для копирования")

    scenarios = (
        db.query(ScenarioTemplate)
        .filter(
            ScenarioTemplate.id.in_(scenario_ids),
            ScenarioTemplate.scenario_kind == kind,
        )
        .order_by(ScenarioTemplate.sort_order, ScenarioTemplate.id)
        .all()
    )
    if not scenarios:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сценарии не найдены")

    copied_items = [_copy_template_entity(db, scenario) for scenario in scenarios]
    db.commit()

    return {
        "message": f"Скопировано: {len(copied_items)}",
        "payload": _build_scenario_workspace_payload(db, copied_items[-1].id, kind=kind),
    }


@router.post("/api/flows/workspace/scenarios/bulk-delete")
def delete_workspace_scenarios_api(
    request: Request,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    require_api_auth(request)
    kind = _normalize_workspace_kind(str(payload.get("kind") or "scenario"))
    scenario_ids = [int(value) for value in (payload.get("scenario_ids") or []) if str(value).isdigit()]
    if not scenario_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Не выбраны сценарии для удаления")

    scenarios = (
        db.query(ScenarioTemplate)
        .filter(
            ScenarioTemplate.id.in_(scenario_ids),
            ScenarioTemplate.scenario_kind == kind,
        )
        .all()
    )
    if not scenarios:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сценарии не найдены")

    deleted_ids = {scenario.id for scenario in scenarios}
    for scenario in scenarios:
        _delete_template_entity(db, scenario)
    db.commit()

    remaining = (
        db.query(ScenarioTemplate)
        .filter(ScenarioTemplate.scenario_kind == kind)
        .order_by(ScenarioTemplate.sort_order, ScenarioTemplate.id)
        .all()
    )
    selected_scenario_id = next((scenario.id for scenario in remaining if scenario.id not in deleted_ids), None)

    return {
        "message": f"Удалено: {len(deleted_ids)}",
        "payload": _build_scenario_workspace_payload(db, selected_scenario_id, kind=kind),
    }


@router.post("/api/flows/workspace/steps/{step_id}")
def update_workspace_step_api(
    request: Request,
    step_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    require_api_auth(request)
    step = db.get(FlowStepTemplate, step_id)
    if not step:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Шаг не найден")

    scenario = _get_workspace_scenario_by_flow_key(db, step.flow_key)
    if not scenario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сценарий не найден")

    _apply_workspace_step_update(step, payload)
    db.commit()

    return {
        "message": "Шаг сохранён",
        "payload": _build_scenario_workspace_payload(db, scenario.id, kind=scenario.scenario_kind),
        "step_id": step.id,
    }


@router.post("/api/flows/workspace/scenarios/{scenario_id}/steps")
def create_workspace_root_step_api(
    request: Request,
    scenario_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    require_api_auth(request)
    scenario = db.get(ScenarioTemplate, scenario_id)
    if not scenario or scenario.scenario_kind not in {"scenario", "survey"}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сценарий не найден")

    last_step = (
        db.query(FlowStepTemplate)
        .filter(
            FlowStepTemplate.flow_key == scenario.scenario_key,
            FlowStepTemplate.parent_step_id.is_(None),
        )
        .order_by(FlowStepTemplate.sort_order.desc(), FlowStepTemplate.id.desc())
        .first()
    )
    next_order = (last_step.sort_order + 10) if last_step else 10
    title = str(payload.get("title") or ("Новый вопрос" if scenario.scenario_kind == "survey" else "Новый шаг")).strip()
    title = title or ("Новый вопрос" if scenario.scenario_kind == "survey" else "Новый шаг")

    step = FlowStepTemplate(
        flow_key=scenario.scenario_key,
        step_key=f"{scenario.scenario_key}_step_{int(datetime.utcnow().timestamp())}",
        step_title=title,
        sort_order=next_order,
        default_text="Новый вопрос опроса." if scenario.scenario_kind == "survey" else "Новое сообщение сценария.",
        custom_text=None,
        response_type="none",
        button_options=None,
        send_mode="immediate",
        send_time=None,
        day_offset_workdays=0,
        target_field=None,
        send_employee_card=False,
    )
    db.add(step)
    db.commit()

    return {
        "message": "Вопрос добавлен" if scenario.scenario_kind == "survey" else "Шаг добавлен",
        "payload": _build_scenario_workspace_payload(db, scenario.id, kind=scenario.scenario_kind),
        "step_id": step.id,
    }


@router.post("/api/flows/workspace/scenarios/{scenario_id}/steps/reorder")
def reorder_workspace_root_steps_api(
    request: Request,
    scenario_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    require_api_auth(request)
    scenario = db.get(ScenarioTemplate, scenario_id)
    if not scenario or scenario.scenario_kind not in {"scenario", "survey"}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сценарий не найден")

    step_ids = [int(value) for value in (payload.get("step_ids") or []) if str(value).isdigit()]
    if not step_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Не передан порядок шагов")

    steps = (
        db.query(FlowStepTemplate)
        .filter(
            FlowStepTemplate.flow_key == scenario.scenario_key,
            FlowStepTemplate.parent_step_id.is_(None),
            FlowStepTemplate.id.in_(step_ids),
        )
        .all()
    )
    step_map = {step.id: step for step in steps}
    for index, step_id in enumerate(step_ids):
        step = step_map.get(step_id)
        if step:
            step.sort_order = (index + 1) * 10
    db.commit()

    return {
        "message": "Порядок вопросов обновлён" if scenario.scenario_kind == "survey" else "Порядок шагов обновлён",
        "payload": _build_scenario_workspace_payload(db, scenario.id, kind=scenario.scenario_kind),
    }


@router.post("/api/flows/workspace/steps/{step_id}/branches")
def create_workspace_branch_step_api(
    request: Request,
    step_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    require_api_auth(request)
    parent_step = db.get(FlowStepTemplate, step_id)
    if not parent_step:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Шаг не найден")

    scenario = _get_workspace_scenario_by_flow_key(db, parent_step.flow_key)
    if not scenario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сценарий не найден")
    if parent_step.response_type != "branching":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ветки можно создавать только для шага с ветвлением")

    try:
        option_index = int(payload.get("option_index"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Не удалось определить кнопку для ветки")

    button_labels = [item.strip() for item in (parent_step.button_options or "").splitlines() if item.strip()]
    if option_index < 0 or option_index >= len(button_labels):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Кнопка для ветки не найдена")

    existing_branch = (
        db.query(FlowStepTemplate)
        .filter(
            FlowStepTemplate.flow_key == parent_step.flow_key,
            FlowStepTemplate.parent_step_id == parent_step.id,
            FlowStepTemplate.branch_option_index == option_index,
        )
        .first()
    )
    if existing_branch:
        return {
            "message": "Ветка уже существует",
            "payload": _build_scenario_workspace_payload(db, scenario.id, kind=scenario.scenario_kind),
            "step_id": existing_branch.id,
        }

    button_label = button_labels[option_index]
    branch_step = FlowStepTemplate(
        flow_key=parent_step.flow_key,
        step_key=f"{parent_step.step_key}__branch_{option_index}",
        parent_step_id=parent_step.id,
        branch_option_index=option_index,
        step_title=f"Ветка: {button_label}",
        sort_order=(parent_step.sort_order or 0) * 100 + option_index + 1,
        default_text="Новое сообщение сценария.",
        custom_text=None,
        response_type="none",
        button_options=None,
        send_mode="immediate",
        send_time=None,
        day_offset_workdays=0,
        target_field=None,
        send_employee_card=False,
    )
    db.add(branch_step)
    db.commit()

    return {
        "message": "Ветка создана",
        "payload": _build_scenario_workspace_payload(db, scenario.id, kind=scenario.scenario_kind),
        "step_id": branch_step.id,
    }


@router.post("/api/flows/workspace/steps/{step_id}/chain")
def create_workspace_chain_step_api(
    request: Request,
    step_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    require_api_auth(request)
    parent_step = db.get(FlowStepTemplate, step_id)
    if not parent_step:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Шаг не найден")

    scenario = _get_workspace_scenario_by_flow_key(db, parent_step.flow_key)
    if not scenario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сценарий не найден")
    if parent_step.parent_step_id is None or parent_step.branch_option_index is None or parent_step.response_type != "chain":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Шаг цепочки можно добавить только внутри ветки с типом «Цепочка шагов»")

    last_step = (
        db.query(FlowStepTemplate)
        .filter(
            FlowStepTemplate.flow_key == parent_step.flow_key,
            FlowStepTemplate.parent_step_id == parent_step.id,
            FlowStepTemplate.branch_option_index.is_(None),
        )
        .order_by(FlowStepTemplate.sort_order.desc(), FlowStepTemplate.id.desc())
        .first()
    )
    next_order = (last_step.sort_order + 10) if last_step else 10
    title = str(payload.get("title") or "Шаг цепочки").strip() or "Шаг цепочки"

    chain_step = FlowStepTemplate(
        flow_key=parent_step.flow_key,
        step_key=f"{parent_step.step_key}__chain_{int(datetime.utcnow().timestamp())}",
        parent_step_id=parent_step.id,
        branch_option_index=None,
        step_title=title,
        sort_order=next_order,
        default_text="Новое сообщение сценария.",
        custom_text=None,
        response_type="none",
        button_options=None,
        send_mode="immediate",
        send_time=None,
        day_offset_workdays=0,
        target_field=None,
        send_employee_card=False,
    )
    db.add(chain_step)
    db.commit()

    return {
        "message": "Шаг цепочки добавлен",
        "payload": _build_scenario_workspace_payload(db, scenario.id, kind=scenario.scenario_kind),
        "step_id": chain_step.id,
    }


@router.post("/api/flows/workspace/steps/{step_id}/delete")
def delete_workspace_step_api(
    request: Request,
    step_id: int,
    db: Session = Depends(get_db),
):
    require_api_auth(request)
    step = db.get(FlowStepTemplate, step_id)
    if not step:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Шаг не найден")

    scenario = _get_workspace_scenario_by_flow_key(db, step.flow_key)
    if not scenario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сценарий не найден")

    deleted_kind = _workspace_node_kind(step)
    _delete_step_subtree(db, step)
    db.commit()

    return {
        "message": "Элемент удалён",
        "payload": _build_scenario_workspace_payload(db, scenario.id, kind=scenario.scenario_kind),
        "deleted_kind": deleted_kind,
    }


@router.get("/app/flows/workspace")
def scenario_workspace_legacy_redirect(
    request: Request,
    scenario_id: Optional[int] = None,
):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    target = f"/app/flows/workspace-v2?scenario_id={scenario_id}" if scenario_id else "/app/flows/workspace-v2"
    return RedirectResponse(url=target, status_code=status.HTTP_303_SEE_OTHER)


@router.post("/api/flows/workspace/steps/{step_id}/attachment")
async def upload_workspace_step_attachment_api(
    request: Request,
    step_id: int,
    upload: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    require_api_auth(request)
    step = db.get(FlowStepTemplate, step_id)
    if not step:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Шаг не найден")
    scenario = _get_workspace_scenario_by_flow_key(db, step.flow_key)
    if not scenario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сценарий не найден")
    await _save_step_attachment(step, upload)
    db.commit()
    return {
        "message": "Вложение добавлено",
        "payload": _build_scenario_workspace_payload(db, scenario.id, kind=scenario.scenario_kind),
        "step_id": step.id,
    }


@router.post("/api/flows/workspace/steps/{step_id}/attachment/delete")
def delete_workspace_step_attachment_api(
    request: Request,
    step_id: int,
    db: Session = Depends(get_db),
):
    require_api_auth(request)
    step = db.get(FlowStepTemplate, step_id)
    if not step:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Шаг не найден")
    scenario = _get_workspace_scenario_by_flow_key(db, step.flow_key)
    if not scenario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сценарий не найден")
    _delete_step_attachment_file(step)
    db.commit()
    return {
        "message": "Вложение удалено",
        "payload": _build_scenario_workspace_payload(db, scenario.id, kind=scenario.scenario_kind),
        "step_id": step.id,
    }


@router.get("/app/flows/workspace-v2")
def scenario_workspace_v2_page(
    request: Request,
    scenario_id: Optional[int] = None,
):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    return render_template(
        request,
        templates,
        "react_scenario_workspace_v2.html",
        {
            "active_tab": "flows",
            "react_api_url": "/api/flows/workspace",
            "react_selected_scenario_id": scenario_id or "",
            "classic_list_url": "/flows",
            "workspace_kind": "scenario",
        },
    )


@router.get("/app/surveys/workspace")
def survey_workspace_page(
    request: Request,
    scenario_id: Optional[int] = None,
):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    return render_template(
        request,
        templates,
        "react_scenario_workspace_v2.html",
        {
            "active_tab": "surveys",
            "react_api_url": "/api/flows/workspace",
            "react_selected_scenario_id": scenario_id or "",
            "classic_list_url": "/surveys",
            "workspace_kind": "survey",
        },
    )


@router.get("/surveys")
def surveys_page(request: Request):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    return RedirectResponse(url="/app/surveys/workspace", status_code=status.HTTP_303_SEE_OTHER)
