import React from "react";
import { Plus, Send, Settings, X } from "lucide-react";

import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PageDetailHeader, PageHeader } from "@/components/ui/page-header";
import { Textarea } from "@/components/ui/textarea";
import {
  buildChildContainer,
  detailTargetFromItem,
  FALLBACK_RESPONSE_TYPE_LABELS,
  findWorkspacePathToStep,
  itemKey,
  makeRootContainer,
  moveItemById,
  normalizeNotificationRecipientIds,
  openActionLabel,
  payloadLabel,
  payloadLabelGenitive,
  rebuildWorkspaceState,
  supportsButtonOptions,
  supportsTargetField,
} from "./model";
import { BroadcastDialog } from "@/mass-broadcast/broadcast-dialog";
import {
  ScenarioSettingsDialog,
  WorkspaceCanvasSection,
  WorkspaceDetailSection,
  WorkspaceFlashNotice,
  WorkspaceCatalogSection,
  WorkspaceStepDetailPane,
} from "./sections";
import type {
  Container,
  ScenarioSettingsForm,
  SingleOption,
  WorkspaceButtonNotification,
  WorkspaceButtonNotificationRule,
  WorkspacePayload,
  WorkspaceRootStepOption,
  WorkspaceStep,
  WorkspaceStepForm,
  WorkspaceStepSendNotificationRule,
} from "./types";

const rootElement = document.getElementById("react-scenario-workspace-v2-root");

function hasScenarioRouteParam() {
  return new URL(window.location.href).searchParams.has("scenario_id");
}

function normalizeStepNotificationRules(rules: WorkspaceStepSendNotificationRule[] = []) {
  return rules
    .map((rule) => ({
      ...rule,
      message_text: rule.message_text || "",
      recipient_ids: normalizeNotificationRecipientIds(rule.recipient_ids || ""),
      recipient_scope: "",
    }))
    .filter((rule) => rule.message_text.trim() && rule.recipient_ids);
}

function normalizeButtonNotificationRules(rules: WorkspaceButtonNotificationRule[] = []) {
  return rules
    .map((rule) => ({
      ...rule,
      message_text: rule.message_text || "",
      recipient_ids: normalizeNotificationRecipientIds(rule.recipient_ids || ""),
      recipient_scope: "",
    }))
    .filter((rule) => rule.message_text.trim() && rule.recipient_ids);
}

function normalizeButtonNotifications(items: WorkspaceButtonNotification[] = []) {
  return items.map((item) => {
    const rules = normalizeButtonNotificationRules(item.rules || []);
    return {
      ...item,
      message_text: rules[0]?.message_text || "",
      recipient_ids: rules[0]?.recipient_ids || "",
      recipient_scope: "",
      rules,
    };
  });
}

function normalizeScenarioRoleScopes(roleScopes: string[] | undefined, legacyRoleScope: string) {
  const normalized = (roleScopes?.length ? roleScopes : legacyRoleScope.split(","))
    .map((item) => item.trim())
    .filter(Boolean);
  const concreteScopes = normalized.filter((item) => item !== "all");
  return concreteScopes.length ? Array.from(new Set(concreteScopes)) : ["all"];
}

export function ScenarioWorkspacePage() {
  const apiUrl = rootElement?.getAttribute("data-api-url") || "/api/flows/workspace";
  const initialScenarioId = Number(rootElement?.getAttribute("data-selected-scenario-id") || 0) || null;
  const workspaceKind = rootElement?.getAttribute("data-workspace-kind") === "survey" ? "survey" : "scenario";
  const initialFlashMessage = rootElement?.getAttribute("data-flash-message") || "";
  const initialFlashType = rootElement?.getAttribute("data-flash-type") || "success";
  const isSurveyWorkspace = workspaceKind === "survey";
  const itemLabel = payloadLabel(workspaceKind);
  const itemLabelGenitive = payloadLabelGenitive(workspaceKind);
  const stepTitle = isSurveyWorkspace ? "Вопросы" : "Шаги сценария";
  const createItemLabel = isSurveyWorkspace ? "Создать опрос" : "Создать сценарий";
  const itemNamePlaceholder = isSurveyWorkspace ? "Название опроса" : "Название сценария";
  const newItemTitle = isSurveyWorkspace ? "Новый опрос" : "Новый сценарий";
  const sectionTitle = isSurveyWorkspace ? "Опросы" : "Сценарии";
  const newStepTitle = isSurveyWorkspace ? "Новый вопрос" : "Новый шаг";
  const stepLabel = isSurveyWorkspace ? "вопрос" : "шаг";

  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState("");
  const [payload, setPayload] = React.useState<WorkspacePayload | null>(null);
  const [selectedScenarioId, setSelectedScenarioId] = React.useState<number | null>(initialScenarioId);
  const [workspaceRouteMode, setWorkspaceRouteMode] = React.useState<"catalog" | "editor">(
    initialScenarioId && hasScenarioRouteParam() ? "editor" : "catalog",
  );
  const [search, setSearch] = React.useState("");
  const [audienceFilter, setAudienceFilter] = React.useState<"all" | "employees" | "candidates">("all");
  const [sortMode, setSortMode] = React.useState<"updated_desc" | "created_desc" | "created_asc" | "title_asc">("updated_desc");
  const [stack, setStack] = React.useState<Container[]>([]);
  const [selectedItemKey, setSelectedItemKey] = React.useState("");
  const [viewMode, setViewMode] = React.useState<"list" | "graph">("list");
  const [form, setForm] = React.useState<WorkspaceStepForm | null>(null);
  const [saveState, setSaveState] = React.useState({ saving: false, message: "", error: false });
  const [scenarioSettingsForm, setScenarioSettingsForm] = React.useState<ScenarioSettingsForm | null>(null);
  const [scenarioSettingsState, setScenarioSettingsState] = React.useState({ saving: false, message: "", error: false });
  const [scenarioSettingsOpen, setScenarioSettingsOpen] = React.useState(false);
  const textRef = React.useRef<HTMLTextAreaElement>(null);
  const fileInputRef = React.useRef<HTMLInputElement>(null);
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
  const isCatalogRoute = workspaceRouteMode === "catalog";
  const currentItems = currentContainer?.items || [];
  const selectedItem = currentItems.find((item) => itemKey(item) === selectedItemKey) || currentItems[0] || null;
  const detailTarget = detailTargetFromItem(selectedItem);
  const selectedStepId = detailTarget?.id || null;
  const openLabel = openActionLabel(selectedItem);
  const responseTypeOptions = React.useMemo(() => {
    const labels = payload?.workspace?.response_type_labels || FALLBACK_RESPONSE_TYPE_LABELS;
    return Object.entries(labels).filter(([value]) => {
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
  const recipientModeOptions = React.useMemo<SingleOption[]>(
    () => Object.entries(payload?.workspace?.recipient_mode_labels || {}).map(([value, label]) => ({ value, label })),
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
  const ancestorRootStepKey = React.useMemo(
    () => {
      if (detailTarget?.kind !== "branch_step" || currentContainer?.type !== "branches") {
        return "";
      }
      const ownerRootStep = (payload?.workspace?.root_steps || []).find((step) => step.id === currentContainer.ownerStepId);
      return ownerRootStep?.step_key || "";
    },
    [currentContainer, detailTarget, payload],
  );
  const rootStepOptions = React.useMemo<WorkspaceRootStepOption[]>(
    () => [
      { value: "", label: "Не возвращать в основной поток" },
      ...((payload?.workspace?.root_steps || [])
        .filter((step) => step.step_key !== ancestorRootStepKey)
        .map((step) => ({
          value: step.step_key,
          label: step.title || step.text_preview || `Шаг ${step.id}`,
        })) as WorkspaceRootStepOption[]),
    ],
    [ancestorRootStepKey, payload],
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

  const replaceRouteScenario = React.useCallback((scenarioId: number | null, mode: "catalog" | "editor") => {
    const nextUrl = new URL(window.location.href);
    if (scenarioId && mode === "editor") {
      nextUrl.searchParams.set("scenario_id", String(scenarioId));
    } else {
      nextUrl.searchParams.delete("scenario_id");
    }
    window.history.pushState({ scenarioWorkspaceMode: mode, scenarioId }, "", nextUrl);
    setWorkspaceRouteMode(mode);
  }, []);

  const openScenarioEditor = React.useCallback(
    (scenarioId: number) => {
      replaceRouteScenario(scenarioId, "editor");
      setSelectedScenarioId(scenarioId);
    },
    [replaceRouteScenario],
  );

  const openScenarioCatalog = React.useCallback(() => {
    replaceRouteScenario(null, "catalog");
    setSelectedScenarioId(null);
    setStack([]);
    setSelectedItemKey("");
    setScenarioSettingsOpen(false);
  }, [replaceRouteScenario]);

  const openScenarioSettings = React.useCallback(() => {
    setScenarioSettingsOpen(true);
  }, []);

  /*
   * Цель рассылки, а не булев флаг: диалог открывается и из шапки детали,
   * и из панели выделения в каталоге, где открытой записи нет.
   */
  const [broadcastTarget, setBroadcastTarget] = React.useState<{ flowKey: string; title: string } | null>(null);

  React.useEffect(() => {
    const handlePopState = () => {
      const params = new URL(window.location.href).searchParams;
      const scenarioId = Number(params.get("scenario_id") || 0) || null;
      setWorkspaceRouteMode(scenarioId ? "editor" : "catalog");
      if (scenarioId) {
        setSelectedScenarioId(scenarioId);
      } else {
        setSelectedScenarioId(null);
        setStack([]);
        setSelectedItemKey("");
      }
      setScenarioSettingsOpen(false);
    };
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  React.useEffect(() => {
    const params = new URLSearchParams();
    params.set("kind", workspaceKind);
    const cleanCatalogRequest = workspaceRouteMode === "catalog";
    if (selectedScenarioId) {
      params.set("scenario_id", String(selectedScenarioId));
    }
    const url = `${apiUrl}?${params.toString()}`;
    setLoading(true);
    setError("");

    fetch(url, { credentials: "same-origin", headers: { Accept: "application/json" } })
      .then((response) => {
        if (!response.ok) throw new Error(`Не удалось загрузить workspace ${itemLabelGenitive}`);
        return response.json() as Promise<WorkspacePayload>;
      })
      .then((nextPayload) => {
        if (cleanCatalogRequest) {
          setPayload(nextPayload);
          setSelectedScenarioId(null);
          setStack([]);
          setSelectedItemKey("");
          return;
        }
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
        setError(loadError.message || `Не удалось загрузить workspace ${itemLabelGenitive}`);
      })
      .finally(() => {
        setLoading(false);
      });
  }, [apiUrl, applyPayload, isSurveyWorkspace, itemLabelGenitive, selectedScenarioId, workspaceKind, workspaceRouteMode]);

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
      response_type: detailTarget.response_type || "none",
      button_options: detailTarget.button_options.join("\n"),
      confirm_choice: Boolean(detailTarget.confirm_choice),
      send_mode: detailTarget.send_mode || "immediate",
      send_time: detailTarget.send_time || "",
      target_field: detailTarget.target_field || "",
      launch_scenario_key: detailTarget.launch_scenario_key || "",
      return_to_step_key: detailTarget.return_to_step_key || "",
      is_terminal: Boolean(detailTarget.is_terminal),
      attachment_document_item_id: detailTarget.attachment_document_item_id ? String(detailTarget.attachment_document_item_id) : "",
      send_employee_card: Boolean(detailTarget.send_employee_card),
      notify_on_send_text: detailTarget.notify_on_send_text || "",
      notify_on_send_recipient_ids: normalizeNotificationRecipientIds(detailTarget.notify_on_send_recipient_ids || ""),
      notify_on_send_recipient_scope: "",
      step_send_notifications: normalizeStepNotificationRules(detailTarget.step_send_notifications || []),
      button_notifications: normalizeButtonNotifications(detailTarget.button_notifications || []),
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
      role_scopes: normalizeScenarioRoleScopes(scenario.role_scopes, scenario.role_scope || "all"),
      employee_scope: scenario.employee_scope || "all",
      recipient_mode: scenario.recipient_mode || "self",
      trigger_mode: scenario.trigger_mode || "manual_only",
      candidate_work_stage_trigger: scenario.candidate_work_stage_trigger || "",
      target_employee_id: scenario.target_employee_id ? String(scenario.target_employee_id) : "",
    });
    setScenarioSettingsState({ saving: false, message: "", error: false });
  }, [payload?.workspace?.scenario?.id]);

  const handleSave = () => {
    if (!detailTarget || !form) return;
    const stepSendNotifications = normalizeStepNotificationRules(form.step_send_notifications || []);
    const buttonNotifications = normalizeButtonNotifications(form.button_notifications || []);
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
        confirm_choice: supportsButtonOptions(form.response_type) ? form.confirm_choice : false,
        send_mode: form.send_mode,
        send_time: form.send_time,
        target_field: supportsTargetField(form.response_type) ? form.target_field : "",
        launch_scenario_key: form.launch_scenario_key,
        return_to_step_key: detailTarget?.kind === "branch_step" ? form.return_to_step_key : "",
        is_terminal: isSurveyWorkspace ? false : form.is_terminal,
        attachment_document_item_id: isSurveyWorkspace ? "" : form.attachment_document_item_id,
        send_employee_card: form.send_employee_card,
        notify_on_send_text: form.notify_on_send_text,
        notify_on_send_recipient_ids: normalizeNotificationRecipientIds(form.notify_on_send_recipient_ids || ""),
        notify_on_send_recipient_scope: "",
        step_send_notifications: stepSendNotifications,
        button_notifications: buttonNotifications,
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
      role_scopes: normalizeScenarioRoleScopes(scenarioSettingsForm.role_scopes, scenarioSettingsForm.role_scope),
      role_scope: normalizeScenarioRoleScopes(scenarioSettingsForm.role_scopes, scenarioSettingsForm.role_scope)
        .filter((item) => item && item !== "all")
        .join(",") || "all",
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
          throw new Error(payload.detail || `Не удалось сохранить настройки ${itemLabelGenitive}`);
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
          message: settingsError.message || `Не удалось сохранить настройки ${itemLabelGenitive}`,
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
        if (result.scenario_id) {
          replaceRouteScenario(result.scenario_id, "editor");
          setSelectedScenarioId(result.scenario_id);
        }
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

  const handleSelectGraphStep = React.useCallback(
    (stepId: number) => {
      const workspace = payload?.workspace;
      if (!workspace) return;
      const path = findWorkspacePathToStep(workspace, stepId);
      if (!path) return;
      setStack(path.stack);
      setSelectedItemKey(path.selectedItemKey);
    },
    [payload?.workspace],
  );

  const handleSendSelectedScenario = () => {
    if (selectedScenarioIds.length !== 1) return;
    const scenario = (payload?.scenarios || []).find((item) => item.id === selectedScenarioIds[0]);
    if (!scenario?.scenario_key) return;
    setBroadcastTarget({ flowKey: scenario.scenario_key, title: scenario.title });
  };

  const renderScenarioCatalogSection = () => (
    <WorkspaceCatalogSection
      isSurveyWorkspace={isSurveyWorkspace}
      itemNamePlaceholder={itemNamePlaceholder}
      creatingScenario={creatingScenario}
      newScenarioTitle={newScenarioTitle}
      search={search}
      audienceFilter={audienceFilter}
      sortMode={sortMode}
      scenarios={scenarios}
      selectedScenarioIds={selectedScenarioIds}
      dragScenarioId={dragScenarioId}
      sidebarState={sidebarState}
      onNewScenarioTitleChange={setNewScenarioTitle}
      onCreateScenario={handleCreateScenario}
      onCancelCreateScenario={() => {
        setCreatingScenario(false);
        setNewScenarioTitle("");
      }}
      onSearchChange={setSearch}
      onAudienceFilterChange={setAudienceFilter}
      onSortModeChange={setSortMode}
      onToggleSelectAllVisibleScenarios={toggleSelectAllVisibleScenarios}
      onBulkScenarioAction={handleBulkScenarioAction}
      onSendSelectedScenario={handleSendSelectedScenario}
      onClearScenarioSelection={() => setSelectedScenarioIds([])}
      onSelectScenario={openScenarioEditor}
      onScenarioDragStart={setDragScenarioId}
      onScenarioDrop={handleScenarioDrop}
      onScenarioDragEnd={() => setDragScenarioId(null)}
      onToggleScenarioSelection={toggleScenarioSelection}
    />
  );

  const renderCanvasSection = () => (
    <WorkspaceCanvasSection
      stack={stack}
      currentContainer={currentContainer}
      currentItems={currentItems}
      selectedItemKey={selectedItemKey}
      selectedStepId={selectedStepId}
      viewMode={viewMode}
      stepTitle={stepTitle}
      isSurveyWorkspace={isSurveyWorkspace}
      graph={payload?.workspace?.graph}
      payloadWorkspace={payload?.workspace}
      exportUrl={exportUrl}
      dragStepId={dragStepId}
      onBreadcrumbClick={(index) => {
        const next = stack.slice(0, index + 1);
        setStack(next);
        setSelectedItemKey(itemKey(next[next.length - 1]?.items?.[0]));
      }}
      onAddRootStep={handleAddRootStep}
      onAddChainStep={handleAddChainStep}
      onSelectItem={setSelectedItemKey}
      onViewModeChange={setViewMode}
      onSelectGraphStep={handleSelectGraphStep}
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
  );

  const renderDetailSection = () => (
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
  );

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
      {isCatalogRoute ? (
        <PageHeader
          title={sectionTitle}
          /* Счётчик стоит там же, где выдача: в детали числу нечего считать. */
          counter={scenarios.length}
          actions={
            !creatingScenario ? (
              <Button size="sm" onClick={() => setCreatingScenario(true)} title={createItemLabel}>
                <Plus data-icon="inline-start" />
                Создать
              </Button>
            ) : undefined
          }
        />
      ) : (
        <PageDetailHeader
          title={payload?.workspace?.scenario?.title || (isSurveyWorkspace ? "Без опроса" : "Без сценария")}
          sectionTitle={sectionTitle}
          onBack={openScenarioCatalog}
          /*
           * Настройки — свойство открытой записи, поэтому вход в них здесь,
           * а не на карточке каталога: там они правили запись, которую
           * пользователь ещё не открыл.
           *
           * У опросов кнопки нет: диалог показывает поле «Кому отправлять
           * сценарий» независимо от вида, и на опросах оно говорило бы
           * чужим языком.
           */
          actions={
            <>
              {/*
                Рассылка — действие над открытой записью, поэтому живёт здесь,
                а не на отдельной странице массовых действий: там запись
                приходилось искать в селекте заново, не видя её содержимого.
              */}
              <Button
                size="sm"
                variant="outline"
                disabled={!payload?.workspace?.scenario?.scenario_key}
                onClick={() =>
                  setBroadcastTarget({
                    flowKey: payload?.workspace?.scenario?.scenario_key || "",
                    title: payload?.workspace?.scenario?.title || "",
                  })
                }
              >
                <Send data-icon="inline-start" />
                Разослать
              </Button>
              {!isSurveyWorkspace ? (
                <Button size="sm" variant="outline" onClick={openScenarioSettings}>
                  <Settings data-icon="inline-start" />
                  Настройки
                </Button>
              ) : null}
            </>
          }
        />
      )}
      <BroadcastDialog
        open={broadcastTarget !== null}
        flowKey={broadcastTarget?.flowKey || ""}
        itemTitle={broadcastTarget?.title || ""}
        kind={isSurveyWorkspace ? "survey" : "scenario"}
        onOpenChange={(open) => {
          if (!open) setBroadcastTarget(null);
        }}
      />
      <WorkspaceFlashNotice message={flashState.message} error={flashState.error} />
      <ScenarioSettingsDialog
        open={scenarioSettingsOpen}
        itemLabelGenitive={itemLabelGenitive}
        scenarioTitle={payload?.workspace?.scenario?.title || ""}
        isSurveyWorkspace={isSurveyWorkspace}
        scenarioSettingsForm={scenarioSettingsForm}
        scenarioSettingsState={scenarioSettingsState}
        roleScopeOptions={roleScopeOptions}
        employeeScopeOptions={employeeScopeOptions}
        recipientModeOptions={recipientModeOptions}
        triggerModeOptions={triggerModeOptions}
        candidateWorkStageOptions={candidateWorkStageOptions}
        targetEmployeeOptions={targetEmployeeOptions}
        onOpenChange={setScenarioSettingsOpen}
        onSave={handleSaveScenarioSettings}
        onFormChange={setScenarioSettingsForm}
      />
      <div
        /*
         * У каталога больше нет собственной ScrollArea: он стал обычной
         * страницей — полоса фильтров и карточки в потоке, — и прокручивается
         * этим контейнером. Редактор остаётся раскладкой фиксированной высоты
         * и режет переполнение внутри своих панелей.
         */
        className={`relative min-h-0 flex-1 ${isCatalogRoute ? "overflow-auto" : "overflow-hidden"}`}
      >
        {loading ? (
          <div className="pointer-events-none absolute inset-x-0 top-0 z-10 flex justify-center">
            <div className="rounded-full border border-border bg-card/95 px-4 py-2 text-sm font-medium text-muted-foreground backdrop-blur">
              Обновляю workspace…
            </div>
          </div>
        ) : null}
        {isCatalogRoute ? (
          renderScenarioCatalogSection()
        ) : (
          <div
            className={`grid h-full min-h-0 grid-cols-[minmax(420px,1fr)_minmax(420px,0.72fr)] gap-4 transition-opacity max-[1400px]:grid-cols-[minmax(360px,1fr)_minmax(380px,0.78fr)] ${loading ? "opacity-80" : "opacity-100"}`}
          >
            {renderCanvasSection()}
            {renderDetailSection()}
          </div>
        )}
      </div>
    </div>
  );
}
