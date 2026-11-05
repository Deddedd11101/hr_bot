import React from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";

type Progress = {id: number; title: string; recipient_name: string; started_at: string; updated_at: string; waiting: boolean; long_wait: boolean};
type Pending = {id: number; title: string; source: string; requested_at: string; blocker: Progress | null; can_cancel: boolean};
type Queue = {active: Progress[]; pending: Pending[]; can_manage: boolean};
type Action = {kind: "progress" | "requests"; id: number; title: string; expected: string};
const sources: Record<string, string> = {adaptation_plan: "Адаптация", scheduled: "По расписанию", manual: "Ручной запуск", status_transition: "Смена этапа"};

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
            const response = await fetch(`${url}/${action.kind}/${action.id}/${action.kind === "progress" ? "interrupt" : "cancel"}`, {
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
        {data && !data.active.length && !data.pending.length && <p className="text-sm text-muted-foreground">Активных диалогов и отдельных запросов запуска нет.</p>}
        {data?.active.map(row => <div key={`p${row.id}`} className="flex flex-wrap items-start justify-between gap-3 border-b py-3">
            <div className="min-w-0 space-y-1"><p className="break-words font-medium">{row.title}</p><p className="text-sm text-muted-foreground">Адресат: {row.recipient_name}</p><p className="text-xs text-muted-foreground">Начат: {new Date(`${row.started_at}Z`).toLocaleString("ru-RU")}</p><Badge variant="secondary">{row.waiting ? "Ожидает ответа" : "Требует проверки состояния"}</Badge>{row.long_wait && <p className="text-xs text-muted-foreground">Нет изменений больше суток</p>}</div>
            {data.can_manage && row.waiting && <Button size="sm" variant="outline" onClick={() => setAction({kind: "progress", id: row.id, title: row.title, expected: row.updated_at})}>Прервать диалог</Button>}
        </div>)}
        {data?.pending.map(row => <div key={`r${row.id}`} className="flex flex-wrap items-start justify-between gap-3 border-b py-3">
            <div className="min-w-0 space-y-1"><p className="break-words font-medium">{row.title}</p><p className="text-xs text-muted-foreground">{sources[row.source] || row.source} · {row.requested_at.replace("T", " ")} {['scheduled', 'adaptation_plan'].includes(row.source) ? "(время приложения)" : "UTC"}</p><Badge variant="secondary">{row.blocker ? "Ожидает диалог" : "В очереди планировщика"}</Badge>{row.blocker && <p className="text-sm text-muted-foreground">Блокирует: {row.blocker.title} · {row.blocker.recipient_name}</p>}</div>
            {data.can_manage && row.can_cancel && <Button size="sm" variant="outline" onClick={() => setAction({kind: "requests", id: row.id, title: row.title, expected: row.requested_at})}>Отменить запуск</Button>}
        </div>)}
        <Dialog open={!!action} onOpenChange={open => {if (!open && !busy) {setAction(null); setError("");}}}><DialogContent><DialogHeader><DialogTitle>{action?.kind === "progress" ? "Прервать диалог?" : "Отменить запуск?"}</DialogTitle><DialogDescription>{action?.title}</DialogDescription></DialogHeader><p className="text-sm text-muted-foreground">Ответы и история сохранятся. Сообщения из Telegram не удаляются. Уже начавшаяся отправка может завершиться. Другие ожидающие запуски смогут продолжиться при следующей проверке планировщика.</p>{error && <p role="alert" className="text-sm text-destructive">{error}</p>}<div className="flex justify-end gap-2"><Button variant="ghost" disabled={busy} onClick={() => setAction(null)}>Оставить</Button><Button variant="destructive" disabled={busy} onClick={() => void perform()}>{busy ? "Сохранение..." : "Подтвердить"}</Button></div></DialogContent></Dialog>
    </section>;
}
