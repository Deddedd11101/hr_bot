import * as React from "react";
import EmojiPicker, { type EmojiClickData } from "emoji-picker-react";
import { ChevronRight, Copy, FileStack, PanelLeft, Paperclip, Plus, Smile, Trash2, X } from "lucide-react";

import { Button } from "@/components/ui/button";
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
  WorkspaceData,
  WorkspaceItem,
  WorkspaceStep,
} from "./types";

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
    <section className="flex min-h-0 flex-col overflow-hidden rounded-[10px] border border-[var(--color-border)] bg-[var(--color-panel)] p-4">
      <div className="mb-3">
        <div>
          <h3 className="text-[1.65rem] font-semibold">{sidebarTitle}</h3>
        </div>
      </div>
      {creatingScenario ? (
        <div className="mb-3 rounded-[10px] border border-[var(--color-border)] bg-[var(--color-panel-muted)] p-2">
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
            <Button size="sm" variant="ghost" className="w-8 p-0" onClick={onCancelCreateScenario}>
              <X className="size-4" />
            </Button>
          </div>
        </div>
      ) : (
        <button
          type="button"
          onClick={onOpenCreateScenario}
          className="mb-3 flex h-11 w-full items-center justify-center gap-2 rounded-[10px] border border-dashed border-[var(--color-border)] bg-[var(--color-panel-muted)] text-sm font-semibold transition-all duration-200 hover:rounded-[20px] hover:bg-white"
        >
          <Plus className="size-4" />
          {createItemLabel}
        </button>
      )}
      <Input
        placeholder={isSurveyWorkspace ? "Найти опрос" : "Найти сценарий"}
        value={search}
        onChange={(e) => onSearchChange(e.target.value)}
        className="text-sm"
      />
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <label className="inline-flex items-center gap-2 rounded-[10px] border border-[var(--color-border)] px-3 py-2 text-xs font-semibold text-[var(--color-muted-foreground)] transition-all duration-200 hover:rounded-[18px]">
          <input
            type="checkbox"
            checked={scenarios.length > 0 && scenarios.every((scenario) => selectedScenarioIds.includes(scenario.id))}
            onChange={onToggleSelectAllVisibleScenarios}
          />
          Выбрать все
        </label>
        <Button
          size="sm"
          variant="secondary"
          className="w-9 p-0"
          title="Копировать выбранные"
          onClick={() => onBulkScenarioAction("bulk-copy")}
          disabled={!selectedScenarioIds.length}
        >
          <Copy className="size-4" />
        </Button>
        <Button
          size="sm"
          variant="secondary"
          className="w-9 p-0 text-red-600 hover:bg-red-50 hover:text-red-700"
          title="Удалить выбранные"
          onClick={() => onBulkScenarioAction("bulk-delete")}
          disabled={!selectedScenarioIds.length}
        >
          <Trash2 className="size-4" />
        </Button>
      </div>
      {sidebarState.message ? (
        <p className={`mt-3 text-sm ${sidebarState.error ? "text-[var(--color-danger)]" : "text-[var(--color-muted-foreground)]"}`}>
          {sidebarState.message}
        </p>
      ) : null}
      <ScrollArea className="mt-4 min-h-0 flex-1">
        <div className="pr-3" style={{ display: "grid", gap: "0.65rem" }}>
          {scenarios.map((scenario) => (
            <button
              key={scenario.id}
              type="button"
              onClick={() => onSelectScenario(scenario.id)}
              draggable
              onDragStart={() => onScenarioDragStart(scenario.id)}
              onDragOver={(event) => event.preventDefault()}
              onDrop={() => onScenarioDrop(scenario.id)}
              onDragEnd={onScenarioDragEnd}
              className={`flex w-full min-w-0 flex-col gap-2 rounded-[10px] border p-3 text-left transition-all duration-200 hover:rounded-[20px] ${
                scenario.id === selectedScenarioId
                  ? "border-[color:var(--color-accent)] bg-[var(--color-panel-muted)] shadow-sm"
                  : "border-[var(--color-border)] bg-white hover:bg-[var(--color-panel-muted)]"
              }`}
            >
              <div className="flex items-center justify-between gap-3">
                <label
                  className="inline-flex items-center gap-2"
                  onClick={(event) => event.stopPropagation()}
                  onMouseDown={(event) => event.stopPropagation()}
                >
                  <input
                    type="checkbox"
                    checked={selectedScenarioIds.includes(scenario.id)}
                    onChange={() => onToggleScenarioSelection(scenario.id)}
                  />
                  <span className="text-[0.95rem] font-semibold">{scenario.title}</span>
                </label>
                <FileStack className="size-4 text-[var(--color-muted-foreground)]" />
              </div>
              <p className="text-[0.83rem] leading-5 text-[var(--color-muted-foreground)]">{scenario.description || "Без описания"}</p>
              <div className="flex flex-wrap gap-2 text-[0.72rem] font-medium text-[var(--color-muted-foreground)]">
                <span className="rounded-[10px] bg-black/5 px-2 py-1 transition-all duration-200 hover:rounded-[16px]">
                  {scenario.role_scope_label}
                </span>
                <span className="rounded-[10px] bg-black/5 px-2 py-1 transition-all duration-200 hover:rounded-[16px]">
                  {scenario.employee_scope_label}
                </span>
                <span className="rounded-[10px] bg-black/5 px-2 py-1 transition-all duration-200 hover:rounded-[16px]">
                  {scenario.trigger_mode_label}
                </span>
              </div>
            </button>
          ))}
        </div>
      </ScrollArea>
    </section>
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
    <section className="flex min-h-0 flex-col overflow-hidden rounded-[10px] border border-[var(--color-border)] bg-[var(--color-panel)] p-4">
      <div className="mb-3 flex flex-wrap items-center gap-2 text-sm text-[var(--color-muted-foreground)]">
        {stack.map((entry, index) => (
          <React.Fragment key={entry.key}>
            {index > 0 ? <ChevronRight className="size-4 shrink-0" /> : null}
            <button
              type="button"
              className="inline-flex max-w-full items-center gap-2 rounded-[10px] bg-black/5 px-3 py-1.5 text-left font-medium whitespace-normal break-words transition-all duration-200 hover:rounded-[18px] hover:bg-black/8"
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
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--color-muted-foreground)]">
              {currentContainer.subtitle}
            </p>
          ) : null}
          <h3 className={currentContainer?.subtitle ? "mt-1 text-[1.55rem] font-semibold" : "text-[1.2rem] font-semibold"}>
            {currentContainer?.type === "root" ? stepTitle : currentContainer?.title || payloadWorkspace?.scenario.title}
          </h3>
        </div>
        {currentContainer?.type === "root" ? (
          <div className="flex flex-wrap items-center gap-2">
            {scenarioSettingsForm ? (
              <Popover open={scenarioSettingsOpen} onOpenChange={onScenarioSettingsOpenChange}>
                <PopoverTrigger asChild>
                  <Button variant="secondary" size="sm">
                    Настройки
                  </Button>
                </PopoverTrigger>
                <PopoverContent align="end" className="p-4" style={{ width: "min(440px, calc(100vw - 32px))" }}>
                  <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h4 className="text-base font-semibold">Настройки {itemLabel}</h4>
                      <p className="mt-1 text-sm text-[var(--color-muted-foreground)]">{payloadWorkspace?.scenario.title}</p>
                    </div>
                    <Button size="sm" onClick={onSaveScenarioSettings} disabled={scenarioSettingsState.saving} className="min-w-[132px] whitespace-nowrap px-8">
                      {scenarioSettingsState.saving ? "Сохраняю..." : "Сохранить"}
                    </Button>
                  </div>
                  <div className="flex flex-col gap-4">
                    <label className="grid min-w-0" style={{ gap: "10px", justifyItems: "stretch", alignItems: "baseline", justifyContent: "stretch", alignContent: "space-between" }}>
                      <span className="text-sm font-semibold text-[var(--color-foreground)]/75">Описание</span>
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
                        <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-[0.58rem] font-semibold text-[var(--color-muted-foreground)]">
                          {scenarioSettingsForm.description.length}/50
                        </span>
                      </div>
                    </label>
                    <label className="grid min-w-0" style={{ gap: "10px", justifyItems: "stretch", alignItems: "baseline", justifyContent: "stretch", alignContent: "space-between" }}>
                      <span className="text-sm font-semibold text-[var(--color-foreground)]/75">Должность</span>
                      <SingleSelectPicker
                        options={roleScopeOptions}
                        value={scenarioSettingsForm.role_scope}
                        placeholder="Должность"
                        onChange={(nextValue) => onScenarioSettingsFormChange((prev) => (prev ? { ...prev, role_scope: nextValue } : prev))}
                      />
                    </label>
                    <label className="grid min-w-0" style={{ gap: "10px", justifyItems: "stretch", alignItems: "baseline", justifyContent: "stretch", alignContent: "space-between" }}>
                      <span className="text-sm font-semibold text-[var(--color-foreground)]/75">Аудитория</span>
                      <SingleSelectPicker
                        options={employeeScopeOptions}
                        value={scenarioSettingsForm.employee_scope}
                        placeholder="Аудитория"
                        onChange={(nextValue) => onScenarioSettingsFormChange((prev) => (prev ? { ...prev, employee_scope: nextValue } : prev))}
                      />
                    </label>
                    {!isSurveyWorkspace ? (
                      <label className="grid min-w-0" style={{ gap: "10px", justifyItems: "stretch", alignItems: "baseline", justifyContent: "stretch", alignContent: "space-between" }}>
                        <span className="text-sm font-semibold text-[var(--color-foreground)]/75">Запуск</span>
                        <SingleSelectPicker
                          options={triggerModeOptions}
                          value={scenarioSettingsForm.trigger_mode}
                          placeholder="Запуск"
                          onChange={(nextValue) => onScenarioSettingsFormChange((prev) => (prev ? { ...prev, trigger_mode: nextValue } : prev))}
                        />
                      </label>
                    ) : null}
                    <label className="grid min-w-0" style={{ gap: "10px", justifyItems: "stretch", alignItems: "baseline", justifyContent: "stretch", alignContent: "space-between" }}>
                      <span className="text-sm font-semibold text-[var(--color-foreground)]/75">Карточка</span>
                      <SingleSelectPicker
                        options={targetEmployeeOptions}
                        value={scenarioSettingsForm.target_employee_id}
                        placeholder="Любая"
                        onChange={(nextValue) => onScenarioSettingsFormChange((prev) => (prev ? { ...prev, target_employee_id: nextValue } : prev))}
                      />
                    </label>
                  </div>
                  {scenarioSettingsState.message ? (
                    <p className={`mt-4 text-sm ${scenarioSettingsState.error ? "text-[var(--color-danger)]" : "text-[var(--color-muted-foreground)]"}`}>
                      {scenarioSettingsState.message}
                    </p>
                  ) : null}
                </PopoverContent>
              </Popover>
            ) : null}
            <Button variant="secondary" size="sm" onClick={onAddRootStep}>
              <Plus className="size-4" />
              {isSurveyWorkspace ? "Добавить вопрос" : "Добавить шаг"}
            </Button>
          </div>
        ) : currentContainer?.type === "chain" ? (
          <Button variant="secondary" size="sm" onClick={onAddChainStep}>
            <Plus className="size-4" />
            Добавить шаг
          </Button>
        ) : null}
      </div>

      <ScrollArea className="min-h-0 flex-1">
        <div className="pr-3" style={{ display: "grid", gap: "0.65rem" }}>
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
                className={`flex w-full min-w-0 cursor-pointer flex-col gap-2 rounded-[10px] border p-3 transition-all duration-200 hover:rounded-[20px] ${
                  active
                    ? "border-[color:var(--color-accent)] bg-[var(--color-panel-muted)] shadow-sm"
                    : "border-[var(--color-border)] bg-white hover:bg-[var(--color-panel-muted)]"
                }`}
              >
                <div className="space-y-1">
                  <h4 className="text-[0.95rem] font-semibold">{workspaceItemTitle(item, index)}</h4>
                  <p className="text-[0.83rem] leading-5 text-[var(--color-muted-foreground)]">{summarizeItem(item)}</p>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <div className="flex flex-wrap gap-2 text-[0.72rem] font-medium text-[var(--color-muted-foreground)]">
                    <span className="rounded-[10px] bg-black/5 px-2 py-1 transition-all duration-200 hover:rounded-[16px]">
                      {item.kind === "branch_slot" ? "Ветка" : item.response_label}
                    </span>
                    {"button_options" in item && item.button_options.length ? (
                      <span className="rounded-[10px] bg-black/5 px-2 py-1 transition-all duration-200 hover:rounded-[16px]">
                        Кнопки: {item.button_options.length}
                      </span>
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
                      <PanelLeft className="size-4" />
                      Открыть
                    </Button>
                  ) : null}
                </div>
              </article>
            );
          })}
        </div>
      </ScrollArea>
    </section>
  );
}

export function WorkspaceDetailSection({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <section
      className="flex min-h-0 flex-col overflow-hidden rounded-[10px] border border-[var(--color-border)] bg-[var(--color-panel)] p-4"
      style={{ position: "sticky", top: 0, alignSelf: "stretch" }}
    >
      <div className="mb-3">
        <p className="text-[1rem] font-medium text-[var(--color-foreground)]/85">Детали</p>
      </div>
      {children}
    </section>
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
  };
  textRef: React.RefObject<HTMLTextAreaElement | null>;
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  emojiOpen: boolean;
  payloadWorkspace: WorkspaceData | null | undefined;
  attachmentState: { uploading: boolean; message: string; error: boolean };
  saveState: { saving: boolean; message: string; error: boolean };
  openLabel: string;
  responseTypePickerOptions: SingleOption[];
  sendModeOptions: SingleOption[];
  targetFieldOptions: SingleOption[];
  launchScenarioOptions: SingleOption[];
  notificationScopeOptions: SingleOption[];
  onEmojiOpenChange: (open: boolean) => void;
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
    emojiOpen,
    payloadWorkspace,
    attachmentState,
    saveState,
    openLabel,
    responseTypePickerOptions,
    sendModeOptions,
    targetFieldOptions,
    launchScenarioOptions,
    notificationScopeOptions,
    onEmojiOpenChange,
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
              <div className="flex flex-col gap-4 rounded-[10px] border border-[var(--color-border)] bg-[var(--color-panel-muted)] p-4">
                <div className="space-y-1">
                  <h4 className="text-base font-semibold">{selectedItem.label}</h4>
                  <p className="text-sm leading-6 text-[var(--color-muted-foreground)]">
                    Для этой кнопки ветка пока не создана. Создай её, и после этого можно будет настроить тип ответа,
                    цепочку шагов и дальнейшую логику.
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <Button onClick={onCreateBranch}>
                    <Plus className="size-4" />
                    Создать ветку
                  </Button>
                </div>
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "0.95rem" }}>
                <label style={{ display: "grid", gap: "0.5rem" }}>
                  <span className="text-sm font-semibold text-[var(--color-foreground)]/75">Название</span>
                  <Input
                    value={form?.title || ""}
                    onChange={(event) => onFormChange((prev) => (prev ? { ...prev, title: event.target.value } : prev))}
                    className="h-10 text-sm"
                  />
                </label>

                <label style={{ display: "grid", gap: "0.5rem" }}>
                  <span className="text-sm font-semibold text-[var(--color-foreground)]/75">Текст</span>
                  <div className="relative">
                    <Textarea
                      ref={textRef}
                      className="min-h-[140px] px-3 py-3 pr-12 text-sm leading-6"
                      value={form?.text || ""}
                      onChange={(event) => onFormChange((prev) => (prev ? { ...prev, text: event.target.value } : prev))}
                    />
                    <Popover open={emojiOpen} onOpenChange={onEmojiOpenChange}>
                      <PopoverTrigger asChild>
                        <button
                          type="button"
                          className="absolute bottom-2.5 right-2.5 inline-flex size-8 items-center justify-center rounded-[10px] border border-[var(--color-border)] bg-white text-base transition-all duration-200 hover:rounded-[16px] hover:bg-[var(--color-panel-muted)]"
                          aria-label="Добавить эмоджи"
                          title="Добавить эмоджи"
                        >
                          <Smile className="size-4" />
                        </button>
                      </PopoverTrigger>
                      <PopoverContent className="w-auto border-none bg-transparent p-0 shadow-none" align="end">
                        <EmojiPicker
                          lazyLoadEmojis
                          skinTonesDisabled
                          width={320}
                          height={400}
                          onEmojiClick={(emojiData: EmojiClickData) => {
                            onInsertIntoText(emojiData.emoji);
                            onEmojiOpenChange(false);
                          }}
                        />
                      </PopoverContent>
                    </Popover>
                  </div>
                </label>

                <div className="flex flex-wrap items-center gap-2 text-[0.72rem]">
                  <span className="text-[var(--color-muted-foreground)]">Теги:</span>
                  <button type="button" onClick={() => onInsertIntoText("{name}")} className="rounded-[10px] border border-[var(--color-border)] px-2.5 py-1.5 font-semibold text-[var(--color-foreground)]/80 transition-all duration-200 hover:rounded-[16px] hover:bg-[var(--color-panel-muted)]">{`{name}`}</button>
                  <button type="button" onClick={() => onInsertIntoText("{full_name}")} className="rounded-[10px] border border-[var(--color-border)] px-2.5 py-1.5 font-semibold text-[var(--color-foreground)]/80 transition-all duration-200 hover:rounded-[16px] hover:bg-[var(--color-panel-muted)]">{`{full_name}`}</button>
                  <button type="button" onClick={() => onInsertIntoText("{doc:Оффер}")} className="rounded-[10px] border border-[var(--color-border)] px-2.5 py-1.5 font-semibold text-[var(--color-foreground)]/80 transition-all duration-200 hover:rounded-[16px] hover:bg-[var(--color-panel-muted)]">{`{doc:Оффер}`}</button>
                </div>

                <div className="space-y-2">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-sm font-semibold text-[var(--color-foreground)]/75">Вложение</span>
                    <input ref={fileInputRef} type="file" className="hidden" onChange={onAttachmentSelected} />
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      onClick={() => fileInputRef.current?.click()}
                      disabled={attachmentState.uploading}
                    >
                      <Paperclip className="size-4" />
                      {detailTarget?.has_attachment ? "Заменить файл" : "Добавить файл"}
                    </Button>
                  </div>
                  {detailTarget?.has_attachment ? (
                    <div className="flex flex-wrap items-center gap-2 rounded-[10px] border border-[var(--color-border)] bg-[var(--color-panel-muted)] px-3 py-2">
                      <a
                        href={`/flows/steps/${detailTarget.id}/attachment`}
                        className="min-w-0 flex-1 truncate text-sm font-medium text-[var(--color-foreground)] underline-offset-4 hover:underline"
                      >
                        {detailTarget.attachment_filename}
                      </a>
                      <Button type="button" variant="ghost" size="sm" onClick={onDeleteAttachment} disabled={attachmentState.uploading}>
                        Удалить
                      </Button>
                    </div>
                  ) : null}
                  <p className={`text-sm ${attachmentState.error ? "text-[var(--color-danger)]" : "text-[var(--color-muted-foreground)]"}`}>
                    {attachmentState.message || " "}
                  </p>
                </div>

                <label style={{ display: "grid", gap: "0.5rem" }}>
                  <span className="text-sm font-semibold text-[var(--color-foreground)]/75">Тип ответа</span>
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
                              target_field: supportsTargetField(nextValue) ? prev.target_field : "",
                            }
                          : prev,
                      )
                    }
                  />
                </label>

                {supportsButtonOptions(form?.response_type || "") ? (
                  <label style={{ display: "grid", gap: "0.5rem" }}>
                    <span className="text-sm font-semibold text-[var(--color-foreground)]/75">Кнопки</span>
                    <Textarea
                      className="min-h-[118px] px-3 py-3 text-sm leading-6"
                      value={form?.button_options || ""}
                      onChange={(event) => onFormChange((prev) => (prev ? { ...prev, button_options: event.target.value } : prev))}
                      placeholder="Каждая строка = отдельная кнопка"
                    />
                  </label>
                ) : null}

                <label style={{ display: "grid", gap: "0.5rem" }}>
                  <span className="text-sm font-semibold text-[var(--color-foreground)]/75">Режим отправки</span>
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
                  <label style={{ display: "grid", gap: "0.5rem" }}>
                    <span className="text-sm font-semibold text-[var(--color-foreground)]/75">Время отправки</span>
                    <Input
                      type="time"
                      value={form.send_time}
                      onChange={(event) => onFormChange((prev) => (prev ? { ...prev, send_time: event.target.value } : prev))}
                      className="h-10 text-sm"
                    />
                  </label>
                ) : null}

                <label style={{ display: "grid", gap: "0.5rem" }}>
                  <span className="text-sm font-semibold text-[var(--color-foreground)]/75">Сохранить ответ</span>
                  <SingleSelectPicker
                    options={targetFieldOptions}
                    value={form?.target_field || ""}
                    placeholder="Не сохранять"
                    onChange={(nextValue) => onFormChange((prev) => (prev ? { ...prev, target_field: nextValue } : prev))}
                  />
                </label>

                <label style={{ display: "grid", gap: "0.5rem" }}>
                  <span className="text-sm font-semibold text-[var(--color-foreground)]/75">Переход к сценарию</span>
                  <SingleSelectPicker
                    options={launchScenarioOptions}
                    value={form?.launch_scenario_key || ""}
                    placeholder="Не выполнять переход"
                    onChange={(nextValue) => onFormChange((prev) => (prev ? { ...prev, launch_scenario_key: nextValue } : prev))}
                  />
                </label>

                <details className="rounded-[10px] border border-[var(--color-border)] bg-[var(--color-panel-muted)] p-3 transition-all duration-200 hover:rounded-[18px]">
                  <summary className="cursor-pointer list-none text-sm font-semibold text-[var(--color-foreground)]/80">
                    Уведомление для шага
                  </summary>
                  <div className="mt-3 space-y-3">
                    <label className="block space-y-2">
                      <span className="text-sm font-semibold text-[var(--color-foreground)]/75">Текст уведомления</span>
                      <Textarea
                        className="min-h-[110px] text-sm"
                        value={form?.notify_on_send_text || ""}
                        onChange={(event) => onFormChange((prev) => (prev ? { ...prev, notify_on_send_text: event.target.value } : prev))}
                        placeholder="Например: Пользователю отправлено сообщение этого шага."
                      />
                    </label>
                    <div className="space-y-2">
                      <span className="text-sm font-semibold text-[var(--color-foreground)]/75">Получатели уведомления</span>
                      <NotificationRecipientsPicker
                        employeeOptions={payloadWorkspace?.employee_options || []}
                        value={form?.notify_on_send_recipient_ids || ""}
                        onChange={(next) => onFormChange((prev) => (prev ? { ...prev, notify_on_send_recipient_ids: next } : prev))}
                      />
                    </div>
                    <label className="block space-y-2">
                      <span className="text-sm font-semibold text-[var(--color-foreground)]/75">Адресаты из карточки сотрудника</span>
                      <SingleSelectPicker
                        options={notificationScopeOptions}
                        value={form?.notify_on_send_recipient_scope || ""}
                        placeholder="Не добавлять адресатов из карточки"
                        onChange={(nextValue) => onFormChange((prev) => (prev ? { ...prev, notify_on_send_recipient_scope: nextValue } : prev))}
                      />
                    </label>
                  </div>
                </details>

                <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                  <p className={`text-sm ${saveState.error ? "text-[var(--color-danger)]" : "text-[var(--color-muted-foreground)]"}`}>{saveState.message || " "}</p>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <Button variant="outline" className="border-red-200 text-red-600 hover:bg-red-50 hover:text-red-700" onClick={onDeleteCurrent}>
                      <Trash2 className="size-4" />
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
            <div className="rounded-2xl border border-dashed border-[var(--color-border)] p-4 text-sm text-[var(--color-muted-foreground)]">
              Выбери {stepLabel}, ветку или элемент цепочки, чтобы увидеть детали справа.
            </div>
          )}
        </div>
      </ScrollArea>
    </>
  );
}
