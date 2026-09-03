import * as React from "react";
import {
  AlertTriangle,
  ArrowRight,
  Bot,
  CalendarClock,
  FileDown,
  Inbox,
  MessageCircle,
  Send,
  Settings,
  Trash2,
  Users,
  Workflow,
} from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/ui/page-header";
import { PageRow } from "@/components/ui/page-row";
import {
  PageSection,
  PageSectionEmpty,
  PageSectionGrid,
  PageSectionRows,
} from "@/components/ui/page-section";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ConfirmAction } from "@/components/ui/confirm-action";
import { Skeleton } from "@/components/ui/skeleton";
import { ПРОЯВЛЕНИЕ } from "@/lib/reveal";
import { cn } from "@/lib/utils";

import type { AttentionItem, DashboardEvent, DashboardPayload, InboundFile, ModuleLink, SentHistoryItem, TelegramLink } from "./types";

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
  messages: Send,
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

/**
 * Строка коллекции внутри модуля.
 *
 * Своей рамки у строки нет: её несёт модуль, а второй уровень рамок читается
 * как карточка в карточке. Разделяют строки линии из PageSectionRows.
 * Отрицательный отступ по бокам даёт подсветке при наведении поля, не сдвигая
 * при этом текст.
 */
const rowLink =
  "-mx-2 rounded-lg px-2 text-foreground no-underline transition-colors hover:bg-muted/45";

function groupedEvents(events: DashboardEvent[]) {
  return events.reduce<Record<string, DashboardEvent[]>>((acc, event) => {
    const key = event.date_label || "Без даты";
    acc[key] = acc[key] || [];
    acc[key].push(event);
    return acc;
  }, {});
}

const DELETE_PATH_BY_KIND: Record<string, string> = {
  mass_scenario: "/api/bulk-actions/scenarios",
  mass_survey: "/api/bulk-actions/surveys",
  mass_message: "/api/bulk-actions/messages",
};

function EventBadge({ kind, label }: { kind: string; label: string }) {
  const variant = kind === "mass_message" ? "outline" : kind === "mass_survey" ? "secondary" : "default";
  return <Badge variant={variant}>{label}</Badge>;
}

function UpcomingEvents({ events, onDelete }: { events: DashboardEvent[]; onDelete: (event: DashboardEvent) => void }) {
  if (!events.length) {
    return <PageSectionEmpty icon={<CalendarClock />} title="Событий нет" description="На ближайшие дни нет запланированных сценариев, опросов или сообщений." />;
  }
  const groups = groupedEvents(events);
  return (
    <PageSectionRows>
      {Object.entries(groups).map(([dateLabel, items]) => (
        <div key={dateLabel} className="flex flex-col gap-2">
          <div className="text-xs font-semibold uppercase text-muted-foreground">{dateLabel}</div>
          <div className="flex flex-col gap-1">
            {items.map((event) => (
              /*
               * Строка — не ссылка, а контейнер с накладкой-ссылкой: рядом
               * с переходом живёт удаление запланированного, и кнопку нельзя
               * вкладывать в <a>. Кнопка стоит над накладкой (z-10) — приём
               * тот же, что в RecordCard.
               */
              <div
                key={event.id}
                className={cn(rowLink, "group/row relative grid gap-3 py-2 md:grid-cols-[116px_minmax(0,1fr)_auto] md:items-center")}
              >
                <a href={event.href} className="absolute inset-0" aria-label={event.title} />
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
                  {event.deletable && event.action_id !== null && DELETE_PATH_BY_KIND[event.kind] ? (
                    <ConfirmAction
                      title="Удалить запланированное действие?"
                      description="Действие будет удалено из расписания. Уже выполненные запуски не затрагиваются."
                      actionLabel="Удалить"
                      onConfirm={() => onDelete(event)}
                    >
                      <Button
                        variant="outline"
                        size="icon-sm"
                        aria-label={`Удалить: ${event.title}`}
                        className={cn("relative z-10", ПРОЯВЛЕНИЕ.row)}
                      >
                        <Trash2 />
                      </Button>
                    </ConfirmAction>
                  ) : (
                    <ArrowRight />
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </PageSectionRows>
  );
}

function TelegramLinks({ items }: { items: TelegramLink[] }) {
  if (!items.length) {
    return <PageSectionEmpty icon={<Bot />} title="Свежих привязок нет" description="Новые Telegram-привязки кандидатов появятся здесь." />;
  }
  return (
    <PageSectionRows>
      {items.map((item) => (
        <a key={`${item.employee_id}-${item.linked_at}`} href={item.href} className={cn(rowLink, "grid gap-2")}>
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
    </PageSectionRows>
  );
}

function InboundFiles({ items }: { items: InboundFile[] }) {
  if (!items.length) {
    return <PageSectionEmpty icon={<FileDown />} title="Документов нет" description="Входящие файлы кандидатов и сотрудников появятся после загрузки в боте." />;
  }
  return (
    <PageSectionRows>
      {items.map((item) => (
        <a key={item.id} href={item.href} className={cn(rowLink, "grid gap-1")}>
          <div className="truncate text-sm font-semibold">{item.filename}</div>
          <div className="flex min-w-0 flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span className="truncate">{item.full_name}</span>
            <span>{item.created_at_label}</span>
          </div>
        </a>
      ))}
    </PageSectionRows>
  );
}

function AttentionItems({ items }: { items: AttentionItem[] }) {
  if (!items.length) {
    return <PageSectionEmpty icon={<AlertTriangle />} title="Все спокойно" description="Нет кандидатов и сотрудников, которые требуют быстрого внимания." />;
  }
  return (
    <PageSectionRows>
      {items.map((item) => (
        <a key={item.id} href={item.href} className={cn(rowLink, "grid gap-1")}>
          <div className="flex min-w-0 items-center justify-between gap-3">
            <div className="truncate text-sm font-semibold">{item.title}</div>
            <Badge variant={item.severity === "danger" ? "destructive" : item.severity === "warning" ? "secondary" : "outline"}>
              {item.kind === "missing_channel" ? "канал" : item.kind === "overdue_test_task" ? "дедлайн" : "бот"}
            </Badge>
          </div>
          <div className="text-xs text-muted-foreground">{item.subtitle}</div>
        </a>
      ))}
    </PageSectionRows>
  );
}

function SentHistory({ items }: { items: SentHistoryItem[] }) {
  if (!items.length) {
    return <PageSectionEmpty icon={<Send />} title="Отправок ещё не было" description="Выполненные массовые рассылки и сообщения появятся здесь." />;
  }
  return (
    <PageSectionRows>
      {items.map((item) => (
        <a key={item.id} href={item.href} className={cn(rowLink, "grid gap-1 py-2")}>
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <EventBadge kind={item.kind} label={item.kind_label} />
            <div className="min-w-0 truncate text-sm font-semibold">{item.title}</div>
          </div>
          <div className="flex min-w-0 flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span>{item.processed_at_label}</span>
            <span className="truncate">{item.subtitle}</span>
            <Badge variant="secondary">{item.recipient_count} получ.</Badge>
          </div>
        </a>
      ))}
    </PageSectionRows>
  );
}

function ModuleLinks({ items }: { items: ModuleLink[] }) {
  return (
    <PageSectionGrid columns={2}>
      {items.map((item) => {
        const Icon = moduleIcons[item.key] || Workflow;
        return (
          <a key={item.key} href={item.href} className={cn(rowLink, "flex min-w-0 items-center gap-3 py-2")}>
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
    </PageSectionGrid>
  );
}

/**
 * Скелет обязан повторять раскладку, которая придёт ему на смену. Раньше он
 * рисовал четыре колонки там, где контент рисовал две, и страница на ширинах
 * 768-1279px перекладывалась прямо на глазах.
 */
function LoadingState() {
  return (
    <div className="admin-page-stack">
      <Skeleton className="h-5 w-96 max-w-full" />
      <PageRow columns={4}>
        {Array.from({ length: 4 }).map((_, index) => (
          <Skeleton key={index} className="h-28 admin-page-surface" />
        ))}
      </PageRow>
      <PageRow columns={3}>
        {Array.from({ length: 3 }).map((_, index) => (
          <Skeleton key={index} className="h-[420px] admin-page-surface" />
        ))}
      </PageRow>
      <PageRow columns={3}>
        {Array.from({ length: 3 }).map((_, index) => (
          <Skeleton key={index} className="h-64 admin-page-surface" />
        ))}
      </PageRow>
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

  const deleteScheduled = React.useCallback(
    async (event: DashboardEvent) => {
      const base = DELETE_PATH_BY_KIND[event.kind];
      if (!base || event.action_id === null) return;
      setError("");
      try {
        const response = await fetch(`${base}/${event.action_id}`, {
          method: "DELETE",
          credentials: "same-origin",
          headers: { Accept: "application/json" },
        });
        if (!response.ok) {
          const body = await response.json().catch(() => ({}));
          throw new Error((body as { detail?: string }).detail || "Не удалось удалить действие");
        }
        setPayload(await requestDashboard(apiUrl));
      } catch (deleteError) {
        setError(deleteError instanceof Error ? deleteError.message : "Не удалось удалить действие");
      }
    },
    [apiUrl],
  );

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
    <>
      <PageHeader
        title="Оперативный дашборд"
        actions={<Badge variant="secondary">Обновлено {payload.meta.generated_at ? "сейчас" : "—"}</Badge>}
      />
      <div className="admin-page-stack">

      {/*
        * Описания страницы здесь нет. Оно уехало из полосы заголовка в контент,
        * а потом ушло совсем: подпись на фоне страницы не принадлежит ни одному
        * блоку и пересказывает то, что уже написано на модулях.
        */}
      {/* Стат-плитки лежат прямо на полосе: обёртки ради обёртки у них нет. */}
      <PageRow columns={4}>
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
      </PageRow>

      <PageRow columns={3}>
        {/*
          * У событий счётчика нет намеренно: записи сгруппированы по датам,
          * и одно число рядом с именем обещало бы плоский список.
          */}
        <PageSection title="Ближайшие события">
          <UpcomingEvents events={payload.upcoming_events} onDelete={deleteScheduled} />
        </PageSection>
        <PageSection title="Требует внимания" counter={payload.attention_items.length}>
          <AttentionItems items={payload.attention_items} />
        </PageSection>
        <PageSection title="Свежие Telegram-привязки" counter={payload.telegram_links.length}>
          <TelegramLinks items={payload.telegram_links} />
        </PageSection>
      </PageRow>

      <PageRow columns={3}>
        <PageSection title="Входящие документы" counter={payload.inbound_files.length}>
          <InboundFiles items={payload.inbound_files} />
        </PageSection>
        <PageSection title="История отправок" counter={payload.sent_history.length}>
          <SentHistory items={payload.sent_history} />
        </PageSection>
        <PageSection title="Модули">
          <ModuleLinks items={payload.module_links} />
        </PageSection>
      </PageRow>
      </div>
    </>
  );
}
