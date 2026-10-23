import { useState } from "react";
import { Button } from "@/components/ui/button";
import { ConfirmAction } from "@/components/ui/confirm-action";
import { Field, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Choice, Feedback, useAction, useUnsaved } from "./components";
import { request } from "./data";
import type { Workspace } from "./types";

type Preview = { specialization: { name: string; action: string }; counts: Record<string, number>; errors: string[]; fingerprint: string; changes: {id: number | null; name: string; previous_name: string | null; state: string; change_kind: string; definition_changed: boolean; changed_levels: Record<string, {previous: number | null; current: number}>; importance_changed: boolean}[]; missing_ids: number[] };
const labels: Record<string, string> = { categories: "Категорий", skills: "Навыков", createCategories: "Новых категорий", createSkills: "Новых навыков", updateCategories: "Существующих категорий", updateSkills: "Существующих навыков" };

export function CatalogImport({ workspace, onSaved }: { workspace: Workspace; onSaved: (w: Workspace) => void }) {
  const [source, setSource] = useState("");
  const [target, setTarget] = useState("new");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [sheet, setSheet] = useState("Системный аналитик");
  const [blankZero, setBlankZero] = useState(false);
  const [workbookNotice, setWorkbookNotice] = useState("");
  const action = useAction();
  useUnsaved(!!source);
  function invalidate() { setPreview(null); action.setMessage(""); action.setError(""); }
  function exportTemplate() {
    const spec = workspace.specializations.find(item => String(item.id) === target);
    if (!spec) return;
    const ids = spec.skill_ids_json ? new Set<number>(JSON.parse(spec.skill_ids_json)) : null;
    const catalog = {specialization: {name: spec.name}, categories: workspace.categories.filter(item => item.active).map(category => ({name: category.name, skills: workspace.skills.filter(skill => skill.active && skill.category_id === category.id && (!ids || ids.has(skill.id))).map(skill => ({id: skill.id, name: skill.name, importance: workspace.importances.find(item => item.skill_id === skill.id && item.specialization_id === spec.id)?.importance || 1, levels: Object.fromEntries(workspace.grades.filter(item => item.active).map(grade => [grade.slug, workspace.expectations.find(item => item.skill_id === skill.id && item.specialization_id === spec.id && item.grade_id === grade.id)?.level || 0])), change_kind: "semantic", description: (skill as typeof skill & {description?: string}).description || null}))})).filter(category => category.skills.length)};
    const url = URL.createObjectURL(new Blob([JSON.stringify(catalog, null, 2)], {type: "application/json"}));
    const link = document.createElement("a"); link.href = url; link.download = `grade-${spec.slug}.json`; link.click(); URL.revokeObjectURL(url);
  }
  function body(dryRun: boolean) {
    let catalog: unknown;
    try { catalog = JSON.parse(source); } catch { throw new Error("Некорректный JSON. Проверьте содержимое файла."); }
    return { dryRun, expectedFingerprint: preview?.fingerprint, mode: target === "new" ? "create-specialization" : "update-specialization", ...(target === "new" ? {} : { targetSpecializationId: Number(target) }), catalog };
  }
  return <section className="space-y-4">
    <h2 className="text-base font-semibold">Импорт каталога</h2>
    <div className="max-w-lg"><Choice label="Специализация" value={target} onChange={v => { setTarget(v); invalidate(); }} disabled={action.busy} options={[{ value: "new", label: "Создать из файла / объединить по имени" }, ...workspace.specializations.filter(s => s.active).map(s => ({ value: String(s.id), label: s.name }))]} /></div>
    <Button variant="outline" disabled={target === "new" || action.busy} onClick={exportTemplate}>Скачать шаблон с ID компетенций</Button>
    <div className="grid max-w-xl gap-3"><Field><FieldLabel htmlFor="grade-import-sheet">Лист Excel</FieldLabel><Input id="grade-import-sheet" value={sheet} onChange={event => setSheet(event.target.value)} disabled={action.busy} /></Field><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={blankZero} onChange={event => setBlankZero(event.target.checked)} disabled={action.busy} />Пустые требования шаблона считать «Нет / 0»</label></div>
    <Field><FieldLabel htmlFor="grade-import-file">Файл JSON или Excel</FieldLabel><Input id="grade-import-file" type="file" accept=".json,.xlsx,application/json,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" disabled={action.busy} onChange={e => { const file = e.target.files?.[0]; if (file) void action.run(async () => {
      if (file.size > 5_000_000) throw new Error("Файл должен быть меньше 5 МБ");
      if (file.name.toLowerCase().endsWith(".xlsx")) {
        const body = new FormData(); body.set("file", file); body.set("sheet", sheet); body.set("blank_requirements_zero", String(blankZero));
        const response = await fetch("/api/grades/workbook-preview", {method: "POST", body, credentials: "same-origin"});
        const result = await response.json(); if (!response.ok) throw new Error(result.detail || "Не удалось прочитать Excel");
        setSource(JSON.stringify(result.catalog, null, 2));
        setWorkbookNotice(`Прочитан лист «${result.sheet}». Найдено колонок сотрудников: ${result.assessment_candidates.length}. Личные оценки не импортируются вместе с шаблоном. ${result.warnings.join("; ")}`);
      } else { setSource(await file.text()); setWorkbookNotice(""); }
      setPreview(null);
    }, "Файл прочитан"); }} /></Field>
    {workbookNotice && <p role="status" className="text-sm text-muted-foreground">{workbookNotice}</p>}
    <Field><FieldLabel htmlFor="grade-import-json">Содержимое каталога</FieldLabel><Textarea id="grade-import-json" value={source} onChange={e => { setSource(e.target.value); invalidate(); }} disabled={action.busy} rows={10} className="font-mono" /></Field>
    <Feedback error={action.error} message={action.message} />
    <Button variant="outline" disabled={!source.trim() || action.busy} onClick={() => void action.run(async () => setPreview(await request<Preview>("/api/grades/import", "POST", body(true))), "Предпросмотр готов")}>Проверить импорт</Button>
    {preview && <div className="space-y-3 border-t pt-4">
      <h3 className="font-medium">{preview.specialization.name}</h3>
      <dl className="grid grid-cols-2 gap-2 max-w-lg">{Object.entries(preview.counts).map(([key, value]) => <div key={key}><dt className="text-muted-foreground">{labels[key] || key}</dt><dd className="font-medium tabular-nums">{value}</dd></div>)}</dl>
      {preview.errors.map((error, i) => <Feedback key={i} error={error} />)}
      <ul className="max-h-64 overflow-y-auto divide-y text-sm">{preview.changes.map((item, index) => <li key={index} className="py-2">{item.previous_name && item.previous_name !== item.name ? `${item.previous_name} → ` : ""}{item.name} · {item.state === "added" ? "Новая компетенция" : item.state === "changed" ? item.definition_changed ? item.change_kind === "editorial" ? "Редактура" : "Новая смысловая версия" : "Изменены требования или важность" : "Совпадает по ID или точному имени"}{!!Object.keys(item.changed_levels).length && <p className="text-xs text-muted-foreground">{Object.entries(item.changed_levels).map(([grade, level]) => `${grade}: ${level.previous ?? "—"} → ${level.current}`).join(", ")}</p>}</li>)}</ul>
      {!!preview.missing_ids.length && <p className="text-sm text-muted-foreground">Отсутствуют в новом шаблоне: {preview.missing_ids.join(", ")}. Из старых оценок они не удаляются.</p>}
      <ConfirmAction title="Применить импорт?" description="Совпадающие категории и навыки будут объединены, ожидания выбранной специализации обновятся. Завершённые оценки сохранятся." actionLabel="Импортировать" onConfirm={() => void action.run(async () => { await request("/api/grades/import", "POST", body(false)); onSaved(await request<Workspace>("/api/grades/workspace")); setSource(""); setPreview(null); }, "Каталог импортирован")}>
        <Button disabled={action.busy || preview.errors.length > 0}>Применить импорт</Button>
      </ConfirmAction>
    </div>}
  </section>;
}
