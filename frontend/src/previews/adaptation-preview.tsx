import React from "react";
import { createRoot } from "react-dom/client";
import { ArrowDown, ArrowUp, CalendarDays, Check, ChevronDown, ChevronRight, Circle, Clock3, MoreHorizontal, Moon, Play, Plus, RotateCcw, Settings2, Sun, X } from "lucide-react";
import "@/index.css";
import "./adaptation-preview.css";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Input } from "@/components/ui/input";
import { DateTimePicker } from "@/components/ui/date-picker";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem } from "@/components/ui/dropdown-menu";

type Stage = { id: string; title: string; date: string; status: "completed" | "active" | "planned" | "new" | "cancelled"; rule: string };
const initial: Stage[] = [
    { id: "organization", title: "Организация адаптации", date: "2026-10-05T10:00", status: "completed", rule: "Первый рабочий день" },
    { id: "first", title: "Первый рабочий день", date: "2026-10-05T10:10", status: "completed", rule: "Первый рабочий день, второй запуск" },
    { id: "week", title: "Конец первой недели", date: "2026-10-12T10:00", status: "completed", rule: "+5 рабочих дней от первого дня" },
    { id: "test1", title: "Тестирование PM · часть 1", date: "2026-10-16T10:00", status: "active", rule: "10-й рабочий день" },
    { id: "pulse1", title: "Пульс · после первого тестирования", date: "2026-10-23T10:00", status: "new", rule: "+5 рабочих дней от плановой даты тестирования" },
    { id: "middle", title: "Середина испытательного срока", date: "2026-11-19T10:00", status: "new", rule: "+45 календарных дней от первого дня" },
    { id: "test2", title: "Тестирование PM · часть 2", date: "2026-12-16T10:00", status: "new", rule: "За 14 календарных дней до конца адаптации" },
    { id: "pulse2", title: "Пульс · после второго тестирования", date: "2026-12-23T10:00", status: "new", rule: "+5 рабочих дней от плановой даты тестирования" },
    { id: "end", title: "Завершение адаптации", date: "2026-12-25T10:00", status: "new", rule: "За 3 рабочих дня до конца адаптации" },
];
const names = { completed: "Завершён", active: "В процессе", planned: "Запланирован", new: "Не запланирован", cancelled: "Отменён" };
const formatDate = (value: string) => value ? new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }).format(new Date(value)) : "Выбрать дату";

function Preview() {
    const [stages, setStages] = React.useState<Stage[]>(initial);
    const [history, setHistory] = React.useState(false);
    const [planning, setPlanning] = React.useState(false);
    const [draft, setDraft] = React.useState<Record<string, string>>({});
    const [selected, setSelected] = React.useState<string[]>([]);
    const [editing, setEditing] = React.useState<string | null>(null);
    const [editDate, setEditDate] = React.useState("");
    const [ordering, setOrdering] = React.useState(false);
    const [orderDraft, setOrderDraft] = React.useState<Stage[]>([]);
    const [newTitle, setNewTitle] = React.useState("");
    const [dark, setDark] = React.useState(false);
    const [notice, setNotice] = React.useState("");
    React.useEffect(() => { document.documentElement.classList.toggle("dark", dark); }, [dark]);
    const completed = stages.filter(stage => stage.status === "completed");
    const remaining = stages.filter(stage => stage.status !== "completed");
    const available = stages.filter(stage => stage.status === "new" || stage.status === "cancelled");
    const changed = stages.find(stage => stage.id === editing);
    const invalidDates = selected.some(id => !draft[id] || Number.isNaN(new Date(draft[id]).getTime()));

    function openPlan() {
        setDraft(Object.fromEntries(available.map(stage => [stage.id, stage.date])));
        setSelected(available.map(stage => stage.id));
        setPlanning(true);
    }
    function edit(stage: Stage) { setEditing(stage.id); setEditDate(stage.date); }
    function move(index: number, delta: number) {
        const next = [...orderDraft];
        [next[index], next[index + delta]] = [next[index + delta], next[index]];
        setOrderDraft(next);
    }
    function row(stage: Stage) {
        const canEdit = stage.status !== "completed" && stage.status !== "active";
        return <li key={stage.id} className="stage-row">
            <span className={`stage-marker ${stage.status === "completed" ? "is-complete" : stage.status === "active" ? "is-active" : ""}`}>
                {stage.status === "completed" ? <Check size={14} /> : stage.status === "active" ? <Play size={12} /> : <span>{stages.indexOf(stage) + 1}</span>}
            </span>
            <div className="stage-name"><span>{stage.title}</span>{stage.status === "active" && <span className="stage-caption">Ожидаем ответ сотрудника</span>}</div>
            {canEdit ? <button className="stage-date" onClick={() => edit(stage)} title="Изменить дату"><CalendarDays size={14} /><span>{stage.status === "planned" ? formatDate(stage.date) : "Без даты"}</span></button> : <span className="stage-date fixed-date">{formatDate(stage.date)}</span>}
            <Badge variant={stage.status === "active" ? "default" : "secondary"} className="stage-status">{names[stage.status]}</Badge>
            {canEdit ? <DropdownMenu><DropdownMenuTrigger render={<Button variant="ghost" size="icon" aria-label={`Действия: ${stage.title}`} title="Действия этапа" />}><MoreHorizontal /></DropdownMenuTrigger><DropdownMenuContent align="end">
                <DropdownMenuItem onClick={() => edit(stage)}><CalendarDays />{stage.status === "planned" ? "Изменить дату" : "Назначить дату"}</DropdownMenuItem>
                {stage.status === "planned" ? <DropdownMenuItem onClick={() => { setStages(prev => prev.map(item => item.id === stage.id ? { ...item, status: "cancelled" } : item)); setNotice("Запуск отменён в прототипе"); }}><X />Отменить запуск</DropdownMenuItem> : null}
            </DropdownMenuContent></DropdownMenu> : <span className="empty-action" />}
        </li>;
    }
    return <div className={dark ? "dark" : ""}><div className="preview-shell">
        <div className="preview-bar"><span>Локальный прототип · тестовые данные</span><div><Button variant="ghost" size="icon" title="Сбросить пример" aria-label="Сбросить пример" onClick={() => { setStages(initial); setHistory(false); setNotice(""); }}><RotateCcw /></Button><Button variant="ghost" size="icon" title="Переключить тему" aria-label="Переключить тему" onClick={() => setDark(!dark)}>{dark ? <Sun /> : <Moon />}</Button></div></div>
        <main className="preview-main"><header className="employee-heading"><div className="employee-avatar">ИИ</div><div><h1>Иванов Иван Иванович</h1><p>Руководитель проектов <span>·</span> Первый день: 5 октября 2026</p></div><Badge variant="secondary">Адаптация</Badge></header>
            <div className="preview-tabs"><span>Обзор</span><span>Сценарии</span><span>Сообщения</span><span>Файлы</span><span>История</span><span className="selected-tab">Адаптация</span><span>Грейд</span></div>
            <section className="adaptation-panel"><div className="plan-heading"><div><h2>План адаптации</h2><p>{completed.length} из {stages.length} этапов завершено</p></div><div className="heading-actions"><Button variant="ghost" size="icon" title="Порядок этапов" aria-label="Порядок этапов" onClick={() => { setOrderDraft([...stages]); setOrdering(true); }}><Settings2 /></Button><Button disabled={!available.length} onClick={openPlan}><CalendarDays />Запланировать адаптацию</Button></div></div>
                <Progress value={completed.length} max={stages.length} aria-label="Прогресс адаптации" />
                {notice && <p role="status" className="preview-notice">{notice}</p>}
                <button className="history-toggle" aria-expanded={history} onClick={() => setHistory(!history)}>{history ? <ChevronDown size={15} /> : <ChevronRight size={15} />}Завершённые этапы <span>{completed.length}</span></button>
                {history && <ol className="stage-list completed-list">{completed.map(row)}</ol>}
                <ol className="stage-list">{remaining.map(row)}</ol>
                <div className="plan-footer"><span><Clock3 size={14} />Московское время</span><span>Конец адаптации: 30 декабря 2026</span></div>
            </section>
            <details className="secondary-section"><summary>Сопровождение и документы</summary><div><p>Руководитель: Анна Смирнова</p><p>Наставник: Алексей Петров</p><p>План испытательного срока · ИПР · Обратная связь</p></div></details>
        </main>
        <Dialog open={planning} onOpenChange={setPlanning}><DialogContent className="preview-dialog sm:max-w-3xl"><DialogHeader><DialogTitle>Запланировать адаптацию</DialogTitle></DialogHeader><p className="text-sm text-muted-foreground">Оставшиеся этапы · даты по производственному календарю · МСК</p>
            <div className="planning-list">{available.map(stage => <label key={stage.id} className="planning-row"><input type="checkbox" checked={selected.includes(stage.id)} onChange={event => setSelected(prev => event.target.checked ? [...prev, stage.id] : prev.filter(id => id !== stage.id))} /><div><strong>{stage.title}</strong><small>{stage.rule}</small></div><Input type="datetime-local" aria-label={`Плановая дата: ${stage.title}`} value={draft[stage.id] || ""} disabled={!selected.includes(stage.id)} onChange={event => setDraft(prev => ({ ...prev, [stage.id]: event.target.value }))} /></label>)}</div>
            <p className="text-xs text-muted-foreground">Уже завершённые и текущий этап не запускаются повторно.</p><div className="dialog-footer"><Button variant="ghost" onClick={() => setPlanning(false)}>Отмена</Button><Button disabled={!selected.length || invalidDates} onClick={() => { setStages(prev => prev.map(stage => selected.includes(stage.id) ? { ...stage, date: draft[stage.id], status: "planned" } : stage)); setPlanning(false); setNotice(`Запланировано этапов: ${selected.length}. Только в локальном прототипе.`); }}>Подтвердить ({selected.length})</Button></div>
        </DialogContent></Dialog>
        <Dialog open={!!editing} onOpenChange={value => { if (!value) setEditing(null); }}><DialogContent className="preview-dialog"><DialogHeader><DialogTitle>Дата запуска</DialogTitle></DialogHeader><p className="text-sm">{changed?.title}</p><DateTimePicker value={editDate} onValueChange={setEditDate} /><p className="text-xs text-muted-foreground">Московское время. Даты остальных этапов не изменятся.</p><div className="dialog-footer"><Button variant="ghost" onClick={() => setEditing(null)}>Отмена</Button><Button disabled={!editDate.includes("T")} onClick={() => { setStages(prev => prev.map(stage => stage.id === editing ? { ...stage, date: editDate, status: "planned" } : stage)); setEditing(null); setNotice("Дата сохранена в прототипе"); }}>Сохранить</Button></div></DialogContent></Dialog>
        <Dialog open={ordering} onOpenChange={setOrdering}><DialogContent className="preview-dialog sm:max-w-xl"><DialogHeader><DialogTitle>Порядок этапов</DialogTitle></DialogHeader><div className="order-list">{orderDraft.map((stage, index) => <div className="order-row" key={stage.id}><span>{index + 1}</span><strong>{stage.title}</strong><Button variant="ghost" size="icon" title="Выше" aria-label={`Выше: ${stage.title}`} disabled={!index} onClick={() => move(index, -1)}><ArrowUp /></Button><Button variant="ghost" size="icon" title="Ниже" aria-label={`Ниже: ${stage.title}`} disabled={index === orderDraft.length - 1} onClick={() => move(index, 1)}><ArrowDown /></Button></div>)}</div><div className="flex gap-2"><Input aria-label="Новый этап" placeholder="Название нового этапа" value={newTitle} onChange={event => setNewTitle(event.target.value)} /><Button variant="outline" title="Добавить этап" aria-label="Добавить этап" disabled={!newTitle.trim()} onClick={() => { setOrderDraft(prev => [...prev, { id: `demo_${Date.now()}`, title: newTitle.trim(), date: "2026-12-28T10:00", status: "new", rule: "Дата назначается вручную" }]); setNewTitle(""); }}><Plus /></Button></div><div className="dialog-footer"><Button variant="ghost" onClick={() => setOrdering(false)}>Отмена</Button><Button onClick={() => { setStages(orderDraft); setOrdering(false); setNotice("Порядок сохранён в прототипе. Даты не изменились."); }}>Сохранить порядок</Button></div></DialogContent></Dialog>
    </div></div>;
}

createRoot(document.getElementById("root")!).render(<Preview />);
