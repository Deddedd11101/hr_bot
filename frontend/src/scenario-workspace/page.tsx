import React from "react";
import { X } from "lucide-react";

import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  buildChildContainer,
  detailTargetFromItem,
  FALLBACK_RESPONSE_TYPE_LABELS,
  itemKey,
  makeRootContainer,
  moveItemById,
  openActionLabel,
  payloadLabel,
  rebuildWorkspaceState,
  supportsButtonOptions,
  supportsTargetField,
} from "./model";
import {
  WorkspaceCanvasSection,
  WorkspaceDetailSection,
  WorkspaceFlashNotice,
  WorkspaceSidebarSection,
  WorkspaceStepDetailPane,
} from "./sections";
import type {
  Container,
  ScenarioSettingsForm,
  SingleOption,
  WorkspaceButtonNotification,
  WorkspacePayload,
  WorkspaceRootStepOption,
  WorkspaceStepSendNotificationRule,
} from "./types";

const rootElement = document.getElementById("react-scenario-workspace-v2-root");

export function ScenarioWorkspacePage() {
  const apiUrl = rootElement?.getAttribute("data-api-url") || "/api/flows/workspace";
  const initialScenarioId = Number(rootElement?.getAttribute("data-selected-scenario-id") || 0) || null;
  const workspaceKind = rootElement?.getAttribute("data-workspace-kind") === "survey" ? "survey" : "scenario";
  const initialFlashMessage = rootElement?.getAttribute("data-flash-message") || "";
  const initialFlashType = rootElement?.getAttribute("data-flash-type") || "success";
  const isSurveyWorkspace = workspaceKind === "survey";
  const itemLabel = payloadLabel(workspaceKind);
  const sidebarTitle = isSurveyWorkspace ? "Опросы" : "Сценарии";
  const stepTitle = isSurveyWorkspace ? "Вопросы" : "Шаги сценария";
  const createItemLabel = isSurveyWorkspace ? "Создать" : "Создать сценарий";
  const itemNamePlaceholder = isSurveyWorkspace ? "Название опроса" : "Название сценария";
  const newItemTitle = isSurveyWorkspace ? "Новый опрос" : "Новый сценарий";
  const newStepTitle = isSurveyWorkspace ? "Новый вопрос" : "Новый шаг";
  const stepLabel = isSurveyWorkspace ? "вопрос" : "шаг";

  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState("");
  const [payload, setPayload] = React.useState<WorkspacePayload | null>(null);
  const [selectedScenarioId, setSelectedScenarioId] = React.useState<number | null>(initialScenarioId);
  const [search, setSearch] = React.useState("");
  const [audienceFilter, setAudienceFilter] = React.useState<"all" | "employees" | "candidates">("all");
  const [sortMode, setSortMode] = React.useState<"updated_desc" | "created_desc" | "created_asc" | "title_asc">("updated_desc");
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
    return_to_step_key: string;
    send_employee_card: boolean;
    notify_on_send_text: string;
    notify_on_send_recipient_ids: string;
    notify_on_send_recipient_scope: string;
    step_send_notifications: WorkspaceStepSendNotificationRule[];
    button_notifications: WorkspaceButtonNotification[];
  }>(null);
  const [saveState, setSaveState] = React.useState({ saving: false, message: "", error: false });
  const [scenarioSettingsForm, setScenarioSettingsForm] = React.useState<ScenarioSettingsForm | null>(null);
  const [scenarioSettingsState, setScenarioSettingsState] = React.useState({ saving: false, message: "", error: false });
  const [scenarioSettingsOpen, setScenarioSettingsOpen] = React.useState(false);
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
  const [attachmentState, setAttachmentState] = React.useState({ uploading: false, message: "", error: false });
  const [flashState, setFlashState] = React.useState({ message: initialFlashMessage, error: initialFlashType === "error" });
  const exportUrl =
    isSurveyWorkspace && payload?.workspace?.scenario?.id ? `/surveys/${payload.workspace.scenario.id}/export` : "";

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
  const roleScopeOptions = React.useMemo<SingleOption[]>(
    () => Object.entries(payload?.workspace?.role_scope_labels || {}).map(([value, label]) => ({ value, label })),
    [payload],
  );
  const employeeScopeOptions = React.useMemo<SingleOption[]>(
    () => Object.entries(payload?.workspace?.employee_scope_labels || {}).map(([value, label]) => ({ value, label })),
    [payload],
  );
  const triggerModeOptions = React.useMemo<SingleOption[]>(
    () => Object.entries(payload?.workspace?.trigger_mode_labels || {}).map(([value, label]) => ({ value, label })),
    [payload],
  );
  const candidateWorkStageOptions = React.useMemo<SingleOption[]>(
    () => [
      { value: "", label: "Не выбрано" },
      ...Object.entries(payload?.workspace?.candidate_work_stage_labels || {}).map(([value, label]) => ({ value, label })),
    ],
    [payload],
  );
  const targetEmployeeOptions = React.useMemo<SingleOption[]>(
    () => [
      { value: "", label: "Не привязывать к конкретной карточке" },
      ...((payload?.workspace?.employee_options || []).map((option) => ({ value: String(option.id), label: option.label })) as SingleOption[]),
    ],
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
  const rootStepOptions = React.useMemo<WorkspaceRootStepOption[]>(
    () => [
      { value: "", label: "Не возвращать в основной поток" },
      ...((payload?.workspace?.root_steps || []).map((step) => ({
        value: step.step_key,
        label: step.title || step.text_preview || `Шаг ${step.id}`,
      })) as WorkspaceRootStepOption[]),
    ],
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
    const params = new URLSearchParams();
    params.set("kind", workspaceKind);
    if (selectedScenarioId) {
      params.set("scenario_id", String(selectedScenarioId));
    }
    const url = `${apiUrl}?${params.toString()}`;
    setLoading(true);
    setError("");

    fetch(url, { credentials: "same-origin", headers: { Accept: "application/json" } })
      .then((response) => {
        if (!response.ok) throw new Error(`Не удалось загрузить workspace ${itemLabel}`);
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
        setError(loadError.message || `Не удалось загрузить workspace ${itemLabel}`);
      })
      .finally(() => {
        setLoading(false);
      });
  }, [apiUrl, itemLabel, selectedScenarioId, workspaceKind]);

  const scenarios = React.useMemo(() => {
    const items = payload?.scenarios || [];
    const filtered = items.filter((scenario) => {
      const matchesAudience = audienceFilter === "all" || scenario.employee_scope === audienceFilter;
      const matchesSearch =
        !search.trim() || `${scenario.title} ${scenario.description}`.toLowerCase().includes(search.toLowerCase());
      return matchesAudience && matchesSearch;
    });
    const timestampValue = (value: string | null, fallback: number) => {
      const parsed = value ? Date.parse(value) : Number.NaN;
      return Number.isFinite(parsed) ? parsed : fallback;
    };
    const byTitle = (left: string, right: string) => left.localeCompare(right, "ru", { sensitivity: "base" });
    return filtered.slice().sort((left, right) => {
      if (sortMode === "title_asc") {
        return byTitle(left.title, right.title);
      }
      if (sortMode === "created_asc") {
        return timestampValue(left.created_at, left.id) - timestampValue(right.created_at, right.id);
      }
      if (sortMode === "created_desc") {
        return timestampValue(right.created_at, right.id) - timestampValue(left.created_at, left.id);
      }
      return timestampValue(right.updated_at || right.created_at, right.id) - timestampValue(left.updated_at || left.created_at, left.id);
    });
  }, [audienceFilter, payload, search, sortMode]);

  React.useEffect(() => {
    const availableIds = new Set((payload?.scenarios || []).map((scenario) => scenario.id));
    setSelectedScenarioIds((prev) => prev.filter((id) => availableIds.has(id)));
  }, [payload]);

  React.useEffect(() => {
    if (sidebarState.message || saveState.message || scenarioSettingsState.message || attachmentState.message) {
      setFlashState({ message: "", error: false });
    }
  }, [attachmentState.message, saveState.message, scenarioSettingsState.message, sidebarState.message]);

  React.useEffect(() => {
    if (!detailTarget) {
      setForm(null);
      setAttachmentState({ uploading: false, message: "", error: false });
      return;
    }
    setForm({
      title: detailTarget.title || "",
      text: detailTarget.text || "",
      response_type:
        !isSurveyWorkspace && detailTarget.response_type === "buttons"
          ? "branching"
          : detailTarget.response_type || "none",
      button_options: detailTarget.button_options.join("\n"),
      send_mode: detailTarget.send_mode || "immediate",
      send_time: detailTarget.send_time || "",
      target_field: detailTarget.target_field || "",
      launch_scenario_key: detailTarget.launch_scenario_key || "",
      return_to_step_key: detailTarget.return_to_step_key || "",
      send_employee_card: Boolean(detailTarget.send_employee_card),
      notify_on_send_text: detailTarget.notify_on_send_text || "",
      notify_on_send_recipient_ids: detailTarget.notify_on_send_recipient_ids || "",
      notify_on_send_recipient_scope: detailTarget.notify_on_send_recipient_scope || "",
      step_send_notifications: detailTarget.step_send_notifications || [],
      button_notifications: detailTarget.button_notifications || [],
    });
    setSaveState({ saving: false, message: "", error: false });
    setAttachmentState({ uploading: false, message: "", error: false });
  }, [detailTarget, isSurveyWorkspace, selectedItemKey, selectedScenarioId]);

  React.useEffect(() => {
    const scenario = payload?.workspace?.scenario;
    if (!scenario) {
      setScenarioSettingsForm(null);
      return;
    }
    setScenarioSettingsForm({
      title: scenario.title || "",
      description: scenario.description || "",
      role_scope: scenario.role_scope || "all",
      employee_scope: scenario.employee_scope || "all",
      trigger_mode: scenario.trigger_mode || "manual_only",
      candidate_work_stage_trigger: scenario.candidate_work_stage_trigger || "",
      target_employee_id: scenario.target_employee_id ? String(scenario.target_employee_id) : "",
    });
    setScenarioSettingsState({ saving: false, message: "", error: false });
  }, [payload?.workspace?.scenario?.id]);

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
        title: isSurveyWorkspace ? (form.text || form.title) : form.title,
        text: isSurveyWorkspace ? (form.text || form.title) : form.text,
        response_type: form.response_type,
        button_options: form.button_options,
        send_mode: form.send_mode,
        send_time: form.send_time,
        target_field: supportsTargetField(form.response_type) ? form.target_field : "",
        launch_scenario_key: form.launch_scenario_key,
        return_to_step_key: detailTarget?.kind === "branch_step" ? form.return_to_step_key : "",
        send_employee_card: form.send_employee_card,
        notify_on_send_text: form.notify_on_send_text,
        notify_on_send_recipient_ids: form.notify_on_send_recipient_ids,
        notify_on_send_recipient_scope: form.notify_on_send_recipient_scope,
        step_send_notifications: form.step_send_notifications,
        button_notifications: form.button_notifications,
      }),
    })
      .then(async (response) => {
        if (!response.ok) {
          const payload = await response.json().catch(() => ({}));
          throw new Error(payload.detail || `Не удалось сохранить ${stepLabel}`);
        }
        return response.json();
      })
      .then((result: { message?: string; payload: WorkspacePayload }) => {
        applyPayload(result.payload, itemKey(selectedItem));
        setSaveState({ saving: false, message: result.message || (isSurveyWorkspace ? "Вопрос сохранён" : "Шаг сохранён"), error: false });
      })
      .catch((saveError: Error) => {
        setSaveState({ saving: false, message: saveError.message || `Не удалось сохранить ${stepLabel}`, error: true });
      });
  };

  const handleSaveScenarioSettings = () => {
    const scenarioId = payload?.workspace?.scenario?.id;
    if (!scenarioId || !scenarioSettingsForm) return;
    const settingsPayload = {
      ...scenarioSettingsForm,
      trigger_mode: isSurveyWorkspace ? "manual_only" : scenarioSettingsForm.trigger_mode,
    };
    setScenarioSettingsState({ saving: true, message: "", error: false });
    fetch(`/api/flows/workspace/scenarios/${scenarioId}/settings`, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(settingsPayload),
    })
      .then(async (response) => {
        if (!response.ok) {
          const payload = await response.json().catch(() => ({}));
          throw new Error(payload.detail || `Не удалось сохранить настройки ${itemLabel}`);
        }
        return response.json();
      })
      .then((result: { message?: string; payload: WorkspacePayload }) => {
        applyPayload(result.payload);
        setScenarioSettingsState({ saving: false, message: result.message || "Настройки сохранены", error: false });
        setScenarioSettingsOpen(false);
      })
      .catch((settingsError: Error) => {
        setScenarioSettingsState({
          saving: false,
          message: settingsError.message || `Не удалось сохранить настройки ${itemLabel}`,
          error: true,
        });
      });
  };

  const handleCreateScenario = () => {
    const title = newScenarioTitle.trim() || newItemTitle;
    setSidebarState({ message: "", error: false });
    fetch("/api/flows/workspace/scenarios", {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ title, description: "", kind: workspaceKind }),
    })
      .then(async (response) => {
        if (!response.ok) {
          const payload = await response.json().catch(() => ({}));
          throw new Error(payload.detail || `Не удалось создать ${itemLabel}`);
        }
        return response.json();
      })
      .then((result: { payload: WorkspacePayload; scenario_id?: number }) => {
        setSidebarState({ message: result.payload.item_label === "опрос" ? "Опрос создан" : "Сценарий создан", error: false });
        setSearch("");
        setCreatingScenario(false);
        setNewScenarioTitle("");
        applyPayload(result.payload);
      })
      .catch((createError: Error) => {
        setSidebarState({ message: createError.message || `Не удалось создать ${itemLabel}`, error: true });
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
      body: JSON.stringify({ title: newStepTitle }),
    })
      .then(async (response) => {
        if (!response.ok) {
          const payload = await response.json().catch(() => ({}));
          throw new Error(payload.detail || (isSurveyWorkspace ? "Не удалось добавить вопрос" : "Не удалось добавить шаг"));
        }
        return response.json();
      })
      .then((result: { payload: WorkspacePayload; step_id?: number }) => {
        applyPayload(result.payload, result.step_id ? String(result.step_id) : undefined);
      })
      .catch((stepError: Error) => {
        setSaveState({ saving: false, message: stepError.message || (isSurveyWorkspace ? "Не удалось добавить вопрос" : "Не удалось добавить шаг"), error: true });
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
    fetch(`/api/flows/workspace/scenarios/${action}`, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ scenario_ids: selectedScenarioIds, kind: workspaceKind }),
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
      body: JSON.stringify({ scenario_ids: scenarioIds, kind: workspaceKind }),
    })
      .then(async (response) => {
        if (!response.ok) {
          const payload = await response.json().catch(() => ({}));
          throw new Error(payload.detail || `Не удалось сохранить порядок ${isSurveyWorkspace ? "опросов" : "сценариев"}`);
        }
        return response.json();
      })
      .then((result: { payload: WorkspacePayload; message?: string }) => {
        setSidebarState({ message: result.message || `Порядок ${isSurveyWorkspace ? "опросов" : "сценариев"} обновлён`, error: false });
        applyPayload(result.payload);
      })
      .catch((reorderError: Error) => {
        setSidebarState({ message: reorderError.message || `Не удалось сохранить порядок ${isSurveyWorkspace ? "опросов" : "сценариев"}`, error: true });
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
          throw new Error(payload.detail || (isSurveyWorkspace ? "Не удалось сохранить порядок вопросов" : "Не удалось сохранить порядок шагов"));
        }
        return response.json();
      })
      .then((result: { payload: WorkspacePayload; message?: string }) => {
        setSaveState({ saving: false, message: result.message || (isSurveyWorkspace ? "Порядок вопросов обновлён" : "Порядок шагов обновлён"), error: false });
        applyPayload(result.payload, selectedKeyRef.current);
      })
      .catch((reorderError: Error) => {
        setSaveState({ saving: false, message: reorderError.message || (isSurveyWorkspace ? "Не удалось сохранить порядок вопросов" : "Не удалось сохранить порядок шагов"), error: true });
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
    return <Card className="border border-border bg-card p-8 shadow-none ring-0">Собираю новый workspace…</Card>;
  }

  if (error) {
    return (
      <Card className="border border-border bg-card p-8 shadow-none ring-0">
        <p className="text-sm text-destructive">{error}</p>
        <div className="mt-4">
          <Button variant="secondary" onClick={() => window.location.reload()}>
            Повторить загрузку
          </Button>
        </div>
      </Card>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-4">
      <WorkspaceFlashNotice message={flashState.message} error={flashState.error} />
      <div
        className="relative min-h-0 flex-1 overflow-hidden"
      >
        {loading ? (
          <div className="pointer-events-none absolute inset-x-0 top-0 z-10 flex justify-center">
            <div className="rounded-full border border-border bg-card/95 px-4 py-2 text-sm font-medium text-muted-foreground backdrop-blur">
              Обновляю workspace…
            </div>
          </div>
        ) : null}
        <div
          className={`grid h-full grid-cols-[392px_minmax(0,1fr)_488px] gap-4 transition-opacity max-[1400px]:grid-cols-[320px_minmax(0,1fr)_400px] ${loading ? "opacity-80" : "opacity-100"}`}
        >
          <WorkspaceSidebarSection
            sidebarTitle={sidebarTitle}
            isSurveyWorkspace={isSurveyWorkspace}
            createItemLabel={createItemLabel}
            itemNamePlaceholder={itemNamePlaceholder}
            creatingScenario={creatingScenario}
            newScenarioTitle={newScenarioTitle}
            search={search}
            audienceFilter={audienceFilter}
            sortMode={sortMode}
            scenarios={scenarios}
            selectedScenarioId={selectedScenarioId}
            selectedScenarioIds={selectedScenarioIds}
            dragScenarioId={dragScenarioId}
            sidebarState={sidebarState}
            onNewScenarioTitleChange={setNewScenarioTitle}
            onCreateScenario={handleCreateScenario}
            onOpenCreateScenario={() => setCreatingScenario(true)}
            onCancelCreateScenario={() => {
              setCreatingScenario(false);
              setNewScenarioTitle("");
            }}
            onSearchChange={setSearch}
            onAudienceFilterChange={setAudienceFilter}
            onSortModeChange={setSortMode}
            onToggleSelectAllVisibleScenarios={toggleSelectAllVisibleScenarios}
            onBulkScenarioAction={handleBulkScenarioAction}
            onSelectScenario={setSelectedScenarioId}
            onScenarioDragStart={setDragScenarioId}
            onScenarioDrop={handleScenarioDrop}
            onScenarioDragEnd={() => setDragScenarioId(null)}
            onToggleScenarioSelection={toggleScenarioSelection}
          />

          <WorkspaceCanvasSection
            stack={stack}
            currentContainer={currentContainer}
            currentItems={currentItems}
            selectedItemKey={selectedItemKey}
            stepTitle={stepTitle}
            itemLabel={itemLabel}
            isSurveyWorkspace={isSurveyWorkspace}
            payloadWorkspace={payload?.workspace}
            exportUrl={exportUrl}
            scenarioSettingsForm={scenarioSettingsForm}
            scenarioSettingsOpen={scenarioSettingsOpen}
            scenarioSettingsState={scenarioSettingsState}
            roleScopeOptions={roleScopeOptions}
            employeeScopeOptions={employeeScopeOptions}
            triggerModeOptions={triggerModeOptions}
            candidateWorkStageOptions={candidateWorkStageOptions}
            targetEmployeeOptions={targetEmployeeOptions}
            dragStepId={dragStepId}
            onBreadcrumbClick={(index) => {
              const next = stack.slice(0, index + 1);
              setStack(next);
              setSelectedItemKey(itemKey(next[next.length - 1]?.items?.[0]));
            }}
            onScenarioSettingsOpenChange={setScenarioSettingsOpen}
            onSaveScenarioSettings={handleSaveScenarioSettings}
            onScenarioSettingsFormChange={setScenarioSettingsForm}
            onAddRootStep={handleAddRootStep}
            onAddChainStep={handleAddChainStep}
            onSelectItem={setSelectedItemKey}
            onDragStepStart={setDragStepId}
            onDragStepDrop={handleRootStepDrop}
            onDragStepEnd={() => setDragStepId(null)}
            onOpenItem={(item) => {
              const nextContainer = buildChildContainer(item);
              if (!nextContainer) return;
              setStack((prev) => prev.concat(nextContainer));
              setSelectedItemKey(itemKey(nextContainer.items[0]));
            }}
          />

          <WorkspaceDetailSection>
            <WorkspaceStepDetailPane
              selectedItem={selectedItem}
              detailTarget={detailTarget}
              stepLabel={stepLabel}
              form={form}
              textRef={textRef}
              fileInputRef={fileInputRef}
              payloadWorkspace={payload?.workspace}
              attachmentState={attachmentState}
              saveState={saveState}
              openLabel={openLabel}
              isSurveyWorkspace={isSurveyWorkspace}
              responseTypePickerOptions={responseTypePickerOptions}
              sendModeOptions={sendModeOptions}
              targetFieldOptions={targetFieldOptions}
              launchScenarioOptions={launchScenarioOptions}
              rootStepOptions={rootStepOptions}
              onInsertIntoText={insertIntoText}
              onFormChange={setForm}
              onCreateBranch={handleCreateBranch}
              onAttachmentSelected={handleAttachmentSelected}
              onDeleteAttachment={handleDeleteAttachment}
              onDeleteCurrent={handleDeleteCurrent}
              onOpenCurrentChild={() => {
                const nextContainer = buildChildContainer(selectedItem);
                if (!nextContainer) return;
                setStack((prev) => prev.concat(nextContainer));
                setSelectedItemKey(itemKey(nextContainer.items[0]));
              }}
              onSave={handleSave}
              supportsButtonOptions={supportsButtonOptions}
              supportsTargetField={supportsTargetField}
            />
          </WorkspaceDetailSection>
        </div>
      </div>
    </div>
  );
}
