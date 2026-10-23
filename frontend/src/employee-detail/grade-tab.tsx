import { useEffect, useState } from "react";
import { Archive } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ConfirmAction } from "@/components/ui/confirm-action";
import { Feedback, LoadingError, useAction } from "@/grades/components";
import { dateLabel, errorMessage, request } from "@/grades/data";
import type { Assessment, EmployeeGrade } from "@/grades/types";
import { GradeAssessment } from "./grade-assessment";
import { GradeComparison } from "./grade-comparison";
import { GradeReviewForm } from "./grade-review-form";
import { Choice } from "@/grades/components";

export function GradeTab({employeeId}: {employeeId: number}) {
  const [data, setData] = useState<EmployeeGrade | null>(null);
  const [latest, setLatest] = useState<Assessment | null>(null);
  const [view, setView] = useState<Assessment | null>(null);
  const [form, setForm] = useState(false);
  const [draft, setDraft] = useState<Assessment | null>(null);
  const [error, setError] = useState("");
  const [attempt, retry] = useState(0);
  const action = useAction();
  const endpoint = `/api/employees/${employeeId}/grade`;
  async function load(signal?: AbortSignal) {
    const result = await request<EmployeeGrade>(endpoint, "GET", undefined, signal);
    const active = result.assessments.filter(item => item.status !== "archived");
    const newest = result.latest_final || (active[0] ? await request<Assessment>(`/api/grade-assessments/${active[0].id}`, "GET", undefined, signal) : null);
    if (signal?.aborted) return;
    setData(result); setLatest(newest);
  }
  useEffect(() => { const controller = new AbortController(); setError(""); void load(controller.signal).catch(e => { if (!controller.signal.aborted) setError(errorMessage(e)); }); return () => controller.abort(); }, [endpoint, attempt]);
  if (!data) return <LoadingError loading={!error} error={error} retry={() => retry(n => n + 1)} />;
  if (view) return <GradeAssessment initial={view} onClose={() => setView(null)} onFinalized={() => load()} />;
  if (form) return <GradeReviewForm employeeId={employeeId} data={data} draft={draft} onClose={() => setForm(false)} onSaved={async () => { await load(); setForm(false); }} />;
  const active = data.assessments.filter(item => item.status !== "archived");
  const archived = data.assessments.filter(item => item.status === "archived");
  const existingDraft = active.find(item => item.status === "draft");
  async function start() { setDraft(existingDraft ? await request<Assessment>(`/api/grade-assessments/${existingDraft.id}`) : null); setForm(true); }
  return <div className="space-y-6">
    <header className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="font-semibold">Грейд и развитие</h2>{data.profile?.current_grade_id && <p className="text-sm text-muted-foreground">{data.specializations.find(item => item.id === data.profile?.specialization_id)?.name} · {data.grades.find(item => item.id === data.profile?.current_grade_id)?.name}</p>}</div>{active.length > 0 && <Button disabled={action.busy} onClick={() => void action.run(start, "")}>{existingDraft ? "Продолжить оценку" : "Новая оценка"}</Button>}</header>
    <Feedback error={action.error || error} />
    {!active.length ? <div className="space-y-4 py-12 text-center"><p className="text-muted-foreground">Ранее не оценивался</p><Button disabled={action.busy} onClick={() => void action.run(start, "")}>Начать оценку</Button></div> : <div className="grid min-w-0 gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(260px,360px)]">
      <section className="min-w-0 space-y-4"><h3 className="text-sm font-medium">{latest?.status === "draft" ? "Текущая оценка · черновик" : "Последняя оценка"}</h3>
        <GradeComparison key={active.map(item => item.id).join(",")} employeeId={employeeId} assessments={active} latest={latest} />
      </section>
      <section className="min-w-0 space-y-3"><h3 className="text-sm font-medium">История оценок</h3>{active.map(item => <div key={item.id} className="flex items-center justify-between gap-2 border-b py-3"><Button variant="ghost" className="h-auto min-w-0 flex-1 justify-start whitespace-normal text-left" disabled={action.busy} onClick={() => void action.run(async () => { if (item.status === "draft") await start(); else setView(await request<Assessment>(`/api/grade-assessments/${item.id}`)); }, "")}><span>{dateLabel(item.created_at)}<span className="block text-xs text-muted-foreground">{item.status === "draft" ? "Черновик" : "Сохранена"}</span></span></Button>{item.status === "draft" && <ArchiveReview id={item.id} refresh={() => load()} />}</div>)}</section>
    </div>}
    {!!archived.length && <details className="border-t pt-3"><summary className="cursor-pointer text-sm text-muted-foreground">Архив · {archived.length}</summary><div className="mt-3 space-y-2">{archived.map(item => <Button key={item.id} variant="ghost" onClick={() => void action.run(async () => setView(await request<Assessment>(`/api/grade-assessments/${item.id}`)), "")}>{dateLabel(item.created_at)}</Button>)}</div></details>}
    {data.assessments.length > 1 && <PurgeReviews employeeId={employeeId} assessments={data.assessments} refresh={() => load()} />}
  </div>;
}

function PurgeReviews({employeeId, assessments, refresh}: {employeeId: number; assessments: EmployeeGrade["assessments"]; refresh: () => Promise<void>}) {
  const [keep, setKeep] = useState(String(assessments.find(item => item.status !== "archived")?.id || ""));
  const action = useAction();
  return <details className="border-t pt-3"><summary className="cursor-pointer text-sm text-muted-foreground">Управление историей</summary><div className="mt-3 max-w-lg space-y-3"><Choice label="Оставить оценку" value={keep} onChange={setKeep} options={assessments.filter(item => item.status !== "archived").map(item => ({value: String(item.id), label: `${dateLabel(item.created_at)} · ${item.status === "draft" ? "Черновик" : "Сохранена"} · #${item.id}`}))} disabled={action.busy} /><ConfirmAction title="Удалить остальные оценки навсегда?" description="Сначала будет создана и проверена резервная копия БД. Все оценки этого сотрудника, кроме выбранной, будут удалены безвозвратно. Нужны права администратора." actionLabel="Удалить остальные" onConfirm={() => void action.run(async () => { const result = await request<{backup: string}>(`/api/employees/${employeeId}/grade/purge-other-reviews`, "POST", {keep_id: Number(keep), expected_ids: assessments.filter(item => item.id !== Number(keep)).map(item => item.id)}); await refresh(); action.setMessage(`История очищена. Резервная копия: ${result.backup}`); }, "История очищена, резервная копия проверена")}><Button variant="destructive" disabled={!keep || action.busy}>Удалить остальные оценки</Button></ConfirmAction><Feedback error={action.error} message={action.message} /></div></details>;
}

function ArchiveReview({id, refresh}: {id: number; refresh: () => Promise<void>}) {
  const action = useAction();
  return <div><ConfirmAction title="Убрать черновик в архив?" description="Оценки сохранятся только для чтения. Можно будет начать новое ревью." actionLabel="В архив" onConfirm={() => void action.run(async () => { await request(`/api/grade-assessments/${id}/archive`, "POST"); await refresh(); }, "")}><Button variant="ghost" size="icon" title="В архив" aria-label="В архив" disabled={action.busy}><Archive className="size-4" /></Button></ConfirmAction><Feedback error={action.error} /></div>;
}
