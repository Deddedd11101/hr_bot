import * as React from "react";
import { RefreshCw, ArrowLeft } from "lucide-react";
import { Button, buttonVariants } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

type QueueItem = {
  id: string;
  employee_name: string;
  employee_href: string | null;
  title: string;
  scenario_href: string | null;
  state: string;
  reason: string;
  at: string;
  source: string;
  recipient_name: string | null;
};
type QueueData = {
  items: QueueItem[];
  total: number;
  counts: Record<string, number>;
  page: number;
  pages: number;
  truncated: boolean;
};
type HistoryItem = {
  id: string;
  at: string;
  kind: string;
  title: string;
  employee_name: string | null;
  employee_href: string | null;
  scenario_href: string | null;
  href: string | null;
  detail: string | null;
  source: string;
  actor: string;
};
type HistoryData = { items: HistoryItem[]; page: number; has_more: boolean };
export const queueStates: Record<string, string> = {
  all: "Все",
  attention: "Требует внимания",
  blocked: "Ожидает диалог",
  waiting: "Ожидает ответа",
  queued: "В очереди",
  active: "В работе",
  scheduled: "Запланировано",
};
const historyKinds: Record<string, string> = {
  all: "Все",
  steps: "Шаги сценариев",
  surveys: "Опросы",
  messages: "Сообщения",
  launches: "Запросы запуска",
};
function dateLabel(value: string) {
  return new Date(value).toLocaleString("ru-RU", {
    timeZone: "Europe/Moscow",
    dateStyle: "short",
    timeStyle: "short",
  });
}

function useResource<T>(url: string) {
  const [data, setData] = React.useState<T | null>(null);
  const [error, setError] = React.useState("");
  const [loading, setLoading] = React.useState(true);
  const [revision, refresh] = React.useReducer((n) => n + 1, 0);
  React.useEffect(() => {
    const controller = new AbortController();
    let inFlight = false;
    setData(null);
    setLoading(true);
    setError("");
    async function load() {
      if (inFlight) return;
      inFlight = true;
      try {
        const response = await fetch(url, {
          signal: controller.signal,
          credentials: "same-origin",
        });
        if (!response.ok) throw new Error("Не удалось загрузить данные");
        const next = await response.json();
        if (!controller.signal.aborted) {
          setData(next);
          setError("");
        }
      } catch (e) {
        if (!controller.signal.aborted)
          setError(e instanceof Error ? e.message : "Ошибка загрузки");
      } finally {
        inFlight = false;
        if (!controller.signal.aborted) setLoading(false);
      }
    }
    void load();
    const timer = window.setInterval(() => {
      if (!document.hidden) void load();
    }, 30000);
    return () => {
      controller.abort();
      window.clearInterval(timer);
    };
  }, [url, revision]);
  return { data, error, loading, refresh };
}

function Linked({
  href,
  children,
}: {
  href: string | null;
  children: React.ReactNode;
}) {
  return href ? (
    <a
      href={href}
      className="font-medium text-primary underline-offset-4 hover:underline"
    >
      {children}
    </a>
  ) : (
    <span>{children}</span>
  );
}
function Chips({
  labels,
  value,
  onChange,
}: {
  labels: Record<string, string>;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div
      className="flex flex-wrap gap-2"
      role="group"
      aria-label="Фильтр записей"
    >
      {Object.entries(labels).map(([key, label]) => (
        <Button
          key={key}
          size="sm"
          variant={key === value ? "secondary" : "ghost"}
          aria-pressed={key === value}
          onClick={() => onChange(key)}
        >
          {label}
        </Button>
      ))}
    </div>
  );
}
function Feedback({ error, loading }: { error: string; loading: boolean }) {
  return error ? (
    <p role="alert" className="py-3 text-sm text-destructive">
      {error}
    </p>
  ) : loading ? (
    <p role="status" className="py-3 text-sm text-muted-foreground">
      Загрузка...
    </p>
  ) : null;
}

export function QueueView({ compact = false }: { compact?: boolean }) {
  const [state, setState] = React.useState(() => {
    const value = compact
      ? "all"
      : new URL(window.location.href).searchParams.get("state") || "all";
    return value in queueStates ? value : "all";
  });
  const [search, setSearch] = React.useState("");
  const [query, setQuery] = React.useState("");
  const [page, setPage] = React.useState(1);
  React.useEffect(() => {
    const t = window.setTimeout(() => {
      setQuery(search);
      setPage(1);
    }, 250);
    return () => window.clearTimeout(t);
  }, [search]);
  const { data, error, loading, refresh } = useResource<QueueData>(
    `/api/scenario-queue?state=${state}&search=${encodeURIComponent(query)}&page=${page}`,
  );
  return (
    <div className="min-w-0 space-y-4">
      {!compact && (
        <>
          <div className="flex items-center gap-3">
            <Input
              aria-label="Поиск по сотруднику или сценарию"
              placeholder="Сотрудник или сценарий"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="max-w-sm"
            />
            <Button
              variant="outline"
              size="icon-sm"
              title="Обновить очередь"
              aria-label="Обновить очередь"
              onClick={refresh}
            >
              <RefreshCw />
            </Button>
          </div>
          <Chips
            labels={queueStates}
            value={state}
            onChange={(v) => {
              setState(v);
              setPage(1);
            }}
          />
        </>
      )}
      {compact && data && (
        <div className="flex flex-wrap gap-3 text-sm">
          {["attention", "blocked", "waiting", "scheduled"].map((key) => (
            <a
              key={key}
              href={`/app/scenario-queue?state=${key}`}
              className="text-muted-foreground hover:text-foreground"
            >
              {queueStates[key]}{" "}
              <strong className="text-foreground">
                {data.counts[key] || 0}
              </strong>
            </a>
          ))}
        </div>
      )}
      <Feedback error={error} loading={loading} />
      {data?.truncated && (
        <p role="status" className="text-sm text-muted-foreground">
          Показаны первые 500 записей каждого источника. Сводные числа относятся
          к этой выборке.
        </p>
      )}
      {!!data && !data.items.length && (
        <p className="py-6 text-sm text-muted-foreground">
          Запусков с такими условиями нет.
        </p>
      )}
      {!!data?.items.length &&
        (compact ? (
          <div className="divide-y">
            {data.items.slice(0, 6).map((item) => (
              <div key={item.id} className="space-y-1 py-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <Linked href={item.scenario_href}>{item.title}</Linked>
                  <Badge
                    variant={
                      item.state === "attention" ? "destructive" : "secondary"
                    }
                  >
                    {queueStates[item.state]}
                  </Badge>
                </div>
                <p className="text-sm">
                  <Linked href={item.employee_href}>
                    {item.employee_name}
                  </Linked>
                  {item.recipient_name && (
                    <span className="text-muted-foreground">
                      {" "}
                      · Получатель: {item.recipient_name}
                    </span>
                  )}
                </p>
                <p className="text-xs text-muted-foreground">{item.reason}</p>
              </div>
            ))}
          </div>
        ) : (
          <Table className="min-w-[900px]">
            <TableHeader>
              <TableRow>
                <TableHead>Сотрудник / получатель</TableHead>
                <TableHead>Сценарий</TableHead>
                <TableHead>Источник</TableHead>
                <TableHead>Состояние</TableHead>
                <TableHead>Причина</TableHead>
                <TableHead>Дата / обновление · МСК</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.items.map((item) => (
                <TableRow key={item.id}>
                  <TableCell className="max-w-56 whitespace-normal break-words">
                    <Linked href={item.employee_href}>
                      {item.employee_name}
                    </Linked>
                    {item.recipient_name && (
                      <p className="mt-1 text-xs text-muted-foreground">
                        Получатель: {item.recipient_name}
                      </p>
                    )}
                  </TableCell>
                  <TableCell className="max-w-56 whitespace-normal break-words">
                    <Linked href={item.scenario_href}>{item.title}</Linked>
                  </TableCell>
                  <TableCell className="max-w-40 whitespace-normal text-xs">
                    {item.source}
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={
                        item.state === "attention" ? "destructive" : "secondary"
                      }
                    >
                      {queueStates[item.state]}
                    </Badge>
                  </TableCell>
                  <TableCell className="max-w-80 whitespace-normal text-sm">
                    {item.reason}
                  </TableCell>
                  <TableCell className="whitespace-normal text-xs">
                    {dateLabel(item.at)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ))}
      {!compact && data && (
        <nav
          aria-label="Страницы очереди"
          className="flex flex-wrap items-center justify-between gap-3"
        >
          <span className="text-xs text-muted-foreground">
            {data.total} записей · Страница {page} из {data.pages}
          </span>
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="outline"
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
            >
              Назад
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={page >= data.pages}
              onClick={() => setPage((p) => p + 1)}
            >
              Далее
            </Button>
          </div>
        </nav>
      )}
    </div>
  );
}

export function HistoryView() {
  const [kind, setKind] = React.useState("all");
  const [page, setPage] = React.useState(1);
  const { data, error, loading, refresh } = useResource<HistoryData>(
    `/api/dashboard/history?kind=${kind}&page=${page}`,
  );
  return (
    <div className="min-w-0 space-y-4">
      <div className="flex items-start justify-between gap-2">
        <Chips
          labels={historyKinds}
          value={kind}
          onChange={(v) => {
            setKind(v);
            setPage(1);
          }}
        />
        <Button
          variant="outline"
          size="icon-sm"
          title="Обновить историю"
          aria-label="Обновить историю"
          onClick={refresh}
        >
          <RefreshCw />
        </Button>
      </div>
      <Feedback error={error} loading={loading} />
      {data && !data.items.length && (
        <p className="py-6 text-sm text-muted-foreground">
          Зафиксированных событий нет.
        </p>
      )}
      {!!data?.items.length && (
        <Table className="min-w-[800px]">
          <TableHeader>
            <TableRow>
              <TableHead>Дата · МСК</TableHead>
              <TableHead>Тип</TableHead>
              <TableHead>Сотрудник</TableHead>
              <TableHead>Событие</TableHead>
              <TableHead>Источник / кто выполнил</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.items.map((item) => (
              <TableRow key={item.id}>
                <TableCell className="whitespace-normal text-xs">
                  {dateLabel(item.at)}
                </TableCell>
                <TableCell>
                  <Badge variant="outline">{historyKinds[item.kind]}</Badge>
                </TableCell>
                <TableCell className="max-w-48 whitespace-normal">
                  <Linked href={item.employee_href}>
                    {item.employee_name || "Группа получателей"}
                  </Linked>
                </TableCell>
                <TableCell className="max-w-md whitespace-normal break-words">
                  <Linked href={item.scenario_href || item.href}>
                    {item.title}
                  </Linked>
                  {item.detail &&
                    (item.detail.length > 180 ? (
                      <details className="mt-2 text-xs text-muted-foreground">
                        <summary className="cursor-pointer">
                          Подробности
                        </summary>
                        <p className="mt-2 whitespace-pre-wrap">
                          {item.detail}
                        </p>
                      </details>
                    ) : (
                      <p className="mt-1 whitespace-pre-wrap text-xs text-muted-foreground">
                        {item.detail}
                      </p>
                    ))}
                </TableCell>
                <TableCell className="max-w-52 whitespace-normal text-xs">
                  {item.source}
                  <p className="mt-1 text-muted-foreground">{item.actor}</p>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
      {data && (
        <nav
          aria-label="Страницы истории"
          className="flex items-center justify-end gap-2"
        >
          <span className="mr-auto text-xs text-muted-foreground">
            Страница {page}
          </span>
          <Button
            size="sm"
            variant="outline"
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
          >
            Назад
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={!data.has_more || page >= 100}
            onClick={() => setPage((p) => p + 1)}
          >
            Далее
          </Button>
        </nav>
      )}
    </div>
  );
}

export function QueuePage() {
  return (
    <>
      <PageHeader
        title="Очередь сценариев"
        actions={
          <a
            href="/app/flows/workspace-v2"
            className={buttonVariants({ variant: "outline", size: "sm" })}
          >
            <ArrowLeft /> К сценариям
          </a>
        }
      />
      <section className="admin-page-surface min-w-0 p-4">
        <QueueView />
      </section>
    </>
  );
}
