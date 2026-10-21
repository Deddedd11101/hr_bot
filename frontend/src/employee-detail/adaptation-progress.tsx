import { PageSection } from "@/components/ui/page-section";

type Stage = { key: string; title: string; status: string };
const labels: Record<string, string> = { completed: "Завершён", in_progress: "В процессе", not_started: "Не запускался", delivery_error: "Ошибка доставки" };

export function AdaptationProgress({ stages }: { stages: Stage[] }) {
    const completed = stages.filter(stage => stage.status === "completed").length;
    return <PageSection title="Прохождение адаптации">
        {stages.length ? <>
            <p className="text-sm text-muted-foreground">Завершено {completed} из {stages.length}</p>
            <progress className="h-2 w-full accent-primary" value={completed} max={stages.length} aria-label="Завершённые сценарии адаптации" />
            <ul className="divide-y">{stages.map(stage => <li key={stage.key} className="flex flex-wrap justify-between gap-2 py-2 text-sm"><span>{stage.title}</span><span className="text-muted-foreground">{labels[stage.status] || stage.status}</span></li>)}</ul>
        </> : <p className="text-sm text-muted-foreground">Сценарии адаптации пока не назначены.</p>}
    </PageSection>;
}
