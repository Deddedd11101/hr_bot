from __future__ import annotations

from typing import Callable

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from ..database import get_session
from . import grades
from .support import render_template, require_api_auth, require_auth

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def get_db(request: Request):
    require_api_auth(request)
    with get_session() as db:
        yield db


def get_write_db(request: Request):
    require_api_auth(request)
    with get_session() as db:
        try:
            # Lock before reading draft/catalog state, not after a finalization race.
            if db.bind.dialect.name == "sqlite":
                db.execute(text("BEGIN IMMEDIATE"))
            yield db
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(409, "Запись с такими данными уже существует или связана с другими данными") from exc
        except LookupError as exc:
            db.rollback()
            raise HTTPException(404, str(exc)) from exc
        except ValueError as exc:
            db.rollback()
            raise HTTPException(422, str(exc)) from exc
        except OperationalError as exc:
            db.rollback()
            raise HTTPException(503, "Не удалось сохранить изменения. Повторите попытку") from exc
        except Exception:
            db.rollback()
            raise


def read_payload(fn: Callable, *args):
    try:
        return fn(*args)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/grades")
def legacy_grades(request: Request):
    return require_auth(request) or RedirectResponse("/app/grades", status_code=303)


@router.get("/app/grades")
def grades_page(request: Request):
    return require_auth(request) or render_template(
        request, templates, "react_grades.html",
        {"active_tab": "grades", "react_api_url": "/api/grades/workspace"},
    )


@router.get("/api/grades/workspace")
def grade_workspace(db: Session = Depends(get_db)):
    return grades.workspace_payload(db)


def register_catalog_routes(kind: str):
    def create(payload: dict = Body(...), db: Session = Depends(get_write_db)):
        grades.save_catalog_item(db, kind, payload)
        return grades.workspace_payload(db)

    def update(item_id: int, payload: dict = Body(...), db: Session = Depends(get_write_db)):
        grades.save_catalog_item(db, kind, payload, item_id=item_id)
        return grades.workspace_payload(db)

    def archive(item_id: int, db: Session = Depends(get_write_db)):
        grades.archive_catalog_item(db, kind, item_id)
        return grades.workspace_payload(db)

    router.add_api_route(f"/api/grades/{kind}", create, methods=["POST"], name=f"create_grade_{kind}")
    router.add_api_route(f"/api/grades/{kind}/{{item_id}}", update, methods=["PUT"], name=f"update_grade_{kind}")
    router.add_api_route(f"/api/grades/{kind}/{{item_id}}", archive, methods=["DELETE"], name=f"archive_grade_{kind}")


for _kind in ("grades", "specializations", "categories", "skills"):
    register_catalog_routes(_kind)


@router.put("/api/grades/matrix")
def update_matrix(payload: dict = Body(...), db: Session = Depends(get_write_db)):
    grades.save_matrix(db, payload)
    return grades.workspace_payload(db)


@router.post("/api/grades/import")
def import_catalog(payload: dict = Body(...), db: Session = Depends(get_write_db)):
    return grades.import_catalog(db, payload)


@router.get("/api/employees/{employee_id}/grade")
def employee_grade(employee_id: int, db: Session = Depends(get_db)):
    return read_payload(grades.employee_grade_payload, db, employee_id)


@router.put("/api/employees/{employee_id}/grade")
def update_employee_grade(employee_id: int, payload: dict = Body(...), db: Session = Depends(get_write_db)):
    grades.update_employee_grade(db, employee_id, payload)
    return grades.employee_grade_payload(db, employee_id)


@router.post("/api/employees/{employee_id}/grade/assessments")
def create_assessment(employee_id: int, request: Request, db: Session = Depends(get_write_db)):
    assessment = grades.create_assessment(db, employee_id, require_api_auth(request).id)
    return grades.assessment_payload(db, assessment.id)


@router.get("/api/grade-assessments/{assessment_id}")
def assessment(assessment_id: int, db: Session = Depends(get_db)):
    return read_payload(grades.assessment_payload, db, assessment_id)


@router.patch("/api/grade-assessments/{assessment_id}")
def update_assessment(assessment_id: int, payload: dict = Body(...), db: Session = Depends(get_write_db)):
    grades.update_assessment(db, assessment_id, payload)
    return grades.assessment_payload(db, assessment_id)


@router.post("/api/grade-assessments/{assessment_id}/finalize")
def finalize_assessment(assessment_id: int, db: Session = Depends(get_write_db)):
    grades.finalize_assessment(db, assessment_id)
    return grades.assessment_payload(db, assessment_id)
