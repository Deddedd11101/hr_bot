import React from "react";
import ReactDOM from "react-dom/client";
import EmojiPicker, { type EmojiClickData } from "emoji-picker-react";
import { Check, ChevronRight, ChevronsUpDown, Copy, FileStack, Paperclip, PanelLeft, Plus, Route, Search, Smile, Split, Trash2, Waypoints, X } from "lucide-react";

import "@/index.css";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";
import type { ScenarioSummary, WorkspaceBranchSlot, WorkspaceData, WorkspacePayload, WorkspaceStep } from "./types";

type Container =
  | {
      type: "root";
      key: string;
      sourceKey: null;
      ownerStepId: null;
      title: string;
      subtitle: string;
      crumbLabel: string;
      items: WorkspaceStep[];
    }
  | {
      type: "branches" | "chain";
      key: string;
      sourceKey: string;
      ownerStepId: number;
      title: string;
      subtitle: string;
      crumbLabel: string;
      items: Array<WorkspaceStep | WorkspaceBranchSlot>;
    };

type WorkspaceItem = WorkspaceStep | WorkspaceBranchSlot;
type SingleOption = { value: string; label: string };

const rootElement = document.getElementById("react-scenario-workspace-v2-root");
const FALLBACK_RESPONSE_TYPE_LABELS: Record<string, string> = {
  none: "Без ответа",
  text: "Текстовый ответ",
  file: "Загрузка файла",
  branching: "Ветвление",
  launch_scenario: "Переход к сценарию",
  chain: "Цепочка шагов",
};

function itemKey(item: WorkspaceItem | null | undefined) {
  return item?.id ? String(item.id) : "";
}

function makeRootContainer(workspace: WorkspaceData): Container {
  return {
    type: "root",
    key: `scenario-${workspace.scenario.id}`,
    sourceKey: null,
    ownerStepId: null,
    title: workspace.scenario.title,
    subtitle: "Основной поток",
    crumbLabel: workspace.scenario.title,
    items: workspace.root_steps,
  };
}

function buildChildContainer(item: WorkspaceItem | null): Container | null {
  if (!item) return null;

  if (item.kind === "branch_slot") {
    if (item.step?.response_type === "branching" && item.step.branch_items.length) {
      return {
        type: "branches",
        key: `branches-${item.step.id}`,
        sourceKey: itemKey(item),
        ownerStepId: item.step.id,
        title: item.label,
        subtitle: "Вложенные ветки",
        crumbLabel: `Ветки: ${item.label}`,
        items: item.step.branch_items,
      };
    }
    if (item.step?.response_type === "chain") {
      return {
        type: "chain",
        key: `chain-${item.step.id}`,
        sourceKey: itemKey(item),
        ownerStepId: item.step.id,
        title: item.label,
        subtitle: "Цепочка ветки",
        crumbLabel: `Цепочка: ${item.label}`,
        items: item.step.chain_steps,
      };
    }
    return null;
  }

  if (item.response_type === "branching" && item.branch_items.length) {
    return {
      type: "branches",
      key: `branches-${item.id}`,
      sourceKey: itemKey(item),
      ownerStepId: item.id,
      title: item.title || "Шаг",
      subtitle: "Ветки по кнопкам",
      crumbLabel: `Ветки: ${item.title || "Шаг"}`,
      items: item.branch_items,
    };
  }

  if (item.response_type === "chain") {
    return {
      type: "chain",
      key: `chain-${item.id}`,
      sourceKey: itemKey(item),
      ownerStepId: item.id,
      title: item.title || "Шаг",
      subtitle: "Цепочка шагов",
      crumbLabel: `Цепочка: ${item.title || "Шаг"}`,
      items: item.chain_steps,
    };
  }

  return null;
}

function itemTitle(item: WorkspaceItem, index: number) {
  if (item.kind === "branch_slot") return item.label || `Ветка ${index + 1}`;
  return item.title || `Шаг ${index + 1}`;
}

function summarizeItem(item: WorkspaceItem) {
  if (item.kind === "branch_slot") {
    return item.has_step ? "Ветка создана и готова к настройке." : "Ветка ещё не создана.";
  }
  if (item.text_preview) return item.text_preview;
  if (item.response_type === "branching") return "Шаг разводит сценарий по отдельным веткам.";
  if (item.response_type === "chain") return "Шаг запускает линейную цепочку внутри ветки.";
  return "Содержимое шага пока не заполнено.";
}

function detailTargetFromItem(item: WorkspaceItem | null) {
  if (!item) return null;
  return item.kind === "branch_slot" ? item.step : item;
}

function supportsButtonOptions(responseType: string) {
  return responseType === "branching";
}

function supportsTargetField(responseType: string) {
  return responseType === "text" || responseType === "file";
}

function parseRecipientIds(value: string) {
  return value
    .split(",")
    .map((chunk) => chunk.trim())
    .filter(Boolean);
}

function openActionLabel(item: WorkspaceItem | null) {
  const container = buildChildContainer(item);
  if (!container) return "";
  return container.type === "branches" ? "Открыть ветки" : "Открыть цепочку";
}

function moveItemById<T extends { id: number }>(items: T[], sourceId: number, targetId: number) {
  const sourceIndex = items.findIndex((item) => item.id === sourceId);
  const targetIndex = items.findIndex((item) => item.id === targetId);
  if (sourceIndex === -1 || targetIndex === -1 || sourceIndex === targetIndex) return items;
  const next = items.slice();
  const [moved] = next.splice(sourceIndex, 1);
  next.splice(targetIndex, 0, moved);
  return next;
}

function rebuildWorkspaceState(
  workspace: WorkspaceData,
  previousStack: Container[],
  previousSelectedKey: string,
  preferredSelectedKey?: string,
) {
  const nextRoot = makeRootContainer(workspace);
  const nextStack: Container[] = [nextRoot];
  let current = nextRoot;

  for (const previous of previousStack.slice(1)) {
    if (!previous.sourceKey) break;
    const sourceItem = current.items.find((item) => itemKey(item) === previous.sourceKey) || null;
    const child = buildChildContainer(sourceItem);
    if (!child) break;
    nextStack.push(child);
    current = child;
  }

  const targetKey = preferredSelectedKey || previousSelectedKey;
  const nextSelectedKey = current.items.find((item) => itemKey(item) === targetKey)
    ? targetKey
    : itemKey(current.items[0]);

  return { stack: nextStack, selectedItemKey: nextSelectedKey };
}

function NotificationRecipientsPicker({
  employeeOptions,
  value,
  onChange,
}: {
  employeeOptions: WorkspaceData["employee_options"];
  value: string;
  onChange: (next: string) => void;
}) {
  const [open, setOpen] = React.useState(false);
  const [search, setSearch] = React.useState("");
  const selectedIds = React.useMemo(() => parseRecipientIds(value), [value]);

  const filteredEmployees = React.useMemo(() => {
    if (!search.trim()) return employeeOptions;
    const query = search.toLowerCase();
    return employeeOptions.filter((option) => option.label.toLowerCase().includes(query));
  }, [employeeOptions, search]);

  const toggleRecipient = (employeeId: string) => {
    const nextIds = selectedIds.includes(employeeId)
      ? selectedIds.filter((value) => value !== employeeId)
      : selectedIds.concat(employeeId);
    onChange(nextIds.join(","));
  };

  const summary =
    selectedIds.length === 0
      ? "Выбери сотрудников"
      : `${selectedIds.length} выбр.`;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="secondary" className="w-full justify-between">
          <span className="truncate">{summary}</span>
          <ChevronsUpDown className="size-4 opacity-60" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[360px] p-0" align="start">
        <div className="border-b border-[var(--color-border)] p-3">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-[var(--color-muted-foreground)]" />
            <Input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Найти сотрудника"
              className="pl-9"
            />
          </div>
        </div>
        <ScrollArea className="h-72">
          <div className="flex flex-col gap-1 p-2">
            {filteredEmployees.map((option) => {
              const checked = selectedIds.includes(String(option.id));
              return (
                <button
                  key={option.id}
                  type="button"
                  onClick={() => toggleRecipient(String(option.id))}
                  className="flex items-center justify-between gap-3 rounded-xl px-3 py-2 text-left hover:bg-black/5"
                >
                  <div className="min-w-0">
                    <div className="truncate text-sm font-medium">{option.label}</div>
                    <div className="text-xs text-[var(--color-muted-foreground)]">{option.kind === "candidates" ? "Кандидат" : "Сотрудник"}</div>
                  </div>
                  <div
                    className={`flex size-5 shrink-0 items-center justify-center rounded-md border ${checked ? "border-[var(--color-accent)] bg-[var(--color-accent)] text-white" : "border-[var(--color-border)] bg-white text-transparent"}`}
                  >
                    <Check className="size-3.5" />
                  </div>
                </button>
              );
            })}
          </div>
        </ScrollArea>
      </PopoverContent>
    </Popover>
  );
}

function SingleSelectPicker({
  options,
  value,
  onChange,
  placeholder,
}: {
  options: SingleOption[];
  value: string;
  onChange: (next: string) => void;
  placeholder: string;
}) {
  const [open, setOpen] = React.useState(false);
  const selected = options.find((option) => option.value === value);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="secondary" className="w-full justify-between">
          <span className="truncate text-left">{selected?.label || placeholder}</span>
          <ChevronsUpDown className="size-4 opacity-60" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="p-1.5" style={{ width: "var(--radix-popover-trigger-width)" }}>
        <div className="flex flex-col gap-1">
          {options.map((option) => {
            const checked = option.value === value;
            return (
              <button
                key={`${option.value || "__empty__"}-${option.label}`}
                type="button"
                onClick={() => {
                  onChange(option.value);
                  setOpen(false);
                }}
                className="flex items-center justify-between gap-3 rounded-[10px] px-3 py-2 text-left text-sm transition-all duration-200 hover:rounded-[16px] hover:bg-black/5"
              >
                <span className="min-w-0 flex-1 truncate">{option.label}</span>
                <div
                  className={`flex size-5 shrink-0 items-center justify-center rounded-md border ${
                    checked
                      ? "border-[var(--color-accent)] bg-[var(--color-accent)] text-white"
                      : "border-[var(--color-border)] bg-white text-transparent"
                  }`}
                >
                  <Check className="size-3.5" />
                </div>
              </button>
            );
          })}
        </div>
      </PopoverContent>
    </Popover>
  );
}

function crumbIcon(entry: Container) {
  if (entry.type === "root") return Route;
  if (entry.type === "branches") return Waypoints;
  return Split;
}

function App() {
  const apiUrl = rootElement?.getAttribute("data-api-url") || "/api/flows/workspace";
  const classicListUrl = rootElement?.getAttribute("data-classic-list-url") || "/flows";
  const initialScenarioId = Number(rootElement?.getAttribute("data-selected-scenario-id") || 0) || null;

  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState("");
  const [payload, setPayload] = React.useState<WorkspacePayload | null>(null);
  const [selectedScenarioId, setSelectedScenarioId] = React.useState<number | null>(initialScenarioId);
  const [search, setSearch] = React.useState("");
  const [stack, setStack] = React.useState<Container[]>([]);
  const [selectedItemKey, setSelectedItemKey] = React.useState("");
  const [form, setForm] = React.useState<null | {
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
  }>(null);
  const [saveState, setSaveState] = React.useState({ saving: false, message: "", error: false });
  const textRef = React.useRef<HTMLTextAreaElement | null>(null);
  const fileInputRef = React.useRef<HTMLInputElement | null>(null);
  const stackRef = React.useRef<Container[]>([]);
  const selectedKeyRef = React.useRef("");
  const [creatingScenario, setCreatingScenario] = React.useState(false);
  const [newScenarioTitle, setNewScenarioTitle] = React.useState("");
  const [selectedScenarioIds, setSelectedScenarioIds] = React.useState<number[]>([]);
  const [sidebarState, setSidebarState] = React.useState({ message: "", error: false });
  const [dragScenarioId, setDragScenarioId] = React.useState<number | null>(null);
  const [dragStepId, setDragStepId] = React.useState<number | null>(null);
  const [emojiOpen, setEmojiOpen] = React.useState(false);
  const [attachmentState, setAttachmentState] = React.useState({ uploading: false, message: "", error: false });

  const currentContainer = stack[stack.length - 1] || null;
  const currentItems = currentContainer?.items || [];
  const selectedItem = currentItems.find((item) => itemKey(item) === selectedItemKey) || currentItems[0] || null;
  const detailTarget = detailTargetFromItem(selectedItem);
  const openLabel = openActionLabel(selectedItem);
  const responseTypeOptions = React.useMemo(() => {
    const labels = payload?.workspace?.response_type_labels || FALLBACK_RESPONSE_TYPE_LABELS;
    return Object.entries(labels).filter(([value]) => {
      if (value === "buttons") return false;
      if (value === "chain") return detailTarget?.kind === "branch_step";
      return true;
    });
  }, [payload, detailTarget]);
  const responseTypePickerOptions = React.useMemo<SingleOption[]>(
    () => responseTypeOptions.map(([value, label]) => ({ value, label })),
    [responseTypeOptions],
  );
  const sendModeOptions = React.useMemo<SingleOption[]>(
    () => Object.entries(payload?.workspace?.send_mode_labels || {}).map(([value, label]) => ({ value, label })),
    [payload],
  );
  const targetFieldOptions = React.useMemo<SingleOption[]>(
    () => Object.entries(payload?.workspace?.target_field_labels || {}).map(([value, label]) => ({ value, label })),
    [payload],
  );
  const launchScenarioOptions = React.useMemo<SingleOption[]>(
    () => [
      { value: "", label: "Не выполнять переход" },
      ...((payload?.workspace?.available_scenarios || []).map((option) => ({ value: option.value, label: option.label })) as SingleOption[]),
    ],
    [payload],
  );
  const notificationScopeOptions = React.useMemo<SingleOption[]>(
    () =>
      Object.entries(payload?.workspace?.notification_recipient_scope_labels || { "": "Не добавлять адресатов из карточки" }).map(
        ([value, label]) => ({ value, label }),
      ),
    [payload],
  );

  React.useEffect(() => {
    stackRef.current = stack;
  }, [stack]);

  React.useEffect(() => {
    selectedKeyRef.current = selectedItemKey;
  }, [selectedItemKey]);

  const insertIntoText = React.useCallback((snippet: string) => {
    setForm((prev) => {
      if (!prev) return prev;
      const textarea = textRef.current;
      if (!textarea) {
        return { ...prev, text: `${prev.text || ""}${snippet}` };
      }
      const start = textarea.selectionStart ?? prev.text.length;
      const end = textarea.selectionEnd ?? prev.text.length;
      const nextText = `${prev.text.slice(0, start)}${snippet}${prev.text.slice(end)}`;
      requestAnimationFrame(() => {
        textarea.focus();
        const nextCursor = start + snippet.length;
        textarea.setSelectionRange(nextCursor, nextCursor);
      });
      return { ...prev, text: nextText };
    });
  }, []);

  const applyPayload = React.useCallback(
    (nextPayload: WorkspacePayload, preferredSelectedKey?: string) => {
      setPayload(nextPayload);
      setSelectedScenarioId(nextPayload.selected_scenario_id ?? null);
      if (nextPayload.workspace) {
        const restored = rebuildWorkspaceState(
          nextPayload.workspace,
          stackRef.current,
          selectedKeyRef.current,
          preferredSelectedKey,
        );
        setStack(restored.stack);
        setSelectedItemKey(restored.selectedItemKey);
      } else {
        setStack([]);
        setSelectedItemKey("");
      }
    },
    [],
  );

  React.useEffect(() => {
    const url = selectedScenarioId ? `${apiUrl}?scenario_id=${selectedScenarioId}` : apiUrl;
    setLoading(true);
    setError("");

    fetch(url, { credentials: "same-origin", headers: { Accept: "application/json" } })
      .then((response) => {
        if (!response.ok) throw new Error("Не удалось загрузить новый workspace сценариев");
        return response.json() as Promise<WorkspacePayload>;
      })
      .then((nextPayload) => {
        if (nextPayload.workspace && selectedScenarioId === nextPayload.selected_scenario_id && stackRef.current.length) {
          applyPayload(nextPayload);
        } else if (nextPayload.workspace) {
          setPayload(nextPayload);
          setSelectedScenarioId(nextPayload.selected_scenario_id ?? null);
          const root = makeRootContainer(nextPayload.workspace);
          setStack([root]);
          setSelectedItemKey(itemKey(root.items[0]));
        } else {
          setPayload(nextPayload);
          setSelectedScenarioId(nextPayload.selected_scenario_id ?? null);
          setStack([]);
          setSelectedItemKey("");
        }
      })
      .catch((loadError) => {
        setError(loadError.message || "Не удалось загрузить новый workspace сценариев");
      })
      .finally(() => {
        setLoading(false);
      });
  }, [apiUrl, selectedScenarioId]);

  const scenarios = React.useMemo(() => {
    const items = payload?.scenarios || [];
    if (!search.trim()) return items;
    const query = search.toLowerCase();
    return items.filter((scenario) => `${scenario.title} ${scenario.description}`.toLowerCase().includes(query));
  }, [payload, search]);

  React.useEffect(() => {
    const availableIds = new Set((payload?.scenarios || []).map((scenario) => scenario.id));
    setSelectedScenarioIds((prev) => prev.filter((id) => availableIds.has(id)));
  }, [payload]);

  React.useEffect(() => {
    if (!detailTarget) {
      setForm(null);
      setAttachmentState({ uploading: false, message: "", error: false });
      return;
    }
    setForm({
      title: detailTarget.title || "",
      text: detailTarget.text || "",
      response_type: detailTarget.response_type === "buttons" ? "branching" : detailTarget.response_type || "none",
      button_options: detailTarget.button_options.join("\n"),
      send_mode: detailTarget.send_mode || "immediate",
      send_time: detailTarget.send_time || "",
      target_field: detailTarget.target_field || "",
      launch_scenario_key: detailTarget.launch_scenario_key || "",
      send_employee_card: Boolean(detailTarget.send_employee_card),
      notify_on_send_text: detailTarget.notify_on_send_text || "",
      notify_on_send_recipient_ids: detailTarget.notify_on_send_recipient_ids || "",
      notify_on_send_recipient_scope: detailTarget.notify_on_send_recipient_scope || "",
    });
    setSaveState({ saving: false, message: "", error: false });
    setAttachmentState({ uploading: false, message: "", error: false });
  }, [detailTarget, selectedItemKey, selectedScenarioId]);

  const handleSave = () => {
    if (!detailTarget || !form) return;
    setSaveState({ saving: true, message: "", error: false });
    fetch(`/api/flows/workspace/steps/${detailTarget.id}`, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({
        title: form.title,
        text: form.text,
        response_type: form.response_type,
        button_options: form.button_options,
        send_mode: form.send_mode,
        send_time: form.send_time,
        target_field: supportsTargetField(form.response_type) ? form.target_field : "",
        launch_scenario_key: form.launch_scenario_key,
        send_employee_card: form.send_employee_card,
        notify_on_send_text: form.notify_on_send_text,
        notify_on_send_recipient_ids: form.notify_on_send_recipient_ids,
        notify_on_send_recipient_scope: form.notify_on_send_recipient_scope,
      }),
    })
      .then(async (response) => {
        if (!response.ok) {
          const payload = await response.json().catch(() => ({}));
          throw new Error(payload.detail || "Не удалось сохранить шаг");
        }
        return response.json();
      })
      .then((result: { message?: string; payload: WorkspacePayload }) => {
        applyPayload(result.payload, itemKey(selectedItem));
        setSaveState({ saving: false, message: result.message || "Шаг сохранён", error: false });
      })
      .catch((saveError: Error) => {
        setSaveState({ saving: false, message: saveError.message || "Не удалось сохранить шаг", error: true });
      });
  };

  const handleCreateScenario = () => {
    const title = newScenarioTitle.trim() || "Новый сценарий";
    setSidebarState({ message: "", error: false });
    fetch("/api/flows/workspace/scenarios", {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ title, description: "" }),
    })
      .then(async (response) => {
        if (!response.ok) {
          const payload = await response.json().catch(() => ({}));
          throw new Error(payload.detail || "Не удалось создать сценарий");
        }
        return response.json();
      })
      .then((result: { payload: WorkspacePayload; scenario_id?: number }) => {
        setSidebarState({ message: "Сценарий создан", error: false });
        setSearch("");
        setCreatingScenario(false);
        setNewScenarioTitle("");
        applyPayload(result.payload);
      })
      .catch((createError: Error) => {
        setSidebarState({ message: createError.message || "Не удалось создать сценарий", error: true });
      });
  };

  const handleAddRootStep = () => {
    if (!payload?.workspace?.scenario?.id) return;
    fetch(`/api/flows/workspace/scenarios/${payload.workspace.scenario.id}/steps`, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ title: "Новый шаг" }),
    })
      .then(async (response) => {
        if (!response.ok) {
          const payload = await response.json().catch(() => ({}));
          throw new Error(payload.detail || "Не удалось добавить шаг");
        }
        return response.json();
      })
      .then((result: { payload: WorkspacePayload; step_id?: number }) => {
        applyPayload(result.payload, result.step_id ? String(result.step_id) : undefined);
      })
      .catch((stepError: Error) => {
        setSaveState({ saving: false, message: stepError.message || "Не удалось добавить шаг", error: true });
      });
  };

  const handleAddChainStep = () => {
    if (currentContainer?.type !== "chain") return;
    fetch(`/api/flows/workspace/steps/${currentContainer.ownerStepId}/chain`, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ title: "Шаг цепочки" }),
    })
      .then(async (response) => {
        if (!response.ok) {
          const payload = await response.json().catch(() => ({}));
          throw new Error(payload.detail || "Не удалось добавить шаг цепочки");
        }
        return response.json();
      })
      .then((result: { payload: WorkspacePayload; step_id?: number }) => {
        applyPayload(result.payload, result.step_id ? String(result.step_id) : undefined);
      })
      .catch((stepError: Error) => {
        setSaveState({ saving: false, message: stepError.message || "Не удалось добавить шаг цепочки", error: true });
      });
  };

  const handleCreateBranch = () => {
    if (currentContainer?.type !== "branches" || selectedItem?.kind !== "branch_slot") return;
    fetch(`/api/flows/workspace/steps/${currentContainer.ownerStepId}/branches`, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ option_index: selectedItem.option_index }),
    })
      .then(async (response) => {
        if (!response.ok) {
          const payload = await response.json().catch(() => ({}));
          throw new Error(payload.detail || "Не удалось создать ветку");
        }
        return response.json();
      })
      .then((result: { payload: WorkspacePayload }) => {
        applyPayload(result.payload, itemKey(selectedItem));
        setSaveState({ saving: false, message: "Ветка создана", error: false });
      })
      .catch((branchError: Error) => {
        setSaveState({ saving: false, message: branchError.message || "Не удалось создать ветку", error: true });
      });
  };

  const handleDeleteCurrent = () => {
    if (!detailTarget) return;
    if (!window.confirm("Удалить выбранный элемент?")) return;
    fetch(`/api/flows/workspace/steps/${detailTarget.id}/delete`, {
      method: "POST",
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    })
      .then(async (response) => {
        if (!response.ok) {
          const payload = await response.json().catch(() => ({}));
          throw new Error(payload.detail || "Не удалось удалить элемент");
        }
        return response.json();
      })
      .then((result: { payload: WorkspacePayload }) => {
        applyPayload(result.payload);
        setSaveState({ saving: false, message: "Элемент удалён", error: false });
      })
      .catch((deleteError: Error) => {
        setSaveState({ saving: false, message: deleteError.message || "Не удалось удалить элемент", error: true });
      });
  };

  const handleAttachmentSelected = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file || !detailTarget) return;
    const formData = new FormData();
    formData.append("upload", file);
    setAttachmentState({ uploading: true, message: "", error: false });
    try {
      const response = await fetch(`/api/flows/workspace/steps/${detailTarget.id}/attachment`, {
        method: "POST",
        credentials: "same-origin",
        body: formData,
        headers: {
          Accept: "application/json",
        },
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || "Не удалось загрузить вложение");
      }
      const result = (await response.json()) as { payload: WorkspacePayload; step_id?: number; message?: string };
      applyPayload(result.payload, result.step_id ? String(result.step_id) : String(detailTarget.id));
      setAttachmentState({ uploading: false, message: result.message || "Вложение добавлено", error: false });
    } catch (attachmentError) {
      const message = attachmentError instanceof Error ? attachmentError.message : "Не удалось загрузить вложение";
      setAttachmentState({ uploading: false, message, error: true });
    } finally {
      if (event.target) {
        event.target.value = "";
      }
    }
  };

  const handleDeleteAttachment = async () => {
    if (!detailTarget || !detailTarget.has_attachment) return;
    if (!window.confirm("Удалить вложение у этого шага?")) return;
    setAttachmentState({ uploading: true, message: "", error: false });
    try {
      const response = await fetch(`/api/flows/workspace/steps/${detailTarget.id}/attachment/delete`, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          Accept: "application/json",
        },
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || "Не удалось удалить вложение");
      }
      const result = (await response.json()) as { payload: WorkspacePayload; step_id?: number; message?: string };
      applyPayload(result.payload, result.step_id ? String(result.step_id) : String(detailTarget.id));
      setAttachmentState({ uploading: false, message: result.message || "Вложение удалено", error: false });
    } catch (attachmentError) {
      const message = attachmentError instanceof Error ? attachmentError.message : "Не удалось удалить вложение";
      setAttachmentState({ uploading: false, message, error: true });
    }
  };

  const toggleScenarioSelection = (scenarioId: number) => {
    setSelectedScenarioIds((prev) => (prev.includes(scenarioId) ? prev.filter((id) => id !== scenarioId) : prev.concat(scenarioId)));
  };

  const toggleSelectAllVisibleScenarios = () => {
    const visibleIds = scenarios.map((scenario) => scenario.id);
    const allSelected = visibleIds.length > 0 && visibleIds.every((id) => selectedScenarioIds.includes(id));
    setSelectedScenarioIds((prev) => {
      if (allSelected) {
        return prev.filter((id) => !visibleIds.includes(id));
      }
      const next = new Set(prev);
      visibleIds.forEach((id) => next.add(id));
      return Array.from(next);
    });
  };

  const handleBulkScenarioAction = (action: "bulk-copy" | "bulk-delete") => {
    if (!selectedScenarioIds.length) return;
    if (action === "bulk-delete" && !window.confirm(`Удалить выбранные сценарии: ${selectedScenarioIds.length}?`)) {
      return;
    }
    fetch(`/api/flows/workspace/scenarios/${action}`, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ scenario_ids: selectedScenarioIds }),
    })
      .then(async (response) => {
        if (!response.ok) {
          const payload = await response.json().catch(() => ({}));
          throw new Error(payload.detail || "Не удалось выполнить массовое действие");
        }
        return response.json();
      })
      .then((result: { message?: string; payload: WorkspacePayload }) => {
        setSelectedScenarioIds([]);
        setSidebarState({ message: result.message || "Готово", error: false });
        applyPayload(result.payload);
      })
      .catch((actionError: Error) => {
        setSidebarState({ message: actionError.message || "Не удалось выполнить массовое действие", error: true });
      });
  };

  const persistScenarioOrder = (scenarioIds: number[]) => {
    fetch("/api/flows/workspace/scenarios/reorder", {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ scenario_ids: scenarioIds }),
    })
      .then(async (response) => {
        if (!response.ok) {
          const payload = await response.json().catch(() => ({}));
          throw new Error(payload.detail || "Не удалось сохранить порядок сценариев");
        }
        return response.json();
      })
      .then((result: { payload: WorkspacePayload; message?: string }) => {
        setSidebarState({ message: result.message || "Порядок сценариев обновлён", error: false });
        applyPayload(result.payload);
      })
      .catch((reorderError: Error) => {
        setSidebarState({ message: reorderError.message || "Не удалось сохранить порядок сценариев", error: true });
      });
  };

  const handleScenarioDrop = (targetScenarioId: number) => {
    if (!payload || dragScenarioId === null || dragScenarioId === targetScenarioId) return;
    const reorderedScenarios = moveItemById(payload.scenarios, dragScenarioId, targetScenarioId);
    setPayload({ ...payload, scenarios: reorderedScenarios });
    setDragScenarioId(null);
    persistScenarioOrder(reorderedScenarios.map((scenario) => scenario.id));
  };

  const persistRootStepOrder = (stepIds: number[]) => {
    if (!payload?.workspace?.scenario?.id) return;
    fetch(`/api/flows/workspace/scenarios/${payload.workspace.scenario.id}/steps/reorder`, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ step_ids: stepIds }),
    })
      .then(async (response) => {
        if (!response.ok) {
          const payload = await response.json().catch(() => ({}));
          throw new Error(payload.detail || "Не удалось сохранить порядок шагов");
        }
        return response.json();
      })
      .then((result: { payload: WorkspacePayload; message?: string }) => {
        setSaveState({ saving: false, message: result.message || "Порядок шагов обновлён", error: false });
        applyPayload(result.payload, selectedKeyRef.current);
      })
      .catch((reorderError: Error) => {
        setSaveState({ saving: false, message: reorderError.message || "Не удалось сохранить порядок шагов", error: true });
      });
  };

  const handleRootStepDrop = (targetStepId: number) => {
    if (currentContainer?.type !== "root" || dragStepId === null || dragStepId === targetStepId) return;
    const rootItems = currentContainer.items as WorkspaceStep[];
    const reorderedItems = moveItemById(rootItems, dragStepId, targetStepId);
    setStack((prev) => prev.map((entry, index) => (index === prev.length - 1 ? { ...entry, items: reorderedItems } as Container : entry)));
    setDragStepId(null);
    persistRootStepOrder(reorderedItems.map((item) => item.id));
  };

  if (loading && !payload) {
    return <div className="rounded-[28px] border border-[var(--color-border)] bg-[var(--color-panel)] p-8 shadow-[var(--shadow-soft)]">Собираю новый workspace…</div>;
  }

  if (error) {
    return (
      <div className="rounded-[28px] border border-[var(--color-border)] bg-[var(--color-panel)] p-8 shadow-[var(--shadow-soft)]">
        <p className="text-sm text-[var(--color-danger)]">{error}</p>
        <div className="mt-4">
          <a className="inline-flex rounded-xl border border-[var(--color-border)] px-4 py-2 text-sm font-semibold" href={classicListUrl}>
            Открыть классический список
          </a>
        </div>
      </div>
    );
  }

  return (
    <div
      className="relative overflow-hidden"
      style={{ height: "calc(100vh - 185px)", minHeight: "720px" }}
    >
      {loading ? (
        <div className="pointer-events-none absolute inset-x-0 top-0 z-10 flex justify-center">
          <div className="rounded-full border border-[var(--color-border)] bg-[var(--color-panel)]/95 px-4 py-2 text-sm font-medium text-[var(--color-muted-foreground)] shadow-sm backdrop-blur">
            Обновляю workspace…
          </div>
        </div>
      ) : null}
      <div
        className={`h-full gap-4 transition-opacity ${loading ? "opacity-80" : "opacity-100"}`}
        style={{ display: "grid", gridTemplateColumns: "392px minmax(0, 1fr) 488px" }}
      >
      <section className="flex min-h-0 flex-col overflow-hidden rounded-[10px] border border-[var(--color-border)] bg-[var(--color-panel)] p-4">
        <div className="mb-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--color-muted-foreground)]">Workspace V2</p>
            <h3 className="mt-1 text-[1.65rem] font-semibold">Сценарии</h3>
          </div>
        </div>
        {creatingScenario ? (
          <div className="mb-3 rounded-[10px] border border-[var(--color-border)] bg-[var(--color-panel-muted)] p-2">
            <div className="flex items-center gap-2">
              <Input
                value={newScenarioTitle}
                onChange={(event) => setNewScenarioTitle(event.target.value)}
                placeholder="Название сценария"
                className="h-10 text-sm"
              />
              <Button size="sm" onClick={handleCreateScenario} className="px-3">
                Готово
              </Button>
              <Button
                size="sm"
                variant="ghost"
                className="w-8 p-0"
                onClick={() => {
                  setCreatingScenario(false);
                  setNewScenarioTitle("");
                }}
              >
                <X className="size-4" />
              </Button>
            </div>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => setCreatingScenario(true)}
            className="mb-3 flex h-11 w-full items-center justify-center gap-2 rounded-[10px] border border-dashed border-[var(--color-border)] bg-[var(--color-panel-muted)] text-sm font-semibold transition-all duration-200 hover:rounded-[20px] hover:bg-white"
          >
            <Plus className="size-4" />
            Создать сценарий
          </button>
        )}
        <Input placeholder="Найти сценарий" value={search} onChange={(e) => setSearch(e.target.value)} className="text-sm" />
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <label className="inline-flex items-center gap-2 rounded-[10px] border border-[var(--color-border)] px-3 py-2 text-xs font-semibold text-[var(--color-muted-foreground)] transition-all duration-200 hover:rounded-[18px]">
            <input
              type="checkbox"
              checked={scenarios.length > 0 && scenarios.every((scenario) => selectedScenarioIds.includes(scenario.id))}
              onChange={toggleSelectAllVisibleScenarios}
            />
            Выбрать все
          </label>
          <Button size="sm" variant="secondary" className="w-9 p-0" title="Копировать выбранные" onClick={() => handleBulkScenarioAction("bulk-copy")} disabled={!selectedScenarioIds.length}>
            <Copy className="size-4" />
          </Button>
          <Button size="sm" variant="secondary" className="w-9 p-0 text-red-600 hover:bg-red-50 hover:text-red-700" title="Удалить выбранные" onClick={() => handleBulkScenarioAction("bulk-delete")} disabled={!selectedScenarioIds.length}>
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
            {scenarios.map((scenario: ScenarioSummary) => (
              <button
                key={scenario.id}
                type="button"
                onClick={() => setSelectedScenarioId(scenario.id)}
                draggable
                onDragStart={() => setDragScenarioId(scenario.id)}
                onDragOver={(event) => event.preventDefault()}
                onDrop={() => handleScenarioDrop(scenario.id)}
                onDragEnd={() => setDragScenarioId(null)}
                className={`flex w-full min-w-0 flex-col gap-2 rounded-[10px] border p-3 text-left transition-all duration-200 hover:rounded-[20px] ${scenario.id === selectedScenarioId ? "border-[color:var(--color-accent)] bg-[var(--color-panel-muted)] shadow-sm" : "border-[var(--color-border)] bg-white hover:bg-[var(--color-panel-muted)]"}`}
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
                      onChange={() => toggleScenarioSelection(scenario.id)}
                    />
                    <span className="text-[0.95rem] font-semibold">{scenario.title}</span>
                  </label>
                  <FileStack className="size-4 text-[var(--color-muted-foreground)]" />
                </div>
                <p className="text-[0.83rem] leading-5 text-[var(--color-muted-foreground)]">{scenario.description || "Без описания"}</p>
                <div className="flex flex-wrap gap-2 text-[0.72rem] font-medium text-[var(--color-muted-foreground)]">
                  <span className="rounded-[10px] bg-black/5 px-2 py-1 transition-all duration-200 hover:rounded-[16px]">{scenario.role_scope_label}</span>
                  <span className="rounded-[10px] bg-black/5 px-2 py-1 transition-all duration-200 hover:rounded-[16px]">{scenario.trigger_mode_label}</span>
                </div>
              </button>
            ))}
          </div>
        </ScrollArea>
      </section>

      <section className="flex min-h-0 flex-col overflow-hidden rounded-[10px] border border-[var(--color-border)] bg-[var(--color-panel)] p-4">
        <div className="mb-3 flex flex-wrap items-center gap-2 text-sm text-[var(--color-muted-foreground)]">
          {stack.map((entry, index) => (
            <React.Fragment key={entry.key}>
              {index > 0 ? <ChevronRight className="size-4 shrink-0" /> : null}
              <button
                type="button"
                className="inline-flex max-w-full items-center gap-2 rounded-[10px] bg-black/5 px-3 py-1.5 text-left font-medium whitespace-normal break-words transition-all duration-200 hover:rounded-[18px] hover:bg-black/8"
                onClick={() => {
                  const next = stack.slice(0, index + 1);
                  setStack(next);
                  setSelectedItemKey(itemKey(next[next.length - 1]?.items?.[0]));
                }}
              >
                {React.createElement(crumbIcon(entry), { className: "size-4 shrink-0" })}
                {entry.crumbLabel}
              </button>
            </React.Fragment>
          ))}
        </div>

        <div className="mb-4 flex items-center justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--color-muted-foreground)]">
              {currentContainer?.subtitle || "Сценарий"}
            </p>
            <h3 className="mt-1 text-[1.55rem] font-semibold">{currentContainer?.title || payload?.workspace?.scenario.title}</h3>
          </div>
          {currentContainer?.type === "root" ? (
            <Button variant="secondary" size="sm" onClick={handleAddRootStep}>
              <Plus className="size-4" />
              Добавить шаг
            </Button>
          ) : currentContainer?.type === "chain" ? (
            <Button variant="secondary" size="sm" onClick={handleAddChainStep}>
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
                  onClick={() => setSelectedItemKey(itemKey(item))}
                  draggable={currentContainer?.type === "root" && item.kind !== "branch_slot"}
                  onDragStart={() => {
                    if (currentContainer?.type === "root" && item.kind !== "branch_slot") {
                      setDragStepId(Number(itemKey(item)));
                    }
                  }}
                  onDragOver={(event) => {
                    if (currentContainer?.type === "root") {
                      event.preventDefault();
                    }
                  }}
                  onDrop={() => {
                    if (currentContainer?.type === "root" && item.kind !== "branch_slot") {
                      handleRootStepDrop(item.id);
                    }
                  }}
                  onDragEnd={() => setDragStepId(null)}
                  className={`flex w-full min-w-0 cursor-pointer flex-col gap-2 rounded-[10px] border p-3 transition-all duration-200 hover:rounded-[20px] ${active ? "border-[color:var(--color-accent)] bg-[var(--color-panel-muted)] shadow-sm" : "border-[var(--color-border)] bg-white hover:bg-[var(--color-panel-muted)]"}`}
                >
                  <div className="space-y-1">
                    <h4 className="text-[0.95rem] font-semibold">{itemTitle(item, index)}</h4>
                    <p className="text-[0.83rem] leading-5 text-[var(--color-muted-foreground)]">{summarizeItem(item)}</p>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex flex-wrap gap-2 text-[0.72rem] font-medium text-[var(--color-muted-foreground)]">
                      <span className="rounded-[10px] bg-black/5 px-2 py-1 transition-all duration-200 hover:rounded-[16px]">{item.kind === "branch_slot" ? "Ветка" : item.response_label}</span>
                      {"button_options" in item && item.button_options.length ? (
                        <span className="rounded-[10px] bg-black/5 px-2 py-1 transition-all duration-200 hover:rounded-[16px]">Кнопки: {item.button_options.length}</span>
                      ) : null}
                    </div>
                    {canOpen ? (
                      <Button variant="ghost" size="sm" onClick={(event) => {
                        event.stopPropagation();
                        const nextContainer = buildChildContainer(item);
                        if (!nextContainer) return;
                        setStack((prev) => prev.concat(nextContainer));
                        setSelectedItemKey(itemKey(nextContainer.items[0]));
                      }}>
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

      <section
        className="flex min-h-0 flex-col overflow-hidden rounded-[10px] border border-[var(--color-border)] bg-[var(--color-panel)] p-4"
        style={{ position: "sticky", top: 0, alignSelf: "stretch" }}
      >
        <div className="mb-3">
          <p className="text-[1rem] font-medium text-[var(--color-foreground)]/85">Детали</p>
        </div>
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
                    <Button onClick={handleCreateBranch}>
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
                    onChange={(event) => setForm((prev) => (prev ? { ...prev, title: event.target.value } : prev))}
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
                      onChange={(event) => setForm((prev) => (prev ? { ...prev, text: event.target.value } : prev))}
                    />
                    <Popover open={emojiOpen} onOpenChange={setEmojiOpen}>
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
                            insertIntoText(emojiData.emoji);
                            setEmojiOpen(false);
                          }}
                        />
                      </PopoverContent>
                    </Popover>
                  </div>
                </label>

                <div className="flex flex-wrap items-center gap-2 text-[0.72rem]">
                  <span className="text-[var(--color-muted-foreground)]">Теги:</span>
                  <button type="button" onClick={() => insertIntoText("{name}")} className="rounded-[10px] border border-[var(--color-border)] px-2.5 py-1.5 font-semibold text-[var(--color-foreground)]/80 transition-all duration-200 hover:rounded-[16px] hover:bg-[var(--color-panel-muted)]">{`{name}`}</button>
                  <button type="button" onClick={() => insertIntoText("{full_name}")} className="rounded-[10px] border border-[var(--color-border)] px-2.5 py-1.5 font-semibold text-[var(--color-foreground)]/80 transition-all duration-200 hover:rounded-[16px] hover:bg-[var(--color-panel-muted)]">{`{full_name}`}</button>
                  <button type="button" onClick={() => insertIntoText("{doc:Оффер}")} className="rounded-[10px] border border-[var(--color-border)] px-2.5 py-1.5 font-semibold text-[var(--color-foreground)]/80 transition-all duration-200 hover:rounded-[16px] hover:bg-[var(--color-panel-muted)]">{`{doc:Оффер}`}</button>
                </div>

                <div className="space-y-2">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-sm font-semibold text-[var(--color-foreground)]/75">Вложение</span>
                    <input ref={fileInputRef} type="file" className="hidden" onChange={handleAttachmentSelected} />
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
                      <Button type="button" variant="ghost" size="sm" onClick={handleDeleteAttachment} disabled={attachmentState.uploading}>
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
                      setForm((prev) =>
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
                      onChange={(event) => setForm((prev) => (prev ? { ...prev, button_options: event.target.value } : prev))}
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
                      setForm((prev) =>
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
                      onChange={(event) => setForm((prev) => (prev ? { ...prev, send_time: event.target.value } : prev))}
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
                    onChange={(nextValue) => setForm((prev) => (prev ? { ...prev, target_field: nextValue } : prev))}
                  />
                </label>

                <label style={{ display: "grid", gap: "0.5rem" }}>
                  <span className="text-sm font-semibold text-[var(--color-foreground)]/75">Переход к сценарию</span>
                  <SingleSelectPicker
                    options={launchScenarioOptions}
                    value={form?.launch_scenario_key || ""}
                    placeholder="Не выполнять переход"
                    onChange={(nextValue) => setForm((prev) => (prev ? { ...prev, launch_scenario_key: nextValue } : prev))}
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
                        onChange={(event) => setForm((prev) => (prev ? { ...prev, notify_on_send_text: event.target.value } : prev))}
                        placeholder="Например: Пользователю отправлено сообщение этого шага."
                      />
                    </label>
                    <div className="space-y-2">
                      <span className="text-sm font-semibold text-[var(--color-foreground)]/75">Получатели уведомления</span>
                      <NotificationRecipientsPicker
                        employeeOptions={payload?.workspace?.employee_options || []}
                        value={form?.notify_on_send_recipient_ids || ""}
                        onChange={(next) => setForm((prev) => (prev ? { ...prev, notify_on_send_recipient_ids: next } : prev))}
                      />
                    </div>
                    <label className="block space-y-2">
                      <span className="text-sm font-semibold text-[var(--color-foreground)]/75">Адресаты из карточки сотрудника</span>
                      <SingleSelectPicker
                        options={notificationScopeOptions}
                        value={form?.notify_on_send_recipient_scope || ""}
                        placeholder="Не добавлять адресатов из карточки"
                        onChange={(nextValue) => setForm((prev) => (prev ? { ...prev, notify_on_send_recipient_scope: nextValue } : prev))}
                      />
                    </label>
                  </div>
                </details>

                <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                  <p className={`text-sm ${saveState.error ? "text-[var(--color-danger)]" : "text-[var(--color-muted-foreground)]"}`}>{saveState.message || " "}</p>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <Button variant="outline" className="border-red-200 text-red-600 hover:bg-red-50 hover:text-red-700" onClick={handleDeleteCurrent}>
                      <Trash2 className="size-4" />
                      Удалить
                    </Button>
                    {openLabel ? (
                      <Button
                        variant="outline"
                        onClick={() => {
                          const nextContainer = buildChildContainer(selectedItem);
                          if (!nextContainer) return;
                          setStack((prev) => prev.concat(nextContainer));
                          setSelectedItemKey(itemKey(nextContainer.items[0]));
                        }}
                      >
                        {openLabel}
                      </Button>
                    ) : null}
                    <Button onClick={handleSave} disabled={saveState.saving} className="px-6">
                      {saveState.saving ? "Сохраняю..." : "Сохранить"}
                    </Button>
                  </div>
                </div>
              </div>
              )
            ) : (
              <div className="rounded-2xl border border-dashed border-[var(--color-border)] p-4 text-sm text-[var(--color-muted-foreground)]">
                Выбери шаг, ветку или элемент цепочки, чтобы увидеть детали справа.
              </div>
            )}
          </div>
        </ScrollArea>
      </section>
      </div>
    </div>
  );
}

if (rootElement) {
  ReactDOM.createRoot(rootElement).render(<App />);
}
