import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { ConfirmAction } from "@/components/ui/confirm-action";
import { Feedback, useAction } from "./components";

type Plan = {fingerprint: string; rows: {sheet: string; name: string; employee_name: string | null; employee_id: number | null; grade: string | null; assessed: number; missing: number; state: string}[]; templates: {name: string; skills: number}[]; warnings: string[]};
const states: Record<string, string> = {ready: "Готово", existing_review: "Пропуск: уже есть оценка", no_scores: "Нет баллов", unmatched: "Карточка не найдена", ambiguous: "Несколько совпадений", duplicate_employee: "Повтор сотрудника", unknown_grade: "Неизвестный грейд"};

export function InitialGradeImport() {
  const [file, setFile] = useState<File | null>(null);
  const [aliases, setAliases] = useState("{}");
  const [zeroSheets, setZeroSheets] = useState("[]");
  const [plan, setPlan] = useState<Plan | null>(null);
  const [resultMessage, setResultMessage] = useState("");
  const action = useAction();
  async function send(apply: boolean) {
    const data = new FormData();
    data.set("file", file!); data.set("aliases", aliases); data.set("zero_sheets", zeroSheets);
    if (apply) data.set("fingerprint", plan!.fingerprint);
    const response = await fetch(`/api/grades/initial-import${apply ? "" : "-preview"}`, {method: "POST", body: data, credentials: "same-origin"});
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "Импорт не выполнен");
    if (apply) { setPlan(null); setFile(null); setResultMessage(`Импортировано: ${result.imported.length}. Резервная копия: ${result.backup || "не требовалась"}`); }
    else setPlan(result);
  }
  const blocked = plan?.rows.some(row => !["ready", "existing_review", "no_scores"].includes(row.state));
  return <section className="space-y-4 border-t pt-6">
    <h2 className="font-semibold">Первичные оценки из Excel</h2>
    <Input aria-label="Файл первичных оценок" type="file" accept=".xlsx" disabled={action.busy} onChange={event => { setFile(event.target.files?.[0] || null); setPlan(null); }} />
    <details className="space-y-3"><summary className="cursor-pointer text-sm">Сопоставления и пустые требования</summary>
      <label className="block text-sm">Подтверждённые имена (JSON)<Textarea value={aliases} disabled={action.busy} onChange={event => {setAliases(event.target.value); setPlan(null);}} /></label>
      <label className="block text-sm">Листы, где пустое требование означает 0 (JSON-массив)<Input value={zeroSheets} disabled={action.busy} onChange={event => {setZeroSheets(event.target.value); setPlan(null);}} /></label>
    </details>
    <Feedback error={action.error} message={resultMessage || action.message} />
    <Button variant="outline" disabled={!file || action.busy} onClick={() => void action.run(() => send(false), "Предпросмотр готов")}>Проверить первичные оценки</Button>
    {plan && <div className="space-y-3">
      <p className="text-sm text-muted-foreground">Шаблонов: {plan.templates.length}. Сотрудников: {plan.rows.length}. Дата исходных оценок не задаётся; дата записи будет датой импорта.</p>
      <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr className="border-b"><th className="p-2">Имя в файле</th><th className="p-2">Карточка</th><th className="p-2">Грейд</th><th className="p-2">Оценено</th><th className="p-2">Результат</th></tr></thead><tbody>{plan.rows.map((row, index) => <tr key={index} className="border-b"><td className="p-2">{row.name}<div className="text-xs text-muted-foreground">{row.sheet}</div></td><td className="p-2">{row.employee_name || "—"}{row.employee_id && ` · #${row.employee_id}`}</td><td className="p-2">{row.grade || "Не указан"}</td><td className="p-2">{row.assessed} / {row.assessed + row.missing}</td><td className="p-2">{states[row.state] || row.state}</td></tr>)}</tbody></table></div>
      {!!plan.warnings.length && <p className="text-sm text-muted-foreground">{plan.warnings.join("; ")}</p>}
      <ConfirmAction title="Импортировать первичные оценки?" description="Будут созданы завершённые оценки для найденных сотрудников без истории. Существующие оценки не изменятся. Перед записью создаётся резервная копия." actionLabel="Импортировать" onConfirm={() => void action.run(() => send(true), "")}><Button disabled={action.busy || blocked || !plan.rows.some(row => row.state === "ready")}>Импортировать первичные оценки</Button></ConfirmAction>
    </div>}
  </section>;
}
