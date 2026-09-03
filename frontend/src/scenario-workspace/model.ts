import { Route, Split, Waypoints } from "lucide-react";

import type { Container, WorkspaceData, WorkspaceItem } from "./types";

export const FALLBACK_RESPONSE_TYPE_LABELS: Record<string, string> = {
  none: "Без ответа",
  text: "Текстовый ответ",
  date: "Выбор даты",
  file: "Загрузка файла",
  buttons: "Выбор кнопками",
  branching: "Ветвление",
  launch_scenario: "Переход к сценарию",
  chain: "Цепочка шагов",
};

const INTERACTIVE_RESPONSE_TYPES = new Set(["text", "date", "file", "buttons", "branching"]);
const ROLE_NOTIFICATION_RECIPIENT_TOKEN_SET = new Set([
  "hr",
  "manager",
  "mentor_adaptation",
  "mentor_ipr",
]);

export const ROLE_NOTIFICATION_RECIPIENT_LABELS: Record<string, string> = {
  hr: "HR",
  manager: "Руководитель",
  mentor_adaptation: "Наставник по адаптации",
  mentor_ipr: "Наставник по ИПР",
};

export const ROLE_NOTIFICATION_RECIPIENT_TOKENS = Object.keys(ROLE_NOTIFICATION_RECIPIENT_LABELS);

export function payloadLabel(kind: "scenario" | "survey") {
  return kind === "survey" ? "опрос" : "сценарий";
}

/*
 * Родительный падеж для подписей вида «Настройки сценария». Одной формы
 * не хватает: «Создать сценарий» и «Настройки сценария» требуют разных,
 * и заголовок диалога читался как «Настройки сценарий».
 */
export function payloadLabelGenitive(kind: "scenario" | "survey") {
  return kind === "survey" ? "опроса" : "сценария";
}

/*
 * Счётчик записей внутри карточки. Форма слова выбирается по числу: до этого
 * подпись всегда стояла в родительном множественном, и опрос с одним вопросом
 * подписывался «1 вопросов».
 */
export function stepsCountLabel(count: number, isSurvey: boolean) {
  const forms = isSurvey ? ["вопрос", "вопроса", "вопросов"] : ["шаг", "шага", "шагов"];
  const tail = Math.abs(count) % 100;
  const last = tail % 10;
  if (tail > 10 && tail < 20) return `${count} ${forms[2]}`;
  if (last === 1) return `${count} ${forms[0]}`;
  if (last >= 2 && last <= 4) return `${count} ${forms[1]}`;
  return `${count} ${forms[2]}`;
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

export function findWorkspacePathToStep(workspace: WorkspaceData, stepId: number): { stack: Container[]; selectedItemKey: string } | null {
  const root = makeRootContainer(workspace);

  function visit(container: Container): { stack: Container[]; selectedItemKey: string } | null {
    for (const item of container.items) {
      if (item.kind !== "branch_slot" && item.id === stepId) {
        return { stack: [container], selectedItemKey: itemKey(item) };
      }

      if (item.kind === "branch_slot" && item.step?.id === stepId) {
        return { stack: [container], selectedItemKey: itemKey(item) };
      }

      const child = buildChildContainer(item);
      if (!child) continue;
      const nested = visit(child);
      if (nested) {
        return { stack: [container, ...nested.stack], selectedItemKey: nested.selectedItemKey };
      }
    }
    return null;
  }

  return visit(root);
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
  return (
    responseType === "text" ||
    responseType === "date" ||
    responseType === "file" ||
    responseType === "buttons" ||
    responseType === "branching"
  );
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

export function normalizeNotificationRecipientIds(value: string) {
  const normalizedTokens: string[] = [];
  parseRecipientIds(value).forEach((token) => {
    if (ROLE_NOTIFICATION_RECIPIENT_TOKEN_SET.has(token) && !normalizedTokens.includes(token)) {
      normalizedTokens.push(token);
    }
  });
  return normalizedTokens.join(",");
}

export function openActionLabel(item: WorkspaceItem | null) {
  const container = buildChildContainer(item);
  if (!container) return "";
  if (container.type === "branches") {
    const hasCreatedBranches = container.items.some(
      (branchItem) => branchItem.kind === "branch_slot" && branchItem.step,
    );
    return hasCreatedBranches ? "Открыть ветки" : "Создать ветки";
  }
  return "Открыть цепочку";
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
