"""Frozen colleague reviews using the existing survey/identity runtime."""
import html
import json
import logging
from copy import deepcopy
from uuid import UUID, uuid4

from sqlalchemy import and_, or_, select, update

from ..database import SessionLocal
from ..messaging.identity import get_primary_chat_id
from ..models import (Employee, EmployeeFeedbackRun, EmployeeFeedbackRecipient, EmployeeGradeProfile,
                      FlowStepTemplate, Grade, GradeAssessment, GradeAssessmentValue, GradeReviewCollection,
                      GradeDevelopmentAction, ScenarioTemplate, SurveyAnswer)
from ..scenario_engine import ScenarioRecipientBusy, get_conflicting_progress_for_survey_launch, start_scenario
from ..time_utils import utc_now
from .calculations import fractional_category_averages
from .catalog import integer, require, row as catalog_row
from .history import matrix_version
from .recommendations import matrix_coverage
from .review_confirmation import STEP_KEY
from .review_intro import review_intro

logger = logging.getLogger(__name__)


def recipient_ids(db, raw):
    if not isinstance(raw, list) or not 1 <= len(raw) <= 100:
        raise ValueError("Выберите от 1 до 100 оценивающих")
    ids = [integer(value, 1, 2**63 - 1, "recipient_id") for value in raw]
    if len(set(ids)) != len(ids):
        raise ValueError("Оценивающие не должны повторяться")
    for employee_id in ids:
        employee = require(db, Employee, employee_id)
        if employee.employee_stage not in {"staff", "adaptation", "ipr"} or employee.is_bot_blocked or not get_primary_chat_id(employee, db=db):
            raise ValueError(f"Оценивающий #{employee_id} недоступен или не привязан к боту")
    return ids


def create(db, employee_id, actor_id, data):
    from ..web import grades
    grades._lock_employee(db, employee_id)
    subject = require(db, Employee, employee_id)
    if subject.employee_stage not in {"staff", "adaptation", "ipr"} or subject.is_bot_blocked:
        raise ValueError("Сотрудник недоступен для оценки")
    required = {"request_id", "specialization_id", "recipient_ids"}
    if not required <= set(data) or set(data) - required - {"open_questions"}:
        raise ValueError("Неизвестные поля сбора оценок")
    from .rubrics import guidance
    specialization_id = integer(data.get("specialization_id"), 1, 2**63 - 1, "specialization_id")
    from ..models import GradeSpecialization
    spec_guidance = guidance(catalog_row(require(db, GradeSpecialization, specialization_id, active=True)))
    questions = data.get("open_questions", spec_guidance.get("open_questions", []))
    if not isinstance(questions, list) or len(questions) > 20 or any(
        not isinstance(q, str) or not 1 <= len(q.strip()) <= 2000 for q in questions
    ):
        raise ValueError("Нужно не более 20 открытых вопросов, каждый от 1 до 2000 символов")
    questions = [q.strip() for q in questions]
    request_id = str(UUID(data["request_id"]))
    digest = matrix_version(data)
    previous = db.scalar(select(GradeReviewCollection).where(GradeReviewCollection.employee_id == employee_id, GradeReviewCollection.request_id == request_id))
    if previous:
        if previous.request_hash != digest:
            raise grades.GradeConflictError("Запрос уже использован с другими настройками")
        return previous
    ids = recipient_ids(db, data.get("recipient_ids"))
    if employee_id in ids:
        raise ValueError("Выберите коллег; самооценку можно сохранить отдельным ревью")
    profile = db.scalar(select(EmployeeGradeProfile).where(EmployeeGradeProfile.employee_id == employee_id))
    view = grades.preview_review(db, employee_id, specialization_id, profile.current_grade_id if profile else None)
    view["open_questions"] = questions
    if not view["scores"]:
        raise ValueError("В выбранном шаблоне нет навыков")
    key = "grade_review_" + uuid4().hex
    scenario = ScenarioTemplate(scenario_key=key, title="Оценка навыков коллегами", scenario_kind="grade_review", purpose="ipr", recipient_mode="self", role_scope="all", employee_scope="employees", trigger_mode="manual_only")
    db.add(scenario)
    if view.get("assessment_intro"):
        db.add(FlowStepTemplate(flow_key=key, step_key="intro", step_title="Начало оценки", sort_order=-1,
            default_text=review_intro(view["assessment_intro"], len(questions)), response_type="none", send_mode="immediate"))
    for index, score in enumerate(view["scores"]):
        prompt = ("Оцени навыки сотрудника {employee_full_name}.\n\n" + html.escape(score["categoryName"]) + ": " + html.escape(score["skillName"]) +
                  "\n\n0 — нет · 1 — понимание · 2 — умение · 3 — экспертиза · 4 — лидерство. Если не можешь оценить, пропусти навык.")
        rubric = score.get("rubric")
        if rubric:
            prompt = ("Оцени навык сотрудника {employee_full_name}.\n\n" + html.escape(score["skillName"]) + "\n\n" +
                "\n\n".join(f"{level}. {html.escape(text)}" for level, text in rubric["levels"].items()) +
                "\n\n" + html.escape(rubric["na"]))
        db.add(FlowStepTemplate(flow_key=key, step_key=f"skill_{score['skillId']}", step_title=score["skillName"], sort_order=index,
            default_text=prompt, response_type="buttons", button_options=("1\n2\n3\n4\nНе могу оценить" if rubric else "0\n1\n2\n3\n4\nНе могу оценить"), target_field="survey_answer", send_mode="immediate"))
    for index, question in enumerate(questions):
        db.add(FlowStepTemplate(flow_key=key, step_key=f"open_{index}", step_title=f"Комментарий {index + 1}",
            sort_order=len(view["scores"]) + index,
            default_text="Обратная связь о сотруднике {employee_full_name}.\n\n" + html.escape(question),
            response_type="text", target_field="survey_answer", send_mode="immediate"))
    db.add(FlowStepTemplate(flow_key=key, step_key=STEP_KEY, step_title="Проверка оценки", sort_order=len(view["scores"]) + len(questions),
        default_text="Проверь ответы выше. Утверди оценку или начни заново.", response_type="buttons",
        button_options="Утвердить\nОценить заново", send_mode="immediate", is_terminal=True))
    run = EmployeeFeedbackRun(subject_employee_id=employee_id, scenario_key=key, scenario_title="Оценка навыков коллегами", created_at=utc_now())
    db.add(run)
    db.flush()
    for respondent in ids:
        db.add(EmployeeFeedbackRecipient(run_id=run.id, respondent_employee_id=respondent, delivery_status="pending"))
    collection = GradeReviewCollection(employee_id=employee_id, request_id=request_id, request_hash=digest,
        feedback_run_id=run.id, scenario_key=key, snapshot_json=json.dumps(view, ensure_ascii=False), created_by=actor_id)
    db.add(collection)
    db.flush()
    return collection


def report(db, collection):
    snapshot = json.loads(collection.snapshot_json)
    final_assessment = db.get(GradeAssessment, collection.assessment_id) if collection.assessment_id else None
    profile = db.scalar(select(EmployeeGradeProfile).where(EmployeeGradeProfile.employee_id == collection.employee_id))
    grade_options = deepcopy(snapshot["catalog"]["grades"])
    if profile and profile.current_grade_id and profile.current_grade_id not in {g["id"] for g in grade_options}:
        current_grade = db.get(Grade, profile.current_grade_id)
        if current_grade:
            grade_options.append(catalog_row(current_grade))
    recipients = list(db.scalars(select(EmployeeFeedbackRecipient).where(EmployeeFeedbackRecipient.run_id == collection.feedback_run_id).order_by(EmployeeFeedbackRecipient.id)))
    answers = list(db.scalars(select(SurveyAnswer).where(SurveyAnswer.feedback_run_id == collection.feedback_run_id).order_by(SurveyAnswer.id)))
    latest = {(a.employee_id, a.step_key): a.answer_value for a in answers}
    completed = [r for r in recipients if r.delivery_status == "completed"]
    reviewers = []
    totals = {s["skillId"]: [] for s in snapshot["scores"]}
    for recipient in recipients:
        scores = []
        for source in snapshot["scores"]:
            value = latest.get((recipient.respondent_employee_id, f"skill_{source['skillId']}")) if recipient in completed else None
            level = int(value) if value in {"0", "1", "2", "3", "4"} else None
            scores.append(dict(source, assessed=level is not None, currentLevel=level or 0))
            if recipient in completed and level is not None:
                totals[source["skillId"]].append(level)
        employee = db.get(Employee, recipient.respondent_employee_id)
        reviewers.append(dict(employee_id=recipient.respondent_employee_id, name=employee.full_name if employee else f"#{recipient.respondent_employee_id}",
            status=recipient.delivery_status, scores=scores, categories=fractional_category_averages(scores),
            comments=[dict(question=question, answer=latest.get((recipient.respondent_employee_id, f"open_{index}")) if recipient in completed else None)
                      for index, question in enumerate(snapshot.get("open_questions", []))]))
    scores = [dict(s, assessed=bool(totals[s["skillId"]]), currentLevel=sum(totals[s["skillId"]]) / len(totals[s["skillId"]]) if totals[s["skillId"]] else 0,
                   respondent_count=len(totals[s["skillId"]])) for s in snapshot["scores"]]
    return dict(id=collection.id, status=collection.status, created_at=collection.created_at.isoformat(), assessment_id=collection.assessment_id,
        current_grade_id=final_assessment.current_grade_id if final_assessment else profile.current_grade_id if profile else None,
        grades=grade_options, recommendation=matrix_coverage(snapshot["catalog"], snapshot["specialization_id"], scores),
        template=snapshot["catalog"]["specializations"], reviewers=reviewers, scores=scores, categories=fractional_category_averages(scores),
        completed_count=len(completed), recipient_count=len(recipients), can_finalize=collection.status == "open" and len(completed) == len(recipients) and any(s["assessed"] for s in scores))


def list_reports(db, employee_id):
    require(db, Employee, employee_id)
    return [report(db, row) for row in db.scalars(select(GradeReviewCollection).where(GradeReviewCollection.employee_id == employee_id).order_by(GradeReviewCollection.id.desc()))]


def finalize(db, employee_id, collection_id, actor_id, data=None):
    from ..web import grades
    grades._lock_employee(db, employee_id)
    collection = require(db, GradeReviewCollection, collection_id)
    if collection.employee_id != employee_id:
        raise LookupError("Сбор оценок не найден")
    data = {} if data is None else data
    if not isinstance(data, dict) or set(data) - {"current_grade_id", "comment", "expected_current_grade_id"}:
        raise ValueError("Неизвестные поля итоговой оценки")
    comment = data.get("comment", "Средняя оценка коллег")
    if not isinstance(comment, str) or len(comment) > 4000:
        raise ValueError("Комментарий должен быть строкой до 4000 символов")
    if collection.assessment_id:
        if "current_grade_id" in data and data["current_grade_id"] != db.get(GradeAssessment, collection.assessment_id).current_grade_id:
            raise ValueError("Итог уже сохранён; используйте исправление оценки")
        return grades.assessment_payload(db, collection.assessment_id)
    profile = db.scalar(select(EmployeeGradeProfile).where(EmployeeGradeProfile.employee_id == employee_id))
    if "expected_current_grade_id" in data and data["expected_current_grade_id"] != (profile.current_grade_id if profile else None):
        raise grades.GradeConflictError("Грейд сотрудника изменён другим HR. Обновите данные перед фиксацией.")
    result = report(db, collection)
    if not result["can_finalize"]:
        raise ValueError("Дождитесь завершения оценивания всеми выбранными сотрудниками; нужен хотя бы один оценённый навык")
    frozen = deepcopy(json.loads(collection.snapshot_json))
    grade_id = data.get("current_grade_id", frozen["current_grade_id"])
    if grade_id is not None:
        grade = require(db, Grade, integer(grade_id, 1, 2**63 - 1, "current_grade_id"), active=True)
        if grade.id not in {g["id"] for g in frozen["catalog"]["grades"]}:
            frozen["catalog"]["grades"].append(catalog_row(grade))
    if "current_grade_id" in data:
        grades.update_employee_grade(db, employee_id, dict(specialization_id=frozen["specialization_id"],
            current_grade_id=grade_id, target_grade_id=None, target_specialization_id=None, comment=comment), actor_id=actor_id)
    now = utc_now()
    assessment = GradeAssessment(employee_id=employee_id, specialization_id=frozen["specialization_id"], current_grade_id=grade_id,
        assessor_admin_account_id=actor_id, status="final", created_at=now, updated_at=now, finalized_at=now,
        catalog_snapshot=json.dumps(dict(review_mode="historical", draft_catalog=frozen["catalog"]), ensure_ascii=False))
    db.add(assessment)
    db.flush()
    for score in result["scores"]:
        if score["assessed"]:
            db.add(GradeAssessmentValue(assessment_id=assessment.id, skill_id=score["skillId"], level=score["currentLevel"]))
    db.flush()
    snapshot = grades._draft_payload(db, assessment)
    snapshot.update(review_comment=comment, collection_id=collection.id, recommendation=result["recommendation"],
        colleague_reviews=result["reviewers"], open_questions=frozen.get("open_questions", []),
        aggregation=dict(method="mean_per_skill", respondent_count=result["completed_count"], frozen_template=True))
    assessment.catalog_snapshot = json.dumps(snapshot, ensure_ascii=False, allow_nan=False)
    collection.assessment_id, collection.status = assessment.id, "final"
    from .development import renew_after_finalization
    renew_after_finalization(db, assessment)
    db.flush()
    return snapshot


async def process_pending(bot, *, session_factory=None, run_id=None):
    factory = session_factory or SessionLocal
    with factory() as db:
        query = (select(EmployeeFeedbackRecipient.id, EmployeeFeedbackRun.id)
            .join(EmployeeFeedbackRun, EmployeeFeedbackRun.id == EmployeeFeedbackRecipient.run_id)
            .outerjoin(GradeReviewCollection, GradeReviewCollection.feedback_run_id == EmployeeFeedbackRun.id)
            .outerjoin(GradeDevelopmentAction, and_(GradeDevelopmentAction.result_id == EmployeeFeedbackRun.id, GradeDevelopmentAction.action_type == "feedback"))
            .where(or_(GradeReviewCollection.status == "open", GradeDevelopmentAction.status == "started",
                and_(EmployeeFeedbackRun.queued_delivery.is_(True), GradeReviewCollection.id.is_(None), GradeDevelopmentAction.id.is_(None))),
                EmployeeFeedbackRecipient.delivery_status == "pending")
            .order_by(EmployeeFeedbackRun.created_at, EmployeeFeedbackRun.id, EmployeeFeedbackRecipient.id))
        eligible_query = query
        if run_id is not None:
            query = query.where(EmployeeFeedbackRun.id == run_id)
        pairs = list(db.execute(query))
    for recipient_id, run_id in pairs:
        with factory() as db:
            row, run = db.get(EmployeeFeedbackRecipient, recipient_id), db.get(EmployeeFeedbackRun, run_id)
            if row is None or run is None:
                continue
            from ..web.grades import _lock_employee
            _lock_employee(db, row.respondent_employee_id)
            db.refresh(row)
            if row.delivery_status != "pending":
                continue
            reserved = db.scalar(select(EmployeeFeedbackRecipient.id).where(
                EmployeeFeedbackRecipient.respondent_employee_id == row.respondent_employee_id,
                EmployeeFeedbackRecipient.id != row.id,
                EmployeeFeedbackRecipient.delivery_status == "starting"))
            if reserved:
                continue
            earliest = db.execute(eligible_query.where(
                EmployeeFeedbackRecipient.respondent_employee_id == row.respondent_employee_id).limit(1)).first()
            if earliest is None or earliest[0] != row.id:
                continue
            employee = db.get(Employee, row.respondent_employee_id)
            subject = db.get(Employee, run.subject_employee_id)
            if not subject or subject.is_bot_blocked or subject.employee_stage not in {"staff", "adaptation", "ipr"} or not employee or employee.employee_stage not in {"staff", "adaptation", "ipr"} or employee.is_bot_blocked or not get_primary_chat_id(employee, db=db):
                row.delivery_status = "failed"
                db.commit()
                continue
            from ..scenario_engine import get_first_step, matches_role_scope, is_survey
            scenario = db.scalar(select(ScenarioTemplate).where(ScenarioTemplate.scenario_key == run.scenario_key))
            if (not is_survey(scenario) or scenario.recipient_mode != "self"
                    or not get_first_step(db, run.scenario_key) or not matches_role_scope(employee, scenario)):
                row.delivery_status = "failed"
                db.commit()
                continue
            if get_conflicting_progress_for_survey_launch(db, employee.id, run.scenario_key):
                continue
            claimed = db.execute(update(EmployeeFeedbackRecipient).where(EmployeeFeedbackRecipient.id == row.id,
                EmployeeFeedbackRecipient.delivery_status == "pending").values(delivery_status="starting")).rowcount
            db.commit()
            if claimed != 1:
                continue
            try:
                started = await start_scenario(bot, db, employee, run.scenario_key, feedback_run_id=run.id, defer_if_busy=True)
                db.refresh(row)
                if row.delivery_status != "completed":
                    row.delivery_status = "sent" if started else "failed"
                db.commit()
            except ScenarioRecipientBusy:
                db.rollback()
                db.execute(update(EmployeeFeedbackRecipient).where(EmployeeFeedbackRecipient.id == recipient_id,
                    EmployeeFeedbackRecipient.delivery_status == "starting").values(delivery_status="pending"))
                db.commit()
            except Exception:
                db.rollback()
                # Ambiguous external send: leave starting, never replay automatically.
                logger.warning("Grade review delivery uncertain: recipient_row_id=%s", recipient_id)
