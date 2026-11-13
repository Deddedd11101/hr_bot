import { useEffect, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { DatePicker } from "@/components/ui/date-picker";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Choice, Feedback, useAction, useUnsaved } from "@/grades/components";
import { errorMessage, request } from "@/grades/data";
import type { CatalogItem } from "@/grades/types";
import { cycleDates } from "./grade-cycle-dates";
import { ReviewerPicker, type Reviewer } from "./grade-collections";
import { GradeDevelopmentRoadmap } from "./grade-development-roadmap";

const kinds = ["ipr6", "ipr12", "review12"] as const;
type Kind = typeof kinds[number];
type StageAction = {key: string; type: "scenario" | "feedback" | "review" | "review360" | "reminder"; scenario_key: string | null; recipient_ids?: number[]; specialization_id?: number; due_at?: string; status?: string; last_error?: string | null};
type Milestone = {id: number; kind: Kind; due_at: string; status: string; last_error: string | null; actions: StageAction[]};
type Delivery = {id: number; milestone_id: number; role: string; status: string; last_error: string | null};
type Template = {key: string; title: string; selectable?: boolean; pulse?: boolean};
type Kickoff = {suggested_at?: string | null; due_at?: string; specialization_id?: number; scenario_key?: string; collection_id?: number; finalized?: boolean; last_error?: string | null; followup_at?: string; followup_processed?: boolean};
type Development = {kickoff?: Kickoff; revision: number; assessment_id: number | null; anchor_date: string | null; enabled: boolean; milestones: Milestone[]; scenarios: Template[]; surveys: Template[]; needs_anchor: boolean; history: Milestone[]; deliveries: Delivery[]; ipr6_scenario_key: string | null; ipr12_scenario_key: string | null; review12_scenario_key: string | null};
const titles: Record<Kind, string> = {ipr6: "Проверка ИПР · 6 месяцев", ipr12: "Проверка ИПР · 12 месяцев", review12: "Новая оценка · 12 месяцев"};
const statuses: Record<string, string> = {planned: "Запланировано", blocked: "Ожидает запуска", starting: "Проверить доставку", started: "Запущено", failed: "Ошибка", cancelled: "Отменено"};
const types = [{value: "scenario", label: "Сценарий сотруднику"}, {value: "feedback", label: "Сбор обратной связи"}, {value: "review", label: "Сбор оценок навыков"}, {value: "review360", label: "Оценка 360 · сотрудник и руководитель"}];
function labelDate(v: string) {return new Intl.DateTimeFormat("ru-RU", {day: "numeric", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "Europe/Moscow"}).format(new Date(`${v.slice(0, 19)}+03:00`));}

const recurring = ["Пульс-опрос", "Сбор обратной связи от команды"];

function roadmap(data: Development) {
  const kickoff = data.kickoff;
  const rows = (kind: Kind) => {
    const m = data.milestones.find(item => item.kind === kind);
    if (!m) return [];
    const status = (value: string) => !data.enabled && ["planned", "blocked"].includes(value) ? "Пауза" : statuses[value] || value;
    const name = (key: string | null) => [...data.scenarios, ...data.surveys].find(item => item.key === key)?.title || key || "Сценарий";
    const planned = m.actions?.filter(a => a.type !== "reminder") ?? [];
    if (!planned.length) {
      return [{key: kind, title: data[`${kind}_scenario_key`] ? name(data[`${kind}_scenario_key`]) : "Напоминание HR и руководителю",
        date: labelDate(m.due_at), status: status(m.status), error: m.last_error}];
    }
    return planned.map(a => ({key: a.key, title: a.type === "review360" ? "Оценка 360 · сотрудник и руководитель" : a.type === "review" ? "Сбор оценок навыков" : name(a.scenario_key),
      date: labelDate(a.due_at || m.due_at), status: status(a.status || m.status), error: a.last_error || m.last_error}));
  };
  return [
    {title: "Старт развития", timing: "Один раз после адаптации", expected: [
      "Оценка 360", "Организация ИПР", "Знакомство с процессом развития", "Знакомство с планом ИПР",
    ], scheduled: kickoff?.due_at ? [
      {key: "kickoff", title: "Оценка 360 · сотрудник и руководитель", date: labelDate(kickoff.due_at),
        status: kickoff.last_error ? "Ошибка" : kickoff.finalized ? "Итог зафиксирован" : kickoff.collection_id ? "Сбор идёт" : "Запланировано", error: kickoff.last_error},
      {key: "organization", title: "Организация ИПР", date: kickoff.followup_at ? labelDate(kickoff.followup_at) : undefined,
        status: kickoff.followup_processed ? "Запрос обработан" : kickoff.followup_at ? "Запланировано" : "После фиксации 360"},
    ] : []},
    {title: "Промежуточная встреча", timing: "Через 6 месяцев", expected: [
      ...recurring, "Рассмотрение результатов ИПР", "Изменение ИПР",
    ], scheduled: rows("ipr6")},
    {title: "Итоговая встреча", timing: "Через 12 месяцев", expected: [
      ...recurring, "Рассмотрение результатов ИПР · итог", "Изменение ИПР", "Оценка 360",
    ], scheduled: [...rows("ipr12"), ...rows("review12")]},
  ];
}
export function GradeDevelopment({employeeId, visible = true}: {employeeId: number; visible?: boolean}) {
  const endpoint = `/api/employees/${employeeId}/grade/development`;
  const [data, setData] = useState<Development | null>(null), [form, setForm] = useState(false), [anchor, setAnchor] = useState(""), [enabled, setEnabled] = useState(false);
  const [actions, setActions] = useState<Record<Kind, StageAction[]>>({ipr6: [], ipr12: [], review12: []}), [dates, setDates] = useState<Record<string, string>>({});
  const [people, setPeople] = useState<Reviewer[]>([]), [specs, setSpecs] = useState<CatalogItem[]>([]), [error, setError] = useState("");
  const action = useAction(); useUnsaved(form);
  const [kickoffForm, setKickoffForm] = useState<Kickoff | null>(null);
  async function load(signal?: AbortSignal) {try {const [c, f, g] = await Promise.all([request<Development>(endpoint, "GET", undefined, signal), request<{recipients: Reviewer[]}>(`/api/employees/${employeeId}/feedback-surveys`, "GET", undefined, signal), request<{specializations: CatalogItem[]}>(`/api/employees/${employeeId}/grade`, "GET", undefined, signal)]); if (!signal?.aborted) {setData(c); setPeople(f.recipients); setSpecs(g.specializations); setError("");}} catch(e) {if (!signal?.aborted) setError(errorMessage(e));}}
  useEffect(() => {if (!visible) return; const c = new AbortController(); void load(c.signal); const timer = window.setInterval(() => {if (!document.hidden && !form) void load(c.signal);}, 60000); return () => {c.abort(); window.clearInterval(timer);};}, [endpoint, form, visible]);
  function edit() {if (!data) return; setAnchor(data.anchor_date || ""); setEnabled(data.enabled); setDates({}); setActions(Object.fromEntries(kinds.map(k => {const saved = data.milestones.find(m => m.kind === k)?.actions || [], legacy = data[`${k}_scenario_key`]; return [k, saved.length ? saved.filter(a => a.type !== "reminder") : legacy ? [{key: crypto.randomUUID(), type: "scenario", scenario_key: legacy}] : []];})) as Record<Kind, StageAction[]>); setForm(true);}
  function change(k: Kind, index: number, patch: Partial<StageAction>) {setActions(old => ({...old, [k]: old[k].map((a, i) => i === index ? {...a, ...patch} : a)}));}
  function calculateDates() {
    void action.run(async () => {
      const proposed = await request<Record<Kind, string>>(`${endpoint}/calendar-dates?anchor_date=${encodeURIComponent(anchor)}`, "GET");
      const next: Record<string, string> = {};
      for (const k of kinds) {
        const milestone = data?.milestones.find(m => m.kind === k);
        if ((!milestone || ["planned", "blocked"].includes(milestone.status)) &&
            new Date(`${proposed[k]}+03:00`).getTime() > Date.now()) next[k] = proposed[k];
      }
      if (!Object.keys(next).length) throw new Error("Нет будущих этапов для пересчёта. Укажите даты вручную.");
      setDates(previous => ({...previous, ...next}));
    }, "Будущие даты рассчитаны. Их можно изменить перед сохранением.");
  }
  const defaults = cycleDates(anchor);
  const upcoming = data?.milestones.filter(m => ["planned", "blocked"].includes(m.status)).flatMap(m =>
    m.actions?.length ? m.actions.filter(a => ["planned", "blocked"].includes(a.status || "planned")).map(a => ({due_at: a.due_at || m.due_at})) : [m]
  ).sort((a, b) => a.due_at.localeCompare(b.due_at))[0];
  const invalid = !data?.assessment_id || !anchor || kinds.some(k => actions[k].some(a => a.type === "review360" ? !a.specialization_id : a.type === "review" ? !a.specialization_id || !a.recipient_ids?.length : !a.scenario_key || (a.type === "feedback" && !a.recipient_ids?.length)));
  return <section className="space-y-4 border-t pt-5" aria-label="Цикл развития"><header className="flex flex-wrap items-center justify-between gap-3"><h3 className="font-medium">Цикл развития</h3>{data && !form && <Button variant="outline" size="sm" onClick={edit}>{data.revision ? "Настроить" : "Запланировать цикл"}</Button>}</header><Feedback error={error || action.error} message={action.message} />
    {!data && !error && <p role="status">Загрузка цикла…</p>}
    {data && <GradeDevelopmentRoadmap phases={roadmap(data)} />}
    {data && !form && !kickoffForm && !data.kickoff?.collection_id && <Button variant="outline" size="sm" onClick={() => setKickoffForm({
      ...data.kickoff, due_at: data.kickoff?.due_at ?? data.kickoff?.suggested_at ?? "",
    })}>{data.kickoff?.due_at ? "Изменить разовый старт" : "Запланировать старт после адаптации"}</Button>}
    {data && kickoffForm && <form className="max-w-lg space-y-3 border-t pt-4" onSubmit={event => {
      event.preventDefault();
      void action.run(async () => {
        await request(`${endpoint}/kickoff`, "PUT", {
          due_at: kickoffForm.due_at, specialization_id: kickoffForm.specialization_id, scenario_key: kickoffForm.scenario_key,
        });
        setKickoffForm(null);
        await load();
      }, "Разовый старт запланирован");
    }}>
      <label className="block text-sm">Дата 360 · МСК<Input type="datetime-local" value={kickoffForm.due_at?.slice(0, 16) || ""} onChange={e => setKickoffForm({...kickoffForm, due_at: e.target.value})} required /></label>
      <Choice label="Шаблон оценки" value={String(kickoffForm.specialization_id || "none")} options={[{value: "none", label: "Выберите"}, ...specs.filter(s => s.active).map(s => ({value: String(s.id), label: s.name}))]} onChange={v => setKickoffForm({...kickoffForm, specialization_id: Number(v) || undefined})} />
      <Choice label="Сценарий организации ИПР" value={kickoffForm.scenario_key || "none"} options={[{value: "none", label: "Выберите"}, ...data.scenarios.filter(s => s.selectable !== false && !s.pulse).map(s => ({value: s.key, label: s.title}))]} onChange={v => setKickoffForm({...kickoffForm, scenario_key: v === "none" ? undefined : v})} />
      <div className="flex gap-2"><Button type="submit" disabled={action.busy || !kickoffForm.due_at || !kickoffForm.specialization_id || !kickoffForm.scenario_key}>Запланировать</Button><Button type="button" variant="ghost" onClick={() => setKickoffForm(null)}>Отмена</Button></div>
    </form>}
    {data && !form && <><p className="text-sm text-muted-foreground">{data.revision ? data.enabled ? "Напоминания и автозапуск включены" : "Цикл на паузе" : "Цикл не настроен"}</p>{data.enabled && upcoming && <p className="text-sm">Следующий этап: {labelDate(upcoming.due_at)} МСК · осталось {Math.max(0, Math.ceil((new Date(`${upcoming.due_at}+03:00`).getTime() - Date.now()) / 86400000))} дн.</p>}{!!data.history.length && <details><summary className="cursor-pointer text-sm text-muted-foreground">Прошлые циклы</summary>{data.history.map(m => <p key={m.id} className="py-2 text-sm">{titles[m.kind]} · {labelDate(m.due_at)} · {statuses[m.status] || m.status}</p>)}</details>}</>}
    {form && data && <form className="space-y-5" onSubmit={e => {e.preventDefault(); void action.run(async () => {setData(await request<Development>(`${endpoint}/actions`, "PUT", {assessment_id: data.assessment_id, expected_revision: data.revision, anchor_date: anchor, enabled, due_dates: dates, actions: Object.fromEntries(kinds.map(k => [k, actions[k].map(a => ({key: a.key, type: a.type, scenario_key: a.scenario_key, ...(a.due_at ? {due_at: a.due_at} : {}), ...((a.type === "feedback" || a.type === "review") ? {recipient_ids: a.recipient_ids} : {}), ...((a.type === "review" || a.type === "review360") ? {specialization_id: a.specialization_id} : {})}))]))})); setForm(false);}, "План цикла сохранён");}}>
      <label className="block max-w-sm space-y-1 text-sm">Дата исходной оценки<DatePicker value={anchor} onValueChange={v => {setAnchor(v || ""); setDates({});}} disabled={action.busy} /></label>{!data.assessment_id && <p className="text-sm text-muted-foreground">Сначала сохраните исходную оценку навыков.</p>}
      <Button type="button" size="sm" variant="outline" disabled={!anchor || action.busy} onClick={calculateDates}>Рассчитать по производственному календарю</Button>
      {kinds.some(k => actions[k].some(a => (a.type === "feedback" ? data.surveys : data.scenarios).some(s => s.key === a.scenario_key && s.selectable === false))) && <p className="text-sm text-destructive">Для «Пульса» выберите действие «Сценарий сотруднику» и шаблон с получателем «Сам сотрудник».</p>}
      {kinds.map(k => {const m = data.milestones.find(m => m.kind === k), editable = !m || ["planned", "blocked"].includes(m.status); return <fieldset key={k} className="space-y-3 border-t pt-4"><legend className="font-medium">{titles[k]}</legend><div className="max-w-sm"><Input aria-label={`Дата: ${titles[k]} · МСК`} type="datetime-local" value={dates[k] ?? (anchor === data.anchor_date && m ? m.due_at.slice(0, 16) : defaults[k] || "")} onChange={e => setDates({...dates, [k]: e.target.value})} disabled={!editable || action.busy} /></div>{actions[k].map((a, index) => {const locked = !editable || action.busy || !!a.status && !["planned", "blocked"].includes(a.status); return <div key={a.key} className="space-y-3 border-l-2 pl-4"><div className="flex items-end gap-2"><div className="min-w-0 flex-1"><Choice label="Действие" value={a.type} options={types.filter(t => (t.value !== "review360" || k === "review12") && (t.value !== "review" || k !== "ipr6" || a.type === "review"))} onChange={v => change(k, index, {type: v as StageAction["type"], scenario_key: null, recipient_ids: [], specialization_id: undefined})} disabled={locked} /></div><Button type="button" variant="ghost" size="icon" title="Удалить действие" aria-label="Удалить действие" disabled={locked} onClick={() => setActions({...actions, [k]: actions[k].filter((_, i) => i !== index)})}><Trash2 className="size-4" /></Button></div><div className="max-w-sm space-y-1"><label htmlFor={`action-date-${a.key}`} className="text-sm">Дата действия · МСК</label><Input id={`action-date-${a.key}`} type="datetime-local" value={a.due_at?.slice(0, 16) || ""} onChange={e => change(k, index, {due_at: e.target.value || undefined})} disabled={locked} /><p className="text-xs text-muted-foreground">Без отдельной даты используется дата этапа.</p></div>{(a.type === "review" || a.type === "review360") ? <Choice label="Шаблон навыков" value={a.specialization_id ? String(a.specialization_id) : "none"} options={[{value: "none", label: "Выберите шаблон"}, ...specs.filter(s => s.active).map(s => ({value: String(s.id), label: s.name}))]} onChange={v => change(k, index, {specialization_id: v === "none" ? undefined : Number(v)})} disabled={locked} /> : <Choice label={a.type === "feedback" ? "Опрос" : "Сценарий"} value={a.scenario_key || "none"} options={[{value: "none", label: "Выберите"}, ...(a.type === "feedback" ? data.surveys : data.scenarios).filter(s => s.selectable !== false || s.key === a.scenario_key).map(s => ({value: s.key, label: s.title}))]} onChange={v => change(k, index, {scenario_key: v === "none" ? null : v})} disabled={locked} />}{a.type === "scenario" && data.scenarios.some(s => s.key === a.scenario_key && s.pulse) && <p className="text-sm text-muted-foreground">Получатель: сотрудник из этой карточки</p>}{(a.type === "feedback" || a.type === "review") && !data.surveys.some(s => s.key === a.scenario_key && s.selectable === false) && <ReviewerPicker items={people} value={a.recipient_ids || []} onChange={ids => change(k, index, {recipient_ids: ids})} disabled={locked} />}</div>;})}{editable && <Button type="button" size="sm" variant="outline" disabled={action.busy || actions[k].length >= 10} onClick={() => setActions({...actions, [k]: [...actions[k], {key: crypto.randomUUID(), type: "scenario", scenario_key: null}]})}><Plus className="size-4" />Добавить действие</Button>}{!actions[k].length && <p className="text-xs text-muted-foreground">Только напоминание HR и руководителю</p>}</fieldset>;})}
      <label className="flex items-center gap-3 text-sm"><Switch checked={enabled} onCheckedChange={setEnabled} disabled={action.busy} />Напоминания и автозапуск</label><div className="flex gap-2"><Button type="submit" disabled={invalid || action.busy}>Сохранить план</Button><Button type="button" variant="ghost" disabled={action.busy} onClick={() => {if (window.confirm("Закрыть без сохранения?")) setForm(false);}}>Отмена</Button></div>
    </form>}
    {data && !form && !!data.deliveries?.length && <details><summary className="cursor-pointer text-sm text-muted-foreground">Доставка напоминаний</summary>{data.deliveries.map(d => <p key={d.id} className={`py-2 text-xs ${d.status === "failed" ? "text-destructive" : "text-muted-foreground"}`}>{titles[data.milestones.find(m => m.id === d.milestone_id)?.kind || "ipr6"]} · {d.role === "hr" ? "HR" : "Руководитель"}: {({sent: "Отправлено", pending: "В очереди", starting: "Проверить доставку", failed: "Ошибка", cancelled: "Отменено"} as Record<string, string>)[d.status] || d.status}{d.last_error ? ` · ${d.last_error}` : ""}</p>)}</details>}
  </section>;
}
