import * as React from "react";
import { ChevronRight, Copy, FileStack, PanelLeft, Paperclip, Plus, Trash2, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { EmojiPickerPopover } from "@/components/ui/emoji-picker-popover";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";

import { buildChildContainer, crumbIcon, itemKey, summarizeItem, workspaceItemTitle } from "./model";
import { NotificationRecipientsPicker, SingleSelectPicker } from "./pickers";
import type {
  Container,
  ScenarioSettingsForm,
  ScenarioSummary,
  SingleOption,
  WorkspaceButtonNotification,
  WorkspaceData,
  WorkspaceItem,
  WorkspaceStep,
} from "./types";

export function WorkspaceFlashNotice(props: { message: string; error: boolean }) {
  if (!props.message) {
    return null;
  }

  return (
    <div
      className={`mb-4 rounded-lg border px-4 py-3 text-sm font-medium ${
        props.error
          ? "border-destructive/30 bg-destructive/10 text-destructive"
          : "border-emerald-200 bg-emerald-50 text-emerald-700"
      }`}
    >
      {props.message}
    </div>
  );
}

export function WorkspaceSidebarSection(props: {
  sidebarTitle: string;
  isSurveyWorkspace: boolean;
  createItemLabel: string;
  itemNamePlaceholder: string;
  creatingScenario: boolean;
  newScenarioTitle: string;
  search: string;
  scenarios: ScenarioSummary[];
  selectedScenarioId: number | null;
  selectedScenarioIds: number[];
  sidebarState: { message: string; error: boolean };
  onNewScenarioTitleChange: (value: string) => void;
  onCreateScenario: () => void;
  onOpenCreateScenario: () => void;
  onCancelCreateScenario: () => void;
  onSearchChange: (value: string) => void;
  onToggleSelectAllVisibleScenarios: () => void;
  onBulkScenarioAction: (action: "bulk-copy" | "bulk-delete") => void;
  onSelectScenario: (scenarioId: number) => void;
  onScenarioDragStart: (scenarioId: number) => void;
  onScenarioDrop: (scenarioId: number) => void;
  onScenarioDragEnd: () => void;
  onToggleScenarioSelection: (scenarioId: number) => void;
}) {
  const {
    sidebarTitle,
    isSurveyWorkspace,
    createItemLabel,
    itemNamePlaceholder,
    creatingScenario,
    newScenarioTitle,
    search,
    scenarios,
    selectedScenarioId,
    selectedScenarioIds,
    sidebarState,
    onNewScenarioTitleChange,
    onCreateScenario,
    onOpenCreateScenario,
    onCancelCreateScenario,
    onSearchChange,
    onToggleSelectAllVisibleScenarios,
    onBulkScenarioAction,
    onSelectScenario,
    onScenarioDragStart,
    onScenarioDrop,
    onScenarioDragEnd,
    onToggleScenarioSelection,
  } = props;

  return (
    <Card className="flex min-h-0 flex-col overflow-hidden rounded-lg border border-border bg-card p-4 shadow-none ring-0">
      <CardHeader className="gap-3 border-b border-border/70 p-0 pb-4">
        <CardTitle className="text-[1.65rem] font-semibold">{sidebarTitle}</CardTitle>
      </CardHeader>
      {creatingScenario ? (
        <div className="mt-4 rounded-lg border border-border bg-muted/50 p-2">
          <div className="flex items-center gap-2">
            <Input
              value={newScenarioTitle}
              onChange={(event) => onNewScenarioTitleChange(event.target.value)}
              placeholder={itemNamePlaceholder}
              className="h-10 text-sm"
            />
            <Button size="sm" onClick={onCreateScenario} className="px-3">
              Готово
            </Button>
            <Button size="icon-sm" variant="ghost" onClick={onCancelCreateScenario} aria-label="Отменить создание">
              <X />
            </Button>
          </div>
        </div>
      ) : (
        <Button
          variant="outline"
          className="mt-4 w-full justify-center border-dashed"
          onClick={onOpenCreateScenario}
        >
          <Plus data-icon="inline-start" />
          {createItemLabel}
        </Button>
      )}
      <Input
        placeholder={isSurveyWorkspace ? "Найти опрос" : "Найти сценарий"}
        value={search}
        onChange={(e) => onSearchChange(e.target.value)}
        className="mt-3 text-sm"
      />
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <label className="inline-flex h-7 items-center gap-2 rounded-lg border border-border bg-background px-2.5 text-xs font-semibold text-muted-foreground">
          <Checkbox
            checked={scenarios.length > 0 && scenarios.every((scenario) => selectedScenarioIds.includes(scenario.id))}
            onCheckedChange={onToggleSelectAllVisibleScenarios}
            aria-label="Выбрать все сценарии"
          />
          Выбрать все
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
        <Button
          size="icon-sm"
          variant="destructive"
          title="Удалить выбранные"
          aria-label="Удалить выбранные"
          onClick={() => onBulkScenarioAction("bulk-delete")}
          disabled={!selectedScenarioIds.length}
        >
          <Trash2 />
        </Button>
      </div>
      {sidebarState.message ? (
        <p className={`mt-3 text-sm ${sidebarState.error ? "text-destructive" : "text-muted-foreground"}`}>
          {sidebarState.message}
        </p>
      ) : null}
      <ScrollArea className="mt-4 min-h-0 flex-1">
        <div className="grid gap-2 pr-3">
          {scenarios.map((scenario) => (
            <article
              key={scenario.id}
              role="button"
              tabIndex={0}
              onClick={() => onSelectScenario(scenario.id)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  onSelectScenario(scenario.id);
                }
              }}
              draggable
              onDragStart={() => onScenarioDragStart(scenario.id)}
              onDragOver={(event) => event.preventDefault()}
              onDrop={() => onScenarioDrop(scenario.id)}
              onDragEnd={onScenarioDragEnd}
              className={`flex w-full min-w-0 cursor-pointer flex-col gap-2 rounded-lg border p-3 text-left transition-colors ${
                scenario.id === selectedScenarioId
                  ? "border-primary/70 bg-muted/50"
                  : "border-border bg-card hover:bg-accent/60"
              }`}
            >
              <div className="flex items-center justify-between gap-3">
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
                <FileStack className="size-4 shrink-0 text-muted-foreground" />
              </div>
              <p className="text-[0.83rem] leading-5 text-muted-foreground">{scenario.description || "Без описания"}</p>
              <div className="flex flex-wrap gap-1.5">
                <Badge variant="secondary">{scenario.role_scope_label}</Badge>
                <Badge variant="secondary">{scenario.employee_scope_label}</Badge>
                <Badge variant="secondary">{scenario.trigger_mode_label}</Badge>
              </div>
            </article>
          ))}
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
  stepTitle: string;
  itemLabel: string;
  isSurveyWorkspace: boolean;
  payloadWorkspace: WorkspaceData | null | undefined;
  exportUrl: string;
  scenarioSettingsForm: ScenarioSettingsForm | null;
  scenarioSettingsOpen: boolean;
  scenarioSettingsState: { saving: boolean; message: string; error: boolean };
  roleScopeOptions: SingleOption[];
  employeeScopeOptions: SingleOption[];
  triggerModeOptions: SingleOption[];
  targetEmployeeOptions: SingleOption[];
  dragStepId: number | null;
  onBreadcrumbClick: (index: number) => void;
  onScenarioSettingsOpenChange: (open: boolean) => void;
  onSaveScenarioSettings: () => void;
  onScenarioSettingsFormChange: (updater: (prev: ScenarioSettingsForm | null) => ScenarioSettingsForm | null) => void;
  onAddRootStep: () => void;
  onAddChainStep: () => void;
  onSelectItem: (itemKey: string) => void;
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
    stepTitle,
    itemLabel,
    isSurveyWorkspace,
    payloadWorkspace,
    exportUrl,
    scenarioSettingsForm,
    scenarioSettingsOpen,
    scenarioSettingsState,
    roleScopeOptions,
    employeeScopeOptions,
    triggerModeOptions,
    targetEmployeeOptions,
    dragStepId,
    onBreadcrumbClick,
    onScenarioSettingsOpenChange,
    onSaveScenarioSettings,
    onScenarioSettingsFormChange,
    onAddRootStep,
    onAddChainStep,
    onSelectItem,
    onDragStepStart,
    onDragStepDrop,
    onDragStepEnd,
    onOpenItem,
  } = props;

  return (
    <Card className="flex min-h-0 flex-col overflow-hidden rounded-lg border border-border bg-card p-4 shadow-none ring-0">
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
        {currentContainer?.type === "root" ? (
          <div className="flex flex-wrap items-center gap-2">
            {exportUrl ? (
              <Button render={<a href={exportUrl} />} variant="outline" size="sm">
                Выгрузить Excel
              </Button>
            ) : null}
            {scenarioSettingsForm ? (
              <Popover open={scenarioSettingsOpen} onOpenChange={onScenarioSettingsOpenChange}>
                <PopoverTrigger render={<Button variant="secondary" size="sm" />}>
                  Настройки
                </PopoverTrigger>
                <PopoverContent align="end" className="w-[min(440px,calc(100vw-32px))] p-4">
                  <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h4 className="text-base font-semibold">Настройки {itemLabel}</h4>
                      <p className="mt-1 text-sm text-muted-foreground">{payloadWorkspace?.scenario.title}</p>
                    </div>
                    <Button size="sm" onClick={onSaveScenarioSettings} disabled={scenarioSettingsState.saving} className="min-w-[132px] whitespace-nowrap px-8">
                      {scenarioSettingsState.saving ? "Сохраняю..." : "Сохранить"}
                    </Button>
                  </div>
                  <div className="flex flex-col gap-4">
                    <label className="grid min-w-0 gap-2.5">
                      <span className="text-sm font-semibold text-foreground/75">Описание</span>
                      <div className="relative">
                        <textarea
                          value={scenarioSettingsForm.description}
                          maxLength={50}
                          placeholder="Коротко"
                          className="min-h-[76px] w-full rounded-lg border border-input bg-background px-3 py-2 pr-12 text-sm outline-none"
                          onChange={(event) =>
                            onScenarioSettingsFormChange((prev) =>
                              prev ? { ...prev, description: event.target.value.slice(0, 50) } : prev,
                            )
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
                        onChange={(nextValue) => onScenarioSettingsFormChange((prev) => (prev ? { ...prev, role_scope: nextValue } : prev))}
                      />
                    </label>
                    <label className="grid min-w-0 gap-2.5">
                      <span className="text-sm font-semibold text-foreground/75">Аудитория</span>
                      <SingleSelectPicker
                        options={employeeScopeOptions}
                        value={scenarioSettingsForm.employee_scope}
                        placeholder="Аудитория"
                        onChange={(nextValue) => onScenarioSettingsFormChange((prev) => (prev ? { ...prev, employee_scope: nextValue } : prev))}
                      />
                    </label>
                    {!isSurveyWorkspace ? (
                      <label className="grid min-w-0 gap-2.5">
                        <span className="text-sm font-semibold text-foreground/75">Запуск</span>
                        <SingleSelectPicker
                          options={triggerModeOptions}
                          value={scenarioSettingsForm.trigger_mode}
                          placeholder="Запуск"
                          onChange={(nextValue) => onScenarioSettingsFormChange((prev) => (prev ? { ...prev, trigger_mode: nextValue } : prev))}
                        />
                      </label>
                    ) : null}
                    <label className="grid min-w-0 gap-2.5">
                      <span className="text-sm font-semibold text-foreground/75">Карточка</span>
                      <SingleSelectPicker
                        options={targetEmployeeOptions}
                        value={scenarioSettingsForm.target_employee_id}
                        placeholder="Любая"
                        onChange={(nextValue) => onScenarioSettingsFormChange((prev) => (prev ? { ...prev, target_employee_id: nextValue } : prev))}
                      />
                    </label>
                  </div>
                  {scenarioSettingsState.message ? (
                    <p className={`mt-4 text-sm ${scenarioSettingsState.error ? "text-destructive" : "text-muted-foreground"}`}>
                      {scenarioSettingsState.message}
                    </p>
                  ) : null}
                </PopoverContent>
              </Popover>
            ) : null}
            <Button variant="secondary" size="sm" onClick={onAddRootStep}>
              <Plus data-icon="inline-start" />
              {isSurveyWorkspace ? "Добавить вопрос" : "Добавить шаг"}
            </Button>
          </div>
        ) : currentContainer?.type === "chain" ? (
          <Button variant="secondary" size="sm" onClick={onAddChainStep}>
            <Plus data-icon="inline-start" />
            Добавить шаг
          </Button>
        ) : null}
      </div>

      <ScrollArea className="min-h-0 flex-1">
        <div className="grid gap-2 pr-3">
          {currentItems.map((item, index) => {
            const canOpen = !!buildChildContainer(item);
            const active = itemKey(item) === selectedItemKey;
            return (
              <article
                key={itemKey(item) || `${currentContainer?.key}-${index}`}
                onClick={() => onSelectItem(itemKey(item))}
                draggable={currentContainer?.type === "root" && item.kind !== "branch_slot"}
                onDragStart={() => {
                  if (currentContainer?.type === "root" && item.kind !== "branch_slot") {
                    onDragStepStart(Number(itemKey(item)));
                  }
                }}
                onDragOver={(event) => {
                  if (currentContainer?.type === "root") {
                    event.preventDefault();
                  }
                }}
                onDrop={() => {
                  if (currentContainer?.type === "root" && item.kind !== "branch_slot") {
                    onDragStepDrop(item.id);
                  }
                }}
                onDragEnd={onDragStepEnd}
                className={`flex w-full min-w-0 cursor-pointer flex-col gap-2 rounded-lg border p-3 transition-colors ${
                  active
                    ? "border-primary/70 bg-muted/50"
                    : "border-border bg-card hover:bg-accent/60"
                }`}
              >
                <div className="flex flex-col gap-1">
                  <h4 className="text-[0.95rem] font-semibold">{workspaceItemTitle(item, index)}</h4>
                  <p className="text-[0.83rem] leading-5 text-muted-foreground">{summarizeItem(item)}</p>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <div className="flex flex-wrap gap-1.5">
                    <Badge variant="secondary">{item.kind === "branch_slot" ? "Ветка" : item.response_label}</Badge>
                    {"button_options" in item && item.button_options.length ? (
                      <Badge variant="secondary">Кнопки: {item.button_options.length}</Badge>
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
      className="flex min-h-0 flex-col overflow-hidden rounded-lg border border-border bg-card p-4 shadow-none ring-0"
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
  form: null | {
    title: string;
    text: string;
    response_type: string;
    button_options: string;
    send_mode: string;
    send_time: string;
    target_field: string;
    launch_scenario_key: string;
    send_employee_card: boolean;
    notify_on_send_text: string;
    notify_on_send_recipient_ids: string;
    notify_on_send_recipient_scope: string;
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
  notificationScopeOptions: SingleOption[];
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
        send_employee_card: boolean;
        notify_on_send_text: string;
        notify_on_send_recipient_ids: string;
        notify_on_send_recipient_scope: string;
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
      send_employee_card: boolean;
      notify_on_send_text: string;
      notify_on_send_recipient_ids: string;
      notify_on_send_recipient_scope: string;
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
    responseTypePickerOptions,
    sendModeOptions,
    targetFieldOptions,
    launchScenarioOptions,
    notificationScopeOptions,
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

  return (
    <>
      <Separator />
      <ScrollArea className="min-h-0 flex-1 pt-3">
        <div className="pr-3">
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
                      onChange={(event) => onFormChange((prev) => (prev ? { ...prev, text: event.target.value } : prev))}
                    />
                    <div className="absolute right-2.5 bottom-2.5">
                      <EmojiPickerPopover onEmojiSelect={onInsertIntoText} />
                    </div>
                  </div>
                </label>

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
                      <Button type="button" variant="ghost" size="sm" onClick={onDeleteAttachment} disabled={attachmentState.uploading}>
                        Удалить
                      </Button>
                    </div>
                  ) : null}
                  <p className={`text-sm ${attachmentState.error ? "text-destructive" : "text-muted-foreground"}`}>
                    {attachmentState.message || " "}
                  </p>
                </div>

                <label className="grid gap-2">
                  <span className="text-sm font-semibold text-foreground/75">Тип ответа</span>
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
                            }
                          : prev,
                      )
                    }
                  />
                </label>

                {supportsButtonOptions(form?.response_type || "") ? (
                  <label className="grid gap-2">
                    <span className="text-sm font-semibold text-foreground/75">Кнопки</span>
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
                            button_notifications: optionLabels.map((option_label, option_index) => {
                              const existing = prev.button_notifications.find((item) => item.option_index === option_index);
                              return {
                                option_index,
                                option_label,
                                message_text: existing?.message_text || "",
                                recipient_ids: existing?.recipient_ids || "",
                                recipient_scope: existing?.recipient_scope || "",
                              };
                            }),
                          };
                        })
                      }
                      placeholder="Каждая строка = отдельная кнопка"
                    />
                  </label>
                ) : null}

                {supportsButtonOptions(form?.response_type || "") && form?.button_notifications?.length ? (
                  <details className="rounded-lg border border-border bg-muted/50 p-3">
                    <summary className="cursor-pointer list-none text-sm font-semibold text-foreground/80">
                      Уведомления по кнопкам
                    </summary>
                    <div className="mt-3 flex flex-col gap-3">
                      {form.button_notifications.map((notification) => (
                        <div key={`${notification.option_index}-${notification.option_label}`} className="rounded-lg border border-border bg-card p-3">
                          <div className="flex flex-col gap-3">
                            <p className="text-sm font-semibold text-foreground/85">Кнопка: {notification.option_label}</p>
                            <label className="flex flex-col gap-2">
                              <span className="text-sm font-semibold text-foreground/75">Текст уведомления</span>
                              <Textarea
                                className="min-h-[96px] text-sm"
                                value={notification.message_text}
                                onChange={(event) =>
                                  onFormChange((prev) =>
                                    prev
                                      ? {
                                          ...prev,
                                          button_notifications: prev.button_notifications.map((item) =>
                                            item.option_index === notification.option_index ? { ...item, message_text: event.target.value } : item,
                                          ),
                                        }
                                      : prev,
                                  )
                                }
                                placeholder={`Например: Пользователь нажал кнопку "${notification.option_label}".`}
                              />
                            </label>
                            <div className="flex flex-col gap-2">
                              <span className="text-sm font-semibold text-foreground/75">Получатели уведомления</span>
                              <NotificationRecipientsPicker
                                employeeOptions={payloadWorkspace?.employee_options || []}
                                value={notification.recipient_ids}
                                onChange={(next) =>
                                  onFormChange((prev) =>
                                    prev
                                      ? {
                                          ...prev,
                                          button_notifications: prev.button_notifications.map((item) =>
                                            item.option_index === notification.option_index ? { ...item, recipient_ids: next } : item,
                                          ),
                                        }
                                      : prev,
                                  )
                                }
                              />
                            </div>
                            <label className="flex flex-col gap-2">
                              <span className="text-sm font-semibold text-foreground/75">Адресаты из карточки сотрудника</span>
                              <SingleSelectPicker
                                options={notificationScopeOptions}
                                value={notification.recipient_scope || ""}
                                placeholder="Не добавлять адресатов из карточки"
                                onChange={(nextValue) =>
                                  onFormChange((prev) =>
                                    prev
                                      ? {
                                          ...prev,
                                          button_notifications: prev.button_notifications.map((item) =>
                                            item.option_index === notification.option_index ? { ...item, recipient_scope: nextValue } : item,
                                          ),
                                        }
                                      : prev,
                                  )
                                }
                              />
                            </label>
                          </div>
                        </div>
                      ))}
                    </div>
                  </details>
                ) : null}

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

                {form?.send_mode === "specific_time" ? (
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
                    onChange={(nextValue) => onFormChange((prev) => (prev ? { ...prev, launch_scenario_key: nextValue } : prev))}
                  />
                </label>

                <details className="rounded-lg border border-border bg-muted/50 p-3">
                  <summary className="cursor-pointer list-none text-sm font-semibold text-foreground/80">
                    Уведомление для шага
                  </summary>
                  <div className="mt-3 flex flex-col gap-3">
                    <label className="flex flex-col gap-2">
                      <span className="text-sm font-semibold text-foreground/75">Текст уведомления</span>
                      <Textarea
                        className="min-h-[110px] text-sm"
                        value={form?.notify_on_send_text || ""}
                        onChange={(event) => onFormChange((prev) => (prev ? { ...prev, notify_on_send_text: event.target.value } : prev))}
                        placeholder="Например: Пользователю отправлено сообщение этого шага."
                      />
                    </label>
                    <div className="flex flex-col gap-2">
                      <span className="text-sm font-semibold text-foreground/75">Получатели уведомления</span>
                      <NotificationRecipientsPicker
                        employeeOptions={payloadWorkspace?.employee_options || []}
                        value={form?.notify_on_send_recipient_ids || ""}
                        onChange={(next) => onFormChange((prev) => (prev ? { ...prev, notify_on_send_recipient_ids: next } : prev))}
                      />
                    </div>
                    <label className="flex flex-col gap-2">
                      <span className="text-sm font-semibold text-foreground/75">Адресаты из карточки сотрудника</span>
                      <SingleSelectPicker
                        options={notificationScopeOptions}
                        value={form?.notify_on_send_recipient_scope || ""}
                        placeholder="Не добавлять адресатов из карточки"
                        onChange={(nextValue) => onFormChange((prev) => (prev ? { ...prev, notify_on_send_recipient_scope: nextValue } : prev))}
                      />
                    </label>
                  </div>
                </details>

                <div className="flex flex-col gap-3">
                  <p className={`text-sm ${saveState.error ? "text-destructive" : "text-muted-foreground"}`}>{saveState.message || " "}</p>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <Button variant="outline" className="border-destructive/30 text-destructive hover:bg-destructive/10 hover:text-destructive" onClick={onDeleteCurrent}>
                      <Trash2 data-icon="inline-start" />
                      Удалить
                    </Button>
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
    </>
  );
}
