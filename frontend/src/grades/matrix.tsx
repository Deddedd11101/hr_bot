import { Fragment, useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { ConfirmAction } from "@/components/ui/confirm-action";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Choice, Feedback, Importance, useAction, useUnsaved } from "./components";
import { request } from "./data";
import type { MatrixRow, Workspace } from "./types";

export function Matrix({ workspace, onSaved }: { workspace: Workspace; onSaved: (w: Workspace) => void }) {
  const [spec, setSpec] = useState(String(workspace.specializations.find(s => s.active)?.id || ""));
  const [edits, setEdits] = useState<Record<number, MatrixRow>>({});
  const action = useAction();
  const dirty = Object.keys(edits).length > 0;
  useUnsaved(dirty);
  useEffect(() => {
    if (!dirty && !workspace.specializations.some(s => s.active && String(s.id) === spec)) {
      setSpec(String(workspace.specializations.find(s => s.active)?.id || ""));
    }
  }, [workspace, spec, dirty]);
  const grades = workspace.grades.filter(g => g.active).sort((a, b) => a.rank - b.rank);
  const rows = useMemo(() => Object.fromEntries(workspace.skills.map(skill => [skill.id, {
    skill_id: skill.id,
    importance: workspace.importances.find(i => i.skill_id === skill.id && i.specialization_id === Number(spec))?.importance ?? 1,
    levels: Object.fromEntries(workspace.grades.map(g => [g.slug, workspace.expectations.find(e => e.skill_id === skill.id && e.specialization_id === Number(spec) && e.grade_id === g.id)?.level ?? 0])),
  }])), [workspace, spec]);
  function cell(value: number, label: string, options: number[], change: (v: number) => void, importance = false) {
    return <Select value={String(value)} onValueChange={v => { if (v !== null) change(Number(v)); }} disabled={action.busy}>
      <SelectTrigger aria-label={label} size="sm" className="min-w-14 border-transparent bg-transparent"><SelectValue>{importance ? <Importance value={value} /> : value}</SelectValue></SelectTrigger>
      <SelectContent><SelectGroup>{options.map(n => <SelectItem key={n} value={String(n)}>{importance ? `${n} · ${["", "Обычный", "Ключевой", "Критичный"][n]}` : `${n} · ${["Нет", "Понимание", "Умение", "Экспертиза", "Лидерство"][n]}`}</SelectItem>)}</SelectGroup></SelectContent>
    </Select>;
  }
  return <section className="space-y-4">
    <div className="flex flex-wrap items-end gap-3"><div className="w-72"><Choice label="Специализация" value={spec} options={workspace.specializations.filter(s => s.active).map(s => ({ value: String(s.id), label: s.name }))} onChange={v => { setSpec(v); action.setMessage(""); }} disabled={dirty || action.busy} /></div>
      <Button disabled={!dirty || action.busy} onClick={() => void action.run(async () => { onSaved(await request<Workspace>("/api/grades/matrix", "PUT", { specialization_id: Number(spec), rows: Object.values(edits) })); setEdits({}); })}>{action.busy ? "Сохранение..." : "Сохранить матрицу"}</Button>
      {dirty && <ConfirmAction title="Сбросить изменения матрицы?" description="Несохранённые уровни и важность будут сброшены." actionLabel="Сбросить" onConfirm={() => setEdits({})}><Button variant="outline" disabled={action.busy}>Сбросить</Button></ConfirmAction>}
    </div>
    <Feedback error={action.error} message={dirty ? "Есть несохранённые изменения. Сохраните или сбросьте их перед сменой специализации." : action.message} />
    {!spec ? <p className="p-6 text-center text-muted-foreground">Сначала добавьте специализацию или импортируйте каталог</p> :
      <Table className="table-fixed min-w-[680px]"><TableHeader><TableRow><TableHead className="w-1/3">Навык</TableHead>{grades.map(g => <TableHead key={g.id} className="whitespace-normal">{g.name}</TableHead>)}<TableHead>Важность</TableHead></TableRow></TableHeader>
        <TableBody>{workspace.categories.filter(c => c.active).sort((a, b) => a.sort_order - b.sort_order).map(category => <Fragment key={category.id}>
          <TableRow className="bg-muted/40"><TableCell colSpan={grades.length + 2} className="font-medium whitespace-normal">{category.name}</TableCell></TableRow>
          {workspace.skills.filter(s => s.active && s.category_id === category.id).sort((a, b) => a.sort_order - b.sort_order).map(skill => {
            const row = edits[skill.id] || rows[skill.id];
            return <TableRow key={skill.id} className="border-0"><TableCell className="whitespace-normal break-words">{skill.name}</TableCell>
              {grades.map(g => <TableCell key={g.id}>{cell(row.levels[g.slug], `${skill.name}, ${g.name}`, [0, 1, 2, 3, 4], level => setEdits(e => ({ ...e, [skill.id]: { ...row, levels: { ...row.levels, [g.slug]: level } } })))}</TableCell>)}
              <TableCell>{cell(row.importance, `${skill.name}, важность`, [1, 2, 3], importance => setEdits(e => ({ ...e, [skill.id]: { ...row, importance } })), true)}</TableCell>
            </TableRow>;
          })}
        </Fragment>)}</TableBody></Table>}
    {spec && !workspace.skills.some(s => s.active) && <p className="p-6 text-center text-muted-foreground">Навыков пока нет. Добавьте категории и навыки или импортируйте JSON.</p>}
  </section>;
}
