import { CalendarDays, Repeat2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";

type PlanRow = {key: string; title: string; date?: string; status: string; error?: string | null};
type Phase = {title: string; timing: string; expected: string[]; scheduled: PlanRow[]; emptyLabel?: string};

export function GradeDevelopmentRoadmap({phases}: {phases: Phase[]}) {
  const count = phases.reduce((total, phase) => total + phase.scheduled.length, 0);
  return <div className="overflow-hidden rounded-lg border">
    <div className="flex flex-wrap items-center justify-between gap-2 border-b px-4 py-3">
      <span className="text-sm font-medium">Весь план развития</span>
      <Badge variant="outline">{count ? `Действий в плане: ${count}` : "План не настроен"}</Badge>
    </div>
    <ol className="divide-y">
      {phases.map((phase, index) => <li key={phase.title} className="p-4">
        <div className="flex flex-wrap items-center gap-2">
          <span className="grid size-6 shrink-0 place-items-center rounded-full border text-xs">{index + 1}</span>
          <h4 className="text-sm font-semibold">{phase.title}</h4>
          <Badge variant="secondary">{phase.timing}</Badge>
        </div>
        <div className="mt-3 grid gap-3 lg:grid-cols-2">
          <div>
            <h5 className="mb-1 text-xs font-medium text-muted-foreground">Состав этапа</h5>
            <ol className="divide-y">
              {phase.expected.map(title => <li key={title} className="py-2 text-sm">{title}</li>)}
            </ol>
          </div>
          <div>
            <h5 className="mb-1 text-xs font-medium text-muted-foreground">В плане сотрудника</h5>
            {phase.scheduled.length ? <ul className="divide-y">{phase.scheduled.map(row => <li key={row.key} className="space-y-1 py-2">
              <div className="flex flex-wrap items-center justify-between gap-1.5"><span className="text-sm">{row.title}</span>
                <Badge variant={row.error ? "destructive" : "outline"}>{row.status}</Badge></div>
              {row.date && <p className="flex items-center gap-1.5 text-xs text-muted-foreground"><CalendarDays className="size-3" aria-hidden />{row.date} МСК</p>}
              {row.error && <p className="text-xs text-destructive">{row.error}</p>}
            </li>)}</ul> : <p className="py-2 text-sm text-muted-foreground">{phase.emptyLabel ?? "Не запланировано"}</p>}
          </div>
        </div>
      </li>)}
    </ol>
    <div className="flex items-start gap-2 border-t px-4 py-3 text-sm text-muted-foreground">
      <Repeat2 className="mt-0.5 size-4 shrink-0" aria-hidden />
      <p>Разовый старт не повторяется. После фиксации новой итоговой оценки цикл обновляется: даты промежуточной и итоговой встреч считаются заново от этой оценки.</p>
    </div>
  </div>;
}
