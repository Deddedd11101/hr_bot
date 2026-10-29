import React from "react";
import { ArrowDown, ArrowUp, CalendarDays, Check, ChevronDown, ChevronRight, Clock3, MoreHorizontal, Play, Plus, RefreshCw, Settings2, Trash2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { PageSection } from "@/components/ui/page-section";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { DateTimePicker } from "@/components/ui/date-picker";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import "./adaptation-planner.css";

type Entry = { key: string; scenario_key: string; group: string; anchor: string; offset: number; unit: string; time: string };
type Row = { key: string; title: string; rule: Entry | null; rule_label?: string; proposed_at: string; requested_at: string; error: string; past: boolean; conflict_ids: number[]; previous_completed: boolean; item_id: number | null; status: string; manual_date: boolean; last_error: string | null };
type Plan = { fingerprint: string; rows: Row[]; group: string; timezone: string; calendar_versions: Record<string, number>; adaptation_midpoint: string; adaptation_end: string; adaptation_end_source: "saved" | "calculated" | "missing" };
type Template = { entries: Entry[]; revision: number; scenario_options: { value: string; label: string }[] };
const labels: Record<string, string> = { planned: "Запланирован", blocked: "Ожидает диалог", starting: "Запускается", in_progress: "В процессе", completed: "Завершён", interrupted: "Прерван", failed: "Ошибка запуска", cancelled: "Отменён", not_planned: "Не запланирован", previously_completed: "Есть прошлый запуск" };
const editable = new Set(["planned", "blocked", "failed", "cancelled"]);
const selectClass = "h-9 min-w-0 rounded-md border border-input bg-background px-2 text-sm";
const validDate = (value: string) => /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value);
function dateLabel(value: string) {
    if (!value) return "Назначить дату";
    const day = new Date(value);
    return Number.isNaN(day.getTime()) ? "Назначить дату" : new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }).format(day);
}

async function api<T>(url: string, method = "GET", body?: unknown): Promise<T> {
    const response = await fetch(url, { method, credentials: "same-origin", headers: body ? { "Content-Type": "application/json" } : undefined, body: body ? JSON.stringify(body) : undefined });
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Не удалось сохранить план");
    return data as T;
}

export function AdaptationPlanner({ employeeId, visible = true }: { employeeId: number; visible?: boolean }) {
    const [plan, setPlan] = React.useState<Plan | null>(null);
    const [template, setTemplate] = React.useState<Template | null>(null);
    const [replanning, setReplanning] = React.useState(false);
    const [dates, setDates] = React.useState<Record<string, string>>({});
    const [error, setError] = React.useState("");
    const [notice, setNotice] = React.useState("");
    const [busy, setBusy] = React.useState(false);
    const [open, setOpen] = React.useState(false);
    const [planning, setPlanning] = React.useState(false);
    const [historyOpen, setHistoryOpen] = React.useState(false);
    const [editing, setEditing] = React.useState<Row | null>(null);
    const [editDate, setEditDate] = React.useState("");
    const [cancelling, setCancelling] = React.useState<Row | null>(null);
    const url = `/api/employees/${employeeId}/adaptation-plan`;

    function accept(next: Plan) {
        setPlan(next);
        setDates(Object.fromEntries(next.rows.map(row => [row.key, row.requested_at || row.proposed_at])));
    }
    React.useEffect(() => {
        let active = true;
        api<Plan>(url).then(next => { if (active) accept(next); }).catch(cause => { if (active) setError(cause.message); });
        return () => { active = false; };
    }, [url]);

    React.useEffect(() => {
        if (!visible || busy || planning || open || editing || cancelling) return;
        let active = true;
        let pending = false;
        async function refresh() {
            if (document.hidden || pending) return;
            pending = true;
            try { const next = await api<Plan>(url); if (active) setPlan(next); }
            catch { /* Keep the last good plan on a transient refresh failure. */ }
            finally { pending = false; }
        }
        void refresh();
        const timer = window.setInterval(() => void refresh(), 15000);
        window.addEventListener("focus", refresh);
        document.addEventListener("visibilitychange", refresh);
        return () => { active = false; window.clearInterval(timer); window.removeEventListener("focus", refresh); document.removeEventListener("visibilitychange", refresh); };
    }, [url, visible, busy, planning, open, editing, cancelling]);

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
    const completedRows = plan?.rows.filter(row => row.status === "completed") || [];
    const currentRows = plan?.rows.filter(row => row.status !== "completed") || [];
    const availableRows = plan?.rows.filter(row => replanning ? row.item_id && ["planned", "blocked"].includes(row.status) : !row.item_id) || [];
    const selected = availableRows.map(row => row.key);
    const hasPlan = plan?.rows.some(row => row.item_id);
    const invalidSelection = availableRows.some(row => !!row.error || !!row.conflict_ids.length || !validDate(dates[row.key] || ""));
    function titleFor(row: Row) {
        const copies = plan?.rows.filter(other => other.title === row.title) || [];
        return copies.length > 1 ? `${row.title} · ${copies.findIndex(other => other.key === row.key) + 1}` : row.title;
    }
    function renderRow(row: Row) {
        const canEdit = !!row.item_id && editable.has(row.status);
        const active = row.status === "in_progress" || row.status === "starting";
        const issue = row.error || row.last_error || (row.conflict_ids.length ? "Уже есть отдельный запланированный запуск" : "");
        return <li key={row.key} className="adaptation-stage-row">
            <span className={`adaptation-stage-marker ${row.status === "completed" ? "is-completed" : active ? "is-active" : ""}`}>
                {row.status === "completed" ? <Check size={14} /> : active ? <Play size={12} /> : <span>{(plan?.rows.indexOf(row) || 0) + 1}</span>}
            </span>
            <div className="adaptation-stage-name"><span>{titleFor(row)}</span>{issue && <p className={row.status === "failed" ? "text-destructive" : "text-muted-foreground"}>{issue}</p>}{row.manual_date && <p className="text-muted-foreground">Дата изменена вручную</p>}</div>
            {canEdit ? <button type="button" className="adaptation-stage-date" disabled={busy} title="Изменить дату запуска" aria-label={`Дата запуска: ${titleFor(row)}`} onClick={() => { setError(""); setEditing(row); setEditDate(row.requested_at || row.proposed_at); }}><CalendarDays size={14} /><span>{row.item_id ? dateLabel(row.requested_at) : "Назначить дату"}</span></button> : <span className="adaptation-stage-date is-readonly">{row.item_id ? dateLabel(row.requested_at) : "—"}</span>}
            <Badge variant={active ? "default" : "secondary"} className="adaptation-stage-status">{labels[row.status] || row.status}</Badge>
            {canEdit ? <DropdownMenu><DropdownMenuTrigger render={<Button variant="ghost" size="icon" disabled={busy} title="Действия этапа" aria-label={`Действия: ${titleFor(row)}`} />}><MoreHorizontal /></DropdownMenuTrigger><DropdownMenuContent align="end">
                <DropdownMenuItem onClick={() => { setError(""); setEditing(row); setEditDate(row.requested_at || row.proposed_at); }}><CalendarDays />{row.item_id && ["failed", "cancelled"].includes(row.status) ? "Запланировать повторно" : "Изменить дату"}</DropdownMenuItem>
                {row.item_id && row.status !== "cancelled" && <DropdownMenuItem onClick={() => { setError(""); setCancelling(row); }}><X />Отменить запуск</DropdownMenuItem>}
            </DropdownMenuContent></DropdownMenu> : <span className="adaptation-empty-action" />}
        </li>;
    }
    function openPlanning(recalculate: boolean) {
        void perform(async () => {
            const next = await api<Plan>(url);
            accept(next);
            setReplanning(recalculate);
            if (recalculate) setDates(Object.fromEntries(next.rows.map(row => [row.key, row.proposed_at])));
            setPlanning(true);
        });
    }
    return <PageSection title="План адаптации" className="adaptation-planner-section" action={<DropdownMenu><DropdownMenuTrigger render={<Button variant="ghost" size="icon" disabled={busy} title="Настройки плана" aria-label="Настройки плана" />}><Settings2 /></DropdownMenuTrigger><DropdownMenuContent align="end"><DropdownMenuItem onClick={() => void perform(async () => { setTemplate(await api<Template>("/api/adaptation-plan/template")); setOpen(true); })}><Settings2 />Порядок и правила</DropdownMenuItem>{hasPlan && <DropdownMenuItem disabled={!plan?.rows.some(row => ["planned", "blocked"].includes(row.status))} onClick={() => openPlanning(true)}><RefreshCw />Пересчитать оставшиеся этапы</DropdownMenuItem>}</DropdownMenuContent></DropdownMenu>}>
        {error && <p role="alert" className="mb-3 text-sm text-destructive">{error}</p>}
        {notice && <p role="status" className="mb-3 text-sm text-muted-foreground">{notice}</p>}
        {!plan ? <p role="status" className="text-sm text-muted-foreground">{error ? "План недоступен" : "Загрузка плана..."}</p> : <>
            <div className="adaptation-overview">{hasPlan && <div><p className="mb-3 text-sm text-muted-foreground">{completedRows.length} из {plan.rows.length} этапов завершено</p><Progress value={completedRows.length} max={Math.max(1, plan.rows.length)} aria-label="Завершённые этапы нового плана" /></div>}{hasPlan && plan.rows.some(row => ["planned", "blocked"].includes(row.status)) && <Button variant="outline" disabled={busy} onClick={() => openPlanning(true)}><RefreshCw />Пересчитать оставшиеся</Button>}{plan.rows.some(row => !row.item_id) && <Button disabled={busy} onClick={() => openPlanning(false)}><CalendarDays />{hasPlan ? "Добавить новые этапы" : "Запланировать адаптацию"}</Button>}</div>
            {!!completedRows.length && <><button type="button" className="adaptation-history-toggle" aria-expanded={historyOpen} onClick={() => setHistoryOpen(!historyOpen)}>{historyOpen ? <ChevronDown size={15} /> : <ChevronRight size={15} />}Завершённые этапы <span>{completedRows.length}</span></button>{historyOpen && <ol className="adaptation-stage-list adaptation-completed-list">{completedRows.map(renderRow)}</ol>}</>}
            {hasPlan && <ol className="adaptation-stage-list">{currentRows.map(renderRow)}</ol>}
            {plan.adaptation_midpoint && <p className="mt-3 text-xs text-muted-foreground">Середина адаптации: {plan.adaptation_midpoint.split("-").reverse().join(".")}</p>}
            {plan.adaptation_end && <p className="mt-3 text-xs text-muted-foreground">Конец адаптации: {plan.adaptation_end.split("-").reverse().join(".")} · {plan.adaptation_end_source === "calculated" ? "первый день + 3 месяца" : "дата из карточки"}. Изменить можно в «Сопровождение и документы».</p>}
            <div className="adaptation-plan-footer"><Clock3 size={14} /><span>{plan.timezone === "Europe/Moscow" ? "Московское время" : plan.timezone}</span><span>{plan.group}</span></div>
        </>}
        <Dialog open={planning} onOpenChange={value => { if (!busy) setPlanning(value); }}><DialogContent className="max-h-[88vh] overflow-y-auto sm:max-w-3xl"><DialogHeader><DialogTitle>{replanning ? "Перепланировать оставшиеся этапы" : "Запланировать адаптацию"}</DialogTitle></DialogHeader><p className="text-sm text-muted-foreground">{replanning ? "Завершённые, идущие и отменённые этапы не изменятся. Проверьте переносы, включая даты, изменённые вручную." : "Будут запланированы все этапы, включая повторные прохождения. Проверьте даты перед подтверждением."} Время: {plan?.timezone}.</p>{error && <p role="alert" className="text-sm text-destructive">{error}</p>}
            <div>{availableRows.map(row => <div key={row.key} className="adaptation-planning-row"><span><CalendarDays size={14} /></span><div><p className="font-medium">{titleFor(row)}</p><p className="text-xs text-muted-foreground">{row.rule_label}</p>{replanning && <p className="text-xs text-muted-foreground">Было: {dateLabel(row.requested_at)}{row.manual_date ? " · вручную" : ""}</p>}{(row.error || row.conflict_ids.length > 0) && <p className="text-xs text-destructive">{row.error || "Уже есть отдельный запланированный запуск"}</p>}{row.previous_completed && !replanning && <p className="text-xs text-muted-foreground">Будет повторное прохождение.</p>}</div><Input type="datetime-local" aria-label={`Плановая дата: ${titleFor(row)}`} value={dates[row.key] || ""} disabled={busy || !!row.error || !!row.conflict_ids.length} onChange={event => setDates(prev => ({ ...prev, [row.key]: event.target.value }))} /></div>)}</div>
            <div className="flex flex-wrap items-center justify-between gap-2"><Button variant="ghost" disabled={busy} onClick={() => openPlanning(replanning)}><RefreshCw />Обновить расчёт</Button><div className="flex gap-2"><Button variant="ghost" disabled={busy} onClick={() => setPlanning(false)}>Отмена</Button><Button disabled={busy || !selected.length || invalidSelection} onClick={() => void perform(async () => { accept(await api<Plan>(replanning ? `${url}/replan` : url, "POST", { fingerprint: plan?.fingerprint, rules_confirmed: true, full_plan: true, rows: selected.map(key => ({ key, requested_at: dates[key] })) })); setPlanning(false); setNotice(replanning ? "Оставшиеся этапы перепланированы" : "Адаптация запланирована"); })}>{replanning ? "Подтвердить перенос" : "Запланировать все этапы"} ({selected.length})</Button></div></div>
        </DialogContent></Dialog>
        <Dialog open={!!editing} onOpenChange={value => { if (!busy && !value) setEditing(null); }}><DialogContent><DialogHeader><DialogTitle>{editing?.item_id ? "Дата запуска" : "Запланировать этап"}</DialogTitle></DialogHeader><p className="text-sm">{editing?.title}</p><p className="text-xs text-muted-foreground">{editing?.rule_label}</p>{error && <p role="alert" className="text-sm text-destructive">{error}</p>}<DateTimePicker value={editDate} onValueChange={setEditDate} disabled={busy} /><p className="text-xs text-muted-foreground">Время: {plan?.timezone}. Даты остальных этапов не изменятся.</p><div className="flex justify-end gap-2"><Button variant="ghost" disabled={busy} onClick={() => setEditing(null)}>Отмена</Button><Button disabled={busy || !validDate(editDate)} onClick={() => void perform(async () => { if (!editing) return; const next = editing.item_id ? await api<Plan>(`${url}/${editing.item_id}`, "PATCH", { expected_at: editing.requested_at, requested_at: editDate }) : await api<Plan>(url, "POST", { fingerprint: plan?.fingerprint, rules_confirmed: true, rows: [{ key: editing.key, requested_at: editDate }] }); accept(next); setEditing(null); setNotice("Дата сохранена, запуск запланирован"); })}>{editing?.item_id && !["failed", "cancelled"].includes(editing.status) ? "Сохранить" : "Запланировать"}</Button></div></DialogContent></Dialog>
        <Dialog open={!!cancelling} onOpenChange={value => { if (!busy && !value) setCancelling(null); }}><DialogContent><DialogHeader><DialogTitle>Отменить запланированный запуск?</DialogTitle></DialogHeader><p className="text-sm">{cancelling?.title}</p><p className="text-sm text-muted-foreground">История этапа сохранится. Его можно будет запланировать повторно.</p>{error && <p role="alert" className="text-sm text-destructive">{error}</p>}<div className="flex justify-end gap-2"><Button variant="ghost" disabled={busy} onClick={() => setCancelling(null)}>Оставить</Button><Button variant="destructive" disabled={busy} onClick={() => void perform(async () => { if (!cancelling) return; accept(await api<Plan>(`${url}/${cancelling.item_id}`, "PATCH", { expected_at: cancelling.requested_at, action: "cancel" })); setCancelling(null); setNotice("Запуск отменён"); })}>Отменить запуск</Button></div></DialogContent></Dialog>
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
