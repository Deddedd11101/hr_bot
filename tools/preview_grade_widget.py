"""Export a standalone browser preview of the Telegram grade widget."""

import argparse
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app.grades.review_widgets import SINGLE_WIDGET, widget_state

    states = [
        widget_state("Оценка навыков", "Работа с требованиями", "Как коллега выявляет и уточняет требования?", current=1, total=2),
        widget_state("Оценка навыков", "Моделирование процессов", "Как коллега описывает процессы и согласовывает их с командой?", current=2, total=2),
        widget_state("Проверка ответов", "Ваши ответы", current=2, total=2, rows=[
            ["Работа с требованиями", "Умение"], ["Моделирование процессов", "Экспертность"],
            ["Что получается особенно хорошо?", "Структурирует сложные задачи и помогает команде договориться."],
        ]),
    ]
    shell = """<!doctype html><html lang="ru"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Предпросмотр виджета оценки</title><style>
:root{color-scheme:light dark;--tg-theme-text-color:CanvasText;font-family:system-ui,sans-serif}
body{background:Canvas}section{max-width:420px;margin:24px auto;padding:0 12px}
main{border:1px solid #32a66355;border-top-width:3px;border-radius:8px}
nav{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:12px}
button{font:inherit;padding:6px 10px;border:1px solid #32a66388;border-radius:6px;cursor:pointer}
button[aria-pressed=true]{background:#218449;color:white}
</style><section><h1>Предпросмотр оценки</h1><nav aria-label="Состояние виджета">
<button aria-pressed="true">Вопрос 1</button><button aria-pressed="false">Вопрос 2</button>
<button aria-pressed="false">Итоговая таблица</button></nav>"""
    data = json.dumps(states, ensure_ascii=False)
    shim = f"""<script>
const samples={data};
let update;
window.TelegramWidget={{chatData:samples[0],onEvent:(name,fn)=>{{if(name==='chatDataChanged')update=fn}}}};
const buttons=Array.from(document.querySelectorAll('nav button'));
buttons.forEach((button,i)=>button.addEventListener('click',()=>{{
 buttons.forEach((item,j)=>item.setAttribute('aria-pressed',String(i===j)));
 window.TelegramWidget.chatData=samples[i];update();
}}));
</script>"""
    args.output.write_text(shell + shim + SINGLE_WIDGET + "</section></html>", encoding="utf-8")


if __name__ == "__main__":
    main()
