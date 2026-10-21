import React from "react";
import { Download, RefreshCcw } from "lucide-react";
import { Button, buttonVariants } from "@/components/ui/button";
import { PageSection } from "@/components/ui/page-section";

type Run = { id: number; title: string; started_at: string; status: string; answer_count: number; download_url: string | null };
const statuses: Record<string, string> = { in_progress: "В процессе", completed: "Завершён", interrupted: "Прерван" };

export function EmployeeScenarioResults({ employeeId }: { employeeId: number }) {
    const [runs, setRuns] = React.useState<Run[]>([]);
    const [loading, setLoading] = React.useState(true);
    const [error, setError] = React.useState("");
    const [revision, setRevision] = React.useState(0);
    React.useEffect(() => {
        const controller = new AbortController();
        setLoading(true);
        setError("");
        fetch(`/api/employees/${employeeId}/scenario-results`, { credentials: "same-origin", signal: controller.signal })
            .then(async response => {
                if (!response.ok) throw new Error("Не удалось загрузить результаты сценариев.");
                return response.json() as Promise<{ runs: Run[] }>;
            })
            .then(data => setRuns(data.runs))
            .catch(reason => { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "Ошибка загрузки"); })
            .finally(() => { if (!controller.signal.aborted) setLoading(false); });
        return () => controller.abort();
    }, [employeeId, revision]);
    return <PageSection title="Результаты сценариев" action={<Button type="button" variant="ghost" size="sm" disabled={loading} onClick={() => setRevision(value => value + 1)}><RefreshCcw aria-hidden="true" />Обновить</Button>}>
        {loading ? <p role="status">Загрузка...</p> : error ? <p role="alert">{error}</p> : runs.length === 0 ? <p className="text-sm text-muted-foreground">Результатов пока нет.</p> : <ul className="divide-y">
            {runs.map(run => <li key={run.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                <div className="min-w-0"><p className="break-words font-medium">{run.title}</p><p className="text-sm text-muted-foreground">{new Date(run.started_at + (/[Zz]|[+-]\d\d:\d\d$/.test(run.started_at) ? "" : "Z")).toLocaleString("ru-RU")} · {statuses[run.status] || run.status} · Ответов: {run.answer_count}</p></div>
                {run.download_url ? <a className={buttonVariants({ variant: "outline", size: "sm" })} href={run.download_url}><Download aria-hidden="true" />Excel</a> : null}
            </li>)}
        </ul>}
    </PageSection>;
}
