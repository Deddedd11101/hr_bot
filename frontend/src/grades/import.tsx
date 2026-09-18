import { useState } from "react";
import { Button } from "@/components/ui/button";
import { ConfirmAction } from "@/components/ui/confirm-action";
import { Field, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Choice, Feedback, useAction, useUnsaved } from "./components";
import { request } from "./data";
import type { Workspace } from "./types";

type Preview = { specialization: { name: string; action: string }; counts: Record<string, number>; errors: string[] };
const labels: Record<string, string> = { categories: "Категорий", skills: "Навыков", createCategories: "Новых категорий", createSkills: "Новых навыков", updateCategories: "Существующих категорий", updateSkills: "Существующих навыков" };

export function CatalogImport({ workspace, onSaved }: { workspace: Workspace; onSaved: (w: Workspace) => void }) {
  const [source, setSource] = useState("");
  const [target, setTarget] = useState("new");
  const [preview, setPreview] = useState<Preview | null>(null);
  const action = useAction();
  useUnsaved(!!source);
  function invalidate() { setPreview(null); action.setMessage(""); action.setError(""); }
  function body(dryRun: boolean) {
    let catalog: unknown;
    try { catalog = JSON.parse(source); } catch { throw new Error("Некорректный JSON. Проверьте содержимое файла."); }
    return { dryRun, mode: target === "new" ? "create-specialization" : "update-specialization", ...(target === "new" ? {} : { targetSpecializationId: Number(target) }), catalog };
  }
  return <section className="space-y-4">
    <h2 className="text-base font-semibold">Импорт каталога</h2>
    <div className="max-w-lg"><Choice label="Специализация" value={target} onChange={v => { setTarget(v); invalidate(); }} disabled={action.busy} options={[{ value: "new", label: "Создать из файла / объединить по имени" }, ...workspace.specializations.filter(s => s.active).map(s => ({ value: String(s.id), label: s.name }))]} /></div>
    <Field><FieldLabel htmlFor="grade-import-file">Файл JSON</FieldLabel><Input id="grade-import-file" type="file" accept=".json,application/json" disabled={action.busy} onChange={e => { const file = e.target.files?.[0]; if (file) void action.run(async () => { if (file.size > 5_000_000) throw new Error("Файл должен быть меньше 5 МБ"); setSource(await file.text()); setPreview(null); }, "Файл прочитан"); }} /></Field>
    <Field><FieldLabel htmlFor="grade-import-json">Содержимое каталога</FieldLabel><Textarea id="grade-import-json" value={source} onChange={e => { setSource(e.target.value); invalidate(); }} disabled={action.busy} rows={10} className="font-mono" /></Field>
    <Feedback error={action.error} message={action.message} />
    <Button variant="outline" disabled={!source.trim() || action.busy} onClick={() => void action.run(async () => setPreview(await request<Preview>("/api/grades/import", "POST", body(true))), "Предпросмотр готов")}>Проверить импорт</Button>
    {preview && <div className="space-y-3 border-t pt-4">
      <h3 className="font-medium">{preview.specialization.name}</h3>
      <dl className="grid grid-cols-2 gap-2 max-w-lg">{Object.entries(preview.counts).map(([key, value]) => <div key={key}><dt className="text-muted-foreground">{labels[key] || key}</dt><dd className="font-medium tabular-nums">{value}</dd></div>)}</dl>
      {preview.errors.map((error, i) => <Feedback key={i} error={error} />)}
      <ConfirmAction title="Применить импорт?" description="Совпадающие категории и навыки будут объединены, ожидания выбранной специализации обновятся. Завершённые оценки сохранятся." actionLabel="Импортировать" onConfirm={() => void action.run(async () => { await request("/api/grades/import", "POST", body(false)); onSaved(await request<Workspace>("/api/grades/workspace")); setSource(""); setPreview(null); }, "Каталог импортирован")}>
        <Button disabled={action.busy || preview.errors.length > 0}>Применить импорт</Button>
      </ConfirmAction>
    </div>}
  </section>;
}
