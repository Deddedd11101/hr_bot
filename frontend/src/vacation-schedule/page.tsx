import { useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";
import { Field, FieldLabel } from "@/components/ui/field";
import { Choice, Feedback } from "@/grades/components";
import { errorMessage } from "@/grades/data";

type Entry = {employee_id: number; name: string; group_name: string; starts_on: string; ends_on: string};
type Schedule = {year: number; items: Entry[]; people: {employee_id: number; name: string; group_name: string}[]; total: number; groups: {id: number; name: string}[]};
type TelegramWindow = Window & {Telegram?: {WebApp?: {initData?: string}}};
const currentYear = () => Number(new Intl.DateTimeFormat("en", {year: "numeric", timeZone: "Europe/Moscow"}).format(new Date()));
const dateLabel = (date: string) => date.split("-").reverse().join(".");
const dayNumber = (date: string) => Date.parse(`${date}T00:00:00Z`) / 86400000;

export function VacationSchedule({embedded = false}: {embedded?: boolean}) {
  const [year, setYear] = useState(currentYear);
  const [search, setSearch] = useState("");
  const [group, setGroup] = useState("all");
  const [data, setData] = useState<Schedule | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [revision, refresh] = useState(0);
  const [selection, setSelection] = useState("");
  const scrollRoot = useRef<HTMLDivElement>(null);
  const drag = useRef<{x: number; left: number} | null>(null);
  const viewport = () => scrollRoot.current?.querySelector<HTMLElement>('[data-slot="scroll-area-viewport"]');
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError(""); setSelection("");
    const timer = setTimeout(async () => {
      try {
        const params = new URLSearchParams({year: String(year), search});
        if (group !== "all") params.set("group_id", group);
        let headers: Record<string, string> = {};
        if (embedded) {
          const initData = (window.parent as TelegramWindow).Telegram?.WebApp?.initData;
          if (!initData) throw new Error("Открой график через личный кабинет в Telegram.");
          headers = {"X-Telegram-Init-Data": initData};
        }
        const base = embedded ? "/employee-cabinet/vacation/team-schedule" : "/api/vacation-schedule";
        const response = await fetch(`${base}?${params}`, {signal: controller.signal, credentials: embedded ? "omit" : "same-origin", headers, cache: "no-store"});
        const result = await response.json();
        if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Не удалось загрузить график");
        if (!controller.signal.aborted) setData(result);
      } catch (e) {if (!controller.signal.aborted) {setData(null); setError(errorMessage(e));}}
      finally {if (!controller.signal.aborted) setLoading(false);}
    }, 200);
    return () => {clearTimeout(timer); controller.abort();};
  }, [year, search, group, revision, embedded]);
  useEffect(() => {
    const node = viewport();
    if (!node) return;
    const wheel = (event: WheelEvent) => {
      if (event.ctrlKey || node.scrollWidth <= node.clientWidth) return;
      const delta = (event.deltaX || event.deltaY) * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? node.clientWidth : 1);
      const next = Math.max(0, Math.min(node.scrollWidth - node.clientWidth, node.scrollLeft + delta));
      if (Math.abs(next - node.scrollLeft) > .5) {event.preventDefault(); node.scrollLeft = next;}
    };
    node.addEventListener("wheel", wheel, {passive: false});
    return () => node.removeEventListener("wheel", wheel);
  }, [data, loading]);
  const people = new Map<number, {name: string; group: string; entries: Entry[]}>();
  for (const person of data?.people ?? []) people.set(person.employee_id, {name: person.name, group: person.group_name, entries: []});
  for (const item of data?.items ?? []) {
    if (!people.has(item.employee_id)) people.set(item.employee_id, {name: item.name, group: item.group_name, entries: []});
    people.get(item.employee_id)!.entries.push(item);
  }
  const firstDay = dayNumber(`${year}-01-01`);
  const totalDays = dayNumber(`${year + 1}-01-01`) - firstDay;
  const months = Array.from({length: 12}, (_, i) => ({name: new Intl.DateTimeFormat("ru", {month: "short", timeZone: "UTC"}).format(new Date(Date.UTC(year, i, 1))),
    days: new Date(Date.UTC(year, i + 1, 0)).getUTCDate()}));
  const monthColumns = months.map(month => `${month.days}fr`).join(" ");
  const scroll = (direction: number) => viewport()?.scrollBy({left: direction * (viewport()?.clientWidth ?? 500) * .7,
    behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth"});
  return <>
    {!embedded && <PageHeader title="График отпусков" counter={people.size} />}
    <div className={embedded ? "p-1" : "admin-page-stack"}><section className={embedded ? "space-y-3" : "admin-page-surface min-w-0 space-y-4 p-4"}>
      <div className="grid items-end gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(150px,1fr)_auto]">
        <Field className="gap-1"><FieldLabel htmlFor="schedule-search">Сотрудник</FieldLabel><Input id="schedule-search" type="search" maxLength={200} value={search} placeholder="Имя или группа" onChange={e => setSearch(e.target.value)} /></Field>
        <Choice label="Группа" value={group} onChange={setGroup} options={[{value: "all", label: "Все группы"}, {value: "0", label: "Без группы"}, ...(data?.groups ?? []).map(item => ({value: String(item.id), label: item.name}))]} />
        <div className="flex items-center gap-1">
          <Button size="icon" variant="outline" title="Предыдущий год" aria-label="Предыдущий год" disabled={year <= 1900} onClick={() => setYear(y => y - 1)}><ChevronLeft /></Button>
          <strong className="px-2 tabular-nums">{year}</strong>
          <Button size="icon" variant="outline" title="Следующий год" aria-label="Следующий год" disabled={year >= 2100} onClick={() => setYear(y => y + 1)}><ChevronRight /></Button>
          <Button size="icon" variant="ghost" aria-label="Обновить график" title="Обновить график" disabled={loading} onClick={() => refresh(n => n + 1)}><RefreshCw /></Button>
        </div>
      </div>
      <Feedback error={error} />
      {loading && <p role="status" className="text-sm text-muted-foreground">Загрузка графика…</p>}
      {!loading && data && people.size === 0 && <p className="py-8 text-center text-sm text-muted-foreground">Сотрудников с такими условиями не найдено.</p>}
      {!loading && data && people.size > 0 && <>
        <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground"><span>Согласованные отпуска · Весь год</span><div className="flex gap-1">
          <Button size="icon-sm" variant="outline" title="Прокрутить влево" aria-label="Прокрутить влево" onClick={() => scroll(-1)}><ChevronsLeft /></Button>
          <Button size="icon-sm" variant="outline" title="Прокрутить вправо" aria-label="Прокрутить вправо" onClick={() => scroll(1)}><ChevronsRight /></Button>
        </div></div>
        <div ref={scrollRoot}><ScrollArea className="w-full rounded-lg border [&_[data-slot=table-container]]:overflow-visible [&_[data-slot=scroll-area-scrollbar]]:opacity-100" style={{height: Math.min(580, 80 + [...people.values()].reduce((height, person) => height + Math.max(112, person.entries.length * 26 + 16), 0))}}
          onPointerDown={event => {
            if (event.pointerType !== "mouse" || event.button !== 0 || (event.target as HTMLElement).closest("button,a,input")) return;
            const node = viewport(); if (!node || node.scrollWidth <= node.clientWidth) return;
            event.preventDefault(); drag.current = {x: event.clientX, left: node.scrollLeft}; event.currentTarget.setPointerCapture(event.pointerId);
          }} onPointerMove={event => {const node = viewport(); if (drag.current && node) node.scrollLeft = drag.current.left - (event.clientX - drag.current.x);}}
          onPointerUp={() => {drag.current = null;}} onPointerCancel={() => {drag.current = null;}} onLostPointerCapture={() => {drag.current = null;}}>
          <Table className="border-collapse"><TableHeader><TableRow>
            <TableHead className="sticky left-0 z-10 min-w-40 bg-background p-3 sm:min-w-52">Сотрудник</TableHead>
            <TableHead className="min-w-[720px] px-0"><div className="grid" style={{gridTemplateColumns: monthColumns}}>{months.map(month => <span key={month.name} className="border-l py-3 text-center text-xs">{month.name}</span>)}</div></TableHead>
          </TableRow></TableHeader><TableBody>{[...people].sort((a,b) => a[1].name.localeCompare(b[1].name, "ru")).map(([id, person]) => <TableRow key={id}>
            <TableCell className="sticky left-0 z-10 max-w-60 whitespace-normal bg-background p-3">
              {embedded ? <span className="font-medium">{person.name}</span> : <a className="break-words font-medium underline-offset-4 hover:underline" href={`/app/employees/${id}?tab=vacation`}>{person.name}</a>}
              <p className="text-xs text-muted-foreground">{person.group}</p>
              {person.entries.length === 0 && <p className="text-xs text-muted-foreground">Нет согласованных отпусков</p>}
            </TableCell>
            <TableCell className="relative cursor-grab px-0 py-2 active:cursor-grabbing" style={{height: Math.max(70, person.entries.length * 26 + 16)}}>
              <div aria-hidden="true" className="pointer-events-none absolute inset-0 grid" style={{gridTemplateColumns: monthColumns}}>{months.map(month => <span key={month.name} className="border-l" />)}</div>
              {person.entries.map((item, index) => {
                const start = Math.max(0, dayNumber(item.starts_on) - firstDay);
                const end = Math.min(totalDays, dayNumber(item.ends_on) - firstDay + 1);
                const label = `${person.name} · ${dateLabel(item.starts_on)} – ${dateLabel(item.ends_on)}`;
                return <Button key={`${item.starts_on}:${index}`} title={label} aria-label={label} className="absolute min-w-2 rounded-sm p-0" style={{left: `${start / totalDays * 100}%`, width: `${(end - start) / totalDays * 100}%`, height: 20, top: 10 + index * 26}} onClick={() => setSelection(label)}><span className="sr-only">{label}</span></Button>;
              })}
            </TableCell>
          </TableRow>)}</TableBody></Table>
        </ScrollArea></div>
        <p role="status" className="min-h-5 text-xs text-muted-foreground">{selection || `Сотрудников: ${people.size} · Отпусков: ${data.total}`}</p>
      </>}
    </section></div>
  </>;
}
