import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ConfirmAction } from "@/components/ui/confirm-action";
import { Choice, Feedback, Importance, LevelValue, useAction, useUnsaved } from "@/grades/components";
import { dateLabel, request } from "@/grades/data";
import type { Assessment } from "@/grades/types";
import { GradeProfileChart } from "./grade-profile-chart";

const levels = [{ value: "none", label: "Не оценено" }, ...["Нет", "Понимание", "Умение", "Экспертиза", "Лидерство"].map((label, value) => ({ value: String(value), label: `${value} · ${label}` }))];

export function GradeAssessment({ initial, onFinalized, onClose }: { initial: Assessment; onFinalized: () => Promise<void>; onClose: () => void }) {
  const [assessment, setAssessment] = useState(initial);
  const [values, setValues] = useState<Record<number, number | null>>({});
  const action = useAction();
  const dirty = Object.keys(values).length > 0;
  const final = assessment.status !== "draft";
  useUnsaved(dirty);
  const specName = assessment.catalog.specializations.find(s => s.id === assessment.specialization_id)?.name || "Архивная специализация";
  const categories = assessment.categories.filter(category => assessment.scores.some(score => score.categoryId === category.categoryId && score.assessed !== false));
  async function save() {
    const result = await request<Assessment>(`/api/grade-assessments/${assessment.id}`, "PATCH", {
      target_grade_id: null, target_specialization_id: null,
      values: Object.entries(values).map(([id, level]) => ({ skill_id: Number(id), level })),
    });
    setAssessment(result); setValues({});
  }
  return <section className="space-y-4" aria-label="Оценка навыков">
    <div className="flex flex-wrap items-center justify-between gap-3 border-b pb-4">
      <div><h2 className="text-base font-semibold">{assessment.import_source && !assessment.import_source.review_date ? "Импортированная оценка · дата не указана" : `Оценка от ${dateLabel(assessment.import_source?.review_date || assessment.created_at)}`}</h2><p className="text-muted-foreground">{specName} · {assessment.catalog.grades.find(g => g.id === assessment.current_grade_id)?.name || "Архивный грейд"}</p>{assessment.matrix_version && <p className="text-xs text-muted-foreground">Версия матрицы: {assessment.matrix_version.slice(0, 12)}</p>}</div>
      <div className="flex flex-wrap items-center gap-2"><Badge variant={final ? "secondary" : "outline"}>{assessment.status === "archived" ? "Архив" : final ? "Завершена" : "Черновик"}</Badge>
        {dirty ? <ConfirmAction title="Закрыть без сохранения?" description="Несохранённые оценки будут потеряны." actionLabel="Закрыть" onConfirm={onClose}><Button variant="outline" disabled={action.busy}>К истории</Button></ConfirmAction> : <Button variant="outline" disabled={action.busy} onClick={onClose}>К истории</Button>}
      </div>
    </div>
    {!final && <div className="flex flex-wrap gap-3">
      <Button disabled={!dirty || action.busy} onClick={() => void action.run(save)}>Сохранить оценку</Button>
      <ConfirmAction title="Завершить оценку?" description="Оценки и матрица будут зафиксированы. Неоценённые навыки не считаются нулями. Грейд автоматически не изменится." actionLabel="Завершить оценку" onConfirm={() => void action.run(async () => { const result = await request<Assessment>(`/api/grade-assessments/${assessment.id}/finalize`, "POST"); setAssessment(result); await onFinalized(); }, "Оценка завершена")}>
        <Button variant="outline" disabled={dirty || action.busy || !assessment.scores.length}>Завершить оценку</Button>
      </ConfirmAction>
    </div>}
    <Feedback error={action.error} message={dirty ? "Есть несохранённые изменения. График показывает последнюю сохранённую оценку." : action.message} />
    {assessment.review_comment && <p className="text-sm text-muted-foreground">{assessment.review_comment}</p>}
    <div className="grid min-w-0 gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
      <div className="min-w-0 space-y-5">{assessment.categories.map(category => <section key={category.categoryId}>
        <h3 className="border-b bg-muted/40 px-3 py-2 font-medium break-words">{category.categoryName}</h3>
        {assessment.scores.filter(s => s.categoryId === category.categoryId).map(score => {
          const value = Object.prototype.hasOwnProperty.call(values, score.skillId) ? values[score.skillId] : score.assessed === false ? null : score.currentLevel;
          return <div key={score.skillId} className="flex flex-wrap items-center justify-between gap-3 border-b px-3 py-3">
            <div className="min-w-0 flex-1"><p className="break-words">{score.skillName}</p><Importance value={score.importance} /></div>
            {final ? value === null ? <span className="text-sm text-muted-foreground">Не оценено</span> : <LevelValue value={value} /> : <div className="w-48 max-w-full"><Choice label={`Уровень: ${score.skillName}`} value={value === null ? "none" : String(value)} options={assessment.review_mode === "historical" ? levels : levels.slice(1)} disabled={action.busy} onChange={value => setValues(old => ({ ...old, [score.skillId]: value === "none" ? null : Number(value) }))} /></div>}
          </div>;
        })}
      </section>)}
      {!assessment.scores.length && <p className="p-4 text-muted-foreground">В матрице нет навыков.</p>}</div>
      <aside className="min-w-0 space-y-5"><h3 className="font-medium">Фактическая оценка</h3>
        <GradeProfileChart categories={categories} withTarget={false} />
        <dl className="space-y-2 text-sm">{categories.map(category => <div key={category.categoryId} className="flex justify-between gap-3"><dt>{category.categoryName}</dt><dd className="shrink-0 tabular-nums">{category.current.toFixed(1)}</dd></div>)}</dl>
        <p className="text-sm text-muted-foreground">Оценено {assessment.scores.filter(score => score.assessed !== false).length} из {assessment.scores.length}. Неоценённые навыки исключены из средних.</p>
      </aside>
    </div>
  </section>;
}
