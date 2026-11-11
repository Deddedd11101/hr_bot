import React from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";

type Health = {state: string; reason: string; idle_seconds: number; alert_due: boolean; next_at: string | null};
type Progress = {id: number; title: string; recipient_name: string; started_at: string; updated_at: string; waiting: boolean; long_wait: boolean; health: Health};
type Pending = {id: number; title: string; source: string; requested_at: string; blocker: Progress | null; recipient_error: string | null; can_cancel: boolean};
type StepDelivery = {id: number; title: string; due_at: string; status: string; reason: string | null; can_cancel: boolean; recipient_name: string | null; receipt_at: string | null; can_reconcile: boolean};
type Queue = {active: Progress[]; pending: Pending[]; step_deliveries?: StepDelivery[]; can_manage: boolean};
type Action = {kind: "progress" | "requests" | "step-deliveries"; id: number; title: string; expected: string; reconcile?: boolean};
const sources: Record<string, string> = {adaptation_plan: "Адаптация", scheduled: "По расписанию", manual: "Ручной запуск", status_transition: "Смена этапа"};
const healthLabels: Record<string, string> = {waiting_human: "Ожидает ответа", scheduled: "Продолжение запланировано", processing: "В обработке", stale_runtime: "Нужна проверка", delivery_uncertain: "Доставка требует проверки"};
function idleLabel(seconds: number) {
    if (seconds < 60) return "меньше минуты";
    if (seconds < 3600) return `${Math.floor(seconds / 60)} мин`;
    return `${Math.floor(seconds / 3600)} ч ${Math.floor(seconds % 3600 / 60)} мин`;
}

export function ScenarioQueue({employeeId, visible}: {employeeId: number; visible: boolean}) {
    const [data, setData] = React.useState<Queue | null>(null);
    const [error, setError] = React.useState("");
    const [action, setAction] = React.useState<Action | null>(null);
    const [busy, setBusy] = React.useState(false);
    const url = `/api/employees/${employeeId}/scenario-queue`;
    React.useEffect(() => {
        if (!visible || action || busy) return;
        let cancelled = false;
        async function load() {
            if (document.hidden) return;
            try {
                const response = await fetch(url);
                if (!response.ok) throw new Error("Не удалось получить очередь");
                const next = await response.json();
                if (!cancelled) {setData(next); setError("");}
            } catch (e) {if (!cancelled) setError(e instanceof Error ? e.message : "Ошибка загрузки");}
        }
        void load();
        const timer = window.setInterval(() => void load(), 15000);
        return () => {cancelled = true; window.clearInterval(timer);};
    }, [url, visible, action, busy]);
    async function perform() {
        if (!action) return;
        setBusy(true); setError("");
        try {
            const operation = action.reconcile ? "reconcile" : action.kind === "progress" ? "interrupt" : "cancel";
            const response = await fetch(`${url}/${action.kind}/${action.id}/${operation}`, {
                method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({expected_at: action.expected}),
            });
            const next = await response.json();
            if (!response.ok) throw new Error(next.detail || "Действие не выполнено");
            setData(next); setAction(null);
        } catch (e) {setError(e instanceof Error ? e.message : "Действие не выполнено");}
        finally {setBusy(false);}
    }
    return <section className="min-w-0 space-y-3">
        <h3 className="text-base font-semibold">Очередь сценариев</h3>
        {error && !action && <p role="alert" className="text-sm text-destructive">{error}</p>}
        {!data && !error && <p role="status" className="text-sm text-muted-foreground">Загрузка очереди...</p>}
        {data && !data.active.length && !data.pending.length && !data.step_deliveries?.length && <p className="text-sm text-muted-foreground">Активных диалогов и отдельных запросов запуска нет.</p>}
        {data?.active.map(row => <div key={`p${row.id}`} className="flex flex-wrap items-start justify-between gap-3 border-b py-3">
            <div className="min-w-0 space-y-1"><p className="break-words font-medium">{row.title}</p><p className="text-sm text-muted-foreground">Адресат: {row.recipient_name}</p><p className="text-xs text-muted-foreground">Начат: {new Date(`${row.started_at}Z`).toLocaleString("ru-RU", {timeZone: "Europe/Moscow"})} · МСК</p><Badge variant={row.health.alert_due ? "destructive" : "secondary"}>{healthLabels[row.health.state] || "Нужна проверка"}</Badge><p className="text-xs text-muted-foreground">Без изменений: {idleLabel(row.health.idle_seconds)}</p><p className="max-w-xl text-sm text-muted-foreground">{row.health.reason}</p>{row.health.next_at && <p className="text-xs text-muted-foreground">Продолжение: {new Date(`${row.health.next_at}Z`).toLocaleString("ru-RU", {timeZone: "Europe/Moscow"})} · МСК</p>}</div>
            {data.can_manage && row.waiting && <Button size="sm" variant="outline" onClick={() => setAction({kind: "progress", id: row.id, title: row.title, expected: row.updated_at})}>Прервать диалог</Button>}
        </div>)}
        {data?.step_deliveries?.map(row => <div key={`s${row.id}`} className="flex flex-wrap items-start justify-between gap-3 border-b py-3">
            <div className="min-w-0 space-y-1"><p className="break-words font-medium">{row.title}</p><p className="text-xs text-muted-foreground">Плановый шаг · {new Date(`${row.due_at}Z`).toLocaleString("ru-RU", {timeZone: "Europe/Moscow"})} · МСК</p><Badge variant={row.status === "pending" ? "secondary" : "destructive"}>{row.status === "pending" ? "В очереди" : "Нужна проверка доставки"}</Badge>{row.reason && <p className="max-w-xl text-sm text-muted-foreground">{row.reason}</p>}</div>
            {data.can_manage && row.can_cancel && <Button size="sm" variant="outline" onClick={() => setAction({kind: "step-deliveries", id: row.id, title: row.title, expected: row.due_at})}>Отменить запуск</Button>}
            {row.status === "starting" && <div className="basis-full space-y-1 text-sm text-muted-foreground">
                <p>Адресат: {row.recipient_name || "Не зафиксирован"}</p>
                <p>{row.receipt_at ? `Отправка записана в журнале: ${new Date(`${row.receipt_at}Z`).toLocaleString("ru-RU", {timeZone: "Europe/Moscow"})} · МСК` : "В журнале нет подтверждения отправки."}</p>
                {data.can_manage && row.can_reconcile && <Button size="sm" variant="outline" onClick={() => setAction({kind: "step-deliveries", id: row.id, title: row.title, expected: row.due_at, reconcile: true})}>Подтвердить по журналу</Button>}
            </div>}
        </div>)}
        {data?.pending.map(row => <div key={`r${row.id}`} className="flex flex-wrap items-start justify-between gap-3 border-b py-3">
            <div className="min-w-0 space-y-1"><p className="break-words font-medium">{row.title}</p><p className="text-xs text-muted-foreground">{sources[row.source] || row.source} · {row.requested_at.replace("T", " ")} {['scheduled', 'adaptation_plan'].includes(row.source) ? "(время приложения)" : "UTC"}</p><Badge variant="secondary">{row.recipient_error ? "Получатель недоступен" : row.blocker ? "Ожидает диалог" : "В очереди планировщика"}</Badge>{row.recipient_error && <p className="text-sm text-destructive">{row.recipient_error}</p>}{row.blocker && <p className="text-sm text-muted-foreground">Блокирует: {row.blocker.title} · {row.blocker.recipient_name}. Без изменений: {idleLabel(row.blocker.health.idle_seconds)}</p>}</div>
            {data.can_manage && row.can_cancel && <Button size="sm" variant="outline" onClick={() => setAction({kind: "requests", id: row.id, title: row.title, expected: row.requested_at})}>Отменить запуск</Button>}
        </div>)}
        <Dialog open={!!action} onOpenChange={open => {if (!open && !busy) {setAction(null); setError("");}}}><DialogContent><DialogHeader><DialogTitle>{action?.reconcile ? "Подтвердить отправку по журналу?" : action?.kind === "progress" ? "Прервать диалог?" : "Отменить запуск?"}</DialogTitle><DialogDescription>{action?.title}</DialogDescription></DialogHeader><p className="text-sm text-muted-foreground">{action?.reconcile ? "Запись уйдёт из списка спорных отправок. Бот не повторит сообщение, а текущий диалог не изменится." : "Ответы и история сохранятся. Сообщения из Telegram не удаляются. Уже начавшаяся отправка может завершиться. Другие ожидающие запуски смогут продолжиться при следующей проверке планировщика."}</p>{error && <p role="alert" className="text-sm text-destructive">{error}</p>}<div className="flex justify-end gap-2"><Button variant="ghost" disabled={busy} onClick={() => setAction(null)}>Оставить</Button><Button variant={action?.reconcile ? "default" : "destructive"} disabled={busy} onClick={() => void perform()}>{busy ? "Сохранение..." : "Подтвердить"}</Button></div></DialogContent></Dialog>
    </section>;
}
