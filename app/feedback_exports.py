"""Shared XLSX generation for authenticated downloads and Telegram attachments."""

from io import BytesIO

from openpyxl import Workbook
from sqlalchemy.orm import Session

from .models import Employee, EmployeeFeedbackRun, FlowStepTemplate, ScenarioTemplate, SurveyAnswer


def _excel_text(value: str | None) -> str:
    text = value or ""
    return f"'{text}" if text.lstrip().startswith(("=", "+", "-", "@")) else text


def latest_feedback_run(db: Session, employee_id: int) -> EmployeeFeedbackRun | None:
    return (db.query(EmployeeFeedbackRun).filter_by(subject_employee_id=employee_id)
            .order_by(EmployeeFeedbackRun.created_at.desc(), EmployeeFeedbackRun.id.desc()).first())


def feedback_workbook(db: Session, runs: list[EmployeeFeedbackRun]) -> bytes | None:
    run_ids = [run.id for run in runs]
    answers = (db.query(SurveyAnswer).filter(SurveyAnswer.feedback_run_id.in_(run_ids))
               .order_by(SurveyAnswer.answered_at, SurveyAnswer.id).all()) if run_ids else []
    if not answers:
        return None
    runs_by_id = {run.id: run for run in runs}
    scenarios = {row.scenario_key: row.title for row in db.query(ScenarioTemplate).all()}
    steps = {(row.flow_key, row.step_key): row.custom_text if row.custom_text is not None else row.default_text or row.step_title
             for row in db.query(FlowStepTemplate).all()}
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Обратная связь"
    sheet.append(["Дата запуска", "Опрос", "ФИО отвечавшего", "Вопрос", "Ответ", "Дата ответа"])
    for answer in answers:
        run = runs_by_id[answer.feedback_run_id]
        respondent = db.get(Employee, answer.employee_id)
        sheet.append([run.created_at.strftime("%d.%m.%Y %H:%M"),
                      _excel_text(run.scenario_title or scenarios.get(run.scenario_key, run.scenario_key)),
                      _excel_text(answer.respondent_name or (respondent.full_name if respondent else f"Сотрудник #{answer.employee_id}")),
                      _excel_text(answer.question_text or steps.get((run.scenario_key, answer.step_key), answer.step_key)),
                      _excel_text(answer.file_name or answer.answer_value),
                      answer.answered_at.strftime("%d.%m.%Y %H:%M")])
    for row in sheet.iter_rows():
        for cell in row:
            if isinstance(cell.value, str):
                cell.data_type = "s"
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()
