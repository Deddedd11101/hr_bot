import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Choice, Feedback, Importance, useAction, useUnsaved } from "@/grades/components";
import { request, errorMessage } from "@/grades/data";
import type { Assessment, EmployeeGrade } from "@/grades/types";

const levels = [{value: "none", label: "Не оценено"}, ...["Нет", "Понимание", "Умение", "Экспертиза", "Лидерство"].map((label, value) => ({value: String(value), label: `${value} · ${label}`}))];

export function GradeReviewForm({employeeId, data, draft, onClose, onSaved}: {employeeId: number; data: EmployeeGrade; draft: Assessment | null; onClose: () => void; onSaved: () => Promise<void>}) {
  const [spec, setSpec] = useState(String(draft?.specialization_id || data.profile?.specialization_id || data.suggested_specialization_id || "none"));
  const [grade, setGrade] = useState(String(draft?.current_grade_id || data.profile?.current_grade_id || "none"));
  const [comment, setComment] = useState("");
  const [assessment, setAssessment] = useState<Assessment | null>(draft);
  const [values, setValues] = useState<Record<number, number | null>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [requestId] = useState(() => crypto.randomUUID());
  const action = useAction();
  useUnsaved(Object.keys(values).length > 0 || !!comment.trim());
  useEffect(() => {
    if (draft) return;
    setAssessment(null); setError("");
    if (spec === "none") { setLoading(false); return; }
    const controller = new AbortController(); setLoading(true);
    request<Assessment>(`/api/employees/${employeeId}/grade/review-preview?specialization_id=${spec}${grade === "none" ? "" : `&grade_id=${grade}`}`, "GET", undefined, controller.signal)
      .then(result => { if (!controller.signal.aborted) setAssessment(result); })
      .catch(e => { if (!controller.signal.aborted) setError(errorMessage(e)); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [employeeId, spec, grade, draft]);
  const scores = assessment?.scores.map(score => ({...score, level: Object.prototype.hasOwnProperty.call(values, score.skillId) ? values[score.skillId] : score.assessed === false ? null : score.currentLevel})) || [];
  const count = scores.filter(score => score.level !== null).length;
  const dirty = Object.keys(values).length > 0 || !!comment.trim();
  return <section className="space-y-5">
    <header className="flex items-center justify-between gap-3"><h2 className="font-semibold">Новая оценка</h2><Button variant="ghost" disabled={action.busy} onClick={() => { if (!dirty || window.confirm("Закрыть без сохранения изменений?")) onClose(); }}>Отмена</Button></header>
    <div className="grid gap-4 md:grid-cols-2"><Choice label="Шаблон оценки" value={spec} options={[{value: "none", label: "Выберите специализацию"}, ...data.specializations.map(item => ({value: String(item.id), label: item.name}))]} disabled={!!draft || action.busy} onChange={value => { if (!Object.keys(values).length || window.confirm("Сменить шаблон и сбросить введённые баллы?")) { setSpec(value); setValues({}); } }} />
      <Choice label="Грейд по результатам оценки (необязательно)" value={grade} options={[{value: "none", label: "Не указан"}, ...data.grades.map(item => ({value: String(item.id), label: item.name}))]} disabled={action.busy} onChange={setGrade} /></div>
    <label className="block space-y-2 text-sm">Комментарий к решению<Input value={comment} maxLength={4000} onChange={event => setComment(event.target.value)} disabled={action.busy} /></label>
    <Feedback error={error || action.error} />
    {loading && <p role="status" className="text-sm text-muted-foreground">Загрузка навыков...</p>}
    {assessment && <div className="space-y-5">{assessment.categories.map(category => <section key={category.categoryId}>
      <h3 className="border-b bg-muted/40 px-3 py-2 text-sm font-medium">{category.categoryName}</h3>
      {scores.filter(score => score.categoryId === category.categoryId).map(score => <div key={score.skillId} className="flex flex-wrap items-center justify-between gap-3 border-b px-3 py-3"><div className="min-w-0 flex-1"><p className="break-words text-sm">{score.skillName}</p><Importance value={score.importance} /></div><div className="w-48 max-w-full"><Choice label={`Оценка: ${score.skillName}`} value={score.level === null ? "none" : String(score.level)} options={levels} disabled={action.busy} onChange={value => setValues(old => ({...old, [score.skillId]: value === "none" ? null : Number(value)}))} /></div></div>)}
    </section>)}</div>}
    <footer className="sticky bottom-0 flex flex-wrap items-center justify-between gap-3 border-t bg-background py-3"><span className="text-sm text-muted-foreground">Оценено {count} из {scores.length}</span><Button disabled={!assessment || loading || action.busy || !count} onClick={() => void action.run(async () => { await request(`/api/employees/${employeeId}/grade/reviews`, "POST", {request_id: requestId, draft_id: draft?.id, specialization_id: Number(spec), current_grade_id: grade === "none" ? null : Number(grade), comment, matrix_version: assessment?.matrix_version, values: scores.map(score => ({skill_id: score.skillId, level: score.level}))}); await onSaved(); }, "")}>{action.busy ? "Сохранение..." : "Сохранить оценку"}</Button></footer>
  </section>;
}
