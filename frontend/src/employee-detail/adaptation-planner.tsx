import React from "react";
import { ArrowDown, ArrowUp, Plus, RefreshCw, Settings2, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { PageSection } from "@/components/ui/page-section";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

type Entry = { key: string; scenario_key: string; group: string; anchor: string; offset: number; unit: string; time: string };
type Row = { key: string; title: string; rule: Entry | null; rule_label?: string; proposed_at: string; requested_at: string; error: string; past: boolean; conflict_ids: number[]; previous_completed: boolean; item_id: number | null; status: string; manual_date: boolean; last_error: string | null };
type Plan = { fingerprint: string; rows: Row[]; group: string; timezone: string; calendar_versions: Record<string, number> };
type Template = { entries: Entry[]; revision: number; scenario_options: { value: string; label: string }[] };
const labels: Record<string, string> = { planned: "Запланирован", blocked: "Ожидает диалог", starting: "Запускается", in_progress: "В процессе", completed: "Завершён", interrupted: "Прерван", failed: "Ошибка запуска", cancelled: "Отменён", not_planned: "Не запланирован", previously_completed: "Завершён ранее" };
const editable = new Set(["planned", "blocked", "failed", "cancelled"]);
const selectClass = "h-9 min-w-0 rounded-md border border-input bg-background px-2 text-sm";

async function api<T>(url: string, method = "GET", body?: unknown): Promise<T> {
    const response = await fetch(url, { method, credentials: "same-origin", headers: body ? { "Content-Type": "application/json" } : undefined, body: body ? JSON.stringify(body) : undefined });
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Не удалось сохранить план");
    return data as T;
}

export function AdaptationPlanner({ employeeId }: { employeeId: number }) {
    const [plan, setPlan] = React.useState<Plan | null>(null);
    const [template, setTemplate] = React.useState<Template | null>(null);
    const [selected, setSelected] = React.useState<string[]>([]);
    const [dates, setDates] = React.useState<Record<string, string>>({});
    const [error, setError] = React.useState("");
    const [notice, setNotice] = React.useState("");
    const [busy, setBusy] = React.useState(false);
    const [open, setOpen] = React.useState(false);
    const [confirmed, setConfirmed] = React.useState(false);
    const url = `/api/employees/${employeeId}/adaptation-plan`;

    function accept(next: Plan) {
        setPlan(next);
        setDates(Object.fromEntries(next.rows.map(row => [row.key, row.requested_at || row.proposed_at])));
        setSelected(next.rows.filter(row => !row.item_id && !row.error && !row.past && !row.conflict_ids.length && !row.previous_completed).map(row => row.key));
        setConfirmed(false);
    }
    React.useEffect(() => {
        let active = true;
        api<Plan>(url).then(next => { if (active) accept(next); }).catch(cause => { if (active) setError(cause.message); });
        return () => { active = false; };
    }, [url]);

    async function perform(action: () => Promise<void>) {
        setBusy(true); setError(""); setNotice("");
        try { await action(); } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); }
        finally { setBusy(false); }
    }
    function editEntry(index: number, patch: Partial<Entry>) {
        if (template) setTemplate({ ...template, entries: template.entries.map((entry, i) => i === index ? { ...entry, ...patch } : entry) });
    }
    function move(index: number, delta: number) {
        if (!template) return;
        const entries = [...template.entries];
        [entries[index], entries[index + delta]] = [entries[index + delta], entries[index]];
        setTemplate({ ...template, entries });
    }
    const completed = plan?.rows.filter(row => row.status === "completed").length || 0;
    return <PageSection title="План адаптации" action={<Button variant="outline" disabled={busy} onClick={() => void perform(async () => { setTemplate(await api<Template>("/api/adaptation-plan/template")); setOpen(true); })}><Settings2 />Настроить план</Button>}>
        {error && <p role="alert" className="mb-3 text-sm text-destructive">{error}</p>}
        {notice && <p role="status" className="mb-3 text-sm text-muted-foreground">{notice}</p>}
        {!plan ? <p role="status" className="text-sm text-muted-foreground">{error ? "План недоступен" : "Загрузка плана..."}</p> : <>
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                <div className="min-w-48 flex-1"><div className="mb-2 flex justify-between text-sm"><span>{plan.group} · {plan.timezone}</span><span>{completed} / {plan.rows.length}</span></div><progress className="h-2 w-full accent-primary" value={completed} max={Math.max(1, plan.rows.length)} aria-label="Завершённые этапы адаптации" /></div>
                <Button variant="outline" disabled={busy} onClick={() => void perform(async () => accept(await api<Plan>(url)))}><RefreshCw />Рассчитать даты</Button>
            </div>
            <div className="overflow-x-auto"><table className="w-full min-w-[670px] text-left text-sm"><thead className="border-b text-muted-foreground"><tr><th className="w-9 py-2"><span className="sr-only">Выбор</span></th><th className="py-2 font-medium">Этап</th><th className="px-3 py-2 font-medium">Дата и время, МСК</th><th className="py-2 font-medium">Статус</th><th><span className="sr-only">Действия</span></th></tr></thead>
                <tbody>{plan.rows.map((row, index) => <tr key={row.key} className="border-b align-top last:border-0">
                    <td className="py-4"><input type="checkbox" aria-label={`Запланировать ${row.title}`} checked={selected.includes(row.key)} disabled={busy || !!row.item_id || !!row.error || !!row.conflict_ids.length} onChange={event => setSelected(prev => event.target.checked ? [...prev, row.key] : prev.filter(key => key !== row.key))} /></td>
                    <td className="py-3"><div className="font-medium"><span className="mr-2 text-muted-foreground">{index + 1}.</span>{row.title}</div>{row.rule && <div className="mt-1 text-xs text-muted-foreground">{row.rule_label}</div>}{(row.error || row.last_error || row.conflict_ids.length > 0) && <p className="mt-1 max-w-sm text-xs text-destructive">{row.error || row.last_error || "Уже есть отдельный запланированный запуск"}</p>}{row.manual_date && <p className="mt-1 text-xs text-muted-foreground">Дата изменена вручную</p>}</td>
                    <td className="px-3 py-3"><Input type="datetime-local" aria-label={`Дата: ${row.title}`} className="w-48" value={dates[row.key] || ""} disabled={busy || (!!row.item_id && !editable.has(row.status))} onChange={event => setDates(prev => ({ ...prev, [row.key]: event.target.value }))} />{row.proposed_at && row.requested_at && row.proposed_at !== row.requested_at && <p className="mt-1 text-xs text-muted-foreground">Расчёт: {row.proposed_at.replace("T", " ")}</p>}</td>
                    <td className="py-4"><Badge variant={row.status === "completed" ? "default" : "secondary"}>{labels[row.status] || row.status}</Badge></td>
                    <td className="py-3 pl-3">{row.item_id && editable.has(row.status) && <div className="flex flex-wrap gap-1"><Button variant="outline" disabled={busy} onClick={() => void perform(async () => { accept(await api<Plan>(`${url}/${row.item_id}`, "PATCH", { expected_at: row.requested_at, requested_at: dates[row.key] })); setNotice("Дата сохранена, запуск запланирован"); })}>{row.status === "failed" || row.status === "cancelled" ? "Запланировать" : "Сохранить"}</Button>{row.status !== "cancelled" && <Button variant="ghost" disabled={busy} onClick={() => void perform(async () => accept(await api<Plan>(`${url}/${row.item_id}`, "PATCH", { expected_at: row.requested_at, action: "cancel" })))}>Отменить</Button>}</div>}</td>
                </tr>)}</tbody></table></div>
            <div className="mt-4 flex flex-wrap items-center justify-between gap-3"><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)} />Проверены выбранные этапы и даты</label><Button disabled={busy || !confirmed || !selected.length} onClick={() => void perform(async () => { accept(await api<Plan>(url, "POST", { fingerprint: plan.fingerprint, rules_confirmed: true, rows: selected.map(key => ({ key, requested_at: dates[key] })) })); setNotice("Выбранные сценарии запланированы"); })}>Запланировать ({selected.length})</Button></div>
        </>}
        <Dialog open={open} onOpenChange={setOpen}><DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-5xl"><DialogHeader><DialogTitle>Порядок и правила адаптации</DialogTitle></DialogHeader>
            <p className="text-sm text-muted-foreground">Общий шаблон. Сохранённые даты сотрудников не меняются. Пульс отсчитывается от плановой даты тестирования; выходной переносится вперёд. Совпадающие запуски идут с интервалом 10 минут.</p>
            {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
            <div className="space-y-3">{template?.entries.map((entry, index) => <div key={entry.key} className="grid gap-2 border-b pb-3 sm:grid-cols-[70px_1fr_110px]">
                <div className="flex gap-1"><Button variant="ghost" size="icon" title="Выше" aria-label="Выше" disabled={index === 0 || busy} onClick={() => move(index, -1)}><ArrowUp /></Button><Button variant="ghost" size="icon" title="Ниже" aria-label="Ниже" disabled={index === template.entries.length - 1 || busy} onClick={() => move(index, 1)}><ArrowDown /></Button></div>
                <div className="grid min-w-0 gap-2"><select aria-label="Сценарий этапа" className={selectClass} value={entry.scenario_key} onChange={event => editEntry(index, { scenario_key: event.target.value })}>{template.scenario_options.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}</select><div className="grid grid-cols-2 gap-2 sm:grid-cols-4"><select aria-label="Отсчёт даты" className={selectClass} value={entry.anchor} onChange={event => editEntry(index, { anchor: event.target.value })}><option value="first">Первый день</option><option value="end">Конец адаптации</option>{template.entries.filter(other => other.key !== entry.key).map(other => <option key={other.key} value={other.key}>{template.scenario_options.find(option => option.value === other.scenario_key)?.label || other.key} ({other.key})</option>)}</select><Input aria-label="Смещение дней" type="number" min={-365} max={365} value={entry.offset} onChange={event => editEntry(index, { offset: Number(event.target.value) })} /><select className={selectClass} aria-label="Тип дней" value={entry.unit} onChange={event => editEntry(index, { unit: event.target.value })}><option value="workday">Рабочие дни</option><option value="calendar">Календарные дни</option></select><Input type="time" aria-label="Время запуска" value={entry.time} onChange={event => editEntry(index, { time: event.target.value })} /></div></div>
                <div className="flex flex-col gap-2"><select className={selectClass} aria-label="Группа" value={entry.group} onChange={event => editEntry(index, { group: event.target.value })}><option value="all">Все</option><option value="pm">PM</option><option value="other">Не PM</option></select><Button variant="ghost" title="Удалить этап из шаблона" aria-label="Удалить этап из шаблона" disabled={busy} onClick={() => setTemplate({ ...template, entries: template.entries.filter(other => other.key !== entry.key) })}><Trash2 /></Button></div>
            </div>)}</div>
            <div className="flex flex-wrap justify-between gap-2"><Button variant="outline" disabled={busy || !template || template.entries.length >= 40} onClick={() => { if (template) setTemplate({ ...template, entries: [...template.entries, { key: `stage_${Date.now()}`, scenario_key: template.scenario_options[0]?.value || "", group: "all", anchor: "first", offset: 0, unit: "workday", time: "10:00" }] }); }}><Plus />Добавить этап</Button><Button disabled={busy || !template} onClick={() => void perform(async () => { setTemplate(await api<Template>("/api/adaptation-plan/template", "POST", template)); accept(await api<Plan>(url)); setOpen(false); setNotice("Шаблон сохранён. Проверьте новые расчётные даты."); })}>Сохранить шаблон</Button></div>
        </DialogContent></Dialog>
    </PageSection>;
}
