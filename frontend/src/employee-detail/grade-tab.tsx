import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Choice, Feedback, LoadingError, useAction, useUnsaved } from "@/grades/components";
import { dateLabel, errorMessage, request } from "@/grades/data";
import type { Assessment, EmployeeGrade, Profile } from "@/grades/types";
import { GradeAssessment } from "./grade-assessment";
import { GradeComparison } from "./grade-comparison";
import { Input } from "@/components/ui/input";
import { ConfirmAction } from "@/components/ui/confirm-action";

const empty: Profile = { specialization_id: null, current_grade_id: null, target_grade_id: null, target_specialization_id: null };

export function GradeTab({ employeeId }: { employeeId: number }) {
  const [data, setData] = useState<EmployeeGrade | null>(null);
  const [profile, setProfile] = useState<Profile>(empty);
  const [dirty, setDirty] = useState(false);
  const [comment, setComment] = useState("");
  const [error, setError] = useState("");
  const [attempt, retry] = useState(0);
  const [assessment, setAssessment] = useState<Assessment | null>(null);
  const action = useAction();
  const endpoint = `/api/employees/${employeeId}/grade`;
  useUnsaved(dirty || !!comment.trim());
  function apply(result: EmployeeGrade) { setData(result); setProfile(result.profile || empty); setDirty(false); }
  useEffect(() => {
    const controller = new AbortController(); setError("");
    request<EmployeeGrade>(endpoint, "GET", undefined, controller.signal).then(apply).catch(e => { if (!controller.signal.aborted) setError(errorMessage(e)); });
    return () => controller.abort();
  }, [endpoint, attempt]);
  async function refresh() { apply(await request<EmployeeGrade>(endpoint)); }
  if (!data) return <LoadingError loading={!error} error={error} retry={() => retry(n => n + 1)} />;
  if (assessment) return <GradeAssessment key={assessment.id} initial={assessment} onClose={() => setAssessment(null)} onFinalized={refresh} />;
  const existingDraft = data.assessments.find(a => a.status === "draft");
  function edit(next: Profile) { setProfile(next); setDirty(true); action.setMessage(""); }
  return <div className="space-y-6">
    <section className="space-y-4">
      <h2 className="text-base font-semibold">Профиль грейда</h2>
      <div className="grid gap-3 md:grid-cols-2">
        <Choice label="Специализация" value={String(profile.specialization_id || "none")} options={[{ value: "none", label: "Не выбрана" }, ...data.specializations.map(s => ({ value: String(s.id), label: s.name })), ...(profile.specialization_id && !data.specializations.some(s => s.id === profile.specialization_id) ? [{ value: String(profile.specialization_id), label: "Архивная специализация" }] : [])]} disabled={action.busy} onChange={v => edit({ ...profile, specialization_id: v === "none" ? null : Number(v), target_grade_id: null, target_specialization_id: null })} />
        <Choice label="Текущий грейд" value={String(profile.current_grade_id || "none")} options={[{ value: "none", label: "Не выбран" }, ...data.grades.map(g => ({ value: String(g.id), label: g.name })), ...(profile.current_grade_id && !data.grades.some(g => g.id === profile.current_grade_id) ? [{ value: String(profile.current_grade_id), label: "Архивный грейд" }] : [])]} disabled={action.busy} onChange={v => edit({ ...profile, current_grade_id: v === "none" ? null : Number(v), target_grade_id: null, target_specialization_id: null })} />
      </div>
      {data.suggested_specialization_id && !profile.specialization_id && <Button variant="outline" disabled={action.busy} onClick={() => edit({ ...profile, specialization_id: data.suggested_specialization_id })}>Выбрать по должности: {data.specializations.find(s => s.id === data.suggested_specialization_id)?.name}</Button>}
      <label className="block max-w-xl space-y-2 text-sm">Комментарий к решению по грейду<Input value={comment} maxLength={4000} onChange={event => setComment(event.target.value)} /></label>
      <div className="flex flex-wrap gap-2"><Button disabled={(!dirty && !comment.trim()) || action.busy} onClick={() => void action.run(async () => { apply(await request<EmployeeGrade>(endpoint, "PUT", { specialization_id: profile.specialization_id, current_grade_id: profile.current_grade_id, target_grade_id: null, target_specialization_id: null, comment })); setComment(""); })}>Сохранить решение</Button>
        <Button variant="outline" disabled={dirty || action.busy || (!existingDraft && (!profile.specialization_id || !profile.current_grade_id))} onClick={() => void action.run(async () => { const result = await request<Assessment>(`${endpoint}/assessments`, "POST"); await refresh(); setAssessment(result); }, "")}>{existingDraft ? "Продолжить оценку" : "Начать оценку"}</Button>
      </div>
      <Feedback error={action.error} message={dirty ? "Профиль изменён. Сохраните его перед началом оценки." : action.message} />
    </section>
    <GradeComparison key={data.assessments.filter(item => item.status === "final").map(item => item.id).join(",")} employeeId={employeeId} assessments={data.assessments} />
    {!!data.decisions?.length && <section className="space-y-2 border-t pt-4"><h2 className="font-semibold">История назначений грейда</h2>{data.decisions.map(item => { const labels = JSON.parse(item.labels_json); return <div key={item.id} className="border-b py-3 text-sm"><p>{dateLabel(item.created_at)} · {labels.previous_grade || "Не назначен"} → {labels.grade || "Не назначен"} · {labels.specialization || "Без специализации"}</p>{item.comment && <p className="text-muted-foreground">{item.comment}</p>}</div>; })}</section>}
    <section className="space-y-3 border-t pt-4"><h2 className="text-base font-semibold">История оценок</h2>
      {!data.assessments.length && <p className="text-muted-foreground">Оценок пока нет</p>}
      {data.assessments.map(a => <div key={a.id} className="flex flex-wrap items-center justify-between gap-3 border-b py-3"><div><p>{dateLabel(a.created_at)}</p><Badge variant="outline">{a.status === "final" ? "Завершена" : a.status === "archived" ? "Архив" : "Черновик"}</Badge></div><div className="flex gap-2"><Button variant="outline" disabled={dirty || action.busy} onClick={() => void action.run(async () => setAssessment(await request<Assessment>(`/api/grade-assessments/${a.id}`)), "")}>Открыть оценку</Button>{a.status === "draft" && <ConfirmAction title="Убрать черновик в архив?" description="Оценки сохранятся в истории только для чтения. Можно будет начать новое ревью." actionLabel="В архив" onConfirm={() => void action.run(async () => { await request(`/api/grade-assessments/${a.id}/archive`, "POST"); await refresh(); }, "Черновик сохранён в архиве")}><Button variant="outline" disabled={dirty || action.busy}>В архив</Button></ConfirmAction>}</div></div>)}
    </section>
  </div>;
}
