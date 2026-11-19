import { useEffect, useState } from "react";
import { ChevronLeft, ChevronRight, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { DatePicker } from "@/components/ui/date-picker";
import { PageHeader } from "@/components/ui/page-header";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";
import { Field, FieldLabel } from "@/components/ui/field";
import { Choice, Feedback } from "@/grades/components";
import { errorMessage, request } from "@/grades/data";

type Entry = {employee_id: number; name: string; group_name: string; starts_on: string; ends_on: string};
type Schedule = {month: string; days_in_month: number; items: Entry[]; total: number; page_size: number; groups: {id: number; name: string}[]};
const currentMonth = () => new Intl.DateTimeFormat("sv-SE", {year: "numeric", month: "2-digit", timeZone: "Europe/Moscow"}).format(new Date());
function shifted(month: string, offset: number) {
  const day = new Date(`${month}-01T12:00:00Z`); day.setUTCMonth(day.getUTCMonth() + offset);
  return day.toISOString().slice(0, 7);
}
const dateLabel = (date: string) => date.split("-").reverse().join(".");

export function VacationSchedule() {
  const [month, setMonth] = useState(currentMonth);
  const [search, setSearch] = useState("");
  const [group, setGroup] = useState("all");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Schedule | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [revision, refresh] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError("");
    const timer = setTimeout(() => {
      const params = new URLSearchParams({month, search, page: String(page)});
      if (group !== "all") params.set("group_id", group);
      request<Schedule>(`/api/vacation-schedule?${params}`, "GET", undefined, controller.signal)
        .then(result => {if (!controller.signal.aborted) setData(result);})
        .catch(e => {if (!controller.signal.aborted) {setData(null); setError(errorMessage(e));}})
        .finally(() => {if (!controller.signal.aborted) setLoading(false);});
    }, 200);
    return () => {clearTimeout(timer); controller.abort();};
  }, [month, search, group, page, revision]);
  const move = (offset: number) => {setMonth(shifted(month, offset)); setPage(1);};
  const days = Array.from({length: data?.month === month ? data.days_in_month : 0}, (_, i) => `${month}-${String(i + 1).padStart(2, "0")}`);
  const weekend = (day: string) => [0, 6].includes(new Date(`${day}T12:00:00Z`).getUTCDay());
  return <>
    <PageHeader title="График отпусков" counter={data?.total} actions={<Button variant="outline" onClick={() => refresh(n => n + 1)} disabled={loading}><RefreshCw />Обновить</Button>} />
    <div className="admin-page-stack"><section className="admin-page-surface min-w-0 space-y-4 p-4">
      <p className="text-sm text-muted-foreground">Согласованные отпуска · пересечения не запрещены автоматически</p>
      <div className="grid items-end gap-3 md:grid-cols-[minmax(0,1fr)_minmax(180px,1fr)_minmax(220px,auto)]">
        <Field className="gap-1"><FieldLabel htmlFor="schedule-search">Сотрудник или группа</FieldLabel><Input id="schedule-search" type="search" value={search} placeholder="Поиск" onChange={e => {setSearch(e.target.value); setPage(1);}} /></Field>
        <Choice label="Группа" value={group} onChange={value => {setGroup(value); setPage(1);}}
          options={[{value: "all", label: "Все группы"}, {value: "0", label: "Без группы"}, ...(data?.groups ?? []).map(item => ({value: String(item.id), label: item.name}))]} />
        <div className="flex min-w-0 items-center gap-1">
          <Button size="icon" variant="outline" title="Предыдущий месяц" aria-label="Предыдущий месяц" disabled={month <= "1900-01"} onClick={() => move(-1)}><ChevronLeft /></Button>
          <div className="min-w-0 flex-1"><DatePicker value={`${month}-01`} onValueChange={value => {if (value) {setMonth(value.slice(0, 7)); setPage(1);}}} /></div>
          <Button size="icon" variant="outline" title="Следующий месяц" aria-label="Следующий месяц" disabled={month >= "2100-12"} onClick={() => move(1)}><ChevronRight /></Button>
        </div>
      </div>
      <Feedback error={error} />
      {loading && <p role="status" className="text-sm text-muted-foreground">Загрузка графика…</p>}
      {!loading && data && data.items.length === 0 && <p className="py-8 text-center text-sm text-muted-foreground">На этот месяц согласованных отпусков не найдено.</p>}
      {!loading && data && data.items.length > 0 && <>
        <ScrollArea className="w-full rounded-lg border [&_[data-slot=table-container]]:overflow-visible" style={{height: Math.min(600, 52 + data.items.length * 78)}}>
          <Table className="border-collapse"><TableHeader><TableRow>
            <TableHead className="sticky left-0 z-10 min-w-44 border-b bg-background p-3 text-left font-medium sm:min-w-60">Сотрудник</TableHead>
            {days.map(day => <TableHead key={day} className={`min-w-7 border-b py-3 text-center text-xs font-normal ${weekend(day) ? "bg-muted text-muted-foreground" : ""}`}>{Number(day.slice(-2))}</TableHead>)}
          </TableRow></TableHeader><TableBody>{data.items.map((item, index) => <TableRow key={`${item.employee_id}:${item.starts_on}:${index}`}>
            <TableCell className="sticky left-0 z-10 max-w-60 whitespace-normal border-b bg-background p-3 align-top">
              <a className="break-words font-medium underline-offset-4 hover:underline" href={`/app/employees/${item.employee_id}?tab=vacation`}>{item.name}</a>
              <p className="text-xs text-muted-foreground">{item.group_name}</p>
              <p className="whitespace-nowrap text-xs text-muted-foreground">{dateLabel(item.starts_on)} – {dateLabel(item.ends_on)}</p>
            </TableCell>
            {days.map(day => {const absent = day >= item.starts_on && day <= item.ends_on;
              return <TableCell key={day} className={`border-b px-0 py-3 ${weekend(day) ? "bg-muted/50" : ""}`} title={`${dateLabel(day)}${absent ? " · Отпуск" : ""}`}>
                <span className={`block h-6 ${absent ? "bg-primary/80" : ""}`} aria-label={absent ? `${item.name} · ${dateLabel(day)} · отпуск` : undefined} />
              </TableCell>;})}
          </TableRow>)}</TableBody></Table>
        </ScrollArea>
        <nav aria-label="Страницы графика" className="flex flex-wrap items-center justify-between gap-2 text-sm">
          <span className="text-muted-foreground">Отпусков: {data.total} · Страница {page}</span>
          <div className="flex gap-2"><Button variant="outline" disabled={page === 1} onClick={() => setPage(n => n - 1)}>Назад</Button>
            <Button variant="outline" disabled={page * data.page_size >= data.total} onClick={() => setPage(n => n + 1)}>Далее</Button></div>
        </nav>
      </>}
    </section></div>
  </>;
}
