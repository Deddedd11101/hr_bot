import React from "react";
import { FolderOpen, Plus, Save, Trash2, X } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { ConfirmAction } from "@/components/ui/confirm-action";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Field, FieldContent, FieldGroup, FieldLabel, FieldTitle } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
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
  default_employee_menu_set_id: number | null;
  default_candidate_menu_set_id: number | null;
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
    hr_settings: workspace.hr_settings || {
      default_menu_set_id: null,
      default_employee_menu_set_id: null,
      default_candidate_menu_set_id: null,
    },
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

function rootMenuOptionsForAudience(menuSets: MenuSet[], audience: "all" | "employees" | "candidates"): SelectOption[] {
  return menuSets
    .filter((menuSet) => {
      const scope = menuSet.employee_scope || "all";
      if (audience === "employees") {
        return scope !== "candidates";
      }
      if (audience === "candidates") {
        return scope !== "employees";
      }
      return true;
    })
    .map((menuSet) => ({ value: String(menuSet.id), label: menuSet.title }));
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

function actionTypePatch(actionType: string) {
  return {
    action_type: actionType,
    scenario_key: "",
    target_menu_set_id: null,
    document_item_id: null,
  };
}

function draftActionTypePatch(actionType: string) {
  return {
    action_type: actionType,
    scenario_key: "",
    target_menu_set_id: "",
    document_item_id: "",
  };
}

function isScenarioAction(actionType: string) {
  return actionType === "launch_scenario";
}

function isOpenSetAction(actionType: string) {
  return actionType === "open_set";
}

function isSendDocumentAction(actionType: string) {
  return actionType === "send_document";
}

function readSelectedMenuSetId() {
  if (typeof window === "undefined") return null;
  const value = Number(new URLSearchParams(window.location.search).get("set_id"));
  return Number.isInteger(value) && value > 0 ? value : null;
}

function writeSelectedMenuSetId(menuSetId: number | null) {
  if (typeof window === "undefined") return;
  const url = new URL(window.location.href);
  if (menuSetId) {
    url.searchParams.set("set_id", String(menuSetId));
  } else {
    url.searchParams.delete("set_id");
  }
  window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
}

function menuSetTitle(workspace: Workspace, menuSetId: number | null) {
  if (!menuSetId) return "Не выбран";
  return workspace.menu_sets.find((menuSet) => menuSet.id === menuSetId)?.title || `Набор #${menuSetId}`;
}

function childMenuSets(workspace: Workspace, menuSetId: number) {
  const childIds = new Set(
    workspace.menu_sets
      .flatMap((menuSet) => menuSet.buttons)
      .filter((button) => button.action_type === "open_set" && button.menu_set_id === menuSetId && button.target_menu_set_id)
      .map((button) => Number(button.target_menu_set_id)),
  );
  return workspace.menu_sets.filter((menuSet) => childIds.has(menuSet.id));
}

function parentMenuSets(workspace: Workspace, menuSetId: number) {
  const parentIds = new Set(
    workspace.menu_sets
      .filter((menuSet) =>
        menuSet.buttons.some((button) => button.action_type === "open_set" && button.target_menu_set_id === menuSetId),
      )
      .map((menuSet) => menuSet.id),
  );
  return workspace.menu_sets.filter((menuSet) => parentIds.has(menuSet.id));
}

function rootBadges(workspace: Workspace, menuSetId: number) {
  const badges: string[] = [];
  if (workspace.hr_settings.default_employee_menu_set_id === menuSetId) badges.push("root сотрудников");
  if (workspace.hr_settings.default_candidate_menu_set_id === menuSetId) badges.push("root кандидатов");
  if (workspace.hr_settings.default_menu_set_id === menuSetId) badges.push("fallback");
  return badges;
}

export function BotMenuPage({ apiUrl }: BotMenuPageProps) {
  const [workspace, setWorkspace] = React.useState<Workspace | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [message, setMessage] = React.useState("");
  const [error, setError] = React.useState("");
  const [newMenuSetTitle, setNewMenuSetTitle] = React.useState("");
  const [createMenuSetOpen, setCreateMenuSetOpen] = React.useState(false);
  const [buttonDrafts, setButtonDrafts] = React.useState<Record<number, DraftButton>>({});
  const [selectedMenuSetId, setSelectedMenuSetId] = React.useState<number | null>(() => readSelectedMenuSetId());

  React.useEffect(() => {
    requestJson(apiUrl)
      .then((payload) => setWorkspace(normalizeWorkspace(payload)))
      .catch((err) => setError(err instanceof Error ? err.message : "Не удалось загрузить меню бота"))
      .finally(() => setLoading(false));
  }, [apiUrl]);

  React.useEffect(() => {
    if (!workspace || !selectedMenuSetId) return;
    if (!workspace.menu_sets.some((menuSet) => menuSet.id === selectedMenuSetId)) {
      setSelectedMenuSetId(null);
      writeSelectedMenuSetId(null);
    }
  }, [workspace, selectedMenuSetId]);

  const navigateToMenuSet = (menuSetId: number | null) => {
    setSelectedMenuSetId(menuSetId);
    writeSelectedMenuSetId(menuSetId);
  };

  const setWorkspaceFromApi = async (promise: Promise<Workspace>, successMessage: string) => {
    setError("");
    setMessage("");
    try {
      const nextWorkspace = await promise;
      setWorkspace(normalizeWorkspace(nextWorkspace));
      setMessage(successMessage);
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Операция не выполнена");
      return false;
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

  const saveMenuSet = async (menuSet: MenuSet) => {
    setError("");
    setMessage("");
    try {
      let nextWorkspace = await requestJson(`/api/settings/menu-sets/${menuSet.id}`, {
        method: "POST",
        body: JSON.stringify(menuSet),
      });
      for (const button of menuSet.buttons) {
        nextWorkspace = await requestJson(`/api/settings/menu-buttons/${button.id}`, {
          method: "POST",
          body: JSON.stringify(button),
        });
      }
      setWorkspace(normalizeWorkspace(nextWorkspace));
      setMessage("Изменения набора сохранены");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось сохранить набор");
    }
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
  const selectedMenuSet = selectedMenuSetId
    ? workspace.menu_sets.find((menuSet) => menuSet.id === selectedMenuSetId) || null
    : null;
  const employeeRootMenuOptions = rootMenuOptionsForAudience(workspace.menu_sets, "employees");
  const candidateRootMenuOptions = rootMenuOptionsForAudience(workspace.menu_sets, "candidates");
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
    <>
      <PageHeader title="Меню бота" />
      <div className="admin-page-stack gap-5">

      <StatusAlert type="success" message={message} />
      <StatusAlert type="error" message={error} />

      <SettingsCard title={selectedMenuSet ? selectedMenuSet.title || "Набор меню" : "Наборы меню"}>
        <div className="grid gap-4 rounded-lg border border-border bg-muted/35 p-3 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_auto_auto] xl:items-end">
          <Field>
            <FieldLabel>Общий fallback-набор</FieldLabel>
            <AppSelect
              value={workspace.hr_settings.default_menu_set_id ? String(workspace.hr_settings.default_menu_set_id) : ""}
              onChange={(value) =>
                updateHrSettingsLocal({ default_menu_set_id: value ? Number(value) : null })
              }
              options={menuOptions}
              placeholder="Автовыбор по аудитории"
            />
          </Field>
          <Field>
            <FieldLabel>Главный набор для сотрудников</FieldLabel>
            <AppSelect
              value={workspace.hr_settings.default_employee_menu_set_id ? String(workspace.hr_settings.default_employee_menu_set_id) : ""}
              onChange={(value) =>
                updateHrSettingsLocal({ default_employee_menu_set_id: value ? Number(value) : null })
              }
              options={employeeRootMenuOptions}
              placeholder="Не выбран"
            />
          </Field>
          <Field>
            <FieldLabel>Главный набор для кандидатов</FieldLabel>
            <AppSelect
              value={workspace.hr_settings.default_candidate_menu_set_id ? String(workspace.hr_settings.default_candidate_menu_set_id) : ""}
              onChange={(value) =>
                updateHrSettingsLocal({ default_candidate_menu_set_id: value ? Number(value) : null })
              }
              options={candidateRootMenuOptions}
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
                "Настройки главного меню сохранены",
              )
            }
          >
            <Save data-icon="inline-start" />
            Сохранить root-меню
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
            Разослать актуальные root-меню
          </Button>
        </div>
        <div className="rounded-lg border border-border/70 bg-background px-3 py-2 text-sm text-muted-foreground">
          Для кандидатов и сотрудников можно задать разные главные меню. Если профильный root не указан, бот попробует взять общий fallback-набор, а затем подобрать подходящий набор по аудитории автоматически.
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex min-w-0 items-center gap-2 text-sm text-muted-foreground">
            {selectedMenuSet ? (
              <>
                {/* Тот же ключ, что у шапок деталей: крошка вместо кнопки «назад». */}
                <Button variant="ghost" size="sm" onClick={() => navigateToMenuSet(null)}>
                  Все наборы
                </Button>
                <span aria-hidden="true">/</span>
                <span className="truncate text-foreground">{selectedMenuSet.title}</span>
              </>
            ) : (
              <span>Выбери набор, чтобы редактировать его отдельно от общей карты меню.</span>
            )}
          </div>
          <Dialog open={createMenuSetOpen} onOpenChange={setCreateMenuSetOpen}>
            <DialogTrigger render={<Button />}>
              <Plus data-icon="inline-start" />
              Создать набор
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Создать набор кнопок</DialogTitle>
                <DialogDescription>Название можно изменить после создания.</DialogDescription>
              </DialogHeader>
              <Field>
                <FieldLabel>Название</FieldLabel>
                <Input value={newMenuSetTitle} onChange={(event) => setNewMenuSetTitle(event.target.value)} placeholder="Главное меню" autoComplete="off" />
              </Field>
              <DialogFooter>
                <Button
                  disabled={!newMenuSetTitle.trim()}
                  onClick={() =>
                    setWorkspaceFromApi(
                      requestJson("/api/settings/menu-sets", { method: "POST", body: JSON.stringify({ title: newMenuSetTitle }) }),
                      "Набор кнопок создан",
                    ).then((created) => {
                      if (!created) return;
                      setNewMenuSetTitle("");
                      setCreateMenuSetOpen(false);
                    })
                  }
                >
                  Создать
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>

        {selectedMenuSet ? (
          <div className="grid gap-4 xl:grid-cols-[280px_minmax(0,1fr)]">
            <Card size="sm" className="border border-border bg-background shadow-none ring-0">
              <CardHeader className="border-b border-border/70 pb-3">
                <CardTitle className="text-sm font-semibold">Навигация</CardTitle>
              </CardHeader>
              <CardContent className="grid gap-3 pt-3">
                <Button variant="secondary" className="justify-start" onClick={() => navigateToMenuSet(null)}>
                  <FolderOpen data-icon="inline-start" />
                  Все наборы
                </Button>
                <div className="grid gap-2">
                  <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Родители</div>
                  {parentMenuSets(workspace, selectedMenuSet.id).length ? (
                    parentMenuSets(workspace, selectedMenuSet.id).map((menuSet) => (
                      <Button key={menuSet.id} variant="ghost" className="justify-start" onClick={() => navigateToMenuSet(menuSet.id)}>
                        {menuSet.title}
                      </Button>
                    ))
                  ) : (
                    <div className="rounded-lg border border-dashed border-border px-3 py-2 text-sm text-muted-foreground">
                      В этот набор пока никто не ведет.
                    </div>
                  )}
                </div>
                <div className="grid gap-2">
                  <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Вложенные наборы</div>
                  {childMenuSets(workspace, selectedMenuSet.id).length ? (
                    childMenuSets(workspace, selectedMenuSet.id).map((menuSet) => (
                      <Button key={menuSet.id} variant="ghost" className="justify-start" onClick={() => navigateToMenuSet(menuSet.id)}>
                        {menuSet.title}
                      </Button>
                    ))
                  ) : (
                    <div className="rounded-lg border border-dashed border-border px-3 py-2 text-sm text-muted-foreground">
                      Вложенных наборов нет.
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>

            <Card size="sm" className="border border-border bg-background shadow-none ring-0">
              <CardHeader className="border-b border-border/70 pb-3">
                <div className="grid gap-3 xl:grid-cols-[1fr_1fr_auto] xl:items-end">
                  <Field>
                    <FieldLabel>Название набора</FieldLabel>
                    <Input
                      value={selectedMenuSet.title}
                      onChange={(event) => updateMenuSetLocal(selectedMenuSet.id, { title: event.target.value })}
                      autoComplete="off"
                    />
                  </Field>
                  <Field>
                    <FieldLabel>Описание</FieldLabel>
                    <Input
                      value={selectedMenuSet.description}
                      onChange={(event) => updateMenuSetLocal(selectedMenuSet.id, { description: event.target.value })}
                      autoComplete="off"
                    />
                  </Field>
                  <div className="flex gap-2 xl:justify-end">
                    <Button variant="secondary" onClick={() => saveMenuSet(selectedMenuSet)}>
                      <Save data-icon="inline-start" />
                      Сохранить
                    </Button>
                    <ConfirmAction
                      title="Удалить набор меню?"
                      description="Набор и его кнопки будут удалены из меню бота. Это действие нельзя отменить."
                      onConfirm={() =>
                        setWorkspaceFromApi(
                          requestJson(`/api/settings/menu-sets/${selectedMenuSet.id}`, { method: "DELETE" }),
                          "Набор удален",
                        ).then((deleted) => {
                          if (deleted) navigateToMenuSet(null);
                        })
                      }
                    >
                      <Button variant="outline" size="icon" aria-label="Удалить набор">
                        <Trash2 />
                      </Button>
                    </ConfirmAction>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="grid gap-4 pt-4">
                <div className="flex flex-wrap gap-2">
                  {rootBadges(workspace, selectedMenuSet.id).map((badge) => (
                    <Badge key={badge} variant="secondary">
                      {badge}
                    </Badge>
                  ))}
                  <Badge variant="outline">{selectedMenuSet.buttons.length} кнопок</Badge>
                  <Badge variant="outline">{childMenuSets(workspace, selectedMenuSet.id).length} вложенных наборов</Badge>
                </div>

                <div className="grid gap-4 rounded-lg border border-border bg-muted/35 p-3 lg:grid-cols-2">
                  <Field>
                    <FieldLabel>Аудитория</FieldLabel>
                    <AppSelect
                      value={selectedMenuSet.employee_scope}
                      onChange={(value) => updateMenuSetLocal(selectedMenuSet.id, { employee_scope: value })}
                      options={menuEmployeeScopeOptions}
                      allowEmpty={false}
                    />
                  </Field>
                  <Field>
                    <FieldLabel>Должность</FieldLabel>
                    <AppSelect
                      value={selectedMenuSet.role_scope}
                      onChange={(value) => updateMenuSetLocal(selectedMenuSet.id, { role_scope: value })}
                      options={menuRoleOptions}
                      allowEmpty={false}
                      placeholder="Все должности"
                    />
                  </Field>
                  <EmployeeTargetSelect
                    workspace={workspace}
                    menuSet={selectedMenuSet}
                    onChange={(ids) => updateMenuSetLocal(selectedMenuSet.id, { target_employee_ids: ids })}
                  />
                </div>

                <div className="grid gap-3">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <h3 className="text-base font-semibold">Кнопки набора</h3>
                      <p className="text-sm text-muted-foreground">Редактируется только текущая “папка”, без раскрытия всех меню сразу.</p>
                    </div>
                  </div>

                  {selectedMenuSet.buttons.length ? (
                    selectedMenuSet.buttons.map((button) => (
                      <div key={button.id} className="grid gap-3 rounded-lg border border-border bg-muted/35 p-3">
                        <div className="grid gap-3 xl:grid-cols-[1.1fr_0.8fr_auto] xl:items-end">
                          <Field>
                            <FieldLabel>Название кнопки</FieldLabel>
                            <Input
                              value={button.label}
                              onChange={(event) => updateMenuButtonLocal(button.id, { label: event.target.value })}
                              placeholder="Кнопка"
                              autoComplete="off"
                            />
                          </Field>
                          <Field>
                            <FieldLabel>Действие</FieldLabel>
                            <AppSelect
                              value={button.action_type}
                              onChange={(value) => updateMenuButtonLocal(button.id, actionTypePatch(value))}
                              options={actionTypeOptions}
                              allowEmpty={false}
                            />
                          </Field>
                          <div className="flex gap-2 xl:justify-end">
                            {isOpenSetAction(button.action_type) && button.target_menu_set_id ? (
                              <Button variant="secondary" onClick={() => navigateToMenuSet(Number(button.target_menu_set_id))}>
                                Открыть набор
                              </Button>
                            ) : null}
                            <ConfirmAction
                              title="Удалить кнопку?"
                              description="Кнопка исчезнет из этого набора меню. Это действие нельзя отменить."
                              onConfirm={() =>
                                setWorkspaceFromApi(
                                  requestJson(`/api/settings/menu-buttons/${button.id}`, { method: "DELETE" }),
                                  "Кнопка удалена",
                                )
                              }
                            >
                              <Button variant="outline" size="icon" aria-label="Удалить кнопку">
                                <Trash2 />
                              </Button>
                            </ConfirmAction>
                          </div>
                        </div>
                        <div className="grid gap-3 xl:grid-cols-3">
                          <Field>
                            <FieldLabel>Сценарий</FieldLabel>
                            <AppSelect
                              value={button.scenario_key}
                              onChange={(value) => updateMenuButtonLocal(button.id, { scenario_key: value })}
                              options={scenarios}
                              placeholder={isScenarioAction(button.action_type) ? "Сценарий" : "Недоступно для этого действия"}
                              disabled={!isScenarioAction(button.action_type)}
                            />
                          </Field>
                          <Field>
                            <FieldLabel>Набор для перехода</FieldLabel>
                            <AppSelect
                              value={button.target_menu_set_id ? String(button.target_menu_set_id) : ""}
                              onChange={(value) => updateMenuButtonLocal(button.id, { target_menu_set_id: value ? Number(value) : null })}
                              options={menuOptions}
                              placeholder={isOpenSetAction(button.action_type) ? "Набор" : "Недоступно для этого действия"}
                              disabled={!isOpenSetAction(button.action_type)}
                            />
                          </Field>
                          <Field>
                            <FieldLabel>Документ</FieldLabel>
                            <AppSelect
                              value={button.document_item_id ? String(button.document_item_id) : ""}
                              onChange={(value) => updateMenuButtonLocal(button.id, { document_item_id: value ? Number(value) : null })}
                              options={workspace.document_options || []}
                              placeholder={isSendDocumentAction(button.action_type) ? "Документ" : "Недоступно для этого действия"}
                              disabled={!isSendDocumentAction(button.action_type)}
                            />
                          </Field>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="rounded-lg border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
                      В этом наборе пока нет кнопок.
                    </div>
                  )}

                  {(() => {
                    const draft =
                      buttonDrafts[selectedMenuSet.id] || {
                        label: "",
                        action_type: "inactive",
                        scenario_key: "",
                        target_menu_set_id: "",
                        document_item_id: "",
                      };
                    return (
                      <div className="grid gap-3 rounded-lg border border-dashed border-border p-3">
                        <div className="grid gap-3 xl:grid-cols-[1.1fr_0.8fr_auto] xl:items-end">
                          <Field>
                            <FieldLabel>Новая кнопка</FieldLabel>
                            <Input
                              value={draft.label}
                              onChange={(event) =>
                                setButtonDrafts((current) => ({
                                  ...current,
                                  [selectedMenuSet.id]: { ...draft, label: event.target.value },
                                }))
                              }
                              placeholder="Новая кнопка"
                              autoComplete="off"
                            />
                          </Field>
                          <Field>
                            <FieldLabel>Действие</FieldLabel>
                            <AppSelect
                              value={draft.action_type}
                              onChange={(value) =>
                                setButtonDrafts((current) => ({
                                  ...current,
                                  [selectedMenuSet.id]: { ...draft, ...draftActionTypePatch(value) },
                                }))
                              }
                              options={actionTypeOptions}
                              allowEmpty={false}
                            />
                          </Field>
                          <Button
                            aria-label="Создать кнопку"
                            onClick={() =>
                              setWorkspaceFromApi(
                                requestJson(`/api/settings/menu-sets/${selectedMenuSet.id}/buttons`, {
                                  method: "POST",
                                  body: JSON.stringify(draft),
                                }),
                                "Кнопка создана",
                              ).then((created) => {
                                if (!created) return;
                                setButtonDrafts((current) => ({
                                  ...current,
                                  [selectedMenuSet.id]: {
                                    label: "",
                                    action_type: "inactive",
                                    scenario_key: "",
                                    target_menu_set_id: "",
                                    document_item_id: "",
                                  },
                                }));
                              })
                            }
                          >
                            <Plus data-icon="inline-start" />
                            Создать
                          </Button>
                        </div>
                        <div className="grid gap-3 xl:grid-cols-3">
                          <Field>
                            <FieldLabel>Сценарий</FieldLabel>
                            <AppSelect
                              value={draft.scenario_key}
                              onChange={(value) =>
                                setButtonDrafts((current) => ({
                                  ...current,
                                  [selectedMenuSet.id]: { ...draft, scenario_key: value },
                                }))
                              }
                              options={scenarios}
                              placeholder={isScenarioAction(draft.action_type) ? "Сценарий" : "Недоступно для этого действия"}
                              disabled={!isScenarioAction(draft.action_type)}
                            />
                          </Field>
                          <Field>
                            <FieldLabel>Набор для перехода</FieldLabel>
                            <AppSelect
                              value={draft.target_menu_set_id}
                              onChange={(value) =>
                                setButtonDrafts((current) => ({
                                  ...current,
                                  [selectedMenuSet.id]: { ...draft, target_menu_set_id: value },
                                }))
                              }
                              options={menuOptions}
                              placeholder={isOpenSetAction(draft.action_type) ? "Набор" : "Недоступно для этого действия"}
                              disabled={!isOpenSetAction(draft.action_type)}
                            />
                          </Field>
                          <Field>
                            <FieldLabel>Документ</FieldLabel>
                            <AppSelect
                              value={draft.document_item_id}
                              onChange={(value) =>
                                setButtonDrafts((current) => ({
                                  ...current,
                                  [selectedMenuSet.id]: { ...draft, document_item_id: value },
                                }))
                              }
                              options={workspace.document_options || []}
                              placeholder={isSendDocumentAction(draft.action_type) ? "Документ" : "Недоступно для этого действия"}
                              disabled={!isSendDocumentAction(draft.action_type)}
                            />
                          </Field>
                        </div>
                      </div>
                    );
                  })()}
                </div>
              </CardContent>
            </Card>
          </div>
        ) : (
          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
            <div className="grid gap-3 sm:grid-cols-2">
              {workspace.menu_sets.map((menuSet) => {
                const childCount = childMenuSets(workspace, menuSet.id).length;
                const parentCount = parentMenuSets(workspace, menuSet.id).length;
                return (
                  <button
                    key={menuSet.id}
                    type="button"
                    onClick={() => navigateToMenuSet(menuSet.id)}
                    className="group rounded-xl border border-border bg-background p-4 text-left shadow-none transition-colors hover:border-primary/40 hover:bg-muted/40 focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] focus-visible:outline-none"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="truncate text-base font-semibold">{menuSet.title}</div>
                        <div className="mt-1 line-clamp-2 text-sm text-muted-foreground">
                          {menuSet.description || "Описание не задано"}
                        </div>
                      </div>
                      <FolderOpen className="size-5 shrink-0 text-muted-foreground transition-colors group-hover:text-primary" />
                    </div>
                    <div className="mt-4 flex flex-wrap gap-2">
                      {rootBadges(workspace, menuSet.id).map((badge) => (
                        <Badge key={badge} variant="secondary">
                          {badge}
                        </Badge>
                      ))}
                      <Badge variant="outline">{menuSet.buttons.length} кнопок</Badge>
                      <Badge variant="outline">{childCount} внутри</Badge>
                      {parentCount ? <Badge variant="outline">{parentCount} входов</Badge> : null}
                    </div>
                  </button>
                );
              })}
            </div>
            <Card size="sm" className="border border-border bg-background shadow-none ring-0">
              <CardHeader className="border-b border-border/70 pb-3">
                <CardTitle className="text-sm font-semibold">Root-наборы</CardTitle>
              </CardHeader>
              <CardContent className="grid gap-3 pt-3 text-sm">
                <button type="button" className="rounded-lg border border-border p-3 text-left hover:bg-muted/40" onClick={() => navigateToMenuSet(workspace.hr_settings.default_employee_menu_set_id)}>
                  <div className="font-semibold">Сотрудники</div>
                  <div className="text-muted-foreground">{menuSetTitle(workspace, workspace.hr_settings.default_employee_menu_set_id)}</div>
                </button>
                <button type="button" className="rounded-lg border border-border p-3 text-left hover:bg-muted/40" onClick={() => navigateToMenuSet(workspace.hr_settings.default_candidate_menu_set_id)}>
                  <div className="font-semibold">Кандидаты</div>
                  <div className="text-muted-foreground">{menuSetTitle(workspace, workspace.hr_settings.default_candidate_menu_set_id)}</div>
                </button>
                <button type="button" className="rounded-lg border border-border p-3 text-left hover:bg-muted/40" onClick={() => navigateToMenuSet(workspace.hr_settings.default_menu_set_id)}>
                  <div className="font-semibold">Fallback</div>
                  <div className="text-muted-foreground">{menuSetTitle(workspace, workspace.hr_settings.default_menu_set_id)}</div>
                </button>
              </CardContent>
            </Card>
          </div>
        )}
      </SettingsCard>
      </div>
    </>
  );
}
