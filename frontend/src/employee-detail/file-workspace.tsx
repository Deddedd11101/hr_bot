import { useEffect, useMemo, useState } from "react";
import { Download, ExternalLink } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { PageSection } from "@/components/ui/page-section";
import { Input } from "@/components/ui/input";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";
import { Choice } from "@/grades/components";
import { dateLabel } from "@/grades/data";
import { errorMessage, request } from "@/grades/data";
import { RecordPager } from "./record-lists";

type FileRow = {id: string; name: string; group: string; purpose: string; source: string; url: string; isFile: boolean; at: string; size?: number; category?: string};
const purposes: Record<string,string> = {resume: "Резюме", offer: "Оффер", test_task_result: "Ответ на тестовое", test_result: "Ответ на тестовое", test_task_explanation: "Пояснение к тестовому", test_explanation: "Пояснение к тестовому", probation_plan: "План ИС", ipr: "План ИПР", hr_file: "Дополнительный файл", candidate_file: "Ответ в боте", inn: "ИНН", snils: "СНИЛС", passport: "Паспорт"};
const groupOptions = [{value: "all", label: "Все документы"}, {value: "hiring", label: "Найм"}, {value: "development", label: "Адаптация и развитие"}, {value: "other", label: "Прочие файлы и ссылки"}];
function groupFor(slot: string) {return ["resume", "offer", "test_task_result", "test_result", "test_task_explanation", "test_explanation"].includes(slot) ? "hiring" : ["ipr", "probation_plan", "feedback"].includes(slot) ? "development" : "other";}
function safeUrl(raw: unknown) {
  const value = typeof raw === "string" ? raw.trim() : "";
  if (value.startsWith("/") && !value.startsWith("//") && !value.includes("\\")) return value;
  try {const parsed = new URL(value); return ["https:", "http:"].includes(parsed.protocol) ? value : "";} catch {return "";}
}
function fileSize(value?: number) {return value == null ? "—" : value < 1024 ? `${value} Б` : value < 1048576 ? `${(value / 1024).toFixed(1)} КБ` : `${(value / 1048576).toFixed(1)} МБ`;}

export function EmployeeFileWorkspace({payload}: {payload: any}) {
  const [group, setGroup] = useState("all");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const rows = useMemo(() => {
    const result: FileRow[] = (payload.files || []).map((file: any) => ({id: `file:${file.id}`, name: file.original_filename || `Файл №${file.id}`, group: groupFor(file.category), purpose: purposes[file.category] || file.category || "Дополнительный файл", source: file.direction === "inbound" ? "Получено через бота" : "Загружено HR", url: safeUrl(file.download_url), isFile: true, at: file.created_at || "", size: file.file_size, category: file.category}));
    const byId = new Map(result.map(item => [item.id, item]));
    const links = [...(payload.document_links || []), payload.resume_document, payload.offer_document, payload.test_task_result, payload.test_task_explanation, payload.probation_plan_document].filter(Boolean);
    const seenLinks = new Set<string>();
    for (const document of links) {
      const slot = document.slot_key || (document === payload.resume_document ? "resume" : document === payload.offer_document ? "offer" : document === payload.test_task_result ? "test_task_result" : document === payload.test_task_explanation ? "test_task_explanation" : document === payload.probation_plan_document ? "probation_plan" : "");
      const url = safeUrl(document.download_url || document.open_url || document.url);
      const file = byId.get(`file:${document.employee_file_id}`);
      if (file) {if (slot) {file.purpose = purposes[slot] || slot; file.group = groupFor(slot);} continue;}
      if (!url || seenLinks.has(url)) continue;
      seenLinks.add(url);
      result.push({id: `link:${document.id || result.length}:${url}`, name: document.original_filename || document.title || document.label || purposes[slot] || "Документ", group: groupFor(slot), purpose: purposes[slot] || "Документ", source: "Документ карточки", url, isFile: document.kind === "file" || !!document.download_url, at: document.created_at || "", size: document.file_size});
    }
    for (const [key, purpose, slot] of [["adaptation_tasks_url", "План ИС", "probation_plan"], ["ipr_url", "План ИПР", "ipr"], ["adaptation_feedback_url", "Обратная связь", "feedback"]]) {
      const url = safeUrl(payload.employee?.[key]);
      if (url && !seenLinks.has(url) && !result.some(item => item.url === url)) {seenLinks.add(url); result.push({id: key, name: purpose, group: groupFor(slot), purpose, source: "Ссылка из карточки", url, isFile: false, at: ""});}
    }
    return result.sort((a, b) => b.at.localeCompare(a.at) || b.id.localeCompare(a.id));
  }, [payload]);
  const filtered = rows.filter(item => (group === "all" || group === item.group) && `${item.name} ${item.purpose}`.toLocaleLowerCase("ru").includes(query.trim().toLocaleLowerCase("ru")));
  const pages = Math.ceil(filtered.length / 20);
  const currentPage = Math.min(page, Math.max(1, pages));
  return <PageSection title="Файлы и документы" counter={rows.length} contentClassName="gap-4">
    <div className="grid gap-3 sm:grid-cols-2"><Choice label="Раздел" value={group} options={groupOptions} onChange={value => {setGroup(value); setPage(1);}} /><label className="block space-y-1 text-sm"><span>Поиск</span><Input type="search" value={query} onChange={event => {setQuery(event.target.value); setPage(1);}} placeholder="Название или назначение" /></label></div>
    <Table className="min-w-[640px] table-fixed"><TableHeader><TableRow><TableHead>Документ</TableHead><TableHead className="w-40">Источник</TableHead><TableHead className="w-32">Дата · МСК</TableHead><TableHead className="w-20">Размер</TableHead><TableHead className="w-16"><span className="sr-only">Действия</span></TableHead></TableRow></TableHeader><TableBody>{filtered.slice((currentPage - 1) * 20, currentPage * 20).map(item => <TableRow key={item.id}><TableCell className="whitespace-normal break-words [overflow-wrap:anywhere]"><p className="font-medium">{item.name}</p><p className="text-xs text-muted-foreground">{item.purpose} · {item.isFile ? item.name.split(".").length > 1 ? item.name.split(".").pop()?.toUpperCase() : "Файл" : "Ссылка"}</p></TableCell><TableCell className="text-xs whitespace-normal">{item.source}</TableCell><TableCell className="text-xs whitespace-normal">{item.at ? dateLabel(item.at) : "Не зафиксирована"}</TableCell><TableCell className="text-xs">{fileSize(item.size)}</TableCell><TableCell>{item.url && <a className={buttonVariants({variant: "outline", size: "icon-sm"})} href={item.url} title={item.isFile ? "Скачать" : "Открыть ссылку"} aria-label={`${item.isFile ? "Скачать" : "Открыть"}: ${item.name}`} {...(!item.isFile ? {target: "_blank", rel: "noopener noreferrer"} : {})}>{item.isFile ? <Download /> : <ExternalLink />}</a>}</TableCell></TableRow>)}{!filtered.length && <TableRow><TableCell colSpan={5} className="py-8 text-center text-muted-foreground">Документы не найдены</TableCell></TableRow>}</TableBody></Table>
    <RecordPager page={currentPage} pages={pages} total={filtered.length} onChange={setPage} />
  </PageSection>;
}

type FeedbackRun = {id: number; title: string; created_at: string; answer_count: number; completed_count: number; recipient_count: number; download_url: string | null};
export function EmployeeFeedbackFiles({employeeId, active}: {employeeId: number; active: boolean}) {
  const [runs, setRuns] = useState<FeedbackRun[] | null>(null);
  const [error, setError] = useState("");
  const [page, setPage] = useState(1);
  const [attempt, retry] = useState(0);
  useEffect(() => {if (!active) return; const controller = new AbortController(); setError("");
    void request<{runs: FeedbackRun[]}>(`/api/employees/${employeeId}/feedback-surveys`, "GET", undefined, controller.signal).then(value => {if (!controller.signal.aborted) setRuns(value.runs);}).catch(e => {if (!controller.signal.aborted) setError(errorMessage(e));});
    return () => controller.abort();
  }, [employeeId, attempt, active]);
  return <PageSection title="Файлы обратной связи" counter={runs?.length} contentClassName="gap-3">
    {error ? <div role="alert" className="space-y-2 text-sm"><p>{error}</p><button type="button" className="underline" onClick={() => retry(n => n + 1)}>Повторить</button></div> : runs === null ? <p role="status" className="text-sm text-muted-foreground">Загрузка…</p> : !runs.length ? <p className="text-sm text-muted-foreground">Запусков сбора обратной связи пока нет.</p> : <ul className="divide-y">{runs.slice((page - 1) * 10, page * 10).map(run => <li key={run.id} className="flex flex-wrap items-center justify-between gap-3 py-3"><div className="min-w-0"><p className="text-sm font-medium break-words">{run.title}</p><p className="text-xs text-muted-foreground">{dateLabel(run.created_at)} · Прошли: {run.completed_count} из {run.recipient_count} · Ответов: {run.answer_count}</p></div>{safeUrl(run.download_url) && <a href={safeUrl(run.download_url)} className={buttonVariants({variant: "outline", size: "sm"})}><Download />Excel</a>}</li>)}</ul>}
    {runs && <RecordPager page={page} pages={Math.ceil(runs.length / 10)} total={runs.length} onChange={setPage} />}
  </PageSection>;
}
