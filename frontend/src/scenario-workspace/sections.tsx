import * as React from "react";
import { ArrowRight, ChevronRight, Copy, FileStack, MoreHorizontal, PanelLeft, Paperclip, Plus, Search, Trash2, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
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
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

import {
  buildChildContainer,
  crumbIcon,
  itemKey,
  normalizeNotificationRecipientIds,
  parseRecipientIds,
  responseTypeWaitState,
  ROLE_NOTIFICATION_RECIPIENT_LABELS,
  summarizeItem,
  workspaceItemTitle,
} from "./model";
import { NotificationRecipientsPicker, SingleSelectPicker } from "./pickers";
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
  WorkspaceStepSendNotificationRule,
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
  itemLabel: string;
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
    itemLabel,
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
      <DialogContent className="max-h-[min(760px,calc(100vh-40px))] w-[min(560px,calc(100vw-32px))] overflow-hidden p-0">
        <DialogHeader className="border-b border-border px-5 py-4">
          <DialogTitle>Настройки {itemLabel}</DialogTitle>
          <DialogDescription>{scenarioTitle || "Загружаю данные"}</DialogDescription>
        </DialogHeader>
        {!scenarioSettingsForm ? (
          <div className="px-5 py-8 text-sm font-medium text-muted-foreground">Загружаю настройки…</div>
        ) : (
          <>
            <ScrollArea className="max-h-[calc(100vh-210px)]">
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
                  <SingleSelectPicker
                    options={roleScopeOptions}
                    value={scenarioSettingsForm.role_scope}
                    placeholder="Должность"
                    onChange={(nextValue) => onFormChange((prev) => (prev ? { ...prev, role_scope: nextValue } : prev))}
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
            <DialogFooter className="border-t border-border px-5 py-4">
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

export function WorkspaceSidebarSection(props: {
  variant?: "sidebar" | "catalog";
  sidebarTitle: string;
  isSurveyWorkspace: boolean;
  createItemLabel: string;
  itemNamePlaceholder: string;
  creatingScenario: boolean;
  newScenarioTitle: string;
  search: string;
  audienceFilter: "all" | "employees" | "candidates";
  sortMode: "updated_desc" | "created_desc" | "created_asc" | "title_asc";
  scenarios: ScenarioSummary[];
  selectedScenarioId: number | null;
  selectedScenarioIds: number[];
  dragScenarioId: number | null;
  sidebarState: { message: string; error: boolean };
  onNewScenarioTitleChange: (value: string) => void;
  onCreateScenario: () => void;
  onOpenCreateScenario: () => void;
  onCancelCreateScenario: () => void;
  onSearchChange: (value: string) => void;
  onAudienceFilterChange: (value: "all" | "employees" | "candidates") => void;
  onSortModeChange: (value: "updated_desc" | "created_desc" | "created_asc" | "title_asc") => void;
  onToggleSelectAllVisibleScenarios: () => void;
  onBulkScenarioAction: (action: "bulk-copy" | "bulk-delete") => void;
  onSelectScenario: (scenarioId: number) => void;
  onScenarioDragStart: (scenarioId: number) => void;
  onScenarioDrop: (scenarioId: number) => void;
  onScenarioDragEnd: () => void;
  onToggleScenarioSelection: (scenarioId: number) => void;
  onOpenScenarioSettings?: (scenarioId: number) => void;
}) {
  const {
    variant = "sidebar",
    sidebarTitle,
    isSurveyWorkspace,
    createItemLabel,
    itemNamePlaceholder,
    creatingScenario,
    newScenarioTitle,
    search,
    audienceFilter,
    sortMode,
    scenarios,
    selectedScenarioId,
    selectedScenarioIds,
    dragScenarioId,
    sidebarState,
    onNewScenarioTitleChange,
    onCreateScenario,
    onOpenCreateScenario,
    onCancelCreateScenario,
    onSearchChange,
    onAudienceFilterChange,
    onSortModeChange,
    onToggleSelectAllVisibleScenarios,
    onBulkScenarioAction,
    onSelectScenario,
    onScenarioDragStart,
    onScenarioDrop,
    onScenarioDragEnd,
    onToggleScenarioSelection,
    onOpenScenarioSettings,
  } = props;
  const [dropTargetId, setDropTargetId] = React.useState<number | null>(null);
  const isCatalog = variant === "catalog";

  return (
    <Card className={cn("flex min-h-0 flex-col overflow-hidden border border-border bg-card shadow-none ring-0", isCatalog ? "h-full p-5" : "p-4")}>
      <CardHeader className="gap-2 border-b border-border/70 p-0 pb-3">
        <div className="flex min-w-0 items-center justify-between gap-2">
          <div className="flex min-w-0 items-center gap-2">
            <CardTitle className={cn("truncate font-semibold", isCatalog ? "text-[1.75rem]" : "text-[1.35rem]")}>
              {isCatalog ? `Каталог: ${sidebarTitle.toLowerCase()}` : sidebarTitle}
            </CardTitle>
            <Badge variant="secondary" className="shrink-0">
              {scenarios.length}
            </Badge>
          </div>
          {!creatingScenario ? (
            <Button size="sm" onClick={onOpenCreateScenario} title={createItemLabel} aria-label={createItemLabel}>
              <Plus data-icon="inline-start" />
              Создать
            </Button>
          ) : null}
        </div>
      </CardHeader>
      <div className={cn("mt-3 flex gap-2 rounded-lg border border-border bg-muted/35 p-2", isCatalog ? "flex-row flex-wrap items-center" : "flex-col")}>
        {creatingScenario ? (
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
        ) : null}
        <div className={cn("relative", isCatalog ? "min-w-[260px] flex-1" : "")}>
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder={isSurveyWorkspace ? "Найти" : "Найти сценарий"}
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            className="h-8 pl-8 text-sm"
          />
        </div>
        <div className={isCatalog ? "min-w-[260px]" : ""}>
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
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          {!isSurveyWorkspace ? (
            <div className="flex items-center gap-1 rounded-lg border border-border bg-background p-1">
              <Button
                size="xs"
                variant={audienceFilter === "all" ? "secondary" : "ghost"}
                onClick={() => onAudienceFilterChange("all")}
              >
                Все
              </Button>
              <Button
                size="xs"
                variant={audienceFilter === "employees" ? "secondary" : "ghost"}
                onClick={() => onAudienceFilterChange("employees")}
              >
                Сотрудники
              </Button>
              <Button
                size="xs"
                variant={audienceFilter === "candidates" ? "secondary" : "ghost"}
                onClick={() => onAudienceFilterChange("candidates")}
              >
                Кандидаты
              </Button>
            </div>
          ) : null}
          <label className="inline-flex h-7 items-center gap-2 rounded-lg border border-border bg-background px-2.5 text-xs font-semibold text-muted-foreground">
            <Checkbox
              checked={scenarios.length > 0 && scenarios.every((scenario) => selectedScenarioIds.includes(scenario.id))}
              onCheckedChange={onToggleSelectAllVisibleScenarios}
              aria-label="Выбрать все сценарии"
            />
            Все
          </label>
          <Button
            size="icon-sm"
            variant="secondary"
            title="Копировать выбранные"
            aria-label="Копировать выбранные"
            onClick={() => onBulkScenarioAction("bulk-copy")}
            disabled={!selectedScenarioIds.length}
          >
            <Copy />
          </Button>
          <ConfirmAction
            title={`Удалить выбранные ${isSurveyWorkspace ? "опросы" : "сценарии"}?`}
            description={`Будет удалено: ${selectedScenarioIds.length}. Это действие нельзя отменить.`}
            actionLabel="Удалить"
            onConfirm={() => onBulkScenarioAction("bulk-delete")}
          >
            <Button
              size="icon-sm"
              variant="outline"
              title="Удалить выбранные"
              aria-label="Удалить выбранные"
              disabled={!selectedScenarioIds.length}
            >
              <Trash2 />
            </Button>
          </ConfirmAction>
        </div>
      </div>
      {sidebarState.message ? (
        <p className={`mt-3 text-sm ${sidebarState.error ? "text-destructive" : "text-muted-foreground"}`}>
          {sidebarState.message}
        </p>
      ) : null}
      <ScrollArea className="mt-4 min-h-0 flex-1 rounded-lg">
        <div className={cn("grid gap-2 pr-3 pb-1", isCatalog && "grid-cols-[repeat(auto-fill,minmax(320px,1fr))] gap-3")}>
          {scenarios.map((scenario) => {
            const isDragging = dragScenarioId === scenario.id;
            const isDropTarget = dropTargetId === scenario.id && !isDragging;
            return (
              <article
              key={scenario.id}
              role={isCatalog ? undefined : "button"}
              tabIndex={isCatalog ? undefined : 0}
              onClick={isCatalog ? undefined : () => onSelectScenario(scenario.id)}
              onKeyDown={
                isCatalog
                  ? undefined
                  : (event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        onSelectScenario(scenario.id);
                      }
                    }
              }
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
              className={cn(
                "relative flex w-full min-w-0 flex-col rounded-lg border text-left transition-[border-color,background-color,opacity,transform,box-shadow]",
                isCatalog ? "gap-3 p-4" : "gap-2 p-3",
                isCatalog ? "cursor-default" : "cursor-pointer",
                !isCatalog && scenario.id === selectedScenarioId
                  ? "border-primary/70 bg-muted/50"
                  : "border-border bg-card hover:bg-accent/60",
                isDragging && "scale-[0.985] border-primary/40 bg-muted/70 opacity-50",
                isDropTarget && "border-primary bg-primary/5 ring-2 ring-primary/20",
              )}
            >
              {isDropTarget ? <span className="pointer-events-none absolute inset-x-3 -top-1 h-0.5 rounded-full bg-primary" /> : null}
              <div className="flex items-start justify-between gap-3">
                <div
                  className="inline-flex min-w-0 items-center gap-2"
                  onClick={(event) => event.stopPropagation()}
                  onMouseDown={(event) => event.stopPropagation()}
                >
                  <Checkbox
                    checked={selectedScenarioIds.includes(scenario.id)}
                    onCheckedChange={() => onToggleScenarioSelection(scenario.id)}
                    aria-label={`Выбрать ${scenario.title}`}
                  />
                  <span className="min-w-0 truncate text-[0.95rem] font-semibold">{scenario.title}</span>
                </div>
                <div className="flex shrink-0 items-center gap-1">
                  {onOpenScenarioSettings && !isSurveyWorkspace ? (
                    <Button
                      size="icon-sm"
                      variant="ghost"
                      title="Настройки"
                      aria-label={`Настройки ${scenario.title}`}
                      onClick={(event) => {
                        event.stopPropagation();
                        onOpenScenarioSettings(scenario.id);
                      }}
                    >
                      <MoreHorizontal />
                    </Button>
                  ) : null}
                  {!isCatalog ? <FileStack className="size-4 text-muted-foreground" /> : null}
                </div>
              </div>
              <p className="text-[0.83rem] leading-5 text-muted-foreground">{scenario.description || "Без описания"}</p>
              <div className="flex flex-wrap gap-1.5">
                <Badge variant="secondary">{scenario.role_scope_label}</Badge>
                <Badge variant="secondary">{scenario.employee_scope_label}</Badge>
                {!isSurveyWorkspace ? <Badge variant="secondary">{scenario.recipient_mode_label}</Badge> : null}
                <Badge variant="secondary">{scenario.trigger_mode_label}</Badge>
                <Badge variant="outline">{scenario.steps_count} шагов</Badge>
              </div>
              {isCatalog ? (
                <div className="flex justify-end pt-1">
                  <Button size="sm" variant="secondary" onClick={() => onSelectScenario(scenario.id)}>
                    Открыть
                    <ArrowRight data-icon="inline-end" />
                  </Button>
                </div>
              ) : null}
            </article>
            );
          })}
        </div>
      </ScrollArea>
    </Card>
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
              const canOpen = !!buildChildContainer(item);
              const active = itemKey(item) === selectedItemKey;
              const isDragging = dragStepId === item.id;
              const isDropTarget = dropTargetId === item.id && !isDragging;
              return (
                <article
                  key={itemKey(item) || `${currentContainer?.key}-${index}`}
                  onClick={() => onSelectItem(itemKey(item))}
                  draggable={currentContainer?.type === "root" && item.kind !== "branch_slot"}
                  onDragStart={(event) => {
                    if (currentContainer?.type === "root" && item.kind !== "branch_slot") {
                      event.dataTransfer.effectAllowed = "move";
                      setWorkspaceDragImage(event, {
                        title: workspaceItemTitle(item, index),
                        meta: isSurveyWorkspace ? "Перемещение вопроса" : "Перемещение шага",
                      });
                      onDragStepStart(Number(itemKey(item)));
                    }
                  }}
                  onDragOver={(event) => {
                    if (currentContainer?.type === "root" && item.kind !== "branch_slot") {
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
                    if (currentContainer?.type === "root" && item.kind !== "branch_slot") {
                      setDropTargetId(null);
                      onDragStepDrop(item.id);
                    }
                  }}
                  onDragEnd={() => {
                    setDropTargetId(null);
                    onDragStepEnd();
                  }}
                  className={cn(
                    "relative flex w-full min-w-0 cursor-pointer flex-col gap-2 rounded-lg border p-3 transition-[border-color,background-color,opacity,transform,box-shadow]",
                    active ? "border-primary/70 bg-muted/50" : "border-border bg-card hover:bg-accent/60",
                    isDragging && "scale-[0.985] border-primary/40 bg-muted/70 opacity-50",
                    isDropTarget && "border-primary bg-primary/5 ring-2 ring-primary/20",
                  )}
                >
                  {isDropTarget ? <span className="pointer-events-none absolute inset-x-3 -top-1 h-0.5 rounded-full bg-primary" /> : null}
                  <div className="flex flex-col gap-1">
                    <h4 className="text-[0.95rem] font-semibold">{workspaceItemTitle(item, index)}</h4>
                    <p className="text-[0.83rem] leading-5 text-muted-foreground">{summarizeItem(item)}</p>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex flex-wrap gap-1.5">
                      <Badge variant="secondary">{item.kind === "branch_slot" ? "Ветка" : item.response_label}</Badge>
                      {"response_type" in item ? (
                        <Badge variant={responseTypeWaitState(item.response_type).tone === "waiting" ? "default" : "outline"}>
                          {responseTypeWaitState(item.response_type).badge}
                        </Badge>
                      ) : null}
                      {"button_options" in item && item.button_options.length ? (
                        <Badge variant="secondary">
                          {isSurveyWorkspace ? `Ответы: ${item.button_options.length}` : `Кнопки: ${item.button_options.length}`}
                        </Badge>
                      ) : null}
                    </div>
                    {canOpen ? (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(event) => {
                          event.stopPropagation();
                          onOpenItem(item);
                        }}
                      >
                        <PanelLeft data-icon="inline-start" />
                        Открыть
                      </Button>
                    ) : null}
                  </div>
                </article>
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

export function WorkspaceStepDetailPane(props: {
  selectedItem: WorkspaceItem | null;
  detailTarget: WorkspaceStep | null;
  stepLabel: string;
  isSurveyWorkspace: boolean;
  form: null | {
    title: string;
    text: string;
    response_type: string;
    button_options: string;
    send_mode: string;
    send_time: string;
    target_field: string;
    launch_scenario_key: string;
    return_to_step_key: string;
    send_employee_card: boolean;
    notify_on_send_text: string;
    notify_on_send_recipient_ids: string;
    notify_on_send_recipient_scope: string;
    step_send_notifications: WorkspaceStepSendNotificationRule[];
    button_notifications: WorkspaceButtonNotification[];
  };
  textRef: React.RefObject<HTMLTextAreaElement | null>;
  fileInputRef: React.RefObject<HTMLInputElement | null>;
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
  onFormChange: (
    updater: (
      prev: {
        title: string;
        text: string;
        response_type: string;
        button_options: string;
        send_mode: string;
        send_time: string;
        target_field: string;
        launch_scenario_key: string;
        return_to_step_key: string;
        send_employee_card: boolean;
        notify_on_send_text: string;
        notify_on_send_recipient_ids: string;
        notify_on_send_recipient_scope: string;
        step_send_notifications: WorkspaceStepSendNotificationRule[];
        button_notifications: WorkspaceButtonNotification[];
      } | null,
    ) => {
      title: string;
      text: string;
      response_type: string;
      button_options: string;
      send_mode: string;
      send_time: string;
      target_field: string;
      launch_scenario_key: string;
      return_to_step_key: string;
      send_employee_card: boolean;
      notify_on_send_text: string;
      notify_on_send_recipient_ids: string;
      notify_on_send_recipient_scope: string;
      step_send_notifications: WorkspaceStepSendNotificationRule[];
      button_notifications: WorkspaceButtonNotification[];
    } | null,
  ) => void;
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
                    Для этой кнопки ветка пока не создана. Создай её, и после этого можно будет настроить тип ответа,
                    цепочку шагов и дальнейшую логику.
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <Button onClick={onCreateBranch}>
                    <Plus data-icon="inline-start" />
                    Создать ветку
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

                    <label className="grid gap-2">
                      <span className="text-sm font-semibold text-foreground/75">Текст</span>
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
                    </label>
                  </>
                )}

                <div className="flex flex-wrap items-center gap-2 text-[0.72rem]">
                  <span className="text-muted-foreground">Теги:</span>
                  <Button type="button" variant="outline" size="xs" onClick={() => onInsertIntoText("{name}")}>{`{name}`}</Button>
                  <Button type="button" variant="outline" size="xs" onClick={() => onInsertIntoText("{full_name}")}>{`{full_name}`}</Button>
                  <Button type="button" variant="outline" size="xs" onClick={() => onInsertIntoText("{doc:Оффер}")}>{`{doc:Оффер}`}</Button>
                </div>

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
                      {detailTarget?.has_attachment ? "Заменить файл" : "Добавить файл"}
                    </Button>
                  </div>
                  {detailTarget?.has_attachment ? (
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
            <label className="grid gap-2">
              <span className="text-sm font-semibold text-foreground/75">Текст уведомления</span>
              <Textarea
                className="min-h-[120px] text-sm"
                value={notificationRuleEditor?.message_text || ""}
                onChange={(event) =>
                  setNotificationRuleEditor((prev) => (prev ? { ...prev, message_text: event.target.value } : prev))
                }
                placeholder="Например: Пользователь нажал кнопку."
              />
            </label>
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
            <label className="grid gap-2">
              <span className="text-sm font-semibold text-foreground/75">Текст уведомления</span>
              <Textarea
                className="min-h-[120px] text-sm"
                value={stepNotificationRuleEditor?.message_text || ""}
                onChange={(event) =>
                  setStepNotificationRuleEditor((prev) => (prev ? { ...prev, message_text: event.target.value } : prev))
                }
                placeholder="Например: Пользователю отправлен шаг."
              />
            </label>
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
