import * as React from "react";
import {
  ArrowUpDown,
  BadgeCheck,
  BriefcaseBusiness,
  FileClock,
  LayoutGrid,
  ListFilter,
  List,
  MessageCircle,
  Plus,
  Search,
  Users,
  X,
} from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";

import {
  candidateStageCreateOptions,
  employeeStageCreateOptions,
  kindCreateOptions,
  listKindOptions,
  sortOptions,
  statusOptions,
} from "./data";
import { EmployeeCard, EmployeeTableRow, MetaChip, SinglePicker } from "./components";
import type { CreatePayload, EmployeesPayload, ListKind, ViewMode } from "./types";

export function EmployeesListPage({
  apiBaseUrl,
  createUrl,
  defaultListKind,
}: {
  apiBaseUrl: string;
  createUrl: string;
  defaultListKind: ListKind;
}) {
  const [listKind, setListKind] = React.useState<ListKind>(defaultListKind);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState("");
  const [payload, setPayload] = React.useState<EmployeesPayload | null>(null);
  const [search, setSearch] = React.useState("");
  const [statusFilter, setStatusFilter] = React.useState("all");
  const [sortMode, setSortMode] = React.useState("id_desc");
  const [viewMode, setViewMode] = React.useState<ViewMode>("cards");
  const [creating, setCreating] = React.useState(false);
  const [submitting, setSubmitting] = React.useState(false);
  const [submitError, setSubmitError] = React.useState("");
  const [form, setForm] = React.useState({
    list_kind: defaultListKind,
    full_name: "",
    employee_stage: "staff",
    candidate_work_stage: "testing",
  });

  React.useEffect(() => {
    setLoading(true);
    setError("");
    fetch(`${apiBaseUrl}?list_kind=${encodeURIComponent(listKind)}`, {
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    })
      .then(async (response) => {
        if (!response.ok) throw new Error("Не удалось загрузить сотрудников");
        return (await response.json()) as EmployeesPayload;
      })
      .then((nextPayload) => {
        setPayload(nextPayload);
      })
      .catch((loadError: Error) => {
        setError(loadError.message || "Не удалось загрузить сотрудников");
      })
      .finally(() => {
        setLoading(false);
      });
  }, [apiBaseUrl, listKind]);

  React.useEffect(() => {
    setStatusFilter("all");
    setSortMode("id_desc");
    setSearch("");
    setCreating(false);
    setSubmitError("");
    setForm({
      list_kind: listKind,
      full_name: "",
      employee_stage: listKind === "candidates" ? "candidate" : "staff",
      candidate_work_stage: "testing",
    });
  }, [listKind]);

  const items = payload?.items || [];
  const meta = payload?.meta;
  const payloadListKind = (meta?.list_kind || listKind) as ListKind;

  const visibleItems = React.useMemo(() => {
    let next = items.filter((item) => {
      const currentStatus = payloadListKind === "candidates" ? item.candidate_work_stage_label || "—" : item.status_label || "—";
      const matchesStatus = statusFilter === "all" || currentStatus === statusFilter;
      const query = search.trim().toLowerCase();
      const matchesSearch =
        !query ||
        [
          item.full_name,
          item.chat_id,
          item.chat_handle,
          item.position,
          item.status_label,
          item.candidate_work_stage_label,
          item.planned_scenario_title,
        ]
          .filter(Boolean)
          .join(" ")
          .toLowerCase()
          .includes(query);

      return matchesStatus && matchesSearch;
    });

    next = next.slice().sort((left, right) => {
      if (sortMode === "name_asc") return (left.full_name || "").localeCompare(right.full_name || "", "ru");
      if (sortMode === "name_desc") return (right.full_name || "").localeCompare(left.full_name || "", "ru");
      if (sortMode === "deadline_asc") return (left.test_task_due_at || "9999-12-31").localeCompare(right.test_task_due_at || "9999-12-31");
      if (sortMode === "deadline_desc") return (right.test_task_due_at || "").localeCompare(left.test_task_due_at || "");
      if (sortMode === "workday_asc") return (left.first_workday || "9999-12-31").localeCompare(right.first_workday || "9999-12-31");
      if (sortMode === "workday_desc") return (right.first_workday || "").localeCompare(left.first_workday || "");
      return (right.id || 0) - (left.id || 0);
    });

    return next;
  }, [items, payloadListKind, search, sortMode, statusFilter]);

  const stats = React.useMemo(() => {
    const withChannel = items.filter((item) => Boolean(item.chat_id || item.chat_handle)).length;
    const withScenario = items.filter((item) => item.planned_scenario_title && item.planned_scenario_title !== "—").length;
    return {
      total: items.length,
      withChannel,
      withScenario,
    };
  }, [items]);

  const handleCreate = async () => {
    setSubmitting(true);
    setSubmitError("");
    try {
      const response = await fetch(createUrl, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify({
          list_kind: form.list_kind,
          full_name: form.full_name,
          employee_stage: form.employee_stage,
          candidate_work_stage: form.candidate_work_stage,
        }),
      });
      if (!response.ok) {
        const errorPayload = await response.json().catch(() => ({}));
        throw new Error(errorPayload.detail || "Не удалось создать запись");
      }

      const result = (await response.json()) as CreatePayload;
      const nextKind = form.list_kind;
      setPayload((prev) => {
        const nextMeta = result.meta || prev?.meta || meta;
        const nextItems =
          nextKind === listKind && result.item ? [result.item].concat(prev?.items || []) : prev?.items || [];
        return {
          meta: nextMeta!,
          items: nextItems,
        };
      });
      setListKind(nextKind);
      setCreating(false);
      setForm({
        list_kind: nextKind,
        full_name: "",
        employee_stage: nextKind === "candidates" ? "candidate" : "staff",
        candidate_work_stage: "testing",
      });
    } catch (createError) {
      setSubmitError(createError instanceof Error ? createError.message : "Не удалось создать запись");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="admin-page-shell">
      <Card className="admin-page-surface flex min-h-0 flex-col overflow-hidden border border-border bg-card p-4 shadow-none ring-0">
        <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div className="flex flex-wrap gap-2">
            {listKindOptions().map((option) => {
              const active = option.value === listKind;
              return (
                <Button
                  key={option.value}
                  variant={active ? "default" : "outline"}
                  size="sm"
                  onClick={() => setListKind(option.value as ListKind)}
                >
                  {option.value === "employees" ? <Users data-icon="inline-start" /> : <FileClock data-icon="inline-start" />}
                  {option.label}
                </Button>
              );
            })}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <MetaChip icon={<Users className="size-3.5" />} label={`${stats.total} всего`} />
            <MetaChip icon={<MessageCircle className="size-3.5" />} label={`${stats.withChannel} с каналом`} />
            <MetaChip icon={<ListFilter className="size-3.5" />} label={`${visibleItems.length} в выдаче`} />
            <Button size="sm" onClick={() => setCreating((prev) => !prev)}>
              {creating ? <X data-icon="inline-start" /> : <Plus data-icon="inline-start" />}
              {creating ? "Закрыть" : "Добавить"}
            </Button>
          </div>
        </div>

        {creating ? (
          <div
            className="mb-4 flex flex-wrap items-end gap-2 rounded-lg border border-border bg-muted/45 p-3"
          >
            <SinglePicker
              value={form.list_kind}
              options={kindCreateOptions()}
              onChange={(next) =>
                setForm((prev) => ({
                  ...prev,
                  list_kind: next as ListKind,
                  employee_stage: next === "candidates" ? "candidate" : "staff",
                  candidate_work_stage: "testing",
                }))
              }
              icon={<Plus className="size-4 opacity-70" />}
              className="w-[180px] min-w-[180px]"
            />
            <SinglePicker
              value={form.list_kind === "candidates" ? form.candidate_work_stage : form.employee_stage}
              options={form.list_kind === "candidates" ? candidateStageCreateOptions() : employeeStageCreateOptions()}
              onChange={(next) =>
                setForm((prev) =>
                  prev.list_kind === "candidates"
                    ? { ...prev, candidate_work_stage: next }
                    : { ...prev, employee_stage: next }
                )
              }
              icon={<BriefcaseBusiness className="size-4 opacity-70" />}
              className="w-[210px] min-w-[210px]"
            />
            <Input
              className="w-[280px] flex-none"
              placeholder="ФИО"
              value={form.full_name}
              onChange={(event) => setForm((prev) => ({ ...prev, full_name: event.target.value }))}
            />
            <Button onClick={handleCreate} disabled={submitting || !form.full_name.trim()}>
              {submitting ? "Создаю..." : "Готово"}
            </Button>
            {submitError ? (
              <Alert variant="destructive" className="md:col-span-4">
                <AlertTitle>Не удалось создать запись</AlertTitle>
                <AlertDescription>{submitError}</AlertDescription>
              </Alert>
            ) : null}
          </div>
        ) : null}

        <div className="mb-4 flex flex-wrap items-center gap-3">
          <div className="relative min-w-[280px] flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              className="pl-9"
              placeholder={listKind === "candidates" ? "Поиск по кандидатам" : "Поиск по сотрудникам"}
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>
          <SinglePicker
            value={statusFilter}
            options={statusOptions(listKind)}
            onChange={setStatusFilter}
            icon={listKind === "candidates" ? <FileClock className="size-4 opacity-70" /> : <BadgeCheck className="size-4 opacity-70" />}
          />
          <SinglePicker
            value={sortMode}
            options={sortOptions(listKind)}
            onChange={setSortMode}
            icon={<ArrowUpDown className="size-4 opacity-70" />}
          />
          <div className="flex items-center gap-1 rounded-lg border border-border bg-background p-1">
            <Button
              variant={viewMode === "cards" ? "secondary" : "ghost"}
              size="icon-sm"
              onClick={() => setViewMode("cards")}
              title="Карточки"
              aria-label="Карточки"
            >
              <LayoutGrid />
            </Button>
            <Button
              variant={viewMode === "table" ? "secondary" : "ghost"}
              size="icon-sm"
              onClick={() => setViewMode("table")}
              title="Таблица"
              aria-label="Таблица"
            >
              <List />
            </Button>
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-auto">
          <div className="relative pr-2">
            {loading ? (
              <div className="grid gap-3">
                {Array.from({ length: 5 }).map((_, index) => (
                  <Skeleton key={index} className="h-[104px] rounded-lg" />
                ))}
              </div>
            ) : error ? (
              <Alert variant="destructive">
                <AlertTitle>Список не загрузился</AlertTitle>
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            ) : visibleItems.length === 0 ? (
              <Empty className="min-h-[220px] border border-border bg-muted/35">
                <EmptyHeader>
                  <EmptyMedia variant="icon">
                    <Users />
                  </EmptyMedia>
                  <EmptyTitle>Нет записей</EmptyTitle>
                  <EmptyDescription>{meta?.empty_message || "Список пока пуст."}</EmptyDescription>
                </EmptyHeader>
              </Empty>
            ) : (
              <div
                className="transition-opacity duration-200"
                data-view={viewMode}
              >
                {viewMode === "table" ? (
                  <div className="sticky top-0 z-[1] flex items-center gap-3 rounded-lg border border-border bg-card px-4 py-2 text-[0.72rem] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                    <div className="min-w-0 flex-[1.6]">ФИО</div>
                    <div className="min-w-0 flex-1">Статус</div>
                    <div className="min-w-0 flex-1">Канал</div>
                    <div className="min-w-0 flex-[0.9]">{listKind === "candidates" ? "Дедлайн" : "Выход"}</div>
                    <div className="min-w-0 flex-[1.2]">Сценарий</div>
                    <div className="w-[88px] shrink-0 text-right">Действия</div>
                  </div>
                ) : null}
                <div
                  className={
                    viewMode === "cards"
                      ? "grid items-start gap-3 [grid-template-columns:repeat(auto-fit,minmax(420px,1fr))]"
                      : "flex flex-col gap-2.5"
                  }
                >
                  {visibleItems.map((item) =>
                    viewMode === "cards" ? <EmployeeCard key={item.id} item={item} /> : <EmployeeTableRow key={item.id} item={item} />
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </Card>
    </div>
  );
}
