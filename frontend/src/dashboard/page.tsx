import * as React from "react";
import {
  AlertTriangle,
  ArrowRight,
  Bot,
  CalendarClock,
  ClipboardList,
  FileDown,
  Inbox,
  MessageCircle,
  Settings,
  Users,
  Workflow,
} from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

import type { AttentionItem, DashboardEvent, DashboardPayload, InboundFile, ModuleLink, TelegramLink } from "./types";

type DashboardPageProps = {
  apiUrl: string;
};

type StatCard = {
  key: keyof DashboardPayload["stats"];
  label: string;
  helper: string;
  icon: React.ComponentType<{ className?: string }>;
};

const statCards: StatCard[] = [
  {
    key: "candidates_without_channel",
    label: "Без Telegram",
    helper: "кандидаты без канала",
    icon: Users,
  },
  {
    key: "recent_telegram_links",
    label: "Привязки",
    helper: "за 7 дней",
    icon: Bot,
  },
  {
    key: "recent_inbound_files",
    label: "Документы",
    helper: "входящие за 7 дней",
    icon: FileDown,
  },
  {
    key: "scheduled_next_7_days",
    label: "Запланировано",
    helper: "на 7 дней",
    icon: CalendarClock,
  },
];

const moduleIcons: Record<string, React.ComponentType<{ className?: string }>> = {
  employees: Users,
  bulk_actions: ClipboardList,
  flows: Workflow,
  surveys: Inbox,
  settings: Settings,
};

async function requestDashboard(apiUrl: string) {
  const response = await fetch(apiUrl, {
    credentials: "same-origin",
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || "Не удалось загрузить дашборд");
  }
  return (await response.json()) as DashboardPayload;
}

function SectionCard({
  title,
  description,
  children,
  className,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <Card className={cn("border border-border/80 bg-card shadow-none ring-0", className)}>
      <CardHeader className="border-b border-border/70 pb-4">
        <CardTitle className="text-base font-semibold">{title}</CardTitle>
        {description ? <CardDescription>{description}</CardDescription> : null}
      </CardHeader>
      <CardContent className="pt-4">{children}</CardContent>
    </Card>
  );
}

function EmptyBlock({ title, description }: { title: string; description: string }) {
  return (
    <Empty className="min-h-36 border border-dashed border-border bg-muted/20">
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <Inbox />
        </EmptyMedia>
        <EmptyTitle>{title}</EmptyTitle>
        <EmptyDescription>{description}</EmptyDescription>
      </EmptyHeader>
    </Empty>
  );
}

function groupedEvents(events: DashboardEvent[]) {
  return events.reduce<Record<string, DashboardEvent[]>>((acc, event) => {
    const key = event.date_label || "Без даты";
    acc[key] = acc[key] || [];
    acc[key].push(event);
    return acc;
  }, {});
}

function EventBadge({ kind, label }: { kind: string; label: string }) {
  const variant = kind === "mass_message" ? "outline" : kind === "mass_survey" ? "secondary" : "default";
  return <Badge variant={variant}>{label}</Badge>;
}

function UpcomingEvents({ events }: { events: DashboardEvent[] }) {
  if (!events.length) {
    return <EmptyBlock title="Событий нет" description="На ближайшие дни нет запланированных сценариев, опросов или сообщений." />;
  }
  const groups = groupedEvents(events);
  return (
    <div className="flex flex-col gap-4">
      {Object.entries(groups).map(([dateLabel, items]) => (
        <div key={dateLabel} className="flex flex-col gap-2">
          <div className="text-xs font-semibold uppercase text-muted-foreground">{dateLabel}</div>
          <div className="flex flex-col gap-2">
            {items.map((event) => (
              <a
                key={event.id}
                href={event.href}
                className="grid gap-3 rounded-lg border border-border bg-background p-3 text-foreground no-underline transition-colors hover:bg-muted/45 md:grid-cols-[116px_minmax(0,1fr)_auto] md:items-center"
              >
                <div className="text-sm font-semibold">{event.scheduled_at_label}</div>
                <div className="min-w-0">
                  <div className="flex min-w-0 flex-wrap items-center gap-2">
                    <EventBadge kind={event.kind} label={event.kind_label} />
                    <div className="min-w-0 truncate text-sm font-semibold">{event.title}</div>
                  </div>
                  <div className="mt-1 truncate text-xs text-muted-foreground">{event.subtitle}</div>
                </div>
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <Badge variant="secondary">{event.recipient_count} получ.</Badge>
                  <ArrowRight />
                </div>
              </a>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function TelegramLinks({ items }: { items: TelegramLink[] }) {
  if (!items.length) {
    return <EmptyBlock title="Свежих привязок нет" description="Новые Telegram-привязки кандидатов появятся здесь." />;
  }
  return (
    <div className="flex flex-col gap-2">
      {items.map((item) => (
        <a key={`${item.employee_id}-${item.linked_at}`} href={item.href} className="grid gap-2 rounded-lg border border-border bg-background p-3 text-foreground no-underline hover:bg-muted/45">
          <div className="flex min-w-0 items-center justify-between gap-3">
            <div className="truncate text-sm font-semibold">{item.full_name}</div>
            <Badge variant="outline">{item.channel}</Badge>
          </div>
          <div className="flex min-w-0 flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <MessageCircle />
            <span className="truncate">{item.handle_or_id}</span>
            <span>{item.linked_at_label}</span>
          </div>
        </a>
      ))}
    </div>
  );
}

function InboundFiles({ items }: { items: InboundFile[] }) {
  if (!items.length) {
    return <EmptyBlock title="Документов нет" description="Входящие файлы кандидатов и сотрудников появятся после загрузки в боте." />;
  }
  return (
    <div className="flex flex-col gap-2">
      {items.map((item) => (
        <a key={item.id} href={item.href} className="grid gap-1 rounded-lg border border-border bg-background p-3 text-foreground no-underline hover:bg-muted/45">
          <div className="truncate text-sm font-semibold">{item.filename}</div>
          <div className="flex min-w-0 flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span className="truncate">{item.full_name}</span>
            <span>{item.created_at_label}</span>
          </div>
        </a>
      ))}
    </div>
  );
}

function AttentionItems({ items }: { items: AttentionItem[] }) {
  if (!items.length) {
    return <EmptyBlock title="Все спокойно" description="Нет кандидатов и сотрудников, которые требуют быстрого внимания." />;
  }
  return (
    <div className="flex flex-col gap-2">
      {items.map((item) => (
        <a key={item.id} href={item.href} className="grid gap-1 rounded-lg border border-border bg-background p-3 text-foreground no-underline hover:bg-muted/45">
          <div className="flex min-w-0 items-center justify-between gap-3">
            <div className="truncate text-sm font-semibold">{item.title}</div>
            <Badge variant={item.severity === "danger" ? "destructive" : item.severity === "warning" ? "secondary" : "outline"}>
              {item.kind === "missing_channel" ? "канал" : item.kind === "overdue_test_task" ? "дедлайн" : "бот"}
            </Badge>
          </div>
          <div className="text-xs text-muted-foreground">{item.subtitle}</div>
        </a>
      ))}
    </div>
  );
}

function ModuleLinks({ items }: { items: ModuleLink[] }) {
  return (
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
      {items.map((item) => {
        const Icon = moduleIcons[item.key] || Workflow;
        return (
          <a key={item.key} href={item.href} className="flex min-w-0 items-center gap-3 rounded-lg border border-border bg-background p-3 text-foreground no-underline hover:bg-muted/45">
            <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
              <Icon />
            </span>
            <span className="min-w-0">
              <span className="block truncate text-sm font-semibold">{item.title}</span>
              <span className="block truncate text-xs text-muted-foreground">{item.description}</span>
            </span>
          </a>
        );
      })}
    </div>
  );
}

function LoadingState() {
  return (
    <div className="admin-page-stack gap-5">
      <Skeleton className="h-20 admin-page-surface" />
      <div className="grid gap-3 md:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <Skeleton key={index} className="h-28 admin-page-surface" />
        ))}
      </div>
      <Skeleton className="h-[420px] admin-page-surface" />
    </div>
  );
}

export function DashboardPage({ apiUrl }: DashboardPageProps) {
  const [payload, setPayload] = React.useState<DashboardPayload | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState("");

  React.useEffect(() => {
    requestDashboard(apiUrl)
      .then(setPayload)
      .catch((loadError) => setError(loadError instanceof Error ? loadError.message : "Не удалось загрузить дашборд"))
      .finally(() => setLoading(false));
  }, [apiUrl]);

  if (loading) return <LoadingState />;

  if (error || !payload) {
    return (
      <div className="admin-page-shell">
        <Alert variant="destructive">
          <AlertTriangle />
          <AlertTitle>Дашборд не загрузился</AlertTitle>
          <AlertDescription>{error || "Нет данных для отображения."}</AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <div className="admin-page-stack gap-5">
      <header className="admin-page-surface border border-border/80 bg-card p-5 shadow-none ring-0">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold">Оперативный дашборд</h1>
            <p className="mt-1 text-sm text-muted-foreground">Ближайшие события, документы и записи, которые требуют внимания.</p>
          </div>
          <Badge variant="secondary">Обновлено {payload.meta.generated_at ? "сейчас" : "—"}</Badge>
        </div>
      </header>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {statCards.map((item) => {
          const Icon = item.icon;
          return (
            <Card key={item.key} className="border border-border/80 bg-card shadow-none ring-0">
              <CardContent className="flex items-center justify-between gap-4 pt-0">
                <div className="min-w-0">
                  <div className="text-3xl font-semibold">{payload.stats[item.key]}</div>
                  <div className="mt-1 truncate text-sm font-medium">{item.label}</div>
                  <div className="truncate text-xs text-muted-foreground">{item.helper}</div>
                </div>
                <span className="flex size-11 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
                  <Icon />
                </span>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.45fr)_minmax(360px,0.85fr)]">
        <SectionCard title="Ближайшие события" description="Запланированные сценарии, опросы и массовые сообщения на ближайшие дни.">
          <UpcomingEvents events={payload.upcoming_events} />
        </SectionCard>

        <div className="grid gap-5">
          <SectionCard title="Требует внимания">
            <AttentionItems items={payload.attention_items} />
          </SectionCard>
          <SectionCard title="Свежие Telegram-привязки">
            <TelegramLinks items={payload.telegram_links} />
          </SectionCard>
        </div>
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <SectionCard title="Входящие документы">
          <InboundFiles items={payload.inbound_files} />
        </SectionCard>
        <SectionCard title="Модули" description="Быстрые переходы в рабочие разделы.">
          <ModuleLinks items={payload.module_links} />
        </SectionCard>
      </div>
    </div>
  );
}
