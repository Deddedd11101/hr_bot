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
  Users,
  X,
} from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";
import { RecordCardTag } from "@/components/ui/record-card";
import {
  PageFilters,
  PageFiltersSearch,
  PageFiltersSegments,
} from "@/components/ui/page-filters";
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
  COLUMNS_STORAGE_KEY,
  VIEW_STORAGE_KEY,
  parseSort,
  readStoredColumns,
  readStoredView,
  sortOptionsWithCurrent,
  statusOptions,
} from "./data";
import {
  EmployeeCard,
  EmployeeColumnsPicker,
  EmployeeTable,
  SinglePicker,
} from "./components";
import type { CreatePayload, EmployeeItem, EmployeesPayload, ListKind, ViewMode } from "./types";

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
  /*
   * Вид и набор колонок читаются из хранилища прямо в инициализаторе.
   * В эффекте было бы поздно: первый кадр отрисовался бы значением
   * по умолчанию, и раскладка прыгнула бы на глазах.
   */
  const [viewMode, setViewMode] = React.useState<ViewMode>(readStoredView);
  const [visibleColumns, setVisibleColumns] = React.useState(readStoredColumns);
  React.useEffect(() => {
    window.localStorage.setItem(VIEW_STORAGE_KEY, viewMode);
  }, [viewMode]);

  React.useEffect(() => {
    window.localStorage.setItem(COLUMNS_STORAGE_KEY, JSON.stringify(visibleColumns));
  }, [visibleColumns]);

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

    /*
     * Одно сравнение на все поля вместо шести веток по строковому режиму:
     * колонок стало пять, и перечислять их парами «поле_направление»
     * пришлось бы двенадцатью строками.
     *
     * Пустое значение всегда уезжает вниз, независимо от направления:
     * запись без даты не «самая ранняя» и не «самая поздняя», её просто
     * нет смысла показывать первой.
     */
    const { field, direction } = parseSort(sortMode);
    const isCandidates = payloadListKind === "candidates";

    const ключ = (item: EmployeeItem): string => {
      if (field === "name") return item.full_name || "";
      if (field === "position") return item.position || "";
      if (field === "status") return (isCandidates ? item.candidate_work_stage_label : item.status_label) || "";
      if (field === "channel") return item.chat_id || item.chat_handle || "";
      if (field === "date") return (isCandidates ? item.test_task_due_at : item.first_workday) || "";
      if (field === "scenario") return item.planned_scenario_title === "—" ? "" : item.planned_scenario_title || "";
      return "";
    };

    next = next.slice().sort((left, right) => {
      if (field === "id") {
        const порядок = (right.id || 0) - (left.id || 0);
        return direction === "desc" ? порядок : -порядок;
      }

      const слева = ключ(left);
      const справа = ключ(right);
      if (!слева && !справа) return (right.id || 0) - (left.id || 0);
      if (!слева) return 1;
      if (!справа) return -1;

      const сравнение =
        field === "date" ? слева.localeCompare(справа) : слева.localeCompare(справа, "ru");
      return direction === "asc" ? сравнение : -сравнение;
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
    <>
      <PageHeader
        /*
         * Раздел называется «Люди», а не «Сотрудники»: ниже в полосе
         * фильтров стоят чипы «Сотрудники» и «Кандидаты», и имя раздела,
         * совпадающее с одним из чипов, читалось как выбранный набор.
         */
        title="Люди"
        actions={
          <>
            <RecordCardTag icon={<Users className="size-3.5" />} label={`${stats.total} всего`} />
            <RecordCardTag icon={<MessageCircle className="size-3.5" />} label={`${stats.withChannel} с каналом`} />
            <RecordCardTag icon={<ListFilter className="size-3.5" />} label={`${visibleItems.length} в выдаче`} />
            <Button size="sm" onClick={() => setCreating((prev) => !prev)}>
              {creating ? <X data-icon="inline-start" /> : <Plus data-icon="inline-start" />}
              {creating ? "Закрыть" : "Добавить"}
            </Button>
          </>
        }
      />
      <div className="admin-page-shell">

        <PageFilters
          className="mb-4"
          scope={
            <PageFiltersSegments
              label="Набор списка"
              value={listKind}
              options={listKindOptions().map((option) => ({
                value: option.value,
                label: option.label,
                icon:
                  option.value === "employees" ? (
                    <Users data-icon="inline-start" />
                  ) : (
                    <FileClock data-icon="inline-start" />
                  ),
              }))}
              onValueChange={(next) => setListKind(next as ListKind)}
            />
          }
          search={
            <PageFiltersSearch
              value={search}
              onValueChange={setSearch}
              placeholder={listKind === "candidates" ? "Поиск по кандидатам" : "Поиск по сотрудникам"}
            />
          }
          controls={
            <>
              <SinglePicker
                value={statusFilter}
                options={statusOptions(listKind)}
                onChange={setStatusFilter}
                icon={listKind === "candidates" ? <FileClock className="size-4 opacity-70" /> : <BadgeCheck className="size-4 opacity-70" />}
              />
              {/*
                * В табличном виде сортируют заголовки колонок, и селект
                * прячется: два контрола одного и того же состояния на одном
                * экране заставляют гадать, какой из них главный.
                */}
              {viewMode === "cards" ? (
                <SinglePicker
                  value={sortMode}
                  options={sortOptionsWithCurrent(listKind, sortMode)}
                  onChange={setSortMode}
                  icon={<ArrowUpDown className="size-4 opacity-70" />}
                />
              ) : (
                <EmployeeColumnsPicker
                  listKind={listKind}
                  columns={visibleColumns}
                  onChange={setVisibleColumns}
                />
              )}
            </>
          }
          view={
            <PageFiltersSegments
              label="Представление выдачи"
              iconOnly
              value={viewMode}
              /* Таблица первая: она же вид по умолчанию. */
              options={[
                { value: "table", label: "Таблица", icon: <List /> },
                { value: "cards", label: "Карточки", icon: <LayoutGrid /> },
              ]}
              onValueChange={(next) => setViewMode(next as ViewMode)}
            />
          }
        />

        {/* Создание записи — не фильтр, поэтому идёт под полосой, а не над ней. */}
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
              <Alert variant="destructive">
                <AlertTitle>Не удалось создать запись</AlertTitle>
                <AlertDescription>{submitError}</AlertDescription>
              </Alert>
            ) : null}
          </div>
        ) : null}

        {/*
          * Прокручивается страница целиком, поэтому собственного скролла
          * у выдачи нет. Прежние min-h-0 flex-1 overflow-auto и pr-2 обещали
          * его, но не работали: родитель .admin-page-shell — блок, flex-1
          * к нему не применяется, и высота оставалась auto.
          */}
        <div>
          <div className="relative">
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
                {viewMode === "cards" ? (
                  /* Без items-start: сетка растягивает карточки полосы до самой высокой. */
                  <div className="grid gap-3 [grid-template-columns:repeat(auto-fit,minmax(420px,1fr))]">
                    {visibleItems.map((item) => (
                      <EmployeeCard key={item.id} item={item} />
                    ))}
                  </div>
                ) : (
                  <EmployeeTable
                    items={visibleItems}
                    listKind={listKind}
                    sortMode={sortMode}
                    columns={visibleColumns}
                    onSortChange={setSortMode}
                  />
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
