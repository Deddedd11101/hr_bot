import { useEffect, useState } from "react";
import { Choice, Feedback } from "@/grades/components";
import { dateLabel, errorMessage, request } from "@/grades/data";
import type { Assessment, EmployeeGrade } from "@/grades/types";
import { GradeProfileChart } from "./grade-profile-chart";

type Row = {skill_id: number; name: string; category: string; state: string; previous: number | null; current: number | null; delta: number | null};
type Comparison = {rows: Row[]; categories: Assessment["categories"]};
export function GradeComparison({employeeId, assessments, latest}: {employeeId: number; assessments: EmployeeGrade["assessments"]; latest: Assessment | null}) {
  const finals = assessments.filter(item => item.status === "final");
  const [previous, setPrevious] = useState("none");
  const [current, setCurrent] = useState(String(finals[0]?.id || "none"));
  const [selected, setSelected] = useState(latest);
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    if (current === "none") return;
    const controller = new AbortController(); setBusy(true); setError(""); setComparison(null);
    const load = async () => {
      if (previous !== "none") {
        const result = await request<Comparison>(`/api/employees/${employeeId}/grade/compare?previous_id=${previous}&current_id=${current}`, "GET", undefined, controller.signal);
        if (!controller.signal.aborted) setComparison(result);
      } else {
        const result = await request<Assessment>(`/api/grade-assessments/${current}`, "GET", undefined, controller.signal);
        if (!controller.signal.aborted) setSelected(result);
      }
    };
    void load().catch(e => { if (!controller.signal.aborted) setError(errorMessage(e)); }).finally(() => { if (!controller.signal.aborted) setBusy(false); });
    return () => controller.abort();
  }, [current, previous, employeeId]);
  const categories = comparison?.categories || selected?.categories.filter(category => selected.scores.some(score => score.categoryId === category.categoryId && score.assessed !== false)) || [];
  const options = finals.map(item => ({value: String(item.id), label: `${dateLabel(item.finalized_at || item.created_at)} · #${item.id}`}));
  const labels: Record<string, string> = {added: "Добавлена", removed: "Удалена из новой матрицы", changed: "Изменились критерии — не сравнивается", unassessed: "Не оценена в одном из ревью"};
  return <div className="space-y-4">
    {busy ? <div role="status" className="flex aspect-[4/3] max-w-96 items-center justify-center text-sm text-muted-foreground">Загрузка оценки...</div> : !error && <GradeProfileChart categories={categories} withTarget={!!comparison} secondaryLabel="Прошлая" />}
    <Feedback error={error} />
    {finals.length > 1 && <div className="grid gap-3 md:grid-cols-2"><Choice label="Оценка на графике" value={current} options={options} onChange={value => { setCurrent(value); if (value === previous) setPrevious("none"); }} /><Choice label="Сравнить с" value={previous} options={[{value: "none", label: "Не сравнивать"}, ...options.filter(item => item.value !== current)]} onChange={setPrevious} /></div>}
    {comparison && <details className="border-t pt-3"><summary className="cursor-pointer text-sm">Изменения по навыкам</summary><p className="mt-2 text-xs text-muted-foreground">На графике только сопоставимые навыки; веса обеих оценок взяты из прошлой матрицы.</p><ul className="mt-2 divide-y">{comparison.rows.map(row => <li key={row.skill_id} className="flex flex-wrap justify-between gap-2 py-2 text-sm"><span>{row.name}</span><span className="text-muted-foreground">{row.state === "comparable" ? `${row.previous} → ${row.current} (${row.delta! > 0 ? "+" : ""}${row.delta})` : labels[row.state]}</span></li>)}</ul></details>}
  </div>;
}
