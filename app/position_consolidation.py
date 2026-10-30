"""Guarded, explicit consolidation of the three user-confirmed PM positions."""
import hashlib
from contextlib import closing
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from sqlalchemy import text

from .models import (BotMenuSet, Employee, GradeSpecialization, MassMessageAction,
                     MassScenarioAction, Position, ScenarioTemplate)
from .positions import position_matches_scope, position_title_key

CANONICAL = "rukovoditel_proektov"
TITLES = {"project_manager": "Project manager", "rukovoditel_proekta": "Руководитель проекта",
          CANONICAL: "Руководитель проектов"}
MODELS = {model.__tablename__: model for model in (
    Position, Employee, ScenarioTemplate, BotMenuSet, GradeSpecialization, MassMessageAction, MassScenarioAction)}


def _scope(value):
    if not value:
        return value
    items = value.split(",")
    if not any(item.strip() in TITLES and item.strip() != CANONICAL for item in items):
        return value
    return ",".join(dict.fromkeys(CANONICAL if item.strip() in TITLES else item.strip() for item in items))


def preview(db):
    catalog = db.query(Position).order_by(Position.id).all()
    matched = {row.slug: row for row in catalog if row.slug in TITLES}
    if CANONICAL not in matched or not matched[CANONICAL].is_active:
        raise ValueError("Активная должность «Руководитель проектов» не найдена")
    for key, row in matched.items():
        if position_title_key(row.title) != position_title_key(TITLES[key]):
            raise ValueError("Название ожидаемой должности изменилось; требуется новый review")
    names = {position_title_key(value) for value in (*TITLES, *TITLES.values())}
    employees = db.query(Employee.id, Employee.desired_position).order_by(Employee.id).all()
    changes, deltas, state = [], [], []

    def record(row, field, after):
        before = getattr(row, field)
        state.append([row.__table__.name, row.id, field, before])
        if before != after:
            changes.append(dict(table=row.__table__.name, id=row.id, field=field, before=before, after=after))

    for row in catalog:
        record(row, "title", row.title)
        record(row, "slug", row.slug)
        record(row, "is_active", False if row.slug in TITLES and row.slug != CANONICAL else row.is_active)
    for row in employees:
        after = TITLES[CANONICAL] if position_title_key(row.desired_position or "") in names else row.desired_position
        state.append(["employees", row.id, "desired_position", row.desired_position])
        if after != row.desired_position:
            changes.append(dict(table="employees", id=row.id, field="desired_position", before=row.desired_position, after=after))
    for model, fields in ((ScenarioTemplate, ["role_scope"]), (BotMenuSet, ["role_scope"]),
                          (GradeSpecialization, ["position_slug"]),
                          (MassMessageAction, ["target_role_scope", "target_role_scopes"]),
                          (MassScenarioAction, ["target_role_scope", "target_role_scopes"])):
        query = db.query(model).order_by(model.id)
        if model in (MassMessageAction, MassScenarioAction):
            query = query.filter(model.processed_at.is_(None))
        for row in query:
            for field in fields:
                before = getattr(row, field)
                if field == "target_role_scopes" and before is not None:
                    items = json.loads(before)
                    if not isinstance(items, list) or not all(isinstance(item, str) for item in items):
                        raise ValueError("Некорректная сохранённая аудитория; перенос остановлен")
                    after_items = list(dict.fromkeys(CANONICAL if item in TITLES else item for item in items))
                    after = json.dumps(after_items, separators=(",", ":")) if items != after_items else before
                    old_scope, new_scope = ",".join(items), ",".join(after_items)
                else:
                    after = _scope(before)
                    old_scope, new_scope = before, after
                record(row, field, after)
                if before == after or field == "position_slug":
                    continue
                before_ids = [e.id for e in employees if position_matches_scope(e.desired_position, old_scope, db=db)]
                after_ids = [e.id for e in employees if position_matches_scope(
                    TITLES[CANONICAL] if position_title_key(e.desired_position or "") in names else e.desired_position,
                    new_scope, db=db)]
                if before_ids != after_ids:
                    deltas.append(dict(table=model.__tablename__, id=row.id, field=field,
                                       before_ids=before_ids, after_ids=after_ids))
    digest = hashlib.sha256(json.dumps(state, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return dict(fingerprint=digest, canonical_slug=CANONICAL, changes=changes,
                audience_deltas=deltas, scope="Position filter projection; not delivery simulation")


def apply(db, expected_fingerprint):
    if db.bind.dialect.name != "sqlite":
        raise ValueError("Операция поддерживает только проверенный SQLite workflow")
    database = Path(db.bind.url.database).resolve()
    if not database.is_file():
        raise ValueError("SQLite база не найдена")
    db.commit()
    backup = database.parent / "backups" / f"hr_bot.before-position-consolidation.{uuid4().hex}.db"
    backup.parent.mkdir(exist_ok=True)
    backup.touch(mode=0o600, exist_ok=False)
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as source, closing(sqlite3.connect(backup)) as target:
        source.backup(target)
        if target.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError("Проверка резервной копии не прошла")
    try:
        db.execute(text("BEGIN IMMEDIATE"))
        plan = preview(db)
        if plan["fingerprint"] != expected_fingerprint:
            raise ValueError("Данные изменились после preview; обновите план")
        if plan["audience_deltas"]:
            raise ValueError("Состав аудитории меняется; требуется отдельное согласование")
        for change in plan["changes"]:
            row = db.get(MODELS[change["table"]], change["id"])
            setattr(row, change["field"], change["after"])
        db.flush()
        if preview(db)["changes"]:
            raise ValueError("Проверка результата не прошла")
        db.commit()
        return dict(changed=len(plan["changes"]), backup=str(backup))
    except Exception:
        db.rollback()
        raise
