"""Authenticated employee-scoped exports of answer-collecting scenarios."""

from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_session
from ..models import Employee, ScenarioAnswerRun, SurveyAnswer
from .support import require_api_auth

router = APIRouter()


def get_db():
    with get_session() as db:
        yield db


def _employee(db: Session, employee_id: int) -> Employee:
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Карточка не найдена")
    return employee


@router.get("/api/employees/{employee_id}/scenario-results")
def scenario_results(request: Request, employee_id: int, db: Session = Depends(get_db)):
    require_api_auth(request)
    _employee(db, employee_id)
    rows = (db.query(ScenarioAnswerRun, func.count(SurveyAnswer.id))
            .outerjoin(SurveyAnswer, SurveyAnswer.answer_run_id == ScenarioAnswerRun.id)
            .filter(ScenarioAnswerRun.employee_id == employee_id)
            .group_by(ScenarioAnswerRun.id)
            .order_by(ScenarioAnswerRun.started_at.desc(), ScenarioAnswerRun.id.desc()).all())
    return {"runs": [{"id": run.id, "title": run.scenario_title,
                      "started_at": run.started_at.isoformat(), "status": run.status,
                      "answer_count": count,
                      "download_url": f"/api/employees/{employee_id}/scenario-results/{run.id}/export" if count else None}
                     for run, count in rows]}


@router.get("/api/employees/{employee_id}/scenario-results/{run_id}/export")
def export_scenario_result(request: Request, employee_id: int, run_id: int, db: Session = Depends(get_db)):
    require_api_auth(request)
    _employee(db, employee_id)
    run = db.query(ScenarioAnswerRun).filter_by(id=run_id, employee_id=employee_id).first()
    if run is None:
        raise HTTPException(status_code=404, detail="Запуск не найден")
    answers = (db.query(SurveyAnswer).filter_by(answer_run_id=run.id, employee_id=employee_id)
               .order_by(SurveyAnswer.answered_at, SurveyAnswer.id).all())
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Ответы"
    sheet.append(["ФИО", "Вопрос", "Ответ", "Дата ответа (UTC)"])
    for answer in answers:
        sheet.append([answer.respondent_name or "", answer.question_text or answer.step_key,
                      answer.file_name or answer.answer_value or "", answer.answered_at.isoformat(sep=" ")])
    for row in sheet.iter_rows():
        for cell in row:
            if isinstance(cell.value, str):
                cell.data_type = "s"
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f'attachment; filename="scenario_{employee_id}_run_{run.id}.xlsx"'})
