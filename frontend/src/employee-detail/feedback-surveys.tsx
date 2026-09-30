import React from "react";
import { Download, Play, RefreshCcw } from "lucide-react";

import { Button, buttonVariants } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { PageSection } from "@/components/ui/page-section";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

type Recipient = { id: number; full_name: string; position: string; available: boolean };
type FeedbackPayload = {
    surveys: Array<{ key: string; title: string; eligible_recipient_ids: number[] }>;
    recipients: Recipient[];
    runs: Array<{ id: number; title: string; created_at: string; recipient_count: number; completed_count: number; failed_count: number; answer_count: number; download_url: string | null }>;
    answer_count: number;
    download_url: string | null;
};

export function EmployeeFeedbackSurveys({ employeeId, legacyUrl }: { employeeId: number; legacyUrl?: string | null }) {
    const [payload, setPayload] = React.useState<FeedbackPayload | null>(null);
    const [error, setError] = React.useState("");
    const [notice, setNotice] = React.useState("");
    const [loading, setLoading] = React.useState(true);
    const [submitting, setSubmitting] = React.useState(false);
    const [scenarioKey, setScenarioKey] = React.useState("");
    const [position, setPosition] = React.useState("all");
    const [search, setSearch] = React.useState("");
    const [selectedIds, setSelectedIds] = React.useState<number[]>([]);
    const [revision, setRevision] = React.useState(0);
    const apiUrl = `/api/employees/${employeeId}/feedback-surveys`;

    React.useEffect(() => {
        let active = true;
        setLoading(true);
        fetch(apiUrl, { credentials: "same-origin" })
            .then(async response => {
                if (!response.ok) throw new Error("Не удалось загрузить опросы обратной связи.");
                return response.json() as Promise<FeedbackPayload>;
            })
            .then(next => { if (active) { setPayload(next); setError(""); } })
            .catch(cause => { if (active) setError(String(cause.message || cause)); })
            .finally(() => { if (active) setLoading(false); });
        return () => { active = false; };
    }, [apiUrl, revision]);

    const positions = Array.from(new Set((payload?.recipients || []).map(item => item.position).filter(Boolean))).sort();
    const visibleRecipients = (payload?.recipients || []).filter(item =>
        (position === "all" || item.position === position) &&
        item.full_name.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase()),
    );
    const selectedSurvey = payload?.surveys.find(item => item.key === scenarioKey);
    const canSelect = (item: Recipient) => item.available && !!selectedSurvey?.eligible_recipient_ids.includes(item.id);
    const availableVisibleIds = visibleRecipients.filter(canSelect).map(item => item.id);
    const allVisibleSelected = availableVisibleIds.length > 0 && availableVisibleIds.every(id => selectedIds.includes(id));

    async function launch() {
        if (!scenarioKey || selectedIds.length === 0) return;
        setSubmitting(true);
        setError("");
        setNotice("");
        try {
            const response = await fetch(apiUrl, {
                method: "POST",
                credentials: "same-origin",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ scenario_key: scenarioKey, recipient_employee_ids: selectedIds }),
            });
            const next = await response.json();
            if (!response.ok) throw new Error(next.detail || "Не удалось запустить опрос.");
            setPayload(next as FeedbackPayload);
            setSelectedIds([]);
            const failedCount = (next as FeedbackPayload).runs[0]?.failed_count || 0;
            setNotice(failedCount ? `Не удалось отправить опрос ${failedCount} сотрудникам. Проверьте их связь с ботом.` : "Опрос запущен. Ответы появятся в общем файле после прохождения.");
        } catch (cause) {
            setError(cause instanceof Error ? cause.message : "Не удалось запустить опрос.");
        } finally {
            setSubmitting(false);
        }
    }

    return (
        <PageSection title="Обратная связь" counter={payload?.answer_count} contentClassName="gap-4" action={<Button type="button" size="icon-sm" variant="ghost" onClick={() => setRevision(value => value + 1)} aria-label="Обновить ответы" title="Обновить ответы"><RefreshCcw aria-hidden="true" /></Button>}>
            {loading ? <p className="text-sm text-muted-foreground">Загрузка...</p> : null}
            {error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null}
            {notice ? <p role="status" className="text-sm text-muted-foreground">{notice}</p> : null}
            {payload ? <>
                {!payload.answer_count || (legacyUrl && /^https?:\/\//i.test(legacyUrl)) ? <div className="flex flex-wrap items-center gap-3">
                    {!payload.answer_count ? <span className="text-sm text-muted-foreground">Ответов пока нет</span> : null}
                    {legacyUrl && /^https?:\/\//i.test(legacyUrl) ? <a className="text-sm underline underline-offset-4" href={legacyUrl} target="_blank" rel="noreferrer">Ранее сохранённая ссылка</a> : null}
                </div> : null}
                {payload.runs.length ? <div className="space-y-2 text-sm text-muted-foreground">
                    {payload.runs.map(run => <div key={run.id} className="flex flex-wrap items-center justify-between gap-2">
                        <p>{run.title}: {run.completed_count} из {run.recipient_count} завершили{run.failed_count ? `, ошибок отправки: ${run.failed_count}` : ""} · {new Date(run.created_at).toLocaleString("ru-RU")}</p>
                        {run.download_url ? (
                            <a className={buttonVariants({ variant: "outline", size: "sm" })} href={run.download_url}>
                                <Download aria-hidden="true" /> Ответы (.xlsx)
                            </a>
                        ) : null}
                    </div>)}
                </div> : null}
                <div className="grid gap-3 lg:grid-cols-2">
                    <div className="space-y-2">
                        <label className="text-sm font-medium" htmlFor="feedback-survey-select">Опрос</label>
                        <Select items={payload.surveys.map(item => ({ value: item.key, label: item.title }))} value={scenarioKey || null} onValueChange={value => { setScenarioKey(value || ""); setSelectedIds([]); }}>
                            <SelectTrigger id="feedback-survey-select" className="w-full"><SelectValue placeholder="Выберите опрос" /></SelectTrigger>
                            <SelectContent>{payload.surveys.map(item => <SelectItem key={item.key} value={item.key}>{item.title}</SelectItem>)}</SelectContent>
                        </Select>
                    </div>
                    <div className="space-y-2">
                        <label className="text-sm font-medium" htmlFor="feedback-position-select">Должность отвечающих</label>
                        <Select items={[{ value: "all", label: "Все должности" }, ...positions.map(value => ({ value, label: value }))]} value={position} onValueChange={value => setPosition(value || "all")}>
                            <SelectTrigger id="feedback-position-select" className="w-full"><SelectValue /></SelectTrigger>
                            <SelectContent><SelectItem value="all">Все должности</SelectItem>{positions.map(value => <SelectItem key={value} value={value}>{value}</SelectItem>)}</SelectContent>
                        </Select>
                    </div>
                </div>
                <Input aria-label="Найти сотрудника" value={search} onChange={event => setSearch(event.target.value)} placeholder="Найти сотрудника" />
                <div className="flex items-center justify-between gap-3 text-sm">
                    <span>Выбрано: {selectedIds.length}</span>
                    <Button type="button" size="sm" variant="ghost" disabled={!availableVisibleIds.length} onClick={() => setSelectedIds(current => allVisibleSelected ? current.filter(id => !availableVisibleIds.includes(id)) : Array.from(new Set([...current, ...availableVisibleIds])))}>
                        {allVisibleSelected ? "Снять видимые" : "Выбрать видимых"}
                    </Button>
                </div>
                <ScrollArea className="h-48 rounded-md border">
                    <div className="divide-y">
                        {visibleRecipients.length ? visibleRecipients.map(item => <label key={item.id} className="flex min-w-0 items-center gap-3 px-3 py-2 text-sm">
                            <Checkbox checked={selectedIds.includes(item.id)} disabled={!canSelect(item)} onCheckedChange={checked => setSelectedIds(current => checked ? [...current, item.id] : current.filter(id => id !== item.id))} aria-label={`Выбрать ${item.full_name}`} />
                            <span className="min-w-0 flex-1 truncate">{item.full_name}</span>
                            <span className="max-w-32 truncate text-muted-foreground">{!item.available ? "Нет доступа к боту" : selectedSurvey && !canSelect(item) ? "Не подходит" : item.position}</span>
                        </label>) : <p className="p-3 text-sm text-muted-foreground">Сотрудники не найдены</p>}
                    </div>
                </ScrollArea>
                <Button type="button" disabled={submitting || !scenarioKey || selectedIds.length === 0} onClick={launch}><Play aria-hidden="true" /> {submitting ? "Запуск..." : "Запустить опрос"}</Button>
            </> : null}
        </PageSection>
    );
}
