import { useEffect, useState, type ReactNode } from "react";
import { ChevronLeft, ChevronRight, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ConfirmAction } from "@/components/ui/confirm-action";
import { PageSection, PageSectionEmpty } from "@/components/ui/page-section";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";
import { Choice, Feedback, useAction } from "@/grades/components";
import { dateLabel, errorMessage, request } from "@/grades/data";

type Page<T> = {items: T[]; total: number; page: number; page_size: number; pages: number};
type RecordItem = {id: number; created_at: string; sent_at?: string; author_label?: string; sender_label?: string; note_text?: string; message_text?: string; status?: string; error_text?: string};
type Activity = {id: string; occurred_at: string; kind: string; label: string; detail: string; actor: string};

export function RecordPager({page, pages, total, disabled, onChange}: {page: number; pages: number; total: number; disabled?: boolean; onChange: (page: number) => void}) {
  if (pages <= 1) return null;
  return <nav aria-label="Страницы списка" className="flex flex-wrap items-center justify-between gap-2 border-t pt-3 text-xs text-muted-foreground">
    <span>{total} записей · Страница {page} из {pages}</span>
    <div className="flex gap-1"><Button type="button" variant="outline" size="icon-sm" aria-label="Предыдущая страница" title="Предыдущая страница" disabled={disabled || page <= 1} onClick={() => onChange(page - 1)}><ChevronLeft /></Button><Button type="button" variant="outline" size="icon-sm" aria-label="Следующая страница" title="Следующая страница" disabled={disabled || page >= pages} onClick={() => onChange(page + 1)}><ChevronRight /></Button></div>
  </nav>;
}

export function EmployeeRecords({employeeId, kind, refreshKey, children, onDeleted}: {employeeId: number; kind: "hr-notes" | "bot-messages"; refreshKey?: string; children?: ReactNode; onDeleted?: (text: string) => void}) {
  const notes = kind === "hr-notes";
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Page<RecordItem> | null>(null);
  const [error, setError] = useState("");
  const [attempt, retry] = useState(0);
  const [loading, setLoading] = useState(false);
  const action = useAction();
  const endpoint = `/api/employees/${employeeId}/${kind}`;
  useEffect(() => {setPage(1);}, [employeeId, kind, refreshKey]);
  useEffect(() => {
    const controller = new AbortController(); setLoading(true); setError("");
    void request<Page<RecordItem>>(`${endpoint}?page=${page}&page_size=${notes ? 10 : 20}`, "GET", undefined, controller.signal).then(value => {if (!controller.signal.aborted) {setData(value); const next = Math.min(value.page, Math.max(1, value.pages)); if (next !== page) setPage(next);}}).catch(e => {if (!controller.signal.aborted) setError(errorMessage(e));}).finally(() => {if (!controller.signal.aborted) setLoading(false);});
    return () => controller.abort();
  }, [endpoint, page, refreshKey, attempt]);
  return <PageSection title={notes ? "HR-заметки" : "История ручных сообщений"} counter={data?.total} contentClassName="gap-4">
    {children}
    <Feedback error={error || action.error} message={action.message} />
    {error && <Button type="button" variant="outline" onClick={() => retry(n => n + 1)}>Повторить</Button>}
    {loading && <p role="status" className="text-sm text-muted-foreground">Загрузка…</p>}
    {!loading && !error && data && (data.items.length ? <ul className="divide-y">{data.items.map(item => <li key={item.id} className="space-y-2 py-3">
      <div className="flex flex-wrap items-center justify-between gap-2"><div className="flex min-w-0 flex-wrap items-center gap-2 text-xs text-muted-foreground"><span>{dateLabel(item.sent_at || item.created_at)}</span><span>{item.author_label || item.sender_label || "Автор не указан"}</span>{!notes && <Badge variant={item.status === "failed" ? "destructive" : "secondary"}>{({sent: "Отправлено", failed: "Ошибка", pending: "Ожидает отправки"} as Record<string,string>)[item.status || ""] || item.status}</Badge>}</div>
      <ConfirmAction title={notes ? "Удалить заметку?" : "Удалить сообщение из списка?"} description={notes ? "Текст заметки будет удалён. В истории останется только факт действия." : "Запись будет удалена из админки. Сообщение в Telegram останется, как и факт отправки в истории."} actionLabel="Удалить" onConfirm={() => void action.run(async () => {
        await request(`${endpoint}/${item.id}`, "DELETE");
        onDeleted?.(item.note_text || "");
        if (data.items.length === 1 && page > 1) setPage(page - 1); else retry(n => n + 1);
      }, notes ? "Заметка удалена" : "Запись удалена, Telegram не изменён")}><Button type="button" variant="ghost" size="icon-sm" title={notes ? "Удалить заметку" : "Удалить запись"} aria-label={`${notes ? "Удалить заметку" : "Удалить запись"} №${item.id}`} disabled={action.busy}><Trash2 /></Button></ConfirmAction></div>
      <p className="whitespace-pre-wrap break-words [overflow-wrap:anywhere] text-sm">{item.note_text || item.message_text || "Без текста"}</p>
      {item.error_text && <p className="text-xs text-destructive break-words">{item.error_text}</p>}
    </li>)}</ul> : <PageSectionEmpty title={notes ? "Заметок нет" : "Ручных сообщений нет"} />)}
    {data && <RecordPager page={data.page} pages={data.pages} total={data.total} disabled={loading || action.busy} onChange={setPage} />}
  </PageSection>;
}

export function EmployeeActivity({employeeId, active = true}: {employeeId: number; active?: boolean}) {
  const [kind, setKind] = useState("all");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<(Page<Activity> & {kinds: {value: string; label: string}[]}) | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [attempt, retry] = useState(0);
  useEffect(() => {
    if (!active) return;
    const controller = new AbortController(); setLoading(true); setError("");
    void request<Page<Activity> & {kinds: {value: string; label: string}[]}>(`/api/employees/${employeeId}/activity?page=${page}&page_size=20&kind=${encodeURIComponent(kind)}`, "GET", undefined, controller.signal).then(value => {if (!controller.signal.aborted) {setData(value); const next = Math.min(value.page, Math.max(1, value.pages)); if (next !== page) setPage(next);}}).catch(e => {if (!controller.signal.aborted) setError(errorMessage(e));}).finally(() => {if (!controller.signal.aborted) setLoading(false);});
    return () => controller.abort();
  }, [employeeId, page, kind, attempt, active]);
  return <PageSection title="История действий" counter={data?.total} contentClassName="gap-4">
    <div className="max-w-xs"><Choice label="Тип действия" value={kind} options={data?.kinds?.length ? data.kinds : [{value: "all", label: "Все действия"}]} onChange={value => {setKind(value); setPage(1);}} /></div>
    <Feedback error={error} />{error && <Button type="button" variant="outline" onClick={() => retry(n => n + 1)}>Повторить</Button>}
    {loading && <p role="status" className="text-sm text-muted-foreground">Загрузка…</p>}
    {!error && !loading && <Table className="table-fixed"><TableHeader><TableRow><TableHead className="w-36">Дата · МСК</TableHead><TableHead className="w-36">Тип</TableHead><TableHead>Событие</TableHead><TableHead className="w-32">Кто выполнил</TableHead></TableRow></TableHeader><TableBody>{data?.items.map(item => <TableRow key={item.id}><TableCell className="whitespace-normal align-top text-xs">{dateLabel(item.occurred_at)}</TableCell><TableCell className="whitespace-normal align-top">{data.kinds.find(option => option.value === item.kind)?.label || item.kind}</TableCell><TableCell className="whitespace-normal break-words align-top [overflow-wrap:anywhere]"><p>{item.label}</p>{item.detail && <p className="mt-1 text-xs text-muted-foreground whitespace-pre-wrap">{item.detail}</p>}</TableCell><TableCell className="whitespace-normal break-words align-top text-xs">{item.actor || "Не зафиксирован"}</TableCell></TableRow>)}{!data?.items.length && <TableRow><TableCell colSpan={4} className="py-8 text-center text-muted-foreground">Зафиксированных действий нет</TableCell></TableRow>}</TableBody></Table>}
    {data && <RecordPager page={data.page} pages={data.pages} total={data.total} disabled={loading} onChange={setPage} />}
  </PageSection>;
}
