"""Shared organizational folders only; never change runtime audiences or schedules."""

import unicodedata
from typing import Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from ..database import get_session
from ..models import CatalogGroup, CatalogMembership, Employee, ScenarioTemplate
from .support import require_api_auth

router = APIRouter()
Scope = Literal["people", "scenarios"]


def get_db():
    with get_session() as db:
        yield db


class GroupInput(BaseModel):
    scope: Scope
    name: str = Field(min_length=1, max_length=80)
    expected_revision: int | None = Field(default=None, ge=1)


class MoveInput(BaseModel):
    scope: Scope
    object_id: int = Field(gt=0)
    group_id: int | None = Field(default=None, gt=0)
    expected_group_id: int | None = Field(default=None, gt=0)


def _lock(db):
    if db.get_bind().dialect.name == "sqlite":
        connection = db.connection()
        if not connection.connection.driver_connection.in_transaction:
            connection.execute(text("BEGIN IMMEDIATE"))
    else:
        db.query(CatalogGroup).with_for_update().all()


def _model(scope):
    return Employee if scope == "people" else ScenarioTemplate


def payload(db, scope):
    ids = {r[0] for r in db.query(_model(scope).id)}
    groups = db.query(CatalogGroup).filter_by(scope=scope).order_by(CatalogGroup.name, CatalogGroup.id).all()
    group_ids = {g.id for g in groups}
    members = {str(r.object_id): r.group_id for r in db.query(CatalogMembership).filter_by(scope=scope)
               if r.object_id in ids and r.group_id in group_ids}
    return {"groups": [{"id": g.id, "name": g.name, "revision": g.revision} for g in groups], "memberships": members}


def _name(value):
    name = unicodedata.normalize("NFKC", " ".join(value.split()))
    key = name.casefold()
    if not name or len(name) > 80 or key in {"все", "без группы"}:
        raise HTTPException(422, "Укажите название группы до 80 символов, отличное от «Все» и «Без группы»")
    return name, key


def _commit(db):
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Группа с таким названием уже есть. Обновите список.") from exc


@router.get("/api/catalog-groups")
def groups_api(request: Request, scope: Scope, db: Session = Depends(get_db)):
    require_api_auth(request)
    return payload(db, scope)


@router.post("/api/catalog-groups")
def create_group(request: Request, data: GroupInput, db: Session = Depends(get_db)):
    require_api_auth(request)
    _lock(db)
    name, key = _name(data.name)
    group = CatalogGroup(scope=data.scope, name=name, normalized_name=key)
    db.add(group)
    _commit(db)
    return {**payload(db, data.scope), "created_group_id": group.id}


@router.patch("/api/catalog-groups/{group_id}")
def rename_group(request: Request, group_id: int, data: GroupInput, db: Session = Depends(get_db)):
    require_api_auth(request)
    _lock(db)
    group = db.get(CatalogGroup, group_id)
    if not group or group.scope != data.scope:
        raise HTTPException(404, "Группа не найдена")
    if group.revision != data.expected_revision:
        raise HTTPException(409, "Группа изменилась. Обновите список.")
    group.name, group.normalized_name = _name(data.name)
    group.revision += 1
    _commit(db)
    return payload(db, data.scope)


@router.delete("/api/catalog-groups/{group_id}")
def delete_group(request: Request, group_id: int, scope: Scope, expected_revision: int, db: Session = Depends(get_db)):
    require_api_auth(request)
    _lock(db)
    group = db.get(CatalogGroup, group_id)
    if not group or group.scope != scope:
        raise HTTPException(404, "Группа не найдена")
    if group.revision != expected_revision:
        raise HTTPException(409, "Группа изменилась. Обновите список.")
    db.query(CatalogMembership).filter_by(scope=scope, group_id=group_id).delete()
    db.delete(group)
    _commit(db)
    return payload(db, scope)


@router.put("/api/catalog-group-membership")
def move_object(request: Request, data: MoveInput = Body(...), db: Session = Depends(get_db)):
    require_api_auth(request)
    _lock(db)
    if db.get(_model(data.scope), data.object_id) is None:
        raise HTTPException(404, "Запись не найдена")
    if data.group_id is not None:
        group = db.get(CatalogGroup, data.group_id)
        if not group or group.scope != data.scope:
            raise HTTPException(422, "Выберите группу этого каталога")
    member = db.get(CatalogMembership, (data.scope, data.object_id))
    if (member.group_id if member else None) != data.expected_group_id:
        raise HTTPException(409, "Запись уже переместили. Обновите список.")
    if data.group_id is None:
        if member:
            db.delete(member)
    elif member:
        member.group_id = data.group_id
    else:
        db.add(CatalogMembership(scope=data.scope, object_id=data.object_id, group_id=data.group_id))
    _commit(db)
    return payload(db, data.scope)
