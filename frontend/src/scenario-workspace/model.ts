import { Route, Split, Waypoints } from "lucide-react";

import type { Container, WorkspaceData, WorkspaceItem } from "./types";

export const FALLBACK_RESPONSE_TYPE_LABELS: Record<string, string> = {
  none: "Без ответа",
  text: "Текстовый ответ",
  file: "Загрузка файла",
  buttons: "Выбор кнопками",
  branching: "Ветвление",
  launch_scenario: "Переход к сценарию",
  chain: "Цепочка шагов",
};

const INTERACTIVE_RESPONSE_TYPES = new Set(["text", "file", "buttons", "branching"]);

export function payloadLabel(kind: "scenario" | "survey") {
  return kind === "survey" ? "опрос" : "сценарий";
}

export function itemKey(item: WorkspaceItem | null | undefined) {
  return item?.id ? String(item.id) : "";
}

export function makeRootContainer(workspace: WorkspaceData): Container {
  return {
    type: "root",
    key: `scenario-${workspace.scenario.id}`,
    sourceKey: null,
    ownerStepId: null,
    title: workspace.scenario.title,
    subtitle: "",
    crumbLabel: workspace.scenario.title,
    items: workspace.root_steps,
  };
}

export function buildChildContainer(item: WorkspaceItem | null): Container | null {
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

export function workspaceItemTitle(item: WorkspaceItem, index: number) {
  if (item.kind === "branch_slot") return item.label || `Ветка ${index + 1}`;
  return item.title || `Шаг ${index + 1}`;
}

export function summarizeItem(item: WorkspaceItem) {
  if (item.kind === "branch_slot") {
    return item.has_step ? "Ветка создана и готова к настройке." : "Ветка ещё не создана.";
  }
  if (item.text_preview) return item.text_preview;
  if (item.response_type === "branching") return "Шаг разводит сценарий по отдельным веткам.";
  if (item.response_type === "chain") return "Шаг запускает линейную цепочку внутри ветки.";
  return "Содержимое шага пока не заполнено.";
}

export function detailTargetFromItem(item: WorkspaceItem | null) {
  if (!item) return null;
  return item.kind === "branch_slot" ? item.step : item;
}

export function supportsButtonOptions(responseType: string) {
  return responseType === "buttons" || responseType === "branching";
}

export function supportsTargetField(responseType: string) {
  return responseType === "text" || responseType === "file" || responseType === "buttons";
}

export function responseTypeWaitState(responseType: string) {
  if (INTERACTIVE_RESPONSE_TYPES.has(responseType)) {
    return {
      tone: "waiting" as const,
      badge: "Ждёт ответ",
      title: "Сценарий остановится на этом шаге",
      description:
        "После отправки бот будет ждать ответ пользователя и не пойдёт дальше, пока не получит его.",
    };
  }
  return {
    tone: "passive" as const,
    badge: "Автопереход",
    title: "Шаг не блокирует сценарий",
    description:
      "После отправки бот сам перейдёт дальше по сценарию, если не сработают отдельные условия запуска или времени.",
  };
}

export function parseRecipientIds(value: string) {
  return value
    .split(",")
    .map((chunk) => chunk.trim())
    .filter(Boolean);
}

export function openActionLabel(item: WorkspaceItem | null) {
  const container = buildChildContainer(item);
  if (!container) return "";
  return container.type === "branches" ? "Открыть ветки" : "Открыть цепочку";
}

export function moveItemById<T extends { id: number }>(items: T[], sourceId: number, targetId: number) {
  const sourceIndex = items.findIndex((item) => item.id === sourceId);
  const targetIndex = items.findIndex((item) => item.id === targetId);
  if (sourceIndex === -1 || targetIndex === -1 || sourceIndex === targetIndex) return items;
  const next = items.slice();
  const [moved] = next.splice(sourceIndex, 1);
  next.splice(targetIndex, 0, moved);
  return next;
}

export function rebuildWorkspaceState(
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

export function crumbIcon(entry: Container) {
  if (entry.type === "root") return Route;
  if (entry.type === "branches") return Waypoints;
  return Split;
}
