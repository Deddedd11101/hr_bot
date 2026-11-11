"""Review a respondent's own draft before it contributes to a grade."""

from html import escape
import json
from textwrap import wrap

from ..models import GradeReviewCollection, SurveyAnswer

STEP_KEY = "review_confirm"


def draft_answers(db, progress):
    return db.query(SurveyAnswer).filter_by(employee_id=progress.employee_id,
        scenario_key=progress.scenario_key, feedback_run_id=progress.feedback_run_id)


async def send_summary(messenger, db, progress, chat_id):
    collection = db.query(GradeReviewCollection).filter_by(feedback_run_id=progress.feedback_run_id,
        scenario_key=progress.scenario_key).one()
    snapshot = json.loads(collection.snapshot_json)
    values = {row.step_key: row.answer_value for row in draft_answers(db, progress).order_by(SurveyAnswer.id)}
    rows = [(item["skillName"], values.get(f"skill_{item['skillId']}") or "Нет ответа")
            for item in snapshot["scores"]]
    rows += [(question, values.get(f"open_{i}") or "Нет ответа")
             for i, question in enumerate(snapshot.get("open_questions", []))]
    rich_send = getattr(messenger, "send_rich_text", None)
    for offset in range(0, len(rows), 8):
        page = rows[offset:offset + 8]
        table = "<table><tr><th>Навык / вопрос</th><th>Ответ</th></tr>" + "".join(
            f"<tr><td>{escape(label)}</td><td>{escape(answer).replace(chr(10), '<br>')}</td></tr>"
            for label, answer in page) + "</table>"
        if rich_send and await rich_send(chat_id, table):
            continue
        plain = "\n\n".join(f"{label}: {answer}" for label, answer in page)
        for part in wrap(plain, width=1800, replace_whitespace=False, expand_tabs=False):
            await messenger.send_text(chat_id, f"<pre>{escape(part)}</pre>")
