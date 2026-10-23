import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Choice, Feedback, useAction } from "@/grades/components";
import { dateLabel, request } from "@/grades/data";
import type { EmployeeGrade } from "@/grades/types";

type Row = {skill_id: number; name: string; category: string; state: string; previous: number | null; current: number | null; delta: number | null};
export function GradeComparison({ employeeId, assessments }: {employeeId: number; assessments: EmployeeGrade["assessments"]}) {
  const finals = assessments.filter(item => item.status === "final");
  const [previous, setPrevious] = useState(String(finals[1]?.id || ""));
  const [current, setCurrent] = useState(String(finals[0]?.id || ""));
  const [rows, setRows] = useState<Row[] | null>(null);
  const action = useAction();
  if (finals.length < 2) return <p className="text-sm text-muted-foreground">Сравнение появится после двух завершённых оценок.</p>;
  const options = finals.map(item => ({value: String(item.id), label: `${dateLabel(item.finalized_at || item.created_at)} · #${item.id}`}));
  const labels: Record<string, string> = {added: "Ранее не оценивалась", removed: "Отсутствует в новой матрице", changed: "Изменился смысл или шкала; напрямую не сравнивается", unassessed: "Не оценена в одном из ревью"};
  return <section className="space-y-4 border-t pt-4"><h2 className="font-semibold">Сравнение оценок</h2>
    <div className="grid gap-3 md:grid-cols-2"><Choice label="Прошлая оценка" value={previous} options={options} onChange={value => { setPrevious(value); setRows(null); }} /><Choice label="Текущая оценка" value={current} options={options} onChange={value => { setCurrent(value); setRows(null); }} /></div>
    <Button variant="outline" disabled={action.busy || !previous || !current || previous === current} onClick={() => void action.run(async () => setRows((await request<{rows: Row[]}>(`/api/employees/${employeeId}/grade/compare?previous_id=${previous}&current_id=${current}`)).rows))}>Сравнить</Button>
    <Feedback error={action.error} />
    {rows && <><div className="flex gap-4 text-xs text-muted-foreground"><span>Прошлая — контур</span><span>Текущая — сплошная</span><span>Шкала 0–4</span></div><ul className="divide-y">{rows.map(row => <li key={row.skill_id} className="space-y-2 py-3"><div className="flex flex-wrap justify-between gap-2"><span className="font-medium">{row.name}</span>{row.delta !== null && <span className="tabular-nums">{row.delta > 0 ? "+" : ""}{row.delta}</span>}</div><p className="text-xs text-muted-foreground">{row.category}</p>
      {row.state === "comparable" ? <div className="space-y-2">{[{label: "Прошлая", value: row.previous!, style: "border border-foreground/50 bg-transparent"}, {label: "Текущая", value: row.current!, style: "bg-primary"}].map(bar => <div key={bar.label} className="grid grid-cols-[5rem_minmax(0,1fr)_2rem] items-center gap-2 text-xs"><span>{bar.label}</span><span className="h-2.5 bg-muted" role="img" aria-label={`${bar.label}: ${bar.value} из 4`}><span className={`block h-full ${bar.style}`} style={{width: `${bar.value / 4 * 100}%`}} /></span><span>{bar.value}</span></div>)}</div> : <p className="text-sm text-muted-foreground">{labels[row.state]}{row.previous !== null ? ` · было ${row.previous}` : ""}{row.current !== null ? ` · сейчас ${row.current}` : ""}</p>}
    </li>)}</ul><p className="text-sm text-muted-foreground">Изменение оценок не означает автоматическое повышение грейда. Общий балл разных матриц не сравнивается.</p></>}
  </section>;
}
