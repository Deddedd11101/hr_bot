"""Small, network-free Telegram layouts for the grade-review pilot."""

import json

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from ..config import settings
from ..models import GradeReviewCollection

STYLE = """<style>
body{margin:0;color:#f2f2f2;font-size:14px;background:#262626}
main{padding:12px 14px;border-top:3px solid #52aa79}
header{color:#d0d0d0;font-weight:700;font-size:12px;margin-bottom:6px;overflow-wrap:anywhere}
h3{margin:0 0 8px;font-size:17px}p{margin:0;white-space:pre-wrap;overflow-wrap:anywhere}
table{width:100%;table-layout:fixed;border-collapse:collapse;text-align:left}
th,td{padding:6px 4px;border-bottom:1px solid #32a66355;vertical-align:top;overflow-wrap:anywhere;white-space:pre-wrap}
th:last-child,td:last-child{width:35%}
</style>"""

SINGLE_WIDGET = STYLE + """<style>
.track{height:5px;margin:8px 0 12px;background:#32a66333;border-radius:4px}
.bar{height:5px;background:#32a663;border-radius:4px}
.criterion{display:block;width:100%;text-align:left;margin:6px 0;white-space:normal;overflow-wrap:anywhere}
button{color:#f2f2f2;background:#303030;border:1px solid #555;border-radius:7px;padding:7px}
button[aria-pressed=true],#next{border-color:#52aa79}#next{margin-left:6px;background:#52aa79;color:#1d1d1d}button:disabled{opacity:.5}
</style><main><header id="label">Оценка навыков</header><div class="track"><div id="meter" class="bar"></div></div>
<h3 id="title"></h3><p id="prompt"></p><div id="choices"></div><table id="result" style="display:none"></table></main><script>
const W=window.TelegramWidget;
const el=id=>document.getElementById(id);
let revision=0, nextRead=0;
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function criteria(d, version){
 const box=el('choices'), parts=[];parts[d.page||0]=d.prompt;
 try{
  for(let i=0;i<(d.pages||1);i++){
   if(parts[i]!==undefined)continue;
   await pause(Math.max(0,nextRead-Date.now()));
   if(version!==revision)return;
   nextRead=Date.now()+5200;
   const reply=await W.request('g:r:'+d.step+':'+i);
   nextRead=Date.now()+5200;
   const page=JSON.parse(reply.result);
   if(page.step!==d.step||page.page!==i)throw Error();
   parts[i]=page.prompt;
  }
  if(version!==revision)return;
  const items=parts.join('').split(/(?:^|\\n\\n)[1-4]\\. /).slice(1);
  if(items.length!==4)throw Error();
  el('prompt').textContent='';
  if(d.pages>1)el('label').textContent=d.label.slice(0,d.label.lastIndexOf(' · '));
  let selected=null, busy=false;
  const buttons=[];
  function add(label,click){const b=document.createElement('button');b.textContent=label;b.onclick=click;box.appendChild(b);return b}
  async function submit(index){
   if(busy)return;busy=true;next.disabled=true;skip.disabled=true;
   try{if((await W.request('g:a:'+d.step+':'+index)).result!=='ok')throw Error()}
   catch(e){if(version===revision){busy=false;next.disabled=selected===null;skip.disabled=false;el('prompt').textContent='Не удалось отправить. Попробуй ещё раз.'}}
  }
  items.forEach((text,i)=>{const b=add((i+1)+'. '+text,()=>{
    if(busy)return;selected=i;next.disabled=false;buttons.forEach((item,j)=>item.setAttribute('aria-pressed',String(i===j)))
   });b.className='criterion';b.setAttribute('aria-pressed','false');buttons.push(b)});
  const skip=add('Пропустить',()=>submit(4));
  const next=add('Далее',()=>submit(selected));next.id='next';next.disabled=true;
 }catch(e){if(version===revision)el('prompt').textContent=d.prompt||''}
}
function render(){
 let d;try{d=JSON.parse(W.chatData)}catch(e){return}if(!d)return;
 const version=++revision;el('choices').textContent='';
 el('label').textContent=d.label;el('title').textContent=d.title;el('prompt').textContent=d.prompt||'';
 el('meter').style.width=(100*(d.current||0)/(d.total||1))+'%';
 const t=el('result');t.textContent='';t.style.display=d.rows?'table':'none';
 if(d.rows)for(const values of [['Навык','Оценка'],...d.rows]){
   const row=document.createElement('tr');for(const value of values){const cell=document.createElement('td');cell.textContent=value;row.appendChild(cell)}t.appendChild(row)
 }
 if(d.step&&W.viewer&&typeof W.request==='function')criteria(d,version);
}
W.onEvent('chatDataChanged',render);render();
</script>"""


def enabled_for(employee_id: int) -> bool:
    return str(employee_id) in {part.strip() for part in settings.GRADE_WIDGET_REVIEWER_IDS.split(",")}


def widget_state(label, title, prompt="", *, current=0, total=1, rows=None, **metadata):
    state = dict(label=label, title=title, prompt=prompt, current=current, total=total)
    if rows is not None:
        state["rows"] = rows
    state.update(metadata)
    packed = json.dumps(state, ensure_ascii=False, separators=(",", ":"))
    return packed if len(packed.encode("utf-8")) <= 1024 else None


def skill_content(db, progress, step, employee):
    prompt = progress.feedback_question_text or ""
    collection = db.query(GradeReviewCollection).filter_by(
        feedback_run_id=progress.feedback_run_id, scenario_key=progress.scenario_key,
    ).one_or_none()
    if collection:
        for skill in json.loads(collection.snapshot_json)["scores"]:
            if step.step_key == f"skill_{skill['skillId']}" and skill.get("rubric"):
                levels = skill["rubric"]["levels"]
                return "\n\n".join(f"{level}. {levels[level]}" for level in sorted(levels)), employee.full_name
    return prompt, None


def skill_screen(step, prompt, current, total, markup, page=0, *, subject=None):
    label = f"{(subject or 'Оценка навыков')[:80]} · {current}/{total}"
    title = step.step_title[:100]
    interactive = subject is not None and (step.button_options or "").splitlines()[:4] == ["1", "2", "3", "4"]
    meta = {"step": step.id, "page": 0, "pages": 1} if interactive else {}
    state = widget_state(label, title, prompt, current=current, total=total, **meta)
    if state:
        return (state, markup) if page == 0 else None

    def pack(text, suffix, page_index=999999, page_count=999999):
        extra = {"step": step.id, "page": page_index, "pages": page_count} if interactive else {}
        return widget_state(f"{label} · {suffix}", title, text, current=current, total=total, **extra)

    pages = []
    remaining = prompt
    while remaining:
        low, high = 1, min(1024, len(remaining))
        while low < high:
            mid = (low + high + 1) // 2
            if pack(remaining[:mid], "999999/999999"):
                low = mid
            else:
                high = mid - 1
        end = low
        if end < len(remaining):
            boundary = remaining.rfind("\n", end // 2, end)
            if boundary < 0:
                boundary = remaining.rfind(" ", end // 2, end)
            if boundary > end // 2:
                end = boundary + 1
        pages.append(remaining[:end])
        remaining = remaining[end:]
    if not 0 <= page < len(pages):
        return None
    buttons = []
    if page:
        buttons.append(InlineKeyboardButton(text="← Критерии", callback_data=f"scenario:{step.id}:{-page}"))
    if page + 1 < len(pages):
        buttons.append(InlineKeyboardButton(text="Критерии →", callback_data=f"scenario:{step.id}:{-page - 2}"))
    return pack(pages[page], f"{page + 1}/{len(pages)}", page, len(pages)), InlineKeyboardMarkup(inline_keyboard=[buttons, *markup.inline_keyboard])
