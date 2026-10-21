import React from "react";
import { CalendarDays, FileCheck, Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PageSection } from "@/components/ui/page-section";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

type Day = { date: string; is_workday: boolean; is_shortened: boolean; description: string };
type Preview = { year: number; digest: string; expected_version_id: number; changed_days: number; days: Day[]; workdays: number; days_off: number; shortened: number };
type Version = { id: number; year: number; source_name: string; created_at: string; workdays: number; days_off: number; shortened: number; is_current: boolean };

export function ProductionCalendarSettings() {
  const [file, setFile] = React.useState<File | null>(null);
  const [preview, setPreview] = React.useState<Preview | null>(null);
  const [versions, setVersions] = React.useState<Version[]>([]);
  const [busy, setBusy] = React.useState(false);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState("");
  const [message, setMessage] = React.useState("");
  const [revision, setRevision] = React.useState(0);
  React.useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    fetch("/api/settings/production-calendars", { credentials: "same-origin", signal: controller.signal })
      .then(async response => { if (!response.ok) throw new Error("Не удалось загрузить календари"); return response.json(); })
      .then(data => setVersions(data.versions))
      .catch(reason => { if (!controller.signal.aborted) setError(String(reason.message || reason)); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [revision]);
  async function submit(mode: "preview" | "apply") {
    if (!file || busy || (mode === "apply" && !preview)) return;
    const body = new FormData();
    body.append("file", file);
    body.append("mode", mode);
    if (preview) { body.append("expected_digest", preview.digest); body.append("expected_version_id", String(preview.expected_version_id)); }
    setBusy(true); setError(""); setMessage("");
    try {
      const response = await fetch("/api/settings/production-calendars/import", { method: "POST", credentials: "same-origin", body });
      const data = await response.json();
      if (!response.ok) { setPreview(null); throw new Error(typeof data.detail === "string" ? data.detail : "Не удалось прочитать календарь"); }
      if (mode === "preview") setPreview(data);
      else { setMessage(data.message); setPreview(null); setRevision(value => value + 1); }
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Ошибка импорта"); }
    finally { setBusy(false); }
  }
  return <PageSection title="Производственный календарь">
    <div className="flex flex-wrap items-center gap-3">
      <Input className="min-w-0 max-w-md" type="file" accept=".xlsx,.csv" aria-label="Файл производственного календаря" disabled={busy} onChange={event => { setFile(event.target.files?.[0] || null); setPreview(null); setError(""); setMessage(""); }} />
      <Button type="button" variant="outline" disabled={!file || busy} onClick={() => submit("preview")}><FileCheck aria-hidden="true" />{busy ? "Обработка..." : "Предпросмотр"}</Button>
    </div>
    <p className="text-sm text-muted-foreground">XLSX или UTF-8 CSV до 1 МБ. Полный год: date, is_workday (0/1), is_shortened (0/1, необязательно), description. Поддерживается печатный календарь А4 с 12 месяцами. Сохранение не меняет расписания сценариев.</p>
    {error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null}
    {message ? <p role="status" className="text-sm">{message}</p> : null}
    {preview ? <>
      <div className="flex flex-wrap items-center justify-between gap-3"><p className="text-sm"><CalendarDays className="mr-2 inline size-4" aria-hidden="true" />{preview.year}: рабочих {preview.workdays}, выходных {preview.days_off}, сокращённых {preview.shortened}. Изменений: {preview.changed_days}.</p><Button type="button" disabled={busy} onClick={() => submit("apply")}><Save aria-hidden="true" />Сохранить календарь</Button></div>
      <div className="max-h-80 overflow-auto rounded-md border" tabIndex={0} aria-label="Предпросмотр дней календаря"><Table><TableHeader><TableRow><TableHead>Дата</TableHead><TableHead>Статус</TableHead><TableHead>Описание</TableHead></TableRow></TableHeader><TableBody>{preview.days.map(day => <TableRow key={day.date}><TableCell className="whitespace-nowrap">{day.date}</TableCell><TableCell>{day.is_shortened ? "Рабочий, сокращённый" : day.is_workday ? "Рабочий" : "Выходной"}</TableCell><TableCell>{day.description || ""}</TableCell></TableRow>)}</TableBody></Table></div>
    </> : null}
    <h3 className="text-sm font-medium">История версий</h3>
    {loading ? <p role="status">Загрузка...</p> : versions.length ? <Table><TableHeader><TableRow><TableHead>Год</TableHead><TableHead>Файл</TableHead><TableHead>Дата загрузки</TableHead><TableHead>Статус</TableHead></TableRow></TableHeader><TableBody>{versions.map(version => <TableRow key={version.id}><TableCell>{version.year}</TableCell><TableCell className="break-all">{version.source_name}</TableCell><TableCell>{new Date(version.created_at + "Z").toLocaleString("ru-RU")}</TableCell><TableCell>{version.is_current ? "Текущая" : "Предыдущая"}</TableCell></TableRow>)}</TableBody></Table> : <p className="text-sm text-muted-foreground">Календари пока не загружены.</p>}
  </PageSection>;
}
