import { useState } from "react";
import { PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart } from "recharts";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart";
import { ConfirmAction } from "@/components/ui/confirm-action";
import { Progress } from "@/components/ui/progress";
import { Choice, Feedback, Importance, LevelChoice, useAction, useUnsaved } from "@/grades/components";
import { dateLabel, goalFields, goalKey, request } from "@/grades/data";
import type { Assessment } from "@/grades/types";

export function GradeAssessment({ initial, onFinalized, onClose }: { initial: Assessment; onFinalized: () => Promise<void>; onClose: () => void }) {
  const [assessment, setAssessment] = useState(initial);
  const [values, setValues] = useState<Record<number, number>>({});
  const [goal, setGoal] = useState(goalKey(initial));
  const action = useAction();
  const dirty = Object.keys(values).length > 0 || goal !== goalKey(assessment);
  const final = assessment.status === "final";
  useUnsaved(dirty);
  const specName = assessment.catalog.specializations.find(s => s.id === assessment.specialization_id)?.name || "Архивная специализация";
  const goalName = assessment.goal_options.find(g => g.value === goalKey(assessment))?.label || "Нет";
  async function save() {
    const result = await request<Assessment>(`/api/grade-assessments/${assessment.id}`, "PATCH", {
      ...(goal === goalKey(assessment) ? {} : goalFields(goal, assessment.current_grade_id)),
      values: Object.entries(values).map(([id, level]) => ({ skill_id: Number(id), level })),
    });
    setAssessment(result); setValues({}); setGoal(goalKey(result));
  }
  return <section className="space-y-4" aria-label="Оценка навыков">
    <div className="flex flex-wrap items-center justify-between gap-3 border-b pb-4">
      <div><h2 className="text-base font-semibold">Оценка от {dateLabel(assessment.created_at)}</h2><p className="text-muted-foreground">{specName} · {assessment.catalog.grades.find(g => g.id === assessment.current_grade_id)?.name || "Архивный грейд"}</p></div>
      <div className="flex flex-wrap items-center gap-2"><Badge variant={final ? "secondary" : "outline"}>{final ? "Завершена" : "Черновик"}</Badge>
        {dirty ? <ConfirmAction title="Закрыть без сохранения?" description="Несохранённые уровни и цель будут потеряны." actionLabel="Закрыть" onConfirm={onClose}><Button variant="outline" disabled={action.busy}>К истории</Button></ConfirmAction> : <Button variant="outline" disabled={action.busy} onClick={onClose}>К истории</Button>}
      </div>
    </div>
    {!final && <div className="flex flex-wrap items-end gap-3"><div className="w-72 max-w-full"><Choice label="Цель оценки" value={goal} options={assessment.goal_options} onChange={setGoal} disabled={action.busy} /></div>
      <Button disabled={!dirty || action.busy} onClick={() => void action.run(save)}>Сохранить оценку</Button>
      <ConfirmAction title="Завершить оценку?" description="Уровни и требования будут зафиксированы. Изменить эту оценку после завершения нельзя. Грейд сотрудника автоматически не повышается." actionLabel="Завершить оценку" onConfirm={() => void action.run(async () => { const result = await request<Assessment>(`/api/grade-assessments/${assessment.id}/finalize`, "POST"); setAssessment(result); await onFinalized(); }, "Оценка завершена")}>
        <Button variant="outline" disabled={dirty || action.busy || !assessment.scores.length}>Завершить оценку</Button>
      </ConfirmAction>
    </div>}
    <Feedback error={action.error} message={dirty ? "Есть несохранённые изменения. Диаграмма и пробелы показывают последнюю сохранённую оценку." : action.message} />
    <div className="grid min-w-0 gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
      <div className="min-w-0 space-y-5">{assessment.categories.map(category => <section key={category.categoryId}>
        <h3 className="border-b bg-muted/40 px-3 py-2 font-medium break-words">{category.categoryName}</h3>
        {assessment.scores.filter(s => s.categoryId === category.categoryId).map(score => <div key={score.skillId} className="flex flex-wrap items-center justify-between gap-3 border-b px-3 py-3">
          <div className="min-w-0 flex-1"><p className="break-words">{score.skillName}</p><div className="flex items-center gap-2 text-xs text-muted-foreground"><Importance value={score.importance} />{assessment.progress !== null && <span>Цель: {score.targetLevel}</span>}</div></div>
          <LevelChoice label={score.skillName} value={values[score.skillId] ?? score.currentLevel} disabled={final || action.busy} onChange={level => setValues(old => ({ ...old, [score.skillId]: level }))} />
        </div>)}
      </section>)}
      {!assessment.scores.length && <p className="p-4 text-muted-foreground">Нет активных навыков. Проверьте каталог и специализацию.</p>}</div>
      <aside className="min-w-0 space-y-5">
        <h3 className="font-medium">Профиль навыков</h3>
        {!!assessment.categories.length && <ChartContainer config={{ current: { label: "Текущий", color: "var(--primary)" }, target: { label: "Цель", color: "var(--info)" } }} className="aspect-square w-full" aria-label="Радар по категориям: текущие и целевые уровни">
          <RadarChart data={assessment.categories} outerRadius="55%">
            <PolarGrid /><PolarAngleAxis dataKey="categoryName" tickFormatter={name => String(name).length > 12 ? `${String(name).slice(0, 11)}…` : String(name)} /><PolarRadiusAxis domain={[0, 4]} tickCount={5} />
            {assessment.progress !== null && <Radar name="Цель" dataKey="target" stroke="var(--color-target)" fill="var(--color-target)" fillOpacity={0.08} strokeDasharray="4 3" isAnimationActive={false} />}
            <Radar name="Текущий" dataKey="current" stroke="var(--color-current)" fill="var(--color-current)" fillOpacity={0.25} isAnimationActive={false} />
            <ChartTooltip content={<ChartTooltipContent />} />
          </RadarChart>
        </ChartContainer>}
        <dl className="space-y-2 text-sm">{assessment.categories.map(c => <div key={c.categoryId} className="flex justify-between gap-3"><dt className="break-words">{c.categoryName}</dt><dd className="shrink-0 tabular-nums">{c.current.toFixed(1)}{assessment.progress !== null && ` / ${c.target.toFixed(1)}`}</dd></div>)}</dl>
        {assessment.progress === null ? <p className="text-muted-foreground">Цель не задана</p> : <div className="space-y-2"><h3 className="font-medium">Прогресс к цели: {goalName}</h3><p className="text-lg font-semibold tabular-nums">{Math.round(assessment.progress * 100)}%</p><Progress value={assessment.progress * 100} aria-label="Прогресс к цели" /></div>}
        <section className="space-y-2 border-t pt-4"><h3 className="font-medium">Зоны развития</h3>{assessment.gaps.map(g => <div key={g.skillId} className="flex justify-between gap-3 text-sm"><span className="break-words">{g.skillName}</span><span className="shrink-0 tabular-nums">{g.currentLevel} → {g.targetLevel}</span></div>)}{assessment.progress !== null && !assessment.gaps.length && <p className="text-muted-foreground">Пробелов до цели нет</p>}</section>
      </aside>
    </div>
  </section>;
}
