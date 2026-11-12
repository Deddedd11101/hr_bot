"""Small, network-free Telegram layouts for the grade-review pilot."""

from html import escape

from ..config import settings

STYLE = """<style>
body{margin:0;color:var(--tg-theme-text-color);font-size:14px}
main{padding:12px 14px;border-top:3px solid #32a663}
header{color:#218449;font-weight:700;font-size:12px;margin-bottom:6px}
@media (prefers-color-scheme:dark){header{color:#61cf8a}}
h3{margin:0 0 8px;font-size:17px}p{margin:0;white-space:pre-wrap;overflow-wrap:anywhere}
table{width:100%;table-layout:fixed;border-collapse:collapse;text-align:left}
th,td{padding:6px 4px;border-bottom:1px solid #32a66355;vertical-align:top;overflow-wrap:anywhere;white-space:pre-wrap}
th:last-child,td:last-child{width:35%}
</style>"""


def enabled_for(employee_id: int) -> bool:
    return str(employee_id) in {part.strip() for part in settings.GRADE_WIDGET_REVIEWER_IDS.split(",")}


def question_markup(title: str, prompt: str) -> str | None:
    if not prompt or len(prompt) > 650:
        return None
    return f"{STYLE}<main><header>Оценка навыков</header><h3>{escape(title)}</h3><p>{escape(prompt)}</p></main>"


def summary_markup(rows: list[tuple[str, str]], page: int, pages: int) -> str | None:
    if any(len(label) + len(answer) > 180 for label, answer in rows) or sum(len(a) + len(b) for a, b in rows) > 520:
        return None
    cells = "".join(f"<tr><td>{escape(label)}</td><td>{escape(answer)}</td></tr>" for label, answer in rows)
    return (f"{STYLE}<main><header>Итоги оценки · {page}/{pages}</header>"
            f"<table><tr><th>Навык / вопрос</th><th>Ответ</th></tr>{cells}</table></main>")
