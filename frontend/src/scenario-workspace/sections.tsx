import * as React from "react";
import { ChevronRight, Copy, PanelLeft, Paperclip, Plus, Send, Trash2, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  Card,
  CardContent,
} from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ConfirmAction } from "@/components/ui/confirm-action";
import { EmojiPickerPopover } from "@/components/ui/emoji-picker-popover";
import { Input } from "@/components/ui/input";
import { PageFilters, PageFiltersSearch, PageFiltersSegments } from "@/components/ui/page-filters";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { TelegramFormatToolbar } from "@/components/ui/telegram-format-toolbar";
import { Textarea } from "@/components/ui/textarea";
import { RecordCard, type RecordCardTagSpec } from "@/components/ui/record-card";
import { ПРОЯВЛЕНИЕ } from "@/lib/reveal";
import { cn } from "@/lib/utils";

import {
  buildChildContainer,
  crumbIcon,
  itemKey,
  normalizeNotificationRecipientIds,
  openActionLabel,
  parseRecipientIds,
  responseTypeWaitState,
  ROLE_NOTIFICATION_RECIPIENT_LABELS,
  stepsCountLabel,
  summarizeItem,
  workspaceItemTitle,
} from "./model";
import { NotificationRecipientsPicker, RoleScopesPicker, SingleSelectPicker } from "./pickers";
import type {
  Container,
  ScenarioSettingsForm,
  ScenarioSummary,
  SingleOption,
  WorkspaceButtonNotification,
  WorkspaceButtonNotificationRule,
  WorkspaceData,
  WorkspaceGraph,
  WorkspaceItem,
  WorkspaceRootStepOption,
  WorkspaceStep,
  WorkspaceStepForm,
  WorkspaceTemplateTag,
} from "./types";

const ScenarioGraphView = React.lazy(() => import("./graph-view").then((module) => ({ default: module.ScenarioGraphView })));

export function WorkspaceFlashNotice(props: { message: string; error: boolean }) {
  if (!props.message) {
    return null;
  }

  return (
    <div
      className={`mb-4 rounded-lg border px-4 py-3 text-sm font-medium ${
        props.error
          ? "border-destructive/30 bg-destructive/10 text-destructive"
          : "border-primary/30 bg-primary/5 text-foreground"
      }`}
    >
      {props.message}
    </div>
  );
}

export function ScenarioSettingsDialog(props: {
  open: boolean;
  itemLabelGenitive: string;
  scenarioTitle: string;
  isSurveyWorkspace: boolean;
  scenarioSettingsForm: ScenarioSettingsForm | null;
  scenarioSettingsState: { saving: boolean; message: string; error: boolean };
  roleScopeOptions: SingleOption[];
  employeeScopeOptions: SingleOption[];
  recipientModeOptions: SingleOption[];
  triggerModeOptions: SingleOption[];
  candidateWorkStageOptions: SingleOption[];
  targetEmployeeOptions: SingleOption[];
  onOpenChange: (open: boolean) => void;
  onSave: () => void;
  onFormChange: (updater: (prev: ScenarioSettingsForm | null) => ScenarioSettingsForm | null) => void;
}) {
  const {
    open,
    itemLabelGenitive,
    scenarioTitle,
    isSurveyWorkspace,
    scenarioSettingsForm,
    scenarioSettingsState,
    roleScopeOptions,
    employeeScopeOptions,
    recipientModeOptions,
    triggerModeOptions,
    candidateWorkStageOptions,
    targetEmployeeOptions,
    onOpenChange,
    onSave,
    onFormChange,
  } = props;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {/* sm:max-w-[560px] перебивает sm:max-w-sm базового DialogContent — без него диалог сжимался до 384px. */}
      <DialogContent className="flex h-[min(760px,calc(100vh-40px))] w-[min(560px,calc(100vw-32px))] flex-col gap-0 overflow-hidden p-0 sm:max-w-[560px]">
        <DialogHeader className="shrink-0 border-b border-border px-5 py-4">
          <DialogTitle>Настройки {itemLabelGenitive}</DialogTitle>
          <DialogDescription>{scenarioTitle || "Загружаю данные"}</DialogDescription>
        </DialogHeader>
        {!scenarioSettingsForm ? (
          <div className="px-5 py-8 text-sm font-medium text-muted-foreground">Загружаю настройки…</div>
        ) : (
          <>
            <ScrollArea className="min-h-0 flex-1 rounded-none">
              <div className="grid gap-4 px-5 py-4">
                <label className="grid min-w-0 gap-2.5">
                  <span className="text-sm font-semibold text-foreground/75">Название</span>
                  <Input
                    value={scenarioSettingsForm.title}
                    maxLength={120}
                    placeholder="Название сценария"
                    className="h-10 text-sm"
                    onChange={(event) =>
                      onFormChange((prev) => (prev ? { ...prev, title: event.target.value.slice(0, 120) } : prev))
                    }
                  />
                </label>
                <label className="grid min-w-0 gap-2.5">
                  <span className="text-sm font-semibold text-foreground/75">Описание</span>
                  <div className="relative">
                    <Textarea
                      value={scenarioSettingsForm.description}
                      maxLength={50}
                      placeholder="Коротко"
                      className="min-h-[76px] pr-12 text-sm"
                      onChange={(event) =>
                        onFormChange((prev) => (prev ? { ...prev, description: event.target.value.slice(0, 50) } : prev))
                      }
                    />
                    <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-[0.58rem] font-semibold text-muted-foreground">
                      {scenarioSettingsForm.description.length}/50
                    </span>
                  </div>
                </label>
                <label className="grid min-w-0 gap-2.5">
                  <span className="text-sm font-semibold text-foreground/75">Должность</span>
                  <RoleScopesPicker
                    options={roleScopeOptions}
                    value={scenarioSettingsForm.role_scopes}
                    onChange={(nextValue) =>
                      onFormChange((prev) =>
                        prev
                          ? {
                              ...prev,
                              role_scopes: nextValue,
                              role_scope: nextValue.filter((item) => item && item !== "all").join(",") || "all",
                            }
                          : prev,
                      )
                    }
                  />
                </label>
                <label className="grid min-w-0 gap-2.5">
                  <span className="text-sm font-semibold text-foreground/75">Аудитория</span>
                  <SingleSelectPicker
                    options={employeeScopeOptions}
                    value={scenarioSettingsForm.employee_scope}
                    placeholder="Аудитория"
                    onChange={(nextValue) => onFormChange((prev) => (prev ? { ...prev, employee_scope: nextValue } : prev))}
                  />
                </label>
                <label className="grid min-w-0 gap-2.5">
                  <span className="text-sm font-semibold text-foreground/75">Кому отправлять сценарий</span>
                  <SingleSelectPicker
                    options={recipientModeOptions}
                    value={scenarioSettingsForm.recipient_mode}
                    placeholder="Адресат"
                    onChange={(nextValue) => onFormChange((prev) => (prev ? { ...prev, recipient_mode: nextValue || "self" } : prev))}
                  />
                  <span className="text-xs leading-5 text-muted-foreground">
                    Сценарий запускается по карточке сотрудника, но сообщения получает выбранный адресат.
                  </span>
                </label>
                {scenarioSettingsForm.recipient_mode && scenarioSettingsForm.recipient_mode !== "self" ? (
                  <Alert className="border-warning/30 bg-warning/10">
                    <AlertTitle>Проверь получателя</AlertTitle>
                    <AlertDescription>
                      Получатель должен быть назначен в карточке сотрудника и привязан к Telegram.
                    </AlertDescription>
                  </Alert>
                ) : null}
                {!isSurveyWorkspace ? (
                  <label className="grid min-w-0 gap-2.5">
                    <span className="text-sm font-semibold text-foreground/75">Запуск</span>
                    <SingleSelectPicker
                      options={triggerModeOptions}
                      value={scenarioSettingsForm.trigger_mode}
                      placeholder="Запуск"
                      onChange={(nextValue) =>
                        onFormChange((prev) =>
                          prev
                            ? {
                                ...prev,
                                trigger_mode: nextValue,
                                candidate_work_stage_trigger:
                                  nextValue === "candidate_hr_stage" ? prev.candidate_work_stage_trigger : "",
                              }
                            : prev,
                        )
                      }
                    />
                  </label>
                ) : null}
                {!isSurveyWorkspace && scenarioSettingsForm.trigger_mode === "candidate_hr_stage" ? (
                  <label className="grid min-w-0 gap-2.5">
                    <span className="text-sm font-semibold text-foreground/75">HR-статус кандидата</span>
                    <SingleSelectPicker
                      options={candidateWorkStageOptions}
                      value={scenarioSettingsForm.candidate_work_stage_trigger}
                      placeholder="Выбери статус"
                      onChange={(nextValue) =>
                        onFormChange((prev) => (prev ? { ...prev, candidate_work_stage_trigger: nextValue } : prev))
                      }
                    />
                  </label>
                ) : null}
                <label className="grid min-w-0 gap-2.5">
                  <span className="text-sm font-semibold text-foreground/75">Карточка</span>
                  <SingleSelectPicker
                    options={targetEmployeeOptions}
                    value={scenarioSettingsForm.target_employee_id}
                    placeholder="Любая"
                    onChange={(nextValue) => onFormChange((prev) => (prev ? { ...prev, target_employee_id: nextValue } : prev))}
                  />
                </label>
                {scenarioSettingsState.message ? (
                  <p className={`text-sm ${scenarioSettingsState.error ? "text-destructive" : "text-muted-foreground"}`}>
                    {scenarioSettingsState.message}
                  </p>
                ) : null}
              </div>
            </ScrollArea>
            <DialogFooter className="!m-0 shrink-0 border-t border-border px-5 py-4">
              <Button variant="secondary" onClick={() => onOpenChange(false)}>
                Закрыть
              </Button>
              <Button onClick={onSave} disabled={scenarioSettingsState.saving}>
                {scenarioSettingsState.saving ? "Сохраняю..." : "Сохранить"}
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

function setWorkspaceDragImage(
  event: React.DragEvent<HTMLElement>,
  { title, meta }: { title: string; meta: string },
) {
  const dragImage = document.createElement("div");
  dragImage.className = cn(
    "pointer-events-none fixed -left-[9999px] top-0 z-50 w-[280px] rounded-xl border border-border bg-popover p-3 text-popover-foreground shadow-xl ring-1 ring-foreground/10",
    "flex flex-col gap-1",
  );

  const titleElement = document.createElement("div");
  titleElement.className = "truncate text-sm font-semibold";
  titleElement.textContent = title || "Без названия";

  const metaElement = document.createElement("div");
  metaElement.className = "text-xs text-muted-foreground";
  metaElement.textContent = meta;

  dragImage.append(titleElement, metaElement);
  document.body.appendChild(dragImage);
  event.dataTransfer.setDragImage(dragImage, 18, 18);

  window.setTimeout(() => dragImage.remove(), 0);
}

export function WorkspaceCatalogSection(props: {
  isSurveyWorkspace: boolean;
  itemNamePlaceholder: string;
  creatingScenario: boolean;
  newScenarioTitle: string;
  search: string;
  audienceFilter: "all" | "employees" | "candidates";
  sortMode: "updated_desc" | "created_desc" | "created_asc" | "title_asc";
  scenarios: ScenarioSummary[];
  selectedScenarioIds: number[];
  dragScenarioId: number | null;
  sidebarState: { message: string; error: boolean };
  onNewScenarioTitleChange: (value: string) => void;
  onCreateScenario: () => void;
  onCancelCreateScenario: () => void;
  onSearchChange: (value: string) => void;
  onAudienceFilterChange: (value: "all" | "employees" | "candidates") => void;
  onSortModeChange: (value: "updated_desc" | "created_desc" | "created_asc" | "title_asc") => void;
  onToggleSelectAllVisibleScenarios: () => void;
  onBulkScenarioAction: (action: "bulk-copy" | "bulk-delete") => void;
  onSendSelectedScenario: () => void;
  onClearScenarioSelection: () => void;
  onSelectScenario: (scenarioId: number) => void;
  onScenarioDragStart: (scenarioId: number) => void;
  onScenarioDrop: (scenarioId: number) => void;
  onScenarioDragEnd: () => void;
  onToggleScenarioSelection: (scenarioId: number) => void;
}) {
  const {
    isSurveyWorkspace,
    itemNamePlaceholder,
    creatingScenario,
    newScenarioTitle,
    search,
    audienceFilter,
    sortMode,
    scenarios,
    selectedScenarioIds,
    dragScenarioId,
    sidebarState,
    onNewScenarioTitleChange,
    onCreateScenario,
    onCancelCreateScenario,
    onSearchChange,
    onAudienceFilterChange,
    onSortModeChange,
    onToggleSelectAllVisibleScenarios,
    onBulkScenarioAction,
    onSendSelectedScenario,
    onClearScenarioSelection,
    onSelectScenario,
    onScenarioDragStart,
    onScenarioDrop,
    onScenarioDragEnd,
    onToggleScenarioSelection,
  } = props;
  const [dropTargetId, setDropTargetId] = React.useState<number | null>(null);
  /* Подпись действия называет запись: у иконки другого текста нет. */
  const открытьПодпись = isSurveyWorkspace ? "Открыть опрос" : "Открыть сценарий";

  /*
   * Каталог — это страница, которая состоит ровно из фильтров и карточек,
   * поэтому внешней карточки у неё нет: обёртка ради фильтров даёт ощущение
   * карточки в карточке, когда ниже начинаются карточки записей. Полоса
   * фильтров идёт сразу под заголовком, без фона и без рамки.
   *
   * Раскладка одна и та же для сценариев и для опросов: раньше опросы рисовали
   * список боковой панелью рядом с редактором, и выбор записи менял две панели
   * справа, не меняя адреса. Теперь запись открывается своей страницей.
   */
  const формаСоздания = creatingScenario ? (
    <div className="flex items-center gap-2">
      <Input
        value={newScenarioTitle}
        onChange={(event) => onNewScenarioTitleChange(event.target.value)}
        placeholder={itemNamePlaceholder}
        className="h-8 text-sm"
      />
      <Button size="sm" onClick={onCreateScenario} className="px-3">
        Готово
      </Button>
      <Button size="icon-sm" variant="ghost" onClick={onCancelCreateScenario} aria-label="Отменить создание">
        <X />
      </Button>
    </div>
  ) : null;

  const поиск = (
    <PageFiltersSearch
      value={search}
      onValueChange={onSearchChange}
      placeholder={isSurveyWorkspace ? "Найти" : "Найти сценарий"}
    />
  );

  const сортировка = (
    <SingleSelectPicker
      options={[
        { value: "updated_desc", label: "Сначала недавно изменённые" },
        { value: "created_desc", label: "Сначала новые" },
        { value: "created_asc", label: "Сначала старые" },
        { value: "title_asc", label: "По алфавиту" },
      ]}
      value={sortMode}
      placeholder="Сортировка"
      onChange={(value) => onSortModeChange(value as "updated_desc" | "created_desc" | "created_asc" | "title_asc")}
    />
  );

  const аудитория = !isSurveyWorkspace ? (
    <PageFiltersSegments
      label="Аудитория сценариев"
      value={audienceFilter}
      onValueChange={(value) => onAudienceFilterChange(value as "all" | "employees" | "candidates")}
      options={[
        { value: "all", label: "Все" },
        { value: "employees", label: "Сотрудники" },
        { value: "candidates", label: "Кандидаты" },
      ]}
    />
  ) : null;

  /* Высоты выровнены по 32px — как у поиска и селектов в полосе фильтров. */
  const выделение = (
    <label className="inline-flex h-8 items-center gap-2 rounded-lg border border-border bg-background px-2.5 text-xs font-semibold text-muted-foreground">
      <Checkbox
        checked={scenarios.length > 0 && scenarios.every((scenario) => selectedScenarioIds.includes(scenario.id))}
        onCheckedChange={onToggleSelectAllVisibleScenarios}
        aria-label={isSurveyWorkspace ? "Выбрать все опросы" : "Выбрать все сценарии"}
      />
      Все
    </label>
  );

  /*
   * Действия над выбранным живут в плавающей панели у нижнего края, а не в
   * полосе фильтров: они появляются вместе с выделением и исчезают с ним,
   * поэтому полоса не возит постоянно выключенные кнопки. Панель — sticky
   * внутри прокрутки страницы: перекрывает карточки, пока список длинный,
   * и встаёт после них у конца прокрутки, не пряча последний ряд.
   *
   * Рассылка идёт по одной записи — так работает её API и её диалог, —
   * поэтому «Разослать» гаснет, пока выбрано больше одного.
   */
  const панельВыделения = selectedScenarioIds.length ? (
    <div className="pointer-events-none sticky bottom-4 z-20 mt-4 flex justify-center">
      <div className="admin-selection-bar pointer-events-auto flex flex-wrap items-center gap-1.5 rounded-xl bg-card py-1.5 pl-3.5 pr-1.5">
        <span className="text-sm font-semibold text-foreground/75">Выбрано: {selectedScenarioIds.length}</span>
        <Separator orientation="vertical" className="mx-1 !h-5" />
        <Button
          size="sm"
          title={selectedScenarioIds.length === 1 ? "Разослать выбранное" : "Рассылка идёт по одной записи — оставьте одну"}
          onClick={onSendSelectedScenario}
          disabled={selectedScenarioIds.length !== 1}
        >
          <Send data-icon="inline-start" />
          Разослать
        </Button>
        <Button size="sm" variant="secondary" onClick={() => onBulkScenarioAction("bulk-copy")}>
          <Copy data-icon="inline-start" />
          Копировать
        </Button>
        <ConfirmAction
          title={`Удалить выбранные ${isSurveyWorkspace ? "опросы" : "сценарии"}?`}
          description={`Будет удалено: ${selectedScenarioIds.length}. Это действие нельзя отменить.`}
          actionLabel="Удалить"
          onConfirm={() => onBulkScenarioAction("bulk-delete")}
        >
          <Button size="sm" variant="outline">
            <Trash2 data-icon="inline-start" />
            Удалить
          </Button>
        </ConfirmAction>
        <Button size="icon-sm" variant="ghost" aria-label="Снять выделение" onClick={onClearScenarioSelection}>
          <X />
        </Button>
      </div>
    </div>
  ) : null;

  /*
   * Сообщение панели — Alert, а не абзац: текст, лежащий прямо на фоне
   * страницы, не принадлежит ни одному блоку.
   */
  const сообщение = sidebarState.message ? (
    <Alert variant={sidebarState.error ? "destructive" : "default"} className="mb-4">
      <AlertDescription>{sidebarState.message}</AlertDescription>
    </Alert>
  ) : null;

  /*
   * Адрес записи настоящий: карточка — ссылка, поэтому средняя кнопка мыши
   * и «копировать адрес» работают, а сервер такой маршрут уже понимает.
   * Простой левый клик перехватывается и уходит в pushState, чтобы не
   * перезагружать страницу ради смены панели.
   */
  const адресЗаписи = (scenarioId: number) => {
    const url = new URL(window.location.href);
    url.searchParams.set("scenario_id", String(scenarioId));
    return `${url.pathname}${url.search}`;
  };

  const карточки = (
    <div className="grid grid-cols-[repeat(auto-fill,minmax(320px,1fr))] gap-3 pb-1">
      {scenarios.map((scenario) => {
        const isDragging = dragScenarioId === scenario.id;
        const isDropTarget = dropTargetId === scenario.id && !isDragging;
        const теги: RecordCardTagSpec[] = [
          { label: scenario.role_scope_label },
          { label: scenario.employee_scope_label },
        ];
        if (!isSurveyWorkspace) {
          /*
           * Адресата бэкенд в выдаче каталога сейчас не отдаёт, и тег выходит
           * пустым. Убирает его RecordCard, отбрасывая теги без подписи;
           * строка остаётся, чтобы тег вернулся сам, когда поле появится.
           */
          теги.push({ label: scenario.recipient_mode_label });
        }
        теги.push({ label: scenario.trigger_mode_label });
        теги.push({ label: stepsCountLabel(scenario.steps_count, isSurveyWorkspace), variant: "outline" });

        return (
          <RecordCard
            key={scenario.id}
            title={scenario.title}
            subtitle={scenario.description || "Без описания"}
            tags={теги}
            href={адресЗаписи(scenario.id)}
            onOpen={(event) => {
              if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
              event.preventDefault();
              onSelectScenario(scenario.id);
            }}
            selectable
            checked={selectedScenarioIds.includes(scenario.id)}
            onCheckedChange={() => onToggleScenarioSelection(scenario.id)}
            dragging={isDragging}
            dropTarget={isDropTarget}
            draggable
            onDragStart={(event) => {
              event.dataTransfer.effectAllowed = "move";
              setWorkspaceDragImage(event, {
                title: scenario.title,
                meta: isSurveyWorkspace ? "Перемещение опроса" : "Перемещение сценария",
              });
              onScenarioDragStart(scenario.id);
            }}
            onDragOver={(event) => {
              event.preventDefault();
              setDropTargetId(scenario.id);
            }}
            onDragLeave={(event) => {
              if (!event.currentTarget.contains(event.relatedTarget as Node)) {
                setDropTargetId((current) => (current === scenario.id ? null : current));
              }
            }}
            onDrop={() => {
              setDropTargetId(null);
              onScenarioDrop(scenario.id);
            }}
            onDragEnd={() => {
              setDropTargetId(null);
              onScenarioDragEnd();
            }}
          />
        );
      })}
    </div>
  );

  /*
   * Заголовка у каталога нет: раздел назван в полосе заголовка страницы,
   * а счётчик переехал туда же. Любая подпись здесь читалась бы как дубль.
   */
  return (
    <div className="admin-page-shell">
      <PageFilters
        className="mb-4"
        scope={аудитория}
        search={поиск}
        controls={сортировка}
        view={выделение}
      />
      {/* Создание записи — не фильтр, поэтому идёт под полосой, а не в ней. */}
      {формаСоздания ? <div className="mb-4">{формаСоздания}</div> : null}
      {сообщение}
      {карточки}
      {панельВыделения}
    </div>
  );
}

export function WorkspaceCanvasSection(props: {
  stack: Container[];
  currentContainer: Container | null;
  currentItems: Container["items"];
  selectedItemKey: string;
  selectedStepId: number | null;
  viewMode: "list" | "graph";
  stepTitle: string;
  isSurveyWorkspace: boolean;
  graph: WorkspaceGraph | null | undefined;
  payloadWorkspace: WorkspaceData | null | undefined;
  exportUrl: string;
  dragStepId: number | null;
  onBreadcrumbClick: (index: number) => void;
  onAddRootStep: () => void;
  onAddChainStep: () => void;
  onSelectItem: (itemKey: string) => void;
  onViewModeChange: (viewMode: "list" | "graph") => void;
  onSelectGraphStep: (stepId: number) => void;
  onDragStepStart: (stepId: number) => void;
  onDragStepDrop: (targetStepId: number) => void;
  onDragStepEnd: () => void;
  onOpenItem: (item: Container["items"][number]) => void;
}) {
  const {
    stack,
    currentContainer,
    currentItems,
    selectedItemKey,
    selectedStepId,
    viewMode,
    stepTitle,
    isSurveyWorkspace,
    graph,
    payloadWorkspace,
    exportUrl,
    dragStepId,
    onBreadcrumbClick,
    onAddRootStep,
    onAddChainStep,
    onSelectItem,
    onViewModeChange,
    onSelectGraphStep,
    onDragStepStart,
    onDragStepDrop,
    onDragStepEnd,
    onOpenItem,
  } = props;
  const [dropTargetId, setDropTargetId] = React.useState<number | null>(null);

  return (
    <Card className="flex min-h-0 flex-col overflow-hidden border border-border bg-card p-4 shadow-none ring-0">
      <div className="mb-3 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
        {stack.map((entry, index) => (
          <React.Fragment key={entry.key}>
            {index > 0 ? <ChevronRight className="size-4 shrink-0" /> : null}
            <button
              type="button"
              className="inline-flex max-w-full items-center gap-2 rounded-lg bg-muted px-3 py-1.5 text-left font-medium whitespace-normal break-words transition-colors hover:bg-border"
              onClick={() => onBreadcrumbClick(index)}
            >
              {React.createElement(crumbIcon(entry), { className: "size-4 shrink-0" })}
              {entry.crumbLabel}
            </button>
          </React.Fragment>
        ))}
      </div>

      <div className="mb-4 flex items-center justify-between gap-4">
        <div>
          {currentContainer?.subtitle ? (
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              {currentContainer.subtitle}
            </p>
          ) : null}
          <h3 className={currentContainer?.subtitle ? "mt-1 text-[1.55rem] font-semibold" : "text-[1.2rem] font-semibold"}>
            {currentContainer?.type === "root" ? stepTitle : currentContainer?.title || payloadWorkspace?.scenario.title}
          </h3>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-1 rounded-lg border border-border bg-muted/45 p-1">
            <Button
              size="xs"
              variant={viewMode === "list" ? "secondary" : "ghost"}
              onClick={() => onViewModeChange("list")}
            >
              Список
            </Button>
            <Button
              size="xs"
              variant={viewMode === "graph" ? "secondary" : "ghost"}
              onClick={() => onViewModeChange("graph")}
            >
              Схема
            </Button>
          </div>
          {currentContainer?.type === "root" ? (
            <>
            {exportUrl ? (
              <Button render={<a href={exportUrl} />} variant="outline" size="sm">
                Выгрузить Excel
              </Button>
            ) : null}
            <Button variant="secondary" size="sm" onClick={onAddRootStep}>
              <Plus data-icon="inline-start" />
              {isSurveyWorkspace ? "Добавить" : "Добавить шаг"}
            </Button>
            </>
        ) : currentContainer?.type === "chain" ? (
          <Button variant="secondary" size="sm" onClick={onAddChainStep}>
            <Plus data-icon="inline-start" />
            Добавить шаг
          </Button>
        ) : null}
        </div>
      </div>

      {viewMode === "graph" ? (
        <React.Suspense
          fallback={
            <div className="flex min-h-0 flex-1 items-center justify-center rounded-lg border border-border bg-muted/35 p-6 text-sm font-medium text-muted-foreground">
              Собираю схему…
            </div>
          }
        >
          <ScenarioGraphView graph={graph} selectedStepId={selectedStepId} onSelectStep={onSelectGraphStep} />
        </React.Suspense>
      ) : (
        <ScrollArea className="min-h-0 flex-1">
          <div className="grid gap-2 pr-3">
            {currentItems.map((item, index) => {
              const openChildLabel = openActionLabel(item);
              const active = itemKey(item) === selectedItemKey;
              const isDragging = dragStepId === item.id;
              const isDropTarget = dropTargetId === item.id && !isDragging;
              const перетаскиваемый = currentContainer?.type === "root" && item.kind !== "branch_slot";
              const теги: RecordCardTagSpec[] = [
                { label: item.kind === "branch_slot" ? "Ветка" : item.response_label },
              ];
              if ("response_type" in item) {
                теги.push({
                  label: responseTypeWaitState(item.response_type).badge,
                  variant: responseTypeWaitState(item.response_type).tone === "waiting" ? "default" : "outline",
                });
              }
              if ("is_terminal" in item && item.is_terminal) {
                теги.push({ label: "Финал", variant: "destructive" });
              }
              if ("button_options" in item && item.button_options.length) {
                теги.push({
                  label: isSurveyWorkspace
                    ? `Ответы: ${item.button_options.length}`
                    : `Кнопки: ${item.button_options.length}`,
                });
              }
              return (
                <RecordCard
                  key={itemKey(item) || `${currentContainer?.key}-${index}`}
                  density="compact"
                  title={workspaceItemTitle(item, index)}
                  subtitle={summarizeItem(item)}
                  tags={теги}
                  selected={active}
                  onOpen={() => onSelectItem(itemKey(item))}
                  /*
                   * Переход внутрь — иконка справа сверху, а не кнопка со словом
                   * в подвале: подвал занимал у каждой карточки отдельную строку,
                   * а само слово уезжает в подсказку и доступное имя.
                   */
                  actions={
                    openChildLabel ? (
                      <Button
                        variant="outline"
                        size="icon"
                        className={ПРОЯВЛЕНИЕ.card}
                        title={openChildLabel}
                        aria-label={openChildLabel}
                        onClick={() => onOpenItem(item)}
                      >
                        {openChildLabel.startsWith("Создать") ? <Plus /> : <PanelLeft />}
                      </Button>
                    ) : null
                  }
                  dragging={isDragging}
                  dropTarget={isDropTarget}
                  draggable={перетаскиваемый}
                  onDragStart={(event) => {
                    if (перетаскиваемый) {
                      event.dataTransfer.effectAllowed = "move";
                      setWorkspaceDragImage(event, {
                        title: workspaceItemTitle(item, index),
                        meta: isSurveyWorkspace ? "Перемещение вопроса" : "Перемещение шага",
                      });
                      onDragStepStart(Number(itemKey(item)));
                    }
                  }}
                  onDragOver={(event) => {
                    if (перетаскиваемый) {
                      event.preventDefault();
                      setDropTargetId(item.id);
                    }
                  }}
                  onDragLeave={(event) => {
                    if (!event.currentTarget.contains(event.relatedTarget as Node)) {
                      setDropTargetId((current) => (current === item.id ? null : current));
                    }
                  }}
                  onDrop={() => {
                    if (перетаскиваемый) {
                      setDropTargetId(null);
                      onDragStepDrop(item.id);
                    }
                  }}
                  onDragEnd={() => {
                    setDropTargetId(null);
                    onDragStepEnd();
                  }}
                />
              );
            })}
          </div>
        </ScrollArea>
      )}
    </Card>
  );
}

export function WorkspaceDetailSection({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <Card
      className="flex min-h-0 flex-col overflow-hidden border border-border bg-card p-4 shadow-none ring-0"
      style={{ position: "sticky", top: 0, alignSelf: "stretch" }}
    >
      <div className="mb-3">
        <p className="text-[1rem] font-medium text-foreground/85">Детали</p>
      </div>
      {children}
    </Card>
  );
}

function TemplateTagButtons({
  tags,
  onInsert,
  includeDocumentTags = false,
  documentTagTitles = [],
}: {
  tags: WorkspaceTemplateTag[];
  onInsert: (template: string) => void;
  includeDocumentTags?: boolean;
  documentTagTitles?: string[];
}) {
  const normalizedDocumentTitles = React.useMemo(() => {
    if (!includeDocumentTags) return [];
    const titles = documentTagTitles.map((title) => title.trim()).filter(Boolean);
    return titles.length ? titles : ["Оффер"];
  }, [documentTagTitles, includeDocumentTags]);

  if (!tags.length && !normalizedDocumentTitles.length) {
    return null;
  }

  return (
    <div className="rounded-lg border border-border/70 bg-muted/35 p-2">
      <div className="flex flex-wrap items-center gap-1.5">
        {tags.map((tag) => (
          <Button
            key={tag.template}
            type="button"
            variant="outline"
            size="xs"
            title={tag.description || tag.template}
            onMouseDown={(event) => event.preventDefault()}
            onClick={() => onInsert(tag.template)}
          >
            {tag.label}
          </Button>
        ))}
        {includeDocumentTags
          ? normalizedDocumentTitles.map((title) => (
              <Button
                key={`doc-${title}`}
                type="button"
                variant="outline"
                size="xs"
                title={`Вставить документ: ${title}`}
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => onInsert(`{doc:${title}}`)}
              >
                Документ: {title}
              </Button>
            ))
          : null}
      </div>
    </div>
  );
}

export function WorkspaceStepDetailPane(props: {
  selectedItem: WorkspaceItem | null;
  detailTarget: WorkspaceStep | null;
  stepLabel: string;
  isSurveyWorkspace: boolean;
  form: WorkspaceStepForm | null;
  textRef: React.RefObject<HTMLTextAreaElement>;
  fileInputRef: React.RefObject<HTMLInputElement>;
  payloadWorkspace: WorkspaceData | null | undefined;
  attachmentState: { uploading: boolean; message: string; error: boolean };
  saveState: { saving: boolean; message: string; error: boolean };
  openLabel: string;
  responseTypePickerOptions: SingleOption[];
  sendModeOptions: SingleOption[];
  targetFieldOptions: SingleOption[];
  launchScenarioOptions: SingleOption[];
  rootStepOptions: WorkspaceRootStepOption[];
  onInsertIntoText: (snippet: string) => void;
  onFormChange: React.Dispatch<React.SetStateAction<WorkspaceStepForm | null>>;
  onCreateBranch: () => void;
  onAttachmentSelected: (event: React.ChangeEvent<HTMLInputElement>) => void;
  onDeleteAttachment: () => void;
  onDeleteCurrent: () => void;
  onOpenCurrentChild: () => void;
  onSave: () => void;
  supportsButtonOptions: (responseType: string) => boolean;
  supportsTargetField: (responseType: string) => boolean;
}) {
  const {
    selectedItem,
    detailTarget,
    stepLabel,
    form,
    textRef,
    fileInputRef,
    payloadWorkspace,
    attachmentState,
    saveState,
    openLabel,
    isSurveyWorkspace,
    responseTypePickerOptions,
    sendModeOptions,
    targetFieldOptions,
    launchScenarioOptions,
    rootStepOptions,
    onInsertIntoText,
    onFormChange,
    onCreateBranch,
    onAttachmentSelected,
    onDeleteAttachment,
    onDeleteCurrent,
    onOpenCurrentChild,
    onSave,
    supportsButtonOptions,
    supportsTargetField,
  } = props;
  const [notificationRuleEditor, setNotificationRuleEditor] = React.useState<null | {
    option_index: number;
    option_label: string;
    rule_index: number | null;
    message_text: string;
    recipient_ids: string;
  }>(null);
  const [stepNotificationRuleEditor, setStepNotificationRuleEditor] = React.useState<null | {
    rule_index: number | null;
    message_text: string;
    recipient_ids: string;
  }>(null);
  const notificationTextRef = React.useRef<HTMLTextAreaElement | null>(null);
  const stepNotificationTextRef = React.useRef<HTMLTextAreaElement | null>(null);

  React.useEffect(() => {
    setNotificationRuleEditor(null);
    setStepNotificationRuleEditor(null);
  }, [detailTarget?.id, selectedItem?.kind]);

  const recipientLabelByToken = React.useMemo(() => {
    return ROLE_NOTIFICATION_RECIPIENT_LABELS;
  }, []);
  const waitState = React.useMemo(
    () => responseTypeWaitState(form?.response_type || detailTarget?.response_type || "none"),
    [detailTarget?.response_type, form?.response_type],
  );
  const documentLibraryOptions = React.useMemo<SingleOption[]>(() => {
    const options = payloadWorkspace?.document_library_options || [];
    return [{ value: "", label: "Без документа" }].concat(
      options.map((item) => {
        const kindLabel = item.item_kind_label || (item.item_kind === "link" ? "Ссылка" : "Файл");
        const categoryLabel = item.category ? ` · ${item.category}` : "";
        return {
          value: String(item.id),
          label: `${item.title || "Документ"} · ${kindLabel}${categoryLabel}`,
        };
      }),
    );
  }, [payloadWorkspace?.document_library_options]);
  const selectedLibraryDocument = React.useMemo(() => {
    const selectedId = String(form?.attachment_document_item_id || "");
    if (!selectedId) {
      return null;
    }
    const options = payloadWorkspace?.document_library_options || [];
    const selectedOption = options.find((item) => String(item.id) === selectedId);
    if (selectedOption) {
      return selectedOption;
    }
    const stepDocument = detailTarget?.attachment_document_item;
    return stepDocument && String(stepDocument.id) === selectedId ? stepDocument : null;
  }, [detailTarget?.attachment_document_item, form?.attachment_document_item_id, payloadWorkspace?.document_library_options]);
  const selectedLibraryDocumentLink = selectedLibraryDocument
    ? selectedLibraryDocument.download_url || selectedLibraryDocument.external_url || ""
    : "";
  const uploadedAttachmentFilename = detailTarget?.attachment_filename || "";

  const insertIntoNotificationRuleText = React.useCallback((snippet: string) => {
    setNotificationRuleEditor((prev) => {
      if (!prev) return prev;
      const textarea = notificationTextRef.current;
      if (!textarea) {
        return { ...prev, message_text: `${prev.message_text || ""}${snippet}` };
      }
      const start = textarea.selectionStart ?? prev.message_text.length;
      const end = textarea.selectionEnd ?? prev.message_text.length;
      const nextText = `${prev.message_text.slice(0, start)}${snippet}${prev.message_text.slice(end)}`;
      requestAnimationFrame(() => {
        textarea.focus();
        const nextCursor = start + snippet.length;
        textarea.setSelectionRange(nextCursor, nextCursor);
      });
      return { ...prev, message_text: nextText };
    });
  }, []);

  const insertIntoStepNotificationRuleText = React.useCallback((snippet: string) => {
    setStepNotificationRuleEditor((prev) => {
      if (!prev) return prev;
      const textarea = stepNotificationTextRef.current;
      if (!textarea) {
        return { ...prev, message_text: `${prev.message_text || ""}${snippet}` };
      }
      const start = textarea.selectionStart ?? prev.message_text.length;
      const end = textarea.selectionEnd ?? prev.message_text.length;
      const nextText = `${prev.message_text.slice(0, start)}${snippet}${prev.message_text.slice(end)}`;
      requestAnimationFrame(() => {
        textarea.focus();
        const nextCursor = start + snippet.length;
        textarea.setSelectionRange(nextCursor, nextCursor);
      });
      return { ...prev, message_text: nextText };
    });
  }, []);

  const updateNotificationRuleText = React.useCallback((nextValue: string) => {
    setNotificationRuleEditor((prev) => (prev ? { ...prev, message_text: nextValue } : prev));
  }, []);

  const updateStepNotificationRuleText = React.useCallback((nextValue: string) => {
    setStepNotificationRuleEditor((prev) => (prev ? { ...prev, message_text: nextValue } : prev));
  }, []);

  const saveNotificationRule = () => {
    if (!notificationRuleEditor) return;
    const normalizedMessageText = notificationRuleEditor.message_text.trim();
    const normalizedRecipientIds = normalizeNotificationRecipientIds(notificationRuleEditor.recipient_ids);
    if (!normalizedMessageText || !normalizedRecipientIds) {
      return;
    }
    onFormChange((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        button_notifications: prev.button_notifications.map((item) => {
          if (item.option_index !== notificationRuleEditor.option_index) {
            return item;
          }
          const currentRules = item.rules || [];
          const nextRuleIndex =
            notificationRuleEditor.rule_index ??
            (currentRules.length ? Math.max(...currentRules.map((rule) => rule.rule_index)) + 1 : 0);
          const nextRules = notificationRuleEditor.rule_index === null
            ? currentRules.concat([
                {
                  rule_index: nextRuleIndex,
                  message_text: normalizedMessageText,
                  recipient_ids: normalizedRecipientIds,
                  recipient_scope: "",
                },
              ])
            : currentRules.map((rule) =>
                rule.rule_index === notificationRuleEditor.rule_index
                  ? {
                      ...rule,
                      message_text: normalizedMessageText,
                      recipient_ids: normalizedRecipientIds,
                      recipient_scope: "",
                    }
                  : rule,
              );
          return {
            ...item,
            message_text: nextRules[0]?.message_text || "",
            recipient_ids: nextRules[0]?.recipient_ids || "",
            recipient_scope: nextRules[0]?.recipient_scope || "",
            rules: nextRules.sort((left, right) => left.rule_index - right.rule_index),
          };
        }),
      };
    });
    setNotificationRuleEditor(null);
  };

  const deleteNotificationRule = (optionIndex: number, ruleIndex: number) => {
    onFormChange((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        button_notifications: prev.button_notifications.map((item) => {
          if (item.option_index !== optionIndex) {
            return item;
          }
          const nextRules = (item.rules || []).filter((rule) => rule.rule_index !== ruleIndex);
          return {
            ...item,
            message_text: nextRules[0]?.message_text || "",
            recipient_ids: nextRules[0]?.recipient_ids || "",
            recipient_scope: nextRules[0]?.recipient_scope || "",
            rules: nextRules,
          };
        }),
      };
    });
  };

  const saveStepNotificationRule = () => {
    if (!stepNotificationRuleEditor) return;
    const normalizedMessageText = stepNotificationRuleEditor.message_text.trim();
    const normalizedRecipientIds = normalizeNotificationRecipientIds(stepNotificationRuleEditor.recipient_ids);
    if (!normalizedMessageText || !normalizedRecipientIds) {
      return;
    }
    onFormChange((prev) => {
      if (!prev) return prev;
      const currentRules = prev.step_send_notifications || [];
      const nextRuleIndex =
        stepNotificationRuleEditor.rule_index ??
        (currentRules.length ? Math.max(...currentRules.map((rule) => rule.rule_index)) + 1 : 0);
      const nextRules = stepNotificationRuleEditor.rule_index === null
        ? currentRules.concat([
            {
              rule_index: nextRuleIndex,
              message_text: normalizedMessageText,
              recipient_ids: normalizedRecipientIds,
              recipient_scope: "",
            },
          ])
        : currentRules.map((rule) =>
            rule.rule_index === stepNotificationRuleEditor.rule_index
              ? {
                  ...rule,
                  message_text: normalizedMessageText,
                  recipient_ids: normalizedRecipientIds,
                  recipient_scope: "",
                }
              : rule,
          );
      const sortedRules = nextRules.sort((left, right) => left.rule_index - right.rule_index);
      return {
        ...prev,
        notify_on_send_text: sortedRules[0]?.message_text || "",
        notify_on_send_recipient_ids: sortedRules[0]?.recipient_ids || "",
        notify_on_send_recipient_scope: sortedRules[0]?.recipient_scope || "",
        step_send_notifications: sortedRules,
      };
    });
    setStepNotificationRuleEditor(null);
  };

  const deleteStepNotificationRule = (ruleIndex: number) => {
    onFormChange((prev) => {
      if (!prev) return prev;
      const nextRules = (prev.step_send_notifications || []).filter((rule) => rule.rule_index !== ruleIndex);
      return {
        ...prev,
        notify_on_send_text: nextRules[0]?.message_text || "",
        notify_on_send_recipient_ids: nextRules[0]?.recipient_ids || "",
        notify_on_send_recipient_scope: nextRules[0]?.recipient_scope || "",
        step_send_notifications: nextRules,
      };
    });
  };

  return (
    <>
      <Separator />
      <ScrollArea className="min-h-0 flex-1 pt-3">
        <div className="pl-1 pr-6 pb-3">
          {selectedItem ? (
            selectedItem.kind === "branch_slot" && !detailTarget ? (
              <div className="flex flex-col gap-4 rounded-lg border border-border bg-muted/50 p-4">
                <div className="flex flex-col gap-1">
                  <h4 className="text-base font-semibold">{selectedItem.label}</h4>
                  <p className="text-sm leading-6 text-muted-foreground">
                    Для этой кнопки пока нет шага ветки. Добавь первый шаг, и после этого можно будет настроить ответ,
                    цепочку и дальнейшую логику.
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <Button onClick={onCreateBranch}>
                    <Plus data-icon="inline-start" />
                    Добавить шаг ветки
                  </Button>
                </div>
              </div>
            ) : (
              <div className="flex flex-col gap-4">
                {isSurveyWorkspace ? (
                  <label className="grid gap-2">
                    <span className="text-sm font-semibold text-foreground/75">Вопрос</span>
                    <div className="relative">
                      <Textarea
                        ref={textRef}
                        className="min-h-[140px] px-3 py-3 pr-12 text-sm leading-6"
                        value={form?.text || form?.title || ""}
                        onChange={(event) =>
                          onFormChange((prev) =>
                            prev
                              ? {
                                  ...prev,
                                  title: event.target.value,
                                  text: event.target.value,
                                }
                              : prev,
                          )
                        }
                      />
                      <div className="absolute right-2.5 bottom-2.5">
                        <EmojiPickerPopover onEmojiSelect={onInsertIntoText} />
                      </div>
                    </div>
                  </label>
                ) : (
                  <>
                    <label className="grid gap-2">
                      <span className="text-sm font-semibold text-foreground/75">Название</span>
                      <Input
                        value={form?.title || ""}
                        onChange={(event) => onFormChange((prev) => (prev ? { ...prev, title: event.target.value } : prev))}
                        className="h-10 text-sm"
                      />
                    </label>

                    <div className="grid gap-2">
                      <span className="text-sm font-semibold text-foreground/75">Текст сообщения</span>
                      <TelegramFormatToolbar
                        value={form?.text || ""}
                        textareaRef={textRef}
                        onChange={(nextValue) => onFormChange((prev) => (prev ? { ...prev, text: nextValue } : prev))}
                      />
                      <div className="relative">
                        <Textarea
                          ref={textRef}
                          className="min-h-[140px] px-3 py-3 pr-12 text-sm leading-6"
                          value={form?.text || ""}
                          placeholder="Введите текст сообщения"
                          onChange={(event) => onFormChange((prev) => (prev ? { ...prev, text: event.target.value } : prev))}
                        />
                        <div className="absolute right-2.5 bottom-2.5">
                          <EmojiPickerPopover onEmojiSelect={onInsertIntoText} />
                        </div>
                      </div>
                    </div>
                  </>
                )}

                {!isSurveyWorkspace ? (
                  <div className="grid gap-1.5">
                    <span className="text-xs font-medium text-muted-foreground">Теги сообщения</span>
                    <TemplateTagButtons
                      tags={payloadWorkspace?.step_template_tags || []}
                      includeDocumentTags
                      documentTagTitles={payloadWorkspace?.document_tag_titles || []}
                      onInsert={onInsertIntoText}
                    />
                  </div>
                ) : null}

                <div className="grid gap-2">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-sm font-semibold text-foreground/75">Вложение</span>
                    <input ref={fileInputRef} type="file" className="hidden" onChange={onAttachmentSelected} />
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      onClick={() => fileInputRef.current?.click()}
                      disabled={attachmentState.uploading}
                    >
                      <Paperclip data-icon="inline-start" />
                      {uploadedAttachmentFilename ? "Заменить файл" : "Добавить файл"}
                    </Button>
                  </div>
                  {detailTarget && uploadedAttachmentFilename ? (
                    <div className="flex flex-wrap items-center gap-2 rounded-lg border border-border bg-muted/50 px-3 py-2">
                      <a
                        href={`/flows/steps/${detailTarget.id}/attachment`}
                        className="min-w-0 flex-1 truncate text-sm font-medium text-foreground underline-offset-4 hover:underline"
                      >
                        {detailTarget.attachment_filename}
                      </a>
                      <ConfirmAction
                        title={`Удалить вложение у этого ${stepLabel}?`}
                        description="Файл будет отвязан от текущего элемента workspace."
                        actionLabel="Удалить"
                        onConfirm={onDeleteAttachment}
                      >
                        <Button type="button" variant="ghost" size="sm" disabled={attachmentState.uploading}>
                          Удалить
                        </Button>
                      </ConfirmAction>
                    </div>
                  ) : null}
                  {!isSurveyWorkspace ? (
                    <div className="grid gap-2 rounded-lg border border-border/80 bg-card/70 p-3">
                      <div className="grid gap-1.5">
                        <span className="text-xs font-medium text-muted-foreground">Документ из хранилища</span>
                        <SingleSelectPicker
                          options={documentLibraryOptions}
                          value={form?.attachment_document_item_id || ""}
                          onChange={(nextValue) =>
                            onFormChange((prev) => (prev ? { ...prev, attachment_document_item_id: nextValue } : prev))
                          }
                          placeholder="Выбери документ"
                          disabled={attachmentState.uploading}
                        />
                      </div>
                      {selectedLibraryDocument ? (
                        <div className="grid gap-1.5 rounded-lg border border-amber-300/50 bg-amber-50/70 px-3 py-2 text-sm dark:border-amber-500/25 dark:bg-amber-500/10">
                          <div className="flex min-w-0 flex-wrap items-center justify-between gap-2">
                            <div className="flex min-w-0 flex-wrap items-center gap-2">
                              <Badge variant="outline">
                                {selectedLibraryDocument.item_kind_label || (selectedLibraryDocument.item_kind === "link" ? "Ссылка" : "Файл")}
                              </Badge>
                              <span className="min-w-0 truncate font-medium text-foreground">
                                {selectedLibraryDocument.title || "Документ"}
                              </span>
                            </div>
                            <Button
                              type="button"
                              variant="ghost"
                              size="sm"
                              onClick={() => onFormChange((prev) => (prev ? { ...prev, attachment_document_item_id: "" } : prev))}
                              disabled={attachmentState.uploading}
                            >
                              Очистить
                            </Button>
                          </div>
                          <p className="text-xs leading-5 text-muted-foreground">
                            Будет использован первым. Загруженный файл останется fallback.
                          </p>
                          {selectedLibraryDocument.original_filename || selectedLibraryDocument.category || selectedLibraryDocumentLink ? (
                            <div className="flex min-w-0 flex-wrap items-center gap-2 text-xs text-muted-foreground">
                              {selectedLibraryDocument.category ? <span>{selectedLibraryDocument.category}</span> : null}
                              {selectedLibraryDocument.original_filename ? <span>{selectedLibraryDocument.original_filename}</span> : null}
                              {selectedLibraryDocumentLink ? (
                                <a
                                  href={selectedLibraryDocumentLink}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="truncate font-medium text-foreground underline-offset-4 hover:underline"
                                >
                                  Открыть
                                </a>
                              ) : null}
                            </div>
                          ) : null}
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                  <p className={`text-sm ${attachmentState.error ? "text-destructive" : "text-muted-foreground"}`}>
                    {attachmentState.message || " "}
                  </p>
                </div>

                {!isSurveyWorkspace ? (
                  <div className="grid gap-2">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="text-sm font-semibold text-foreground/75">Тип ответа</span>
                      <Badge variant={waitState.tone === "waiting" ? "default" : "outline"}>{waitState.badge}</Badge>
                    </div>
                    <SingleSelectPicker
                      options={responseTypePickerOptions}
                      value={form?.response_type || "none"}
                      placeholder="Выбери тип ответа"
                      onChange={(nextValue) =>
                        onFormChange((prev) =>
                          prev
                            ? {
                                ...prev,
                                response_type: nextValue,
                                button_options: supportsButtonOptions(nextValue) ? prev.button_options : "",
                                confirm_choice: supportsButtonOptions(nextValue) ? prev.confirm_choice : false,
                                button_notifications: supportsButtonOptions(nextValue) ? prev.button_notifications : [],
                                target_field: supportsTargetField(nextValue) ? prev.target_field : "",
                                launch_scenario_key: nextValue === "launch_scenario" ? prev.launch_scenario_key : "",
                              }
                            : prev,
                        )
                      }
                    />
                    <Alert className={cn("border", waitState.tone === "waiting" ? "border-primary/35 bg-primary/5" : "border-border bg-muted/40")}>
                      <AlertTitle>{waitState.title}</AlertTitle>
                      <AlertDescription>{waitState.description}</AlertDescription>
                    </Alert>
                    <label className="flex items-start gap-3 rounded-lg border border-border bg-muted/35 p-3">
                      <Checkbox
                        checked={Boolean(form?.is_terminal)}
                        onCheckedChange={(checked) => onFormChange((prev) => (prev ? { ...prev, is_terminal: Boolean(checked) } : prev))}
                        className="mt-0.5"
                      />
                      <span className="grid gap-1">
                        <span className="text-sm font-semibold text-foreground/85">Завершить сценарий после этого шага</span>
                        <span className="text-xs leading-5 text-muted-foreground">
                          Бот не пойдёт к следующему шагу и не поставит follow-up после отправки шага или после ответа пользователя.
                        </span>
                      </span>
                    </label>
                  </div>
                ) : null}

                {isSurveyWorkspace || supportsButtonOptions(form?.response_type || "") ? (
                  <label className="grid gap-2">
                    <span className="text-sm font-semibold text-foreground/75">
                      {isSurveyWorkspace ? "Варианты ответа" : "Кнопки"}
                    </span>
                    <Textarea
                      className="min-h-[118px] px-3 py-3 text-sm leading-6"
                      value={form?.button_options || ""}
                      onChange={(event) =>
                        onFormChange((prev) => {
                          if (!prev) return prev;
                          const optionLabels = event.target.value
                            .split("\n")
                            .map((item) => item.trim())
                            .filter(Boolean);
                          return {
                            ...prev,
                            button_options: event.target.value,
                            response_type: isSurveyWorkspace ? "text" : prev.response_type,
                            button_notifications: optionLabels.map((option_label, option_index) => {
                              const existing = prev.button_notifications.find((item) => item.option_index === option_index);
                              return {
                                option_index,
                                option_label,
                                message_text: existing?.message_text || "",
                                recipient_ids: existing?.recipient_ids || "",
                                recipient_scope: existing?.recipient_scope || "",
                                rules: existing?.rules || [],
                              };
                            }),
                          };
                        })
                      }
                      placeholder={isSurveyWorkspace ? "Каждая строка = отдельный вариант ответа" : "Каждая строка = отдельная кнопка"}
                    />
                  </label>
                ) : null}

                {!isSurveyWorkspace && supportsButtonOptions(form?.response_type || "") ? (
                  <label className="flex items-start gap-3 rounded-lg border border-border bg-muted/40 p-3">
                    <Checkbox
                      checked={Boolean(form?.confirm_choice)}
                      onCheckedChange={(checked) =>
                        onFormChange((prev) => (prev ? { ...prev, confirm_choice: checked === true } : prev))
                      }
                    />
                    <span className="grid gap-1 text-sm">
                      <span className="font-semibold text-foreground/80">Запрашивать подтверждение выбора</span>
                      <span className="text-muted-foreground">
                        Бот отредактирует сообщение с кнопками, покажет выбранный вариант и даст подтвердить или изменить ответ.
                      </span>
                    </span>
                  </label>
                ) : null}

                {!isSurveyWorkspace && supportsButtonOptions(form?.response_type || "") && form?.button_notifications?.length ? (
                  <details className="rounded-lg border border-border bg-muted/50 p-3">
                    <summary className="cursor-pointer list-none text-sm font-semibold text-foreground/80">
                      Уведомления по кнопкам
                    </summary>
                    <div className="mt-3 flex flex-col gap-3">
                      {form.button_notifications.map((notification) => (
                        <div key={`${notification.option_index}-${notification.option_label}`} className="rounded-lg border border-border bg-card p-3">
                          <div className="flex flex-col gap-3">
                            <div className="flex items-center justify-between gap-3">
                              <p className="text-sm font-semibold text-foreground/85">Кнопка: {notification.option_label}</p>
                              <Button
                                type="button"
                                variant="secondary"
                                size="sm"
                                onClick={() =>
                                  setNotificationRuleEditor({
                                    option_index: notification.option_index,
                                    option_label: notification.option_label,
                                    rule_index: null,
                                    message_text: "",
                                    recipient_ids: "",
                                  })
                                }
                              >
                                <Plus data-icon="inline-start" />
                                Добавить правило
                              </Button>
                            </div>
                            {(notification.rules || []).length ? (
                              <div className="flex flex-col gap-2">
                                {notification.rules.map((rule) => {
                                  const selectedIds = parseRecipientIds(normalizeNotificationRecipientIds(rule.recipient_ids));
                                  const recipientSummary = selectedIds.length
                                    ? selectedIds
                                        .map((id) => {
                                          return recipientLabelByToken[id] || id;
                                        })
                                        .join(", ")
                                    : "Получатели не выбраны";
                                  return (
                                    <div
                                      key={`${notification.option_index}-${rule.rule_index}`}
                                      className="rounded-lg border border-border/80 bg-muted/30 p-3"
                                    >
                                      <div className="flex items-start justify-between gap-3">
                                        <div className="min-w-0 space-y-2">
                                          <p className="text-sm leading-6 text-foreground/85">
                                            {rule.message_text || "Без текста уведомления"}
                                          </p>
                                          <p className="text-xs leading-5 text-muted-foreground">
                                            {recipientSummary}
                                          </p>
                                        </div>
                                        <div className="flex shrink-0 items-center gap-1">
                                          <Button
                                            type="button"
                                            variant="ghost"
                                            size="sm"
                                            onClick={() =>
                                              setNotificationRuleEditor({
                                                option_index: notification.option_index,
                                                option_label: notification.option_label,
                                                rule_index: rule.rule_index,
                                                message_text: rule.message_text,
                                                recipient_ids: rule.recipient_ids,
                                              })
                                            }
                                          >
                                            Изменить
                                          </Button>
                                          <Button
                                            type="button"
                                            variant="ghost"
                                            size="icon-sm"
                                            onClick={() => deleteNotificationRule(notification.option_index, rule.rule_index)}
                                            aria-label="Удалить правило"
                                            title="Удалить правило"
                                          >
                                            <Trash2 />
                                          </Button>
                                        </div>
                                      </div>
                                    </div>
                                  );
                                })}
                              </div>
                            ) : (
                              <p className="text-sm text-muted-foreground">Правил пока нет.</p>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </details>
                ) : null}

                {!isSurveyWorkspace ? (
                  <label className="grid gap-2">
                    <span className="text-sm font-semibold text-foreground/75">Режим отправки</span>
                    <SingleSelectPicker
                      options={sendModeOptions}
                      value={form?.send_mode || "immediate"}
                      placeholder="Выбери режим отправки"
                      onChange={(nextValue) =>
                        onFormChange((prev) =>
                          prev
                            ? {
                                ...prev,
                                send_mode: nextValue,
                                send_time: nextValue === "specific_time" ? prev.send_time : "",
                              }
                            : prev,
                        )
                      }
                    />
                  </label>
                ) : null}

                {!isSurveyWorkspace && form?.send_mode === "specific_time" ? (
                  <label className="grid gap-2">
                    <span className="text-sm font-semibold text-foreground/75">Время отправки</span>
                    <Input
                      type="time"
                      value={form.send_time}
                      onChange={(event) => onFormChange((prev) => (prev ? { ...prev, send_time: event.target.value } : prev))}
                      className="h-10 text-sm"
                    />
                  </label>
                ) : null}

                {!isSurveyWorkspace ? (
                  <>
                    <label className="grid gap-2">
                      <span className="text-sm font-semibold text-foreground/75">Сохранить ответ</span>
                      <SingleSelectPicker
                        options={targetFieldOptions}
                        value={form?.target_field || ""}
                        placeholder="Не сохранять"
                        onChange={(nextValue) => onFormChange((prev) => (prev ? { ...prev, target_field: nextValue } : prev))}
                      />
                    </label>

                    <label className="grid gap-2">
                      <span className="text-sm font-semibold text-foreground/75">Переход к сценарию</span>
                      <SingleSelectPicker
                        options={launchScenarioOptions}
                        value={form?.launch_scenario_key || ""}
                        placeholder="Не выполнять переход"
                        disabled={(form?.response_type || "") !== "launch_scenario"}
                        onChange={(nextValue) => onFormChange((prev) => (prev ? { ...prev, launch_scenario_key: nextValue } : prev))}
                      />
                    </label>

                    {detailTarget?.kind === "branch_step" ? (
                      <label className="grid gap-2">
                        <span className="text-sm font-semibold text-foreground/75">Вернуться в основной сценарий</span>
                        <SingleSelectPicker
                          options={rootStepOptions}
                          value={form?.return_to_step_key || ""}
                          placeholder="Не возвращать в основной поток"
                          disabled={(form?.response_type || "") === "launch_scenario"}
                          onChange={(nextValue) => onFormChange((prev) => (prev ? { ...prev, return_to_step_key: nextValue } : prev))}
                        />
                        <p className="text-xs leading-5 text-muted-foreground">
                          После завершения этой ветки бот перейдёт к выбранному root-шагу, а не к следующему шагу после точки ветвления.
                        </p>
                      </label>
                    ) : null}

                    <details className="rounded-lg border border-border bg-muted/50 p-3">
                      <summary className="cursor-pointer list-none text-sm font-semibold text-foreground/80">
                        Уведомление для шага
                      </summary>
                      <div className="mt-3 flex flex-col gap-3">
                    <div className="flex items-center justify-between gap-3">
                      <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        className="ml-auto"
                        onClick={() =>
                          setStepNotificationRuleEditor({
                                rule_index: null,
                                message_text: "",
                                recipient_ids: "",
                              })
                            }
                          >
                            <Plus data-icon="inline-start" />
                            Добавить правило
                          </Button>
                        </div>
                        {(form?.step_send_notifications || []).length ? (
                          <div className="flex flex-col gap-2">
                            {form?.step_send_notifications.map((rule) => {
                              const selectedIds = parseRecipientIds(normalizeNotificationRecipientIds(rule.recipient_ids));
                              const recipientSummary = selectedIds.length
                                ? selectedIds
                                    .map((id) => {
                                      return recipientLabelByToken[id] || id;
                                    })
                                    .join(", ")
                                : "Получатели не выбраны";
                              return (
                                <div key={`step-notify-${rule.rule_index}`} className="rounded-lg border border-border/80 bg-card p-3">
                                  <div className="flex items-start justify-between gap-3">
                                    <div className="min-w-0 space-y-2">
                                      <p className="text-sm leading-6 text-foreground/85">
                                        {rule.message_text || "Без текста уведомления"}
                                      </p>
                                      <p className="text-xs leading-5 text-muted-foreground">{recipientSummary}</p>
                                    </div>
                                    <div className="flex shrink-0 items-center gap-1">
                                      <Button
                                        type="button"
                                        variant="ghost"
                                        size="sm"
                                        onClick={() =>
                                          setStepNotificationRuleEditor({
                                            rule_index: rule.rule_index,
                                            message_text: rule.message_text,
                                            recipient_ids: rule.recipient_ids,
                                          })
                                        }
                                      >
                                        Изменить
                                      </Button>
                                      <Button
                                        type="button"
                                        variant="ghost"
                                        size="icon-sm"
                                        onClick={() => deleteStepNotificationRule(rule.rule_index)}
                                        aria-label="Удалить правило"
                                        title="Удалить правило"
                                      >
                                        <Trash2 />
                                      </Button>
                                    </div>
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        ) : (
                          <p className="text-sm text-muted-foreground">Правил пока нет.</p>
                        )}
                      </div>
                    </details>
                  </>
                ) : null}

                <div className="flex flex-col gap-3">
                  <p className={`text-sm ${saveState.error ? "text-destructive" : "text-muted-foreground"}`}>{saveState.message || " "}</p>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <ConfirmAction
                      title={`Удалить ${stepLabel}?`}
                      description="Элемент будет удален из текущего workspace. Это действие нельзя отменить."
                      actionLabel="Удалить"
                      onConfirm={onDeleteCurrent}
                    >
                      <Button variant="outline">
                        <Trash2 data-icon="inline-start" />
                        Удалить
                      </Button>
                    </ConfirmAction>
                    {openLabel ? (
                      <Button variant="outline" onClick={onOpenCurrentChild}>
                        {openLabel}
                      </Button>
                    ) : null}
                    <Button onClick={onSave} disabled={saveState.saving} className="px-6">
                      {saveState.saving ? "Сохраняю..." : "Сохранить"}
                    </Button>
                  </div>
                </div>
              </div>
            )
          ) : (
            <div className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">
              Выбери {stepLabel}, ветку или элемент цепочки, чтобы увидеть детали справа.
            </div>
          )}
        </div>
      </ScrollArea>
      <Dialog open={!!notificationRuleEditor} onOpenChange={(open) => (!open ? setNotificationRuleEditor(null) : undefined)}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>
              {notificationRuleEditor?.rule_index === null ? "Новое правило уведомления" : "Изменить правило уведомления"}
            </DialogTitle>
            <DialogDescription>
              {notificationRuleEditor ? `Кнопка: ${notificationRuleEditor.option_label}` : ""}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4">
            <label className="grid gap-2">
              <span className="text-sm font-semibold text-foreground/75">Получатели</span>
              <NotificationRecipientsPicker
                recipientOptions={payloadWorkspace?.notification_recipient_options || []}
                value={notificationRuleEditor?.recipient_ids || ""}
                onChange={(next) =>
                  setNotificationRuleEditor((prev) => (prev ? { ...prev, recipient_ids: next } : prev))
                }
              />
            </label>
            <div className="grid gap-2">
              <span className="text-sm font-semibold text-foreground/75">Текст уведомления</span>
              <TelegramFormatToolbar
                value={notificationRuleEditor?.message_text || ""}
                textareaRef={notificationTextRef}
                onChange={updateNotificationRuleText}
                disabled={!notificationRuleEditor}
              />
              <Textarea
                ref={notificationTextRef}
                className="min-h-[120px] text-sm"
                value={notificationRuleEditor?.message_text || ""}
                onChange={(event) => updateNotificationRuleText(event.target.value)}
                placeholder="Например: Пользователь нажал кнопку."
              />
              <TemplateTagButtons
                tags={payloadWorkspace?.notification_template_tags || []}
                onInsert={insertIntoNotificationRuleText}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setNotificationRuleEditor(null)}>
              Отмена
            </Button>
            <Button
              onClick={saveNotificationRule}
              disabled={
                !notificationRuleEditor?.message_text.trim() ||
                !parseRecipientIds(normalizeNotificationRecipientIds(notificationRuleEditor?.recipient_ids || "")).length
              }
            >
              Сохранить правило
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <Dialog open={!!stepNotificationRuleEditor} onOpenChange={(open) => (!open ? setStepNotificationRuleEditor(null) : undefined)}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>
              {stepNotificationRuleEditor?.rule_index === null ? "Новое правило уведомления" : "Изменить правило уведомления"}
            </DialogTitle>
            <DialogDescription>Это уведомление отправится сразу после отправки текущего шага.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4">
            <label className="grid gap-2">
              <span className="text-sm font-semibold text-foreground/75">Получатели</span>
              <NotificationRecipientsPicker
                recipientOptions={payloadWorkspace?.notification_recipient_options || []}
                value={stepNotificationRuleEditor?.recipient_ids || ""}
                onChange={(next) =>
                  setStepNotificationRuleEditor((prev) => (prev ? { ...prev, recipient_ids: next } : prev))
                }
              />
            </label>
            <div className="grid gap-2">
              <span className="text-sm font-semibold text-foreground/75">Текст уведомления</span>
              <TelegramFormatToolbar
                value={stepNotificationRuleEditor?.message_text || ""}
                textareaRef={stepNotificationTextRef}
                onChange={updateStepNotificationRuleText}
                disabled={!stepNotificationRuleEditor}
              />
              <Textarea
                ref={stepNotificationTextRef}
                className="min-h-[120px] text-sm"
                value={stepNotificationRuleEditor?.message_text || ""}
                onChange={(event) => updateStepNotificationRuleText(event.target.value)}
                placeholder="Например: Пользователю отправлен шаг."
              />
              <TemplateTagButtons
                tags={payloadWorkspace?.notification_template_tags || []}
                onInsert={insertIntoStepNotificationRuleText}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setStepNotificationRuleEditor(null)}>
              Отмена
            </Button>
            <Button
              onClick={saveStepNotificationRule}
              disabled={
                !stepNotificationRuleEditor?.message_text.trim() ||
                !parseRecipientIds(normalizeNotificationRecipientIds(stepNotificationRuleEditor?.recipient_ids || "")).length
              }
            >
              Сохранить правило
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
