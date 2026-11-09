import * as React from "react";
import { RefreshCw, ArrowRight } from "lucide-react";
import { Button, buttonVariants } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";
import { PageSection, PageSectionRows } from "@/components/ui/page-section";
import { Badge } from "@/components/ui/badge";
import { QueueView, HistoryView } from "./operations";
import type { DashboardPayload } from "./types";

export function DashboardPage({ apiUrl }: { apiUrl: string }) {
  const [payload, setPayload] = React.useState<DashboardPayload | null>(null);
  const [error, setError] = React.useState("");
  const [revision, refresh] = React.useReducer((n) => n + 1, 0);
  React.useEffect(() => {
    const controller = new AbortController();
    async function load() {
      try {
        const response = await fetch(apiUrl, {
          signal: controller.signal,
          credentials: "same-origin",
        });
        if (!response.ok) throw new Error("Не удалось загрузить дашборд");
        const data = await response.json();
        if (!controller.signal.aborted) {
          setPayload(data);
          setError("");
        }
      } catch (e) {
        if (!controller.signal.aborted)
          setError(e instanceof Error ? e.message : "Ошибка загрузки");
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
  }, [apiUrl, revision]);
  return (
    <>
      <PageHeader
        title="Оперативный дашборд"
        actions={
          <Button
            variant="outline"
            size="icon-sm"
            title="Обновить дашборд"
            aria-label="Обновить дашборд"
            onClick={refresh}
          >
            <RefreshCw />
          </Button>
        }
      />
      <div className="admin-page-stack">
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
        <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
          <PageSection
            title="Очередь сценариев"
            action={
              <a
                href="/app/scenario-queue"
                className={buttonVariants({ variant: "ghost", size: "sm" })}
              >
                Открыть очередь <ArrowRight />
              </a>
            }
          >
            <QueueView compact />
          </PageSection>
          <PageSection
            title="Требует внимания"
            counter={payload?.attention_items.length}
          >
            {!payload ? (
              <p role="status" className="text-sm text-muted-foreground">
                Загрузка...
              </p>
            ) : !payload.attention_items.length ? (
              <p className="py-4 text-sm text-muted-foreground">
                Проблем, требующих вмешательства, не найдено.
              </p>
            ) : (
              <PageSectionRows>
                {payload.attention_items.map((item) => (
                  <a
                    key={item.id}
                    href={item.href}
                    className="block space-y-1 py-2 hover:text-primary"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <p className="break-words text-sm font-medium">
                        {item.title}
                      </p>
                      <Badge
                        variant={
                          item.severity === "danger"
                            ? "destructive"
                            : "secondary"
                        }
                      >
                        {item.kind === "scenario_error"
                          ? "Сценарий"
                          : item.kind === "overdue_test_task"
                            ? "Дедлайн"
                            : "Доступ"}
                      </Badge>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {item.subtitle}
                    </p>
                  </a>
                ))}
              </PageSectionRows>
            )}
          </PageSection>
        </div>
        <PageSection title="История событий">
          <HistoryView />
        </PageSection>
        <div className="grid min-w-0 gap-4 lg:grid-cols-2">
          <PageSection
            title="Свежие Telegram-привязки"
            counter={payload?.telegram_links.length}
          >
            {payload ? (
              payload.telegram_links.length ? (
                <PageSectionRows>
                  {payload.telegram_links.map((item) => (
                    <a
                      key={`${item.employee_id}-${item.linked_at}`}
                      href={item.href}
                      className="block space-y-1 py-2 hover:text-primary"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="text-sm font-medium">
                          {item.full_name}
                        </span>
                        <Badge variant="outline">{item.person_label}</Badge>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        {item.handle_or_id} · {item.linked_at_label}
                      </p>
                    </a>
                  ))}
                </PageSectionRows>
              ) : (
                <p className="py-4 text-sm text-muted-foreground">
                  Новых привязок нет.
                </p>
              )
            ) : (
              <p role="status">Загрузка...</p>
            )}
          </PageSection>
          <PageSection
            title="Входящие документы"
            counter={payload?.inbound_files.length}
          >
            {payload ? (
              payload.inbound_files.length ? (
                <PageSectionRows>
                  {payload.inbound_files.map((item) => (
                    <a
                      key={item.id}
                      href={item.href}
                      className="block space-y-1 py-2 hover:text-primary"
                    >
                      <p className="break-words text-sm font-medium">
                        {item.filename}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {item.full_name} · {item.created_at_label}
                      </p>
                    </a>
                  ))}
                </PageSectionRows>
              ) : (
                <p className="py-4 text-sm text-muted-foreground">
                  Новых документов нет.
                </p>
              )
            ) : (
              <p role="status">Загрузка...</p>
            )}
          </PageSection>
        </div>
      </div>
    </>
  );
}
