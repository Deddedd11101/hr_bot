"""Small, network-free Telegram layouts for the grade-review pilot."""

import json

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

SINGLE_WIDGET = STYLE + """<style>
.track{height:5px;margin:8px 0 12px;background:#32a66333;border-radius:4px}
.bar{height:5px;background:#32a663;border-radius:4px}
</style><main><header id="label">Оценка навыков</header><div class="track"><div id="meter" class="bar"></div></div>
<h3 id="title"></h3><p id="prompt"></p><table id="result" style="display:none"></table></main><script>
const W=window.TelegramWidget;
const el=id=>document.getElementById(id);
function render(){
 let d;try{d=JSON.parse(W.chatData)}catch(e){return}if(!d)return;
 el('label').textContent=d.label;el('title').textContent=d.title;el('prompt').textContent=d.prompt||'';
 el('meter').style.width=(100*(d.current||0)/(d.total||1))+'%';
 const t=el('result');t.textContent='';t.style.display=d.rows?'table':'none';
 if(d.rows)for(const values of [['Навык / вопрос','Ответ'],...d.rows]){
   const row=document.createElement('tr');for(const value of values){const cell=document.createElement('td');cell.textContent=value;row.appendChild(cell)}t.appendChild(row)
 }
}
W.onEvent('chatDataChanged',render);render();
</script>"""


def enabled_for(employee_id: int) -> bool:
    return str(employee_id) in {part.strip() for part in settings.GRADE_WIDGET_REVIEWER_IDS.split(",")}


def widget_state(label, title, prompt="", *, current=0, total=1, rows=None):
    state = dict(label=label, title=title, prompt=prompt, current=current, total=total)
    if rows is not None:
        state["rows"] = rows
    packed = json.dumps(state, ensure_ascii=False, separators=(",", ":"))
    return packed if len(packed.encode("utf-8")) <= 1024 else None
