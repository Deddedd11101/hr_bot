import React from "react";
import ReactDOM from "react-dom/client";
import {
  ArrowUpDown,
  BriefcaseBusiness,
  LayoutGrid,
  List,
  ChevronsUpDown,
  ExternalLink,
  FileClock,
  MessageCircle,
  Plus,
  Search,
  Sparkles,
  Users,
  X,
} from "lucide-react";

import "@/index.css";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { ScrollArea } from "@/components/ui/scroll-area";

type EmployeeItem = {
  id: number;
  full_name: string;
  chat_id: string;
  chat_handle: string;
  chat_link?: string | null;
  position: string;
  status_label: string;
  candidate_work_stage_label: string;
  planned_scenario_title: string;
  first_workday: string | null;
  first_workday_label: string;
  test_task_due_at: string | null;
  test_task_due_at_label: string;
  workdays: number;
  edit_url: string;
  react_edit_url: string;
  list_kind: "employees" | "candidates";
};

type EmployeesMeta = {
  active_tab: "employees" | "candidates";
  list_title: string;
  empty_message: string;
  create_button_label: string;
  create_modal_title: string;
  create_intro: string;
  first_workday_label: string;
  default_employee_stage: string;
  list_kind: "employees" | "candidates";
  classic_page_url: string;
};

type EmployeesPayload = {
  meta: EmployeesMeta;
  items: EmployeeItem[];
};

type CreatePayload = {
  meta: EmployeesMeta;
  item: EmployeeItem | null;
};

type Option = {
  value: string;
  label: string;
};

type ListKind = "employees" | "candidates";
type ViewMode = "cards" | "table";

const rootElement = document.getElementById("react-employees-root");

function listKindOptions(): Option[] {
  return [
    { value: "employees", label: "Сотрудники" },
    { value: "candidates", label: "Кандидаты" },
  ];
}

function statusOptions(listKind: "employees" | "candidates"): Option[] {
  if (listKind === "candidates") {
    return [
      { value: "all", label: "Все этапы" },
      { value: "Тестирование", label: "Тестирование" },
      { value: "Оффер", label: "Оффер" },
      { value: "Отказ кандидата", label: "Отказ кандидата" },
      { value: "Наш отказ", label: "Наш отказ" },
      { value: "Преонбординг", label: "Преонбординг" },
      { value: "Заключение договора", label: "Заключение договора" },
    ];
  }
  return [
    { value: "all", label: "Все статусы" },
    { value: "Адаптация", label: "Адаптация" },
    { value: "ИПР", label: "ИПР" },
    { value: "В штате", label: "В штате" },
  ];
}

function sortOptions(listKind: "employees" | "candidates"): Option[] {
  const base = [
    { value: "id_desc", label: "Сначала новые" },
    { value: "name_asc", label: "По имени А-Я" },
    { value: "name_desc", label: "По имени Я-А" },
  ];
  if (listKind === "candidates") {
    return base.concat([
      { value: "deadline_asc", label: "Ближайший дедлайн" },
      { value: "deadline_desc", label: "Поздний дедлайн" },
    ]);
  }
  return base.concat([
    { value: "workday_asc", label: "Ближайший выход" },
    { value: "workday_desc", label: "Поздний выход" },
  ]);
}

function SinglePicker({
  value,
  options,
  onChange,
  icon,
}: {
  value: string;
  options: Option[];
  onChange: (next: string) => void;
  icon?: React.ReactNode;
}) {
  const [open, setOpen] = React.useState(false);
  const selected = options.find((option) => option.value === value) || options[0];

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="secondary" className="justify-between gap-3">
          <span className="inline-flex min-w-0 items-center gap-2 truncate">
            {icon}
            <span className="truncate">{selected?.label}</span>
          </span>
          <ChevronsUpDown className="size-4 opacity-60" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[var(--radix-popover-trigger-width)] p-1.5" align="start">
        <div className="flex flex-col gap-1">
          {options.map((option) => {
            const active = option.value === value;
            return (
              <button
                key={option.value}
                type="button"
                onClick={() => {
                  onChange(option.value);
                  setOpen(false);
                }}
                className={`flex items-center justify-between gap-3 rounded-[10px] px-3 py-2 text-left text-sm transition-all duration-200 hover:rounded-[16px] hover:bg-black/5 ${
                  active ? "bg-[var(--color-panel-muted)]" : ""
                }`}
              >
                <span className="truncate">{option.label}</span>
                {active ? <span className="size-2 rounded-full bg-[var(--color-accent)]" /> : null}
              </button>
            );
          })}
        </div>
      </PopoverContent>
    </Popover>
  );
}

function MetaChip({
  icon,
  label,
}: {
  icon: React.ReactNode;
  label: string;
}) {
  return (
    <span className="inline-flex items-center gap-2 rounded-[10px] bg-black/5 px-2.5 py-1.5 text-[0.72rem] font-medium text-[var(--color-muted-foreground)] transition-all duration-200 hover:rounded-[18px]">
      {icon}
      {label}
    </span>
  );
}

function EmployeeCard({ item }: { item: EmployeeItem }) {
  const isCandidate = item.list_kind === "candidates";
  const statusValue = isCandidate ? item.candidate_work_stage_label : item.status_label;
  const dateLabel = isCandidate ? item.test_task_due_at_label : item.first_workday_label;
  const dateTitle = isCandidate ? "Дедлайн" : "Выход";

  return (
    <article className="flex w-full min-w-0 flex-col gap-3 rounded-[10px] border border-[var(--color-border)] bg-white p-3 transition-all duration-200 hover:rounded-[22px] hover:bg-[var(--color-panel-muted)]">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 space-y-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="truncate text-[1rem] font-semibold">{item.full_name || "Без имени"}</h3>
            <MetaChip
              icon={isCandidate ? <FileClock className="size-3.5" /> : <Sparkles className="size-3.5" />}
              label={statusValue || "Без статуса"}
            />
          </div>
          <div className="flex flex-wrap items-center gap-2 text-[0.92rem] text-[var(--color-muted-foreground)]">
            {item.position ? <span>{item.position}</span> : <span>Без должности</span>}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {item.chat_link ? (
            <a
              href={item.chat_link}
              target="_blank"
              rel="noreferrer noopener"
              className="inline-flex items-center justify-center rounded-[10px] border border-[var(--color-border)] bg-white px-3 py-2 text-sm font-medium transition-all duration-200 hover:rounded-[20px] hover:bg-[var(--color-panel-muted)]"
              title="Открыть чат"
            >
              <MessageCircle className="size-4" />
            </a>
          ) : null}
          <a
            href={item.react_edit_url || item.edit_url}
            className="inline-flex items-center justify-center rounded-[10px] border border-[var(--color-border)] bg-white px-3 py-2 text-sm font-medium transition-all duration-200 hover:rounded-[20px] hover:bg-[var(--color-panel-muted)]"
            title="Открыть карточку"
          >
            <ExternalLink className="size-4" />
          </a>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <MetaChip icon={<MessageCircle className="size-3.5" />} label={item.chat_id || item.chat_handle || "Канал не привязан"} />
        <MetaChip icon={<BriefcaseBusiness className="size-3.5" />} label={`${dateTitle}: ${dateLabel || "—"}`} />
        {item.planned_scenario_title && item.planned_scenario_title !== "—" ? (
          <MetaChip icon={<Sparkles className="size-3.5" />} label={item.planned_scenario_title} />
        ) : null}
      </div>
    </article>
  );
}

function EmployeeTableRow({ item }: { item: EmployeeItem }) {
  const isCandidate = item.list_kind === "candidates";
  const statusValue = isCandidate ? item.candidate_work_stage_label : item.status_label;
  const dateLabel = isCandidate ? item.test_task_due_at_label : item.first_workday_label;

  return (
    <article className="flex w-full min-w-0 items-center gap-3 rounded-[10px] border border-[var(--color-border)] bg-white px-4 py-3 text-sm transition-all duration-200 hover:rounded-[22px] hover:bg-[var(--color-panel-muted)]">
      <div className="min-w-0 flex-[1.6]">
        <div className="truncate font-semibold">{item.full_name || "Без имени"}</div>
        <div className="truncate text-[0.86rem] text-[var(--color-muted-foreground)]">{item.position || "Без должности"}</div>
      </div>
      <div className="min-w-0 flex-1 truncate text-[var(--color-muted-foreground)]">{statusValue || "—"}</div>
      <div className="min-w-0 flex-1 truncate text-[var(--color-muted-foreground)]">{item.chat_id || item.chat_handle || "—"}</div>
      <div className="min-w-0 flex-[0.9] truncate text-[var(--color-muted-foreground)]">{dateLabel || "—"}</div>
      <div className="min-w-0 flex-[1.2] truncate text-[var(--color-muted-foreground)]">{item.planned_scenario_title || "—"}</div>
      <div className="flex shrink-0 items-center gap-2">
        {item.chat_link ? (
          <a
            href={item.chat_link}
            target="_blank"
            rel="noreferrer noopener"
            className="inline-flex items-center justify-center rounded-[10px] border border-[var(--color-border)] bg-white px-3 py-2 text-sm font-medium transition-all duration-200 hover:rounded-[20px] hover:bg-[var(--color-panel-muted)]"
            title="Открыть чат"
          >
            <MessageCircle className="size-4" />
          </a>
        ) : null}
        <a
          href={item.react_edit_url || item.edit_url}
          className="inline-flex items-center justify-center rounded-[10px] border border-[var(--color-border)] bg-white px-3 py-2 text-sm font-medium transition-all duration-200 hover:rounded-[20px] hover:bg-[var(--color-panel-muted)]"
          title="Открыть карточку"
        >
          <ExternalLink className="size-4" />
        </a>
      </div>
    </article>
  );
}

function kindCreateOptions(): Option[] {
  return [
    { value: "employees", label: "Сотрудник" },
    { value: "candidates", label: "Кандидат" },
  ];
}

function employeeStageCreateOptions(): Option[] {
  return [
    { value: "staff", label: "В штате" },
    { value: "adaptation", label: "Адаптация" },
    { value: "ipr", label: "ИПР" },
  ];
}

function candidateStageCreateOptions(): Option[] {
  return [
    { value: "testing", label: "Тестирование" },
    { value: "offer", label: "Оффер" },
    { value: "candidate_decline", label: "Отказ кандидата" },
    { value: "company_decline", label: "Наш отказ" },
    { value: "preonboarding", label: "Преонбординг" },
    { value: "contract", label: "Заключение договора" },
  ];
}

function App() {
  const apiBaseUrl = rootElement?.getAttribute("data-api-base-url") || "/api/employees";
  const createUrl = rootElement?.getAttribute("data-create-url") || "/api/employees";
  const defaultListKind = (rootElement?.getAttribute("data-default-list-kind") || "employees") as ListKind;

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
    const firstLoad = !payload;
    if (firstLoad) {
      setLoading(true);
    }
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
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || "Не удалось создать запись");
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
    <div className="mx-auto w-full max-w-[1960px] px-1">
      <section className="flex min-h-0 flex-col overflow-hidden rounded-[10px] border border-[var(--color-border)] bg-[var(--color-panel)] p-4 shadow-[var(--shadow-soft)]">
        <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div className="flex flex-wrap gap-2">
            {listKindOptions().map((option) => {
              const active = option.value === listKind;
              return (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setListKind(option.value as ListKind)}
                  className={`inline-flex items-center gap-2 rounded-[10px] border px-4 py-2.5 text-sm font-medium transition-all duration-200 hover:rounded-[20px] ${
                    active
                      ? "border-[var(--color-accent)] bg-[var(--color-panel-muted)]"
                      : "border-[var(--color-border)] bg-white hover:bg-[var(--color-panel-muted)]"
                  }`}
                >
                  {option.value === "employees" ? <Users className="size-4" /> : <FileClock className="size-4" />}
                  {option.label}
                </button>
              );
            })}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <MetaChip icon={<Users className="size-3.5" />} label={`${stats.total} всего`} />
            <MetaChip icon={<MessageCircle className="size-3.5" />} label={`${stats.withChannel} с каналом`} />
            <MetaChip icon={<Sparkles className="size-3.5" />} label={`${visibleItems.length} в выдаче`} />
            <Button size="sm" onClick={() => setCreating((prev) => !prev)}>
              {creating ? <X className="size-4" /> : <Plus className="size-4" />}
              {creating ? "Закрыть" : "Добавить"}
            </Button>
          </div>
        </div>

        {creating ? (
          <div
            className="mb-4 rounded-[10px] border border-[var(--color-border)] bg-[var(--color-panel-muted)] p-3 transition-all duration-200 hover:rounded-[20px]"
            style={{
              display: "grid",
              gap: "12px",
              gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
              alignItems: "end",
            }}
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
            />
            <Input
              placeholder="ФИО"
              value={form.full_name}
              onChange={(event) => setForm((prev) => ({ ...prev, full_name: event.target.value }))}
            />
            <Button onClick={handleCreate} disabled={submitting || !form.full_name.trim()}>
              {submitting ? "Создаю..." : "Готово"}
            </Button>
            {submitError ? <p className="md:col-span-4 text-sm text-[var(--color-danger)]">{submitError}</p> : null}
          </div>
        ) : null}

        <div className="mb-4 flex flex-wrap items-center gap-3">
            <div className="relative min-w-[280px] flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-[var(--color-muted-foreground)]" />
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
              icon={listKind === "candidates" ? <FileClock className="size-4 opacity-70" /> : <Sparkles className="size-4 opacity-70" />}
            />
            <SinglePicker
              value={sortMode}
              options={sortOptions(listKind)}
              onChange={setSortMode}
              icon={<ArrowUpDown className="size-4 opacity-70" />}
            />
            <div className="flex items-center gap-1 rounded-[10px] border border-[var(--color-border)] bg-white p-1">
              <button
                type="button"
                onClick={() => setViewMode("cards")}
                className={`inline-flex items-center justify-center rounded-[8px] px-3 py-2 transition-all duration-200 hover:rounded-[16px] ${
                  viewMode === "cards" ? "bg-[var(--color-panel-muted)]" : ""
                }`}
                title="Карточки"
              >
                <LayoutGrid className="size-4" />
              </button>
              <button
                type="button"
                onClick={() => setViewMode("table")}
                className={`inline-flex items-center justify-center rounded-[8px] px-3 py-2 transition-all duration-200 hover:rounded-[16px] ${
                  viewMode === "table" ? "bg-[var(--color-panel-muted)]" : ""
                }`}
                title="Таблица"
              >
                <List className="size-4" />
              </button>
            </div>
        </div>

        <ScrollArea className="min-h-0 flex-1">
          <div className="relative pr-2">
            {loading ? (
              <div className="rounded-[10px] border border-[var(--color-border)] bg-[var(--color-panel-muted)] px-4 py-10 text-center text-sm text-[var(--color-muted-foreground)]">
                Загружаю список…
              </div>
            ) : error ? (
              <div className="rounded-[10px] border border-[var(--color-border)] bg-[var(--color-panel-muted)] px-4 py-10 text-center text-sm text-[var(--color-danger)]">
                {error}
              </div>
            ) : visibleItems.length === 0 ? (
              <div className="rounded-[10px] border border-[var(--color-border)] bg-[var(--color-panel-muted)] px-4 py-10 text-center text-sm text-[var(--color-muted-foreground)]">
                {meta?.empty_message || "Список пока пуст."}
              </div>
            ) : (
              <div
                className="transition-opacity duration-200"
                style={
                  viewMode === "cards"
                    ? {
                        display: "grid",
                        gap: "12px",
                        gridTemplateColumns: "repeat(auto-fit, minmax(420px, 1fr))",
                        alignItems: "start",
                      }
                    : {
                        display: "flex",
                        flexDirection: "column",
                        gap: "10px",
                      }
                }
              >
                {viewMode === "table" ? (
                  <div className="sticky top-0 z-[1] flex items-center gap-3 rounded-[10px] border border-[var(--color-border)] bg-[var(--color-panel)] px-4 py-2 text-[0.72rem] font-semibold uppercase tracking-[0.16em] text-[var(--color-muted-foreground)] shadow-[var(--shadow-soft)]">
                    <div className="min-w-0 flex-[1.6]">ФИО</div>
                    <div className="min-w-0 flex-1">Статус</div>
                    <div className="min-w-0 flex-1">Канал</div>
                    <div className="min-w-0 flex-[0.9]">{listKind === "candidates" ? "Дедлайн" : "Выход"}</div>
                    <div className="min-w-0 flex-[1.2]">Сценарий</div>
                    <div className="w-[88px] shrink-0 text-right">Действия</div>
                  </div>
                ) : null}
                {visibleItems.map((item) =>
                  viewMode === "cards" ? <EmployeeCard key={item.id} item={item} /> : <EmployeeTableRow key={item.id} item={item} />
                )}
              </div>
            )}
          </div>
        </ScrollArea>
      </section>
    </div>
  );
}

if (rootElement) {
  ReactDOM.createRoot(rootElement).render(<App />);
}
