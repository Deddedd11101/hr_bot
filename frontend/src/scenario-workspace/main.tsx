import React from "react";
import ReactDOM from "react-dom/client";
import { ChevronRight, FileStack, GitBranchPlus, ListTree, PanelLeft, PencilLine } from "lucide-react";

import "@/index.css";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
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

const rootElement = document.getElementById("react-scenario-workspace-v2-root");

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

  const currentContainer = stack[stack.length - 1] || null;
  const currentItems = currentContainer?.items || [];
  const selectedItem = currentItems.find((item) => itemKey(item) === selectedItemKey) || currentItems[0] || null;

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
        setPayload(nextPayload);
        setSelectedScenarioId(nextPayload.selected_scenario_id ?? null);
        if (nextPayload.workspace) {
          const root = makeRootContainer(nextPayload.workspace);
          setStack([root]);
          setSelectedItemKey(itemKey(root.items[0]));
        } else {
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

  if (loading) {
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
    <div className="grid min-h-[78vh] grid-cols-[320px_minmax(0,1fr)_400px] gap-5">
      <section className="flex min-h-0 flex-col rounded-[28px] border border-[var(--color-border)] bg-[var(--color-panel)] p-5 shadow-[var(--shadow-soft)]">
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--color-muted-foreground)]">Workspace V2</p>
            <h3 className="mt-2 text-2xl font-semibold">Сценарии</h3>
          </div>
          <Button size="sm">Создать</Button>
        </div>
        <Input placeholder="Найти сценарий" value={search} onChange={(e) => setSearch(e.target.value)} />
        <ScrollArea className="mt-4 min-h-0 flex-1">
          <div className="grid gap-3 pr-3">
            {scenarios.map((scenario: ScenarioSummary) => (
              <button
                key={scenario.id}
                type="button"
                onClick={() => setSelectedScenarioId(scenario.id)}
                className={`grid gap-3 rounded-2xl border p-4 text-left transition ${scenario.id === selectedScenarioId ? "border-[color:var(--color-accent)] bg-[var(--color-panel-muted)] shadow-sm" : "border-[var(--color-border)] bg-white hover:bg-[var(--color-panel-muted)]"}`}
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="text-base font-semibold">{scenario.title}</span>
                  <FileStack className="size-4 text-[var(--color-muted-foreground)]" />
                </div>
                <p className="text-sm leading-5 text-[var(--color-muted-foreground)]">{scenario.description || "Без описания"}</p>
                <div className="flex flex-wrap gap-2 text-xs font-medium text-[var(--color-muted-foreground)]">
                  <span className="rounded-full bg-black/5 px-2.5 py-1">{scenario.role_scope_label}</span>
                  <span className="rounded-full bg-black/5 px-2.5 py-1">{scenario.trigger_mode_label}</span>
                </div>
              </button>
            ))}
          </div>
        </ScrollArea>
      </section>

      <section className="flex min-h-0 flex-col rounded-[28px] border border-[var(--color-border)] bg-[var(--color-panel)] p-5 shadow-[var(--shadow-soft)]">
        <div className="mb-4 flex items-center gap-2 overflow-x-auto text-sm text-[var(--color-muted-foreground)]">
          {stack.map((entry, index) => (
            <React.Fragment key={entry.key}>
              {index > 0 ? <ChevronRight className="size-4 shrink-0" /> : null}
              <button
                type="button"
                className="shrink-0 rounded-full bg-black/5 px-3 py-1.5 font-medium hover:bg-black/8"
                onClick={() => {
                  const next = stack.slice(0, index + 1);
                  setStack(next);
                  setSelectedItemKey(itemKey(next[next.length - 1]?.items?.[0]));
                }}
              >
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
            <h3 className="mt-2 text-2xl font-semibold">{currentContainer?.title || payload?.workspace?.scenario.title}</h3>
          </div>
          <Button variant="secondary" size="sm">Добавить</Button>
        </div>

        <ScrollArea className="min-h-0 flex-1">
          <div className="grid gap-3 pr-3">
            {currentItems.map((item, index) => {
              const canOpen = !!buildChildContainer(item);
              const active = itemKey(item) === selectedItemKey;
              return (
                <article
                  key={itemKey(item) || `${currentContainer?.key}-${index}`}
                  className={`grid gap-3 rounded-2xl border p-4 transition ${active ? "border-[color:var(--color-accent)] bg-[var(--color-panel-muted)] shadow-sm" : "border-[var(--color-border)] bg-white"}`}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="space-y-1">
                      <h4 className="text-base font-semibold">{itemTitle(item, index)}</h4>
                      <p className="text-sm leading-5 text-[var(--color-muted-foreground)]">{summarizeItem(item)}</p>
                    </div>
                    <button
                      type="button"
                      className="rounded-xl border border-[var(--color-border)] px-3 py-2 text-xs font-semibold"
                      onClick={() => setSelectedItemKey(itemKey(item))}
                    >
                      Выбрать
                    </button>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex flex-wrap gap-2 text-xs font-medium text-[var(--color-muted-foreground)]">
                      <span className="rounded-full bg-black/5 px-2.5 py-1">{item.kind === "branch_slot" ? "Ветка" : item.response_label}</span>
                      {"button_options" in item && item.button_options.length ? (
                        <span className="rounded-full bg-black/5 px-2.5 py-1">Кнопки: {item.button_options.length}</span>
                      ) : null}
                    </div>
                    {canOpen ? (
                      <Button variant="ghost" size="sm" onClick={() => {
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

      <section className="flex min-h-0 flex-col rounded-[28px] border border-[var(--color-border)] bg-[var(--color-panel)] p-5 shadow-[var(--shadow-soft)]">
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--color-muted-foreground)]">Детали</p>
            <h3 className="mt-2 text-2xl font-semibold">
              {selectedItem ? itemTitle(selectedItem, 0) : "Выбери элемент"}
            </h3>
          </div>
          <PencilLine className="mt-1 size-5 text-[var(--color-muted-foreground)]" />
        </div>
        <Separator />
        <ScrollArea className="min-h-0 flex-1 pt-4">
          {selectedItem ? (
            <div className="space-y-5 pr-3">
              <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-panel-muted)] p-4">
                <p className="text-sm leading-6 text-[var(--color-muted-foreground)]">{summarizeItem(selectedItem)}</p>
              </section>
              <section className="grid gap-3">
                <label className="grid gap-2">
                  <span className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--color-muted-foreground)]">Название</span>
                  <Input defaultValue={selectedItem.kind === "branch_slot" ? selectedItem.step?.title || selectedItem.label : selectedItem.title} />
                </label>
                <label className="grid gap-2">
                  <span className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--color-muted-foreground)]">Текст</span>
                  <textarea className="min-h-[180px] rounded-2xl border border-[var(--color-border)] bg-white px-4 py-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)]/30" defaultValue={selectedItem.kind === "branch_slot" ? selectedItem.step?.text_preview || "" : selectedItem.text_preview} />
                </label>
              </section>
              <section className="rounded-2xl border border-dashed border-[var(--color-border)] p-4 text-sm text-[var(--color-muted-foreground)]">
                Дальше сюда перенесём полноценные controls шага, уведомления, emoji, вложения и smart recipients на shadcn-стеке.
              </section>
            </div>
          ) : (
            <div className="rounded-2xl border border-dashed border-[var(--color-border)] p-4 text-sm text-[var(--color-muted-foreground)]">
              Выбери шаг, ветку или элемент цепочки, чтобы увидеть детали справа.
            </div>
          )}
        </ScrollArea>
      </section>
    </div>
  );
}

if (rootElement) {
  ReactDOM.createRoot(rootElement).render(<App />);
}
