import { useEffect, useState } from "react";
import { CalendarClock, Settings2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { DatePicker } from "@/components/ui/date-picker";
import { Input } from "@/components/ui/input";
import { cycleDates } from "./grade-cycle-dates";
import { Switch } from "@/components/ui/switch";
import { Choice, Feedback, useAction, useUnsaved } from "@/grades/components";
import { errorMessage, request } from "@/grades/data";

type Milestone = {id: number; kind: string; due_at: string; status: string; last_error: string | null};
type Development = {
  revision: number; assessment_id: number | null; anchor_date: string | null; enabled: boolean;
  ipr6_scenario_key: string | null; ipr12_scenario_key: string | null; review12_scenario_key: string | null;
  milestones: Milestone[]; scenarios: {key: string; title: string}[]; needs_anchor: boolean;
  history: Milestone[];
  deliveries: {id: number; milestone_id: number; role: string; status: string; last_error: string | null}[];
};
const titles: Record<string, string> = {ipr6: "Проверка ИПР · 6 месяцев", ipr12: "Проверка ИПР · 12 месяцев", review12: "Новая оценка · 12 месяцев"};
const statuses: Record<string, string> = {pending: "Ожидает отправки", planned: "Запланировано", blocked: "Ожидает свободного диалога", starting: "Требует проверки доставки", started: "Запущено", sent: "Отправлено", failed: "Ошибка", cancelled: "Отменено", paused: "Пауза", completed: "Завершено"};
const selectionKeys = ["ipr6_scenario_key", "ipr12_scenario_key", "review12_scenario_key"] as const;

function dueDate(value: string) {
  return new Intl.DateTimeFormat("ru-RU", {day: "numeric", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "Europe/Moscow"}).format(new Date(value.endsWith("Z") || /[+-]\d\d:\d\d$/.test(value) ? value : `${value}+03:00`));
}
function remaining(value: string, now: number) {
  const ms = new Date(value.endsWith("Z") || /[+-]\d\d:\d\d$/.test(value) ? value : `${value}+03:00`).getTime() - now;
  if (ms <= 0) return "Время запуска наступило";
  const days = Math.ceil(ms / 86400000);
  return `До запуска: ${days} дн.`;
}

export function GradeDevelopment({employeeId}: {employeeId: number}) {
  const endpoint = `/api/employees/${employeeId}/grade/development`;
  const [data, setData] = useState<Development | null>(null);
  const [form, setForm] = useState<Development | null>(null);
  const [error, setError] = useState("");
  const [now, setNow] = useState(Date.now());
  const [dueDates, setDueDates] = useState<Record<string, string>>({});
  const action = useAction();
  const dirty = !!form && !!data && (Object.keys(dueDates).length > 0 || form.anchor_date !== data.anchor_date || form.enabled !== data.enabled || selectionKeys.some(key => form[key] !== data[key]));
  useUnsaved(dirty);
  async function load(signal?: AbortSignal) {
    try { const value = await request<Development>(endpoint, "GET", undefined, signal); if (!signal?.aborted) {setData(value); setError("");} }
    catch (e) {if (!signal?.aborted) setError(errorMessage(e));}
  }
  useEffect(() => {
    const controller = new AbortController();
    setData(null); setForm(null); setDueDates({}); void load(controller.signal);
    const timer = window.setInterval(() => {setNow(Date.now()); if (!document.hidden) void load(controller.signal);}, 60000);
    return () => {controller.abort(); window.clearInterval(timer);};
  }, [endpoint]);
  const upcoming = data?.milestones.filter(item => ["planned", "blocked"].includes(item.status)).sort((a, b) => a.due_at.localeCompare(b.due_at))[0];
  const options = [{value: "none", label: "Не выбран"}, ...(data?.scenarios || []).map(item => ({value: item.key, label: item.title}))];
  const calculated = cycleDates(form?.anchor_date || "");
  const preview = Object.keys(titles).map(kind => {
    const existing = form?.milestones.find(item => item.kind === kind);
    const editable = !existing || ["planned", "blocked"].includes(existing.status);
    const value = dueDates[kind] ?? (existing && (form?.anchor_date === data?.anchor_date || !editable) ? existing.due_at.slice(0, 16) : calculated[kind]);
    return {kind, editable, value};
  });
  const saveReasons: string[] = [];
  if (form) {
    if (!form.assessment_id) saveReasons.push("Сначала сохраните первую завершённую оценку навыков.");
    if (!Object.keys(calculated).length) saveReasons.push("Укажите дату исходной оценки.");
    const selected = selectionKeys.filter(key => !!form[key]).length;
    if (form.enabled && selected < 3) saveReasons.push(`Для включения выберите все 3 сценария (выбрано ${selected} из 3).`);
    for (const item of preview) {
      const time = item.value ? new Date(`${item.value}+03:00`).getTime() : NaN;
      if (item.kind in dueDates && !Number.isFinite(time)) saveReasons.push(`${titles[item.kind]}: укажите дату и время.`);
      else if (item.editable && (form.enabled || item.kind in dueDates) && time <= now) saveReasons.push(`${titles[item.kind]}: выберите будущую дату в «Даты запусков вручную».`);
    }
    const ipr = preview.find(item => item.kind === "ipr12")?.value;
    const review = preview.find(item => item.kind === "review12")?.value;
    if (ipr && review && new Date(`${review}+03:00`).getTime() < new Date(`${ipr}+03:00`).getTime() + 600000) saveReasons.push("Новая оценка должна идти после годовой проверки ИПР с интервалом не менее 10 минут.");
  }
  return <section className="space-y-4 border-t pt-5" aria-label="Цикл развития">
    <header className="flex flex-wrap items-center justify-between gap-3"><h3 className="inline-flex items-center gap-2 font-medium"><CalendarClock className="size-4" />Цикл развития</h3>{data && !form && <Button variant="outline" size="sm" onClick={() => {setDueDates({}); setForm({...data});}}><Settings2 className="size-4" />{data.revision ? "Настроить" : "Настроить цикл"}</Button>}</header>
    <Feedback error={error || action.error} message={action.message} />
    {error && <Button variant="outline" size="sm" onClick={() => void load()}>Повторить</Button>}
    {!data && !error && <p role="status" className="text-sm text-muted-foreground">Загрузка цикла…</p>}
    {data && !form && <>
      {!data.revision ? <p className="text-sm text-muted-foreground">Цикл ещё не настроен. Проверки ИПР через 6 и 12 месяцев, повторная оценка через год.</p> : <div className="space-y-3">
        <Badge variant="outline">{data.enabled ? "Автозапуск включён" : "Цикл на паузе"}</Badge>
        {data.enabled && upcoming && <div><p className="font-medium">{titles[upcoming.kind] || upcoming.kind}</p><p className="text-sm">{dueDate(upcoming.due_at)} МСК</p><p className="text-sm text-muted-foreground">{remaining(upcoming.due_at, now)}</p></div>}
        <ul className="divide-y">{data.milestones.map(item => <li key={item.id} className="flex flex-wrap items-start justify-between gap-2 py-3 text-sm"><div className="min-w-0"><p>{titles[item.kind] || item.kind}</p><p className="text-xs text-muted-foreground">{dueDate(item.due_at)} МСК</p><p className="text-xs text-muted-foreground break-words">{data.scenarios.find(s => s.key === data[`${item.kind}_scenario_key` as typeof selectionKeys[number]])?.title || "Сценарий не выбран"}</p>{item.last_error && <p className="mt-1 text-xs text-destructive break-words">{item.last_error}</p>}{data.deliveries?.filter(delivery => delivery.milestone_id === item.id).map(delivery => <p key={delivery.id} className={`mt-1 text-xs ${delivery.status === "failed" ? "text-destructive" : "text-muted-foreground"}`}>{delivery.role === "hr" ? "Напоминание HR" : "Напоминание руководителю"}: {statuses[delivery.status] || delivery.status}{delivery.last_error ? ` · ${delivery.last_error}` : ""}</p>)}</div><Badge variant="outline">{!data.enabled && ["planned", "blocked"].includes(item.status) ? "Пауза" : statuses[item.status] || item.status}</Badge></li>)}</ul>
        {!!data.history?.length && <details><summary className="cursor-pointer text-sm text-muted-foreground">Прошлые циклы · {data.history.length} этапов</summary><ul className="mt-2 divide-y">{data.history.map(item => <li key={item.id} className="py-2 text-xs"><span>{titles[item.kind]} · {dueDate(item.due_at)} МСК</span><span className="ml-2 text-muted-foreground">{statuses[item.status] || item.status}</span></li>)}</ul></details>}
      </div>}
    </>}
    {form && <form className="max-w-xl space-y-4" onSubmit={event => {event.preventDefault(); if (action.busy || saveReasons.length) return; void action.run(async () => {
      const value = await request<Development>(endpoint, "PUT", {assessment_id: form.assessment_id, expected_revision: form.revision, anchor_date: form.anchor_date, enabled: form.enabled, ...Object.fromEntries(selectionKeys.map(key => [key, form[key]])), ...(Object.keys(dueDates).length ? {due_dates: dueDates} : {})});
      setData(value); setForm(null); setDueDates({});
    }, "Цикл сохранён");}}>
      {!data?.assessment_id && <p className="text-sm text-muted-foreground">Сначала сохраните первую оценку навыков.</p>}
      <label className="block space-y-1 text-sm"><span>Дата оценки</span><DatePicker value={form.anchor_date || ""} onValueChange={anchor_date => {setDueDates({}); setForm({...form, anchor_date: anchor_date || null});}} disabled={action.busy} /></label>
      {data?.needs_anchor && <p className="text-xs text-muted-foreground">У импортированной оценки нет даты. Укажите дату оценивания, не загрузки файла.</p>}
      {selectionKeys.map((key, i) => <Choice key={key} label={["Сценарий проверки ИПР через 6 месяцев", "Сценарий проверки ИПР через 12 месяцев", "Сценарий новой оценки через 12 месяцев"][i]} value={form[key] || "none"} options={options} onChange={value => setForm({...form, [key]: value === "none" ? null : value})} disabled={action.busy} />)}
      <div className="space-y-2 text-sm" aria-label="Предпросмотр дат цикла">
        <p className="font-medium">Предпросмотр запусков · МСК</p>
        <p className="text-xs text-muted-foreground">От даты оценки +6 и +12 календарных месяцев; если дня нет, берётся последний день месяца. ИПР в 10:00, новая оценка в 10:10. Без переноса по производственному календарю. Сохранённые и ручные даты имеют приоритет.</p>
        <ul className="space-y-2">{preview.map(item => <li key={item.kind}><p>{titles[item.kind]}</p><p className="text-muted-foreground">{item.value ? `${dueDate(item.value)} МСК` : "Укажите дату оценки"}{item.kind in dueDates ? " · вручную" : ""}</p></li>)}</ul>
      </div>
      <details><summary className="cursor-pointer text-sm text-muted-foreground">Даты запусков вручную</summary><div className="mt-3 space-y-3"><p className="text-xs text-muted-foreground">Можно задать будущие даты до первого сохранения, в том числе для старой оценки. Запущенные этапы не переносятся.</p>{preview.filter(item => item.editable).map(item => <label key={item.kind} className="block space-y-1 text-sm"><span>{titles[item.kind]} · МСК</span><Input type="datetime-local" value={item.value || ""} onChange={event => setDueDates({...dueDates, [item.kind]: event.target.value})} disabled={action.busy} /></label>)}{Object.keys(dueDates).length > 0 && <Button type="button" variant="ghost" disabled={action.busy} onClick={() => setDueDates({})}>Сбросить ручные даты</Button>}</div></details>
      <label className="flex items-center gap-3 text-sm"><Switch checked={form.enabled} onCheckedChange={enabled => setForm({...form, enabled})} disabled={action.busy} />Напоминания и автозапуск</label>
      <p className="text-xs text-muted-foreground">Переключатель включает будущие напоминания HR/руководителю и автозапуски сценариев. Изменения применятся только после «Сохранить»; до этого расписание не меняется. В выключенном состоянии настройки сохраняются на паузе.</p>
      {data && form.revision !== data.revision && <p role="status" className="text-sm text-destructive">Настройки изменились на сервере. Ваш черновик сохранён в форме; отмените редактирование и откройте настройки заново перед сохранением.</p>}
      {!!saveReasons.length && <div id={`cycle-save-reasons-${employeeId}`} role="status" className="text-sm text-muted-foreground"><p>Чтобы сохранить:</p><ul className="list-disc pl-5">{saveReasons.map(reason => <li key={reason}>{reason}</li>)}</ul></div>}
      <div className="flex flex-wrap gap-2"><Button type="submit" aria-describedby={saveReasons.length ? `cycle-save-reasons-${employeeId}` : undefined} disabled={action.busy || saveReasons.length > 0}>Сохранить</Button><Button type="button" variant="ghost" disabled={action.busy} onClick={() => {if (!dirty || window.confirm("Закрыть без сохранения настроек цикла?")) setForm(null);}}>Отмена</Button></div>
    </form>}
  </section>;
}
