"""Review a respondent's own draft before it contributes to a grade."""

from html import escape
import json
from textwrap import wrap

from ..models import GradeReviewCollection, SurveyAnswer
from .review_widgets import widget_state
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

STEP_KEY = "review_confirm"


def draft_answers(db, progress):
    return db.query(SurveyAnswer).filter_by(employee_id=progress.employee_id,
        scenario_key=progress.scenario_key, feedback_run_id=progress.feedback_run_id)


def summary_rows(db, progress, *, include_open=True):
    collection = db.query(GradeReviewCollection).filter_by(feedback_run_id=progress.feedback_run_id,
        scenario_key=progress.scenario_key).one()
    snapshot = json.loads(collection.snapshot_json)
    values = {row.step_key: row.answer_value for row in draft_answers(db, progress).order_by(SurveyAnswer.id)}
    rows = [(item["skillName"], values.get(f"skill_{item['skillId']}") or "Нет ответа")
            for item in snapshot["scores"]]
    if include_open:
        rows += [(question, values.get(f"open_{i}") or "Нет ответа")
                 for i, question in enumerate(snapshot.get("open_questions", []))]
    return rows


def summary_screen(db, progress, step, page=0):
    pages = [[]]
    for label, answer in summary_rows(db, progress, include_open=False):
        labels = [label[i:i + 100] for i in range(0, len(label), 100)] or [""]
        answers = [answer[i:i + 110] for i in range(0, len(answer), 110)]
        for i in range(max(len(labels), len(answers))):
            part = (labels[i] if i < len(labels) else "Продолжение", answers[i] if i < len(answers) else "")
            proposed = [*pages[-1], part]
            if len(proposed) > 4 or not widget_state("Итоги оценки · 999999/999999", "Проверь свои ответы", current=1, rows=proposed):
                pages.append([part])
            else:
                pages[-1] = proposed
    if not 0 <= page < len(pages):
        return None
    label = f"Итоги оценки · {page + 1}/{len(pages)}"
    state = widget_state(label, "Проверь свои ответы", current=1, rows=pages[page])
    buttons = []
    if page:
        buttons.append(InlineKeyboardButton(text="←", callback_data=f"scenario:{step.id}:{-page}"))
    if page + 1 < len(pages):
        buttons.append(InlineKeyboardButton(text="→", callback_data=f"scenario:{step.id}:{-page - 2}"))
    decisions = [InlineKeyboardButton(text=label, callback_data=f"scenario:{step.id}:{i}")
                 for i, label in enumerate(("Утвердить", "Оценить заново"))]
    return state, InlineKeyboardMarkup(inline_keyboard=([buttons] if buttons else []) + [decisions])


async def send_summary(messenger, db, progress, chat_id):
    rows = summary_rows(db, progress)
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
