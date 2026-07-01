import React from "react";
import { Plus, Save, Trash2, X } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { ConfirmAction } from "@/components/ui/confirm-action";
import { Field, FieldContent, FieldGroup, FieldLabel, FieldTitle } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";

type ScenarioOption = {
  id: number;
  scenario_key: string;
  title: string;
  scenario_kind: string;
};

type MenuButton = {
  id: number;
  menu_set_id: number;
  label: string;
  sort_order: number;
  action_type: string;
  scenario_key: string;
  target_menu_set_id: number | null;
  document_item_id: number | null;
};

type MenuSet = {
  id: number;
  title: string;
  description: string;
  sort_order: number;
  role_scope: string;
  employee_scope: string;
  target_employee_ids: number[];
  buttons: MenuButton[];
};

type HrSettings = {
  default_menu_set_id: number | null;
};

type Workspace = {
  hr_settings: HrSettings;
  menu_role_scope_labels?: Record<string, string>;
  menu_employee_scope_labels?: Record<string, string>;
  menu_sets: MenuSet[];
  available_scenarios: ScenarioOption[];
  document_options?: SelectOption[];
  employee_options?: { id: number; label: string; audience: "employee" | "candidate" }[];
};

type DraftButton = {
  label: string;
  action_type: string;
  scenario_key: string;
  target_menu_set_id: string;
  document_item_id: string;
};

type SelectOption = {
  value: string;
  label: string;
};

export type BotMenuPageProps = {
  apiUrl: string;
};

const EMPTY_SELECT_VALUE = "__empty__";

const actionTypeOptions = [
  { value: "inactive", label: "Неактивна" },
  { value: "launch_scenario", label: "Запуск сценария" },
  { value: "open_set", label: "Переход к набору" },
  { value: "send_document", label: "Отправить документ" },
];

async function requestJson(path: string, options: RequestInit = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(options.headers || {}),
    },
    ...options,
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || "Запрос не выполнен");
  }
  return response.json() as Promise<Workspace>;
}

async function requestBroadcast(path: string, options: RequestInit = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(options.headers || {}),
    },
    ...options,
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || "Запрос не выполнен");
  }
  return response.json() as Promise<{ workspace: Workspace; refreshed_count: number }>;
}

function normalizeWorkspace(workspace: Workspace): Workspace {
  return {
    ...workspace,
    hr_settings: workspace.hr_settings || { default_menu_set_id: null },
    menu_role_scope_labels: workspace.menu_role_scope_labels || { all: "Для всех ролей" },
    menu_employee_scope_labels:
      workspace.menu_employee_scope_labels || {
        all: "Для всех сотрудников и кандидатов",
        employees: "Для всех сотрудников",
        candidates: "Для всех кандидатов",
      },
    employee_options: workspace.employee_options || [],
    document_options: workspace.document_options || [],
    menu_sets: (workspace.menu_sets || []).map((menuSet) => ({
      ...menuSet,
      role_scope: menuSet.role_scope || "all",
      employee_scope: menuSet.employee_scope || "all",
      target_employee_ids: (menuSet.target_employee_ids || [])
        .map((value) => Number(value))
        .filter((value) => Number.isInteger(value) && value > 0),
      buttons: menuSet.buttons || [],
    })),
  };
}

function cloneWorkspace(workspace: Workspace): Workspace {
  return {
    ...workspace,
    hr_settings: { ...workspace.hr_settings },
    menu_sets: workspace.menu_sets.map((menuSet) => ({
      ...menuSet,
      target_employee_ids: [...menuSet.target_employee_ids],
      buttons: menuSet.buttons.map((button) => ({ ...button })),
    })),
  };
}

function AppSelect({
  value,
  onChange,
  options,
  placeholder = "Не выбрано",
  allowEmpty = true,
  disabled,
}: {
  value: string;
  onChange: (value: string) => void;
  options: SelectOption[];
  placeholder?: string;
  allowEmpty?: boolean;
  disabled?: boolean;
}) {
  const items = allowEmpty ? [{ value: EMPTY_SELECT_VALUE, label: placeholder }].concat(options) : options;
  const currentValue = value || (allowEmpty ? EMPTY_SELECT_VALUE : options[0]?.value || "");

  return (
    <Select
      items={items}
      value={currentValue}
      onValueChange={(nextValue) => {
        const normalizedValue = String(nextValue);
        onChange(normalizedValue === EMPTY_SELECT_VALUE ? "" : normalizedValue);
      }}
    >
      <SelectTrigger className="w-full" disabled={disabled}>
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent align="start" alignItemWithTrigger={false}>
        <SelectGroup>
          {items.map((item) => (
            <SelectItem value={item.value} key={item.value}>
              {item.label}
            </SelectItem>
          ))}
        </SelectGroup>
      </SelectContent>
    </Select>
  );
}

function StatusAlert({ message, type }: { message: string; type: "success" | "error" }) {
  if (!message) return null;
  return (
    <Alert
      variant={type === "error" ? "destructive" : "default"}
      className={type === "success" ? "border-primary/30 bg-primary/5" : undefined}
    >
      <AlertTitle>{type === "success" ? "Сохранено" : "Ошибка"}</AlertTitle>
      <AlertDescription>{message}</AlertDescription>
    </Alert>
  );
}

function SettingsCard({
  title,
  description,
  children,
  className,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <Card className={cn("border border-border/80 bg-card shadow-none ring-0", className)}>
      <CardHeader className="border-b border-border/70 pb-4">
        <CardTitle className="text-base font-semibold">{title}</CardTitle>
        {description ? <CardDescription>{description}</CardDescription> : null}
      </CardHeader>
      <CardContent className="grid gap-5 pt-5">{children}</CardContent>
    </Card>
  );
}

function MultiCheckboxField({
  label,
  options,
  values,
  onChange,
}: {
  label: string;
  options: SelectOption[];
  values: string[];
  onChange: (values: string[]) => void;
}) {
  return (
    <Field>
      <FieldLabel>{label}</FieldLabel>
      <div className="rounded-lg border border-border bg-muted/35 p-3">
        <div className="grid gap-2 sm:grid-cols-2">
          {options.map((option) => {
            const checked = values.includes(option.value);
            return (
              <Field orientation="horizontal" key={option.value}>
                <Checkbox
                  checked={checked}
                  onCheckedChange={() =>
                    onChange(
                      checked ? values.filter((value) => value !== option.value) : values.concat(option.value),
                    )
                  }
                />
                <FieldContent>
                  <FieldTitle>{option.label}</FieldTitle>
                </FieldContent>
              </Field>
            );
          })}
        </div>
      </div>
    </Field>
  );
}

function menuSetOptions(menuSets: MenuSet[]): SelectOption[] {
  return menuSets.map((menuSet) => ({ value: String(menuSet.id), label: menuSet.title }));
}

function selectedEmployeeIdsByOtherMenuSets(workspace: Workspace, currentMenuSetId: number): Set<number> {
  const taken = new Set<number>();
  for (const menuSet of workspace.menu_sets) {
    if (menuSet.id === currentMenuSetId) continue;
    for (const employeeId of menuSet.target_employee_ids) {
      taken.add(employeeId);
    }
  }
  return taken;
}

function filterEmployeeOptions(
  workspace: Workspace,
  menuSet: MenuSet,
): { id: number; label: string; audience: "employee" | "candidate" }[] {
  const taken = selectedEmployeeIdsByOtherMenuSets(workspace, menuSet.id);
  return (workspace.employee_options || []).filter((item) => {
    if (taken.has(item.id) && !menuSet.target_employee_ids.includes(item.id)) {
      return false;
    }
    if (menuSet.employee_scope === "employees" && item.audience !== "employee") {
      return false;
    }
    if (menuSet.employee_scope === "candidates" && item.audience !== "candidate") {
      return false;
    }
    return true;
  });
}

function resolveSelectedEmployees(
  workspace: Workspace,
  menuSet: MenuSet,
): { id: number; label: string; audience: "employee" | "candidate" }[] {
  const byId = new Map((workspace.employee_options || []).map((item) => [item.id, item]));
  return menuSet.target_employee_ids
    .map((id) => byId.get(id))
    .filter((item): item is { id: number; label: string; audience: "employee" | "candidate" } => Boolean(item));
}

function EmployeeTargetSelect({
  workspace,
  menuSet,
  onChange,
}: {
  workspace: Workspace;
  menuSet: MenuSet;
  onChange: (ids: number[]) => void;
}) {
  const [query, setQuery] = React.useState("");
  const options = React.useMemo(() => filterEmployeeOptions(workspace, menuSet), [workspace, menuSet]);
  const selected = React.useMemo(() => resolveSelectedEmployees(workspace, menuSet), [workspace, menuSet]);
  const filtered = React.useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    if (!normalizedQuery) return options;
    return options.filter((item) => item.label.toLowerCase().includes(normalizedQuery));
  }, [options, query]);

  return (
    <Field className="lg:col-span-2">
      <FieldLabel>Конкретные сотрудники и кандидаты</FieldLabel>
      <Popover>
        <PopoverTrigger
          render={
            <button
              type="button"
              className={cn(
                "flex min-h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-left text-sm shadow-xs transition-[color,box-shadow] outline-none hover:bg-accent/30",
                "focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px]",
              )}
            />
          }
        >
          <span className={selected.length ? "text-foreground" : "text-muted-foreground"}>
            {selected.length ? `Выбрано: ${selected.length}` : "Никто не выбран"}
          </span>
        </PopoverTrigger>
        <PopoverContent className="w-[var(--anchor-width)] max-w-[420px]">
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Поиск сотрудника или кандидата"
            autoComplete="off"
          />
          <ScrollArea className="max-h-64 rounded-md border border-border/70">
            <div className="grid gap-1 p-2">
              {filtered.length ? (
                filtered.map((item) => {
                  const checked = menuSet.target_employee_ids.includes(item.id);
                  return (
                    <Field orientation="horizontal" key={item.id} className="rounded-md px-2 py-1.5 hover:bg-muted/50">
                      <Checkbox
                        checked={checked}
                        onCheckedChange={() =>
                          onChange(
                            checked
                              ? menuSet.target_employee_ids.filter((value) => value !== item.id)
                              : menuSet.target_employee_ids.concat(item.id),
                          )
                        }
                      />
                      <FieldContent>
                        <FieldTitle>{item.label}</FieldTitle>
                      </FieldContent>
                    </Field>
                  );
                })
              ) : (
                <div className="px-2 py-3 text-sm text-muted-foreground">Совпадений нет</div>
              )}
            </div>
          </ScrollArea>
        </PopoverContent>
      </Popover>
      {selected.length ? (
        <div className="mt-2 flex flex-wrap gap-2">
          {selected.map((item) => (
            <Badge key={item.id} variant="outline" className="h-auto gap-1 py-1">
              <span>{item.label}</span>
              <button
                type="button"
                className="rounded-full p-0.5 text-muted-foreground hover:bg-muted hover:text-foreground"
                aria-label={`Убрать ${item.label}`}
                onClick={() => onChange(menuSet.target_employee_ids.filter((value) => value !== item.id))}
              >
                <X className="size-3.5" />
              </button>
            </Badge>
          ))}
        </div>
      ) : null}
    </Field>
  );
}

function scenarioOptions(scenarios: ScenarioOption[]): SelectOption[] {
  return scenarios.map((scenario) => ({ value: scenario.scenario_key, label: scenario.title }));
}

function labelOptions(labels: Record<string, string>) {
  return Object.entries(labels).map(([value, label]) => ({ value, label }));
}

export function BotMenuPage({ apiUrl }: BotMenuPageProps) {
  const [workspace, setWorkspace] = React.useState<Workspace | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [message, setMessage] = React.useState("");
  const [error, setError] = React.useState("");
  const [newMenuSetTitle, setNewMenuSetTitle] = React.useState("");
  const [buttonDrafts, setButtonDrafts] = React.useState<Record<number, DraftButton>>({});

  React.useEffect(() => {
    requestJson(apiUrl)
      .then((payload) => setWorkspace(normalizeWorkspace(payload)))
      .catch((err) => setError(err instanceof Error ? err.message : "Не удалось загрузить меню бота"))
      .finally(() => setLoading(false));
  }, [apiUrl]);

  const setWorkspaceFromApi = async (promise: Promise<Workspace>, successMessage: string) => {
    setError("");
    setMessage("");
    try {
      const nextWorkspace = await promise;
      setWorkspace(normalizeWorkspace(nextWorkspace));
      setMessage(successMessage);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Операция не выполнена");
    }
  };

  const updateMenuSetLocal = (menuSetId: number, patch: Partial<MenuSet>) => {
    setWorkspace((current) => {
      if (!current) return current;
      const next = cloneWorkspace(current);
      next.menu_sets = next.menu_sets.map((menuSet) => (menuSet.id === menuSetId ? { ...menuSet, ...patch } : menuSet));
      return next;
    });
  };

  const updateHrSettingsLocal = (patch: Partial<HrSettings>) => {
    setWorkspace((current) => {
      if (!current) return current;
      const next = cloneWorkspace(current);
      next.hr_settings = { ...next.hr_settings, ...patch };
      return next;
    });
  };

  const updateMenuButtonLocal = (buttonId: number, patch: Partial<MenuButton>) => {
    setWorkspace((current) => {
      if (!current) return current;
      const next = cloneWorkspace(current);
      next.menu_sets = next.menu_sets.map((menuSet) => ({
        ...menuSet,
        buttons: menuSet.buttons.map((button) => (button.id === buttonId ? { ...button, ...patch } : button)),
      }));
      return next;
    });
  };

  if (loading) {
    return (
      <Card className="admin-page-shell border border-border/80 bg-card shadow-none ring-0">
        <CardContent className="p-8 text-sm text-muted-foreground">Загружаю меню бота...</CardContent>
      </Card>
    );
  }

  if (!workspace) {
    return (
      <div className="admin-page-stack gap-4">
        <StatusAlert type="error" message={error || "Меню бота не загружено"} />
      </div>
    );
  }

  const menuOptions = menuSetOptions(workspace.menu_sets);
  const scenarios = scenarioOptions(workspace.available_scenarios);
  const menuRoleOptions = labelOptions(workspace.menu_role_scope_labels || { all: "Для всех ролей" });
  const menuEmployeeScopeOptions = labelOptions(
    workspace.menu_employee_scope_labels || {
      all: "Для всех сотрудников и кандидатов",
      employees: "Для всех сотрудников",
      candidates: "Для всех кандидатов",
    },
  );
  return (
    <div className="admin-page-stack gap-5">
      <header className="admin-page-surface border border-border/80 bg-card p-5 shadow-none ring-0">
        <h1 className="text-3xl font-semibold tracking-tight">Меню бота</h1>
      </header>

      <StatusAlert type="success" message={message} />
      <StatusAlert type="error" message={error} />

      <SettingsCard title="Наборы меню">
        <div className="grid gap-4 rounded-lg border border-border bg-muted/35 p-3 lg:grid-cols-[minmax(0,1fr)_auto_auto] lg:items-end">
          <Field>
            <FieldLabel>Главный набор меню</FieldLabel>
            <AppSelect
              value={workspace.hr_settings.default_menu_set_id ? String(workspace.hr_settings.default_menu_set_id) : ""}
              onChange={(value) => updateHrSettingsLocal({ default_menu_set_id: value ? Number(value) : null })}
              options={menuOptions}
              placeholder="Не выбран"
            />
          </Field>
          <Button
            variant="secondary"
            onClick={() =>
              setWorkspaceFromApi(
                requestJson("/api/settings/hr", {
                  method: "POST",
                  body: JSON.stringify(workspace.hr_settings),
                }),
                "Главный набор меню сохранён",
              )
            }
          >
            <Save data-icon="inline-start" />
            Сохранить главный набор
          </Button>
          <Button
            onClick={async () => {
              setError("");
              setMessage("");
              try {
                const result = await requestBroadcast("/api/settings/bot-menu/broadcast", { method: "POST" });
                setWorkspace(normalizeWorkspace(result.workspace));
                setMessage(`Главное меню отправлено ${result.refreshed_count} пользователям`);
              } catch (err) {
                setError(err instanceof Error ? err.message : "Не удалось обновить меню у пользователей");
              }
            }}
          >
            <Plus data-icon="inline-start" />
            Разослать главное меню
          </Button>
        </div>

        <div className="grid gap-3 rounded-lg border border-border bg-muted/35 p-3 md:grid-cols-[minmax(260px,1fr)_auto] md:items-end">
          <Field>
            <FieldLabel>Новый набор кнопок</FieldLabel>
            <Input value={newMenuSetTitle} onChange={(event) => setNewMenuSetTitle(event.target.value)} placeholder="Главное меню" autoComplete="off" />
          </Field>
          <Button
            onClick={() =>
              setWorkspaceFromApi(
                requestJson("/api/settings/menu-sets", { method: "POST", body: JSON.stringify({ title: newMenuSetTitle }) }),
                "Набор кнопок создан",
              ).then(() => setNewMenuSetTitle(""))
            }
          >
            <Plus data-icon="inline-start" />
            Создать
          </Button>
        </div>

        <div className="grid gap-4">
          {workspace.menu_sets.map((menuSet) => {
            const draft = buttonDrafts[menuSet.id] || { label: "", action_type: "inactive", scenario_key: "", target_menu_set_id: "", document_item_id: "" };
            return (
              <Card key={menuSet.id} size="sm" className="border border-border bg-background shadow-none ring-0">
                <CardHeader className="border-b border-border/70 pb-3">
                  <div className="grid gap-3 xl:grid-cols-[1fr_1fr_auto] xl:items-end">
                    <Field>
                      <FieldLabel>Название набора</FieldLabel>
                      <Input value={menuSet.title} onChange={(event) => updateMenuSetLocal(menuSet.id, { title: event.target.value })} autoComplete="off" />
                    </Field>
                    <Field>
                      <FieldLabel>Описание</FieldLabel>
                      <Input value={menuSet.description} onChange={(event) => updateMenuSetLocal(menuSet.id, { description: event.target.value })} autoComplete="off" />
                    </Field>
                    <div className="flex gap-2 xl:justify-end">
                      <Button variant="secondary" onClick={() => setWorkspaceFromApi(requestJson(`/api/settings/menu-sets/${menuSet.id}`, { method: "POST", body: JSON.stringify(menuSet) }), "Набор сохранен")}>
                        <Save data-icon="inline-start" />
                        Сохранить
                      </Button>
                      <ConfirmAction
                        title="Удалить набор меню?"
                        description="Набор и его кнопки будут удалены из меню бота. Это действие нельзя отменить."
                        onConfirm={() => setWorkspaceFromApi(requestJson(`/api/settings/menu-sets/${menuSet.id}`, { method: "DELETE" }), "Набор удален")}
                      >
                        <Button variant="outline" size="icon" aria-label="Удалить набор">
                          <Trash2 />
                        </Button>
                      </ConfirmAction>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="grid gap-3 pt-4">
                  <div className="grid gap-4 rounded-lg border border-border bg-muted/35 p-3 lg:grid-cols-2">
                    <Field>
                      <FieldLabel>Аудитория</FieldLabel>
                      <AppSelect
                        value={menuSet.employee_scope}
                        onChange={(value) => updateMenuSetLocal(menuSet.id, { employee_scope: value })}
                        options={menuEmployeeScopeOptions}
                        allowEmpty={false}
                      />
                    </Field>
                    <Field>
                      <FieldLabel>Должность</FieldLabel>
                      <AppSelect
                        value={menuSet.role_scope}
                        onChange={(value) => updateMenuSetLocal(menuSet.id, { role_scope: value })}
                        options={menuRoleOptions}
                        allowEmpty={false}
                        placeholder="Все должности"
                      />
                    </Field>
                    <EmployeeTargetSelect
                      workspace={workspace}
                      menuSet={menuSet}
                      onChange={(ids) => updateMenuSetLocal(menuSet.id, { target_employee_ids: ids })}
                    />
                  </div>

                  {menuSet.buttons.map((button) => (
                    <div key={button.id} className="grid gap-2 rounded-lg border border-border bg-muted/35 p-3 xl:grid-cols-[1.1fr_0.8fr_1fr_1fr_1fr_auto]">
                      <Input value={button.label} onChange={(event) => updateMenuButtonLocal(button.id, { label: event.target.value })} placeholder="Кнопка" autoComplete="off" />
                      <AppSelect value={button.action_type} onChange={(value) => updateMenuButtonLocal(button.id, { action_type: value })} options={actionTypeOptions} allowEmpty={false} />
                      <AppSelect value={button.scenario_key} onChange={(value) => updateMenuButtonLocal(button.id, { scenario_key: value })} options={scenarios} placeholder="Сценарий" />
                      <AppSelect value={button.target_menu_set_id ? String(button.target_menu_set_id) : ""} onChange={(value) => updateMenuButtonLocal(button.id, { target_menu_set_id: value ? Number(value) : null })} options={menuOptions} placeholder="Набор" />
                      <AppSelect value={button.document_item_id ? String(button.document_item_id) : ""} onChange={(value) => updateMenuButtonLocal(button.id, { document_item_id: value ? Number(value) : null })} options={workspace.document_options || []} placeholder="Документ" />
                      <div className="flex gap-2 xl:justify-end">
                        <Button variant="secondary" size="icon" aria-label="Сохранить кнопку" onClick={() => setWorkspaceFromApi(requestJson(`/api/settings/menu-buttons/${button.id}`, { method: "POST", body: JSON.stringify(button) }), "Кнопка сохранена")}>
                          <Save />
                        </Button>
                        <ConfirmAction
                          title="Удалить кнопку?"
                          description="Кнопка исчезнет из этого набора меню. Это действие нельзя отменить."
                          onConfirm={() => setWorkspaceFromApi(requestJson(`/api/settings/menu-buttons/${button.id}`, { method: "DELETE" }), "Кнопка удалена")}
                        >
                          <Button variant="outline" size="icon" aria-label="Удалить кнопку">
                            <Trash2 />
                          </Button>
                        </ConfirmAction>
                      </div>
                    </div>
                  ))}

                  <div className="grid gap-2 rounded-lg border border-dashed border-border p-3 xl:grid-cols-[1.1fr_0.8fr_1fr_1fr_1fr_auto]">
                    <Input value={draft.label} onChange={(event) => setButtonDrafts((current) => ({ ...current, [menuSet.id]: { ...draft, label: event.target.value } }))} placeholder="Новая кнопка" autoComplete="off" />
                    <AppSelect value={draft.action_type} onChange={(value) => setButtonDrafts((current) => ({ ...current, [menuSet.id]: { ...draft, action_type: value } }))} options={actionTypeOptions} allowEmpty={false} />
                    <AppSelect value={draft.scenario_key} onChange={(value) => setButtonDrafts((current) => ({ ...current, [menuSet.id]: { ...draft, scenario_key: value } }))} options={scenarios} placeholder="Сценарий" />
                    <AppSelect value={draft.target_menu_set_id} onChange={(value) => setButtonDrafts((current) => ({ ...current, [menuSet.id]: { ...draft, target_menu_set_id: value } }))} options={menuOptions} placeholder="Набор" />
                    <AppSelect value={draft.document_item_id} onChange={(value) => setButtonDrafts((current) => ({ ...current, [menuSet.id]: { ...draft, document_item_id: value } }))} options={workspace.document_options || []} placeholder="Документ" />
                    <Button
                      aria-label="Создать кнопку"
                      onClick={() =>
                        setWorkspaceFromApi(
                          requestJson(`/api/settings/menu-sets/${menuSet.id}/buttons`, { method: "POST", body: JSON.stringify(draft) }),
                          "Кнопка создана",
                        ).then(() => setButtonDrafts((current) => ({ ...current, [menuSet.id]: { label: "", action_type: "inactive", scenario_key: "", target_menu_set_id: "", document_item_id: "" } })))
                      }
                    >
                      <Plus data-icon="inline-start" />
                      Создать
                    </Button>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </SettingsCard>
    </div>
  );
}
