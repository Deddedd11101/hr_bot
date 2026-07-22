import React from "react";
import { BriefcaseBusiness, GripVertical, Save, Shield, Trash2 } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmAction } from "@/components/ui/confirm-action";
import { Checkbox } from "@/components/ui/checkbox";
import { Field, FieldContent, FieldGroup, FieldLabel, FieldTitle } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";

type HrSettings = {
  hr_name: string;
  telegram_user_id: string;
  notification_recipient_ids: string;
  notify_scenario_completed: boolean;
  notify_test_task_received: boolean;
  notify_user_actions: boolean;
  default_menu_set_id: number | null;
};

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
};

type MenuSet = {
  id: number;
  title: string;
  description: string;
  sort_order: number;
  role_scope: string;
  employee_scope: string;
  target_employee_id: number | null;
  target_employee_stages: string[];
  target_candidate_stages: string[];
  buttons: MenuButton[];
};

type AdminAccount = {
  id: number;
  login: string;
  role: string;
  role_label: string;
  is_active: boolean;
};

type Position = {
  id: number;
  title: string;
  slug: string;
  is_active: boolean;
  sort_order: number;
  created_at?: string;
};

type Workspace = {
  current_user: AdminAccount;
  role_labels: Record<string, string>;
  menu_role_scope_labels: Record<string, string>;
  menu_employee_scope_labels: Record<string, string>;
  positions: Position[];
  hr_settings: HrSettings;
  menu_sets: MenuSet[];
  available_scenarios: ScenarioOption[];
  employee_options: { id: number; label: string }[];
  employee_stage_options: SelectOption[];
  candidate_stage_options: SelectOption[];
  accounts: AdminAccount[];
};

type DraftButton = {
  label: string;
  action_type: string;
  scenario_key: string;
  target_menu_set_id: string;
};

type SelectOption = {
  value: string;
  label: string;
};

export type SettingsPageProps = {
  apiUrl: string;
};

const EMPTY_SELECT_VALUE = "__empty__";

const actionTypeOptions = [
  { value: "inactive", label: "Неактивна" },
  { value: "launch_scenario", label: "Запуск сценария" },
  { value: "open_set", label: "Переход к набору" },
];

const activeOptions = [
  { value: "true", label: "Активен" },
  { value: "false", label: "Отключен" },
];

function sortedPositions(positions: Position[]): Position[] {
  return [...positions].sort((left, right) => {
    if (left.sort_order !== right.sort_order) {
      return left.sort_order - right.sort_order;
    }
    return left.id - right.id;
  });
}

function movePosition(positions: Position[], draggedId: number, targetId: number): Position[] {
  if (draggedId === targetId) {
    return positions;
  }
  const currentPositions = sortedPositions(positions);
  const draggedPosition = currentPositions.find((position) => position.id === draggedId);
  if (!draggedPosition) {
    return positions;
  }
  const withoutDragged = currentPositions.filter((position) => position.id !== draggedId);
  const targetIndex = withoutDragged.findIndex((position) => position.id === targetId);
  if (targetIndex < 0) {
    return positions;
  }
  const nextPositions = [...withoutDragged];
  nextPositions.splice(targetIndex, 0, draggedPosition);
  return nextPositions.map((position, index) => ({
    ...position,
    sort_order: (index + 1) * 10,
  }));
}

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

function normalizeWorkspace(workspace: Workspace): Workspace {
  return {
    ...workspace,
    menu_role_scope_labels: workspace.menu_role_scope_labels || { all: "Для всех ролей" },
    menu_employee_scope_labels:
      workspace.menu_employee_scope_labels || {
        all: "Для всех сотрудников и кандидатов",
        employees: "Для всех сотрудников",
        candidates: "Для всех кандидатов",
      },
    employee_options: workspace.employee_options || [],
    employee_stage_options: workspace.employee_stage_options || [],
    candidate_stage_options: workspace.candidate_stage_options || [],
    positions: workspace.positions || [],
    menu_sets: (workspace.menu_sets || []).map((menuSet) => ({
      ...menuSet,
      role_scope: menuSet.role_scope || "all",
      employee_scope: menuSet.employee_scope || "all",
      target_employee_id:
        typeof menuSet.target_employee_id === "number" ? menuSet.target_employee_id : null,
      target_employee_stages: menuSet.target_employee_stages || [],
      target_candidate_stages: menuSet.target_candidate_stages || [],
      buttons: menuSet.buttons || [],
    })),
  };
}

function cloneWorkspace(workspace: Workspace): Workspace {
  return {
    ...workspace,
    hr_settings: { ...workspace.hr_settings },
    positions: workspace.positions.map((position) => ({ ...position })),
    menu_sets: workspace.menu_sets.map((menuSet) => ({
      ...menuSet,
      target_employee_stages: [...menuSet.target_employee_stages],
      target_candidate_stages: [...menuSet.target_candidate_stages],
      buttons: menuSet.buttons.map((button) => ({ ...button })),
    })),
    accounts: workspace.accounts.map((account) => ({ ...account })),
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

function menuSetOptions(menuSets: MenuSet[]): SelectOption[] {
  return menuSets.map((menuSet) => ({ value: String(menuSet.id), label: menuSet.title }));
}

function scenarioOptions(scenarios: ScenarioOption[]): SelectOption[] {
  return scenarios.map((scenario) => ({ value: scenario.scenario_key, label: scenario.title }));
}

function roleOptions(labels: Record<string, string>): SelectOption[] {
  return Object.entries(labels).map(([value, label]) => ({ value, label }));
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

export function SettingsPage({ apiUrl }: SettingsPageProps) {
  const [workspace, setWorkspace] = React.useState<Workspace | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [message, setMessage] = React.useState("");
  const [error, setError] = React.useState("");
  const [newAccount, setNewAccount] = React.useState({ login: "", password: "", role: "hr", is_active: true });
  const [accountPasswords, setAccountPasswords] = React.useState<Record<number, string>>({});
  const [newPositionTitle, setNewPositionTitle] = React.useState("");
  const [draggedPositionId, setDraggedPositionId] = React.useState<number | null>(null);
  const [dragOverPositionId, setDragOverPositionId] = React.useState<number | null>(null);
  const [positionsReordering, setPositionsReordering] = React.useState(false);

  React.useEffect(() => {
    requestJson(apiUrl)
      .then((payload) => setWorkspace(normalizeWorkspace(payload)))
      .catch((err) => setError(err instanceof Error ? err.message : "Не удалось загрузить настройки"))
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

  const updateHrSettings = (patch: Partial<HrSettings>) => {
    setWorkspace((current) => {
      if (!current) return current;
      const next = cloneWorkspace(current);
      next.hr_settings = { ...next.hr_settings, ...patch };
      return next;
    });
  };

  const updateAccountLocal = (accountId: number, patch: Partial<AdminAccount>) => {
    setWorkspace((current) => {
      if (!current) return current;
      const next = cloneWorkspace(current);
      next.accounts = next.accounts.map((account) => (account.id === accountId ? { ...account, ...patch } : account));
      return next;
    });
  };

  const updatePositionLocal = (positionId: number, patch: Partial<Position>) => {
    setWorkspace((current) => {
      if (!current) return current;
      const next = cloneWorkspace(current);
      next.positions = next.positions.map((position) =>
        position.id === positionId ? { ...position, ...patch } : position,
      );
      return next;
    });
  };

  const positionPayload = (position: Position) => ({
    title: position.title,
    sort_order: position.sort_order,
    is_active: position.is_active,
  });

  const reloadWorkspace = async () => {
    const nextWorkspace = await requestJson(apiUrl);
    setWorkspace(normalizeWorkspace(nextWorkspace));
    return nextWorkspace;
  };

  const savePositionOrder = async (nextPositions: Position[]) => {
    if (!workspace || positionsReordering) return;

    const orderedPositions = sortedPositions(nextPositions);
    const originalOrders = new Map(workspace.positions.map((position) => [position.id, position.sort_order]));
    const changedPositions = orderedPositions.filter(
      (position) => originalOrders.get(position.id) !== position.sort_order,
    );
    if (!changedPositions.length) return;

    setPositionsReordering(true);
    setError("");
    setMessage("");
    setWorkspace((current) => (current ? { ...cloneWorkspace(current), positions: orderedPositions } : current));

    try {
      let latestWorkspace: Workspace | null = null;
      for (const position of changedPositions) {
        latestWorkspace = await requestJson(`/api/settings/positions/${position.id}`, {
          method: "PATCH",
          body: JSON.stringify({ sort_order: position.sort_order }),
        });
      }
      if (latestWorkspace) {
        setWorkspace(normalizeWorkspace(latestWorkspace));
      }
      setMessage("Порядок должностей сохранен");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось сохранить порядок должностей");
      try {
        await reloadWorkspace();
      } catch (reloadErr) {
        setError(
          reloadErr instanceof Error
            ? `Не удалось сохранить порядок должностей. ${reloadErr.message}`
            : "Не удалось сохранить порядок должностей и обновить данные",
        );
      }
    } finally {
      setPositionsReordering(false);
      setDraggedPositionId(null);
      setDragOverPositionId(null);
    }
  };

  const handlePositionDrop = (targetId: number, sourceId = draggedPositionId) => {
    if (!workspace || sourceId === null || positionsReordering) return;
    const nextPositions = movePosition(workspace.positions, sourceId, targetId);
    void savePositionOrder(nextPositions);
  };

  React.useEffect(() => {
    if (draggedPositionId === null || positionsReordering) return;

    const findPositionIdAtPoint = (clientX: number, clientY: number) => {
      const element = document.elementFromPoint(clientX, clientY);
      const row = element?.closest("[data-position-id]");
      const rowId = row?.getAttribute("data-position-id") || "";
      return rowId ? Number(rowId) : null;
    };

    const handleMouseMove = (event: MouseEvent) => {
      event.preventDefault();
      const targetId = findPositionIdAtPoint(event.clientX, event.clientY);
      setDragOverPositionId(targetId && targetId !== draggedPositionId ? targetId : null);
    };

    const handleMouseUp = (event: MouseEvent) => {
      event.preventDefault();
      const targetId = findPositionIdAtPoint(event.clientX, event.clientY);
      if (targetId && targetId !== draggedPositionId) {
        handlePositionDrop(targetId, draggedPositionId);
      } else {
        setDraggedPositionId(null);
        setDragOverPositionId(null);
      }
    };

    document.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseup", handleMouseUp, { once: true });
    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
    };
  }, [draggedPositionId, positionsReordering, workspace]);

  if (loading) {
    return (
      <Card className="admin-page-shell border border-border/80 bg-card shadow-none ring-0">
        <CardContent className="p-8 text-sm text-muted-foreground">Загружаю настройки...</CardContent>
      </Card>
    );
  }

  if (!workspace) {
    return (
      <div className="admin-page-stack gap-4">
        <StatusAlert type="error" message={error || "Настройки не загружены"} />
      </div>
    );
  }

  const isAdmin = workspace.current_user.role === "admin";
  const roles = roleOptions(workspace.role_labels);
  const orderedPositions = sortedPositions(workspace.positions);

  return (
    <div className="admin-page-stack gap-5">
      <header className="admin-page-surface border border-border/80 bg-card p-5 shadow-none ring-0">
        <h1 className="text-3xl font-semibold tracking-tight">Настройки</h1>
      </header>

      <StatusAlert type="success" message={message} />
      <StatusAlert type="error" message={error} />

      <SettingsCard title="HR-настройки">
        <FieldGroup className="grid gap-4 md:grid-cols-2">
          <Field>
            <FieldLabel>Имя HR</FieldLabel>
            <Input value={workspace.hr_settings.hr_name} onChange={(event) => updateHrSettings({ hr_name: event.target.value })} placeholder="Иван Петров" autoComplete="name" />
          </Field>
          <Field>
            <FieldLabel>Основной ID получателя</FieldLabel>
            <Input value={workspace.hr_settings.telegram_user_id} onChange={(event) => updateHrSettings({ telegram_user_id: event.target.value })} placeholder="123456789" inputMode="numeric" autoComplete="off" />
          </Field>
        </FieldGroup>
        <div className="flex justify-end">
          <Button onClick={() => setWorkspaceFromApi(requestJson("/api/settings/hr", { method: "POST", body: JSON.stringify(workspace.hr_settings) }), "HR-настройки сохранены")}>
            <Save data-icon="inline-start" />
            Сохранить настройки
          </Button>
        </div>
      </SettingsCard>

      {isAdmin ? (
        <SettingsCard title="Должности">
          <div className="grid gap-3 rounded-lg border border-border bg-muted/35 p-3 lg:grid-cols-[1fr_auto] lg:items-end">
            <Field>
              <FieldLabel>Новая должность</FieldLabel>
              <Input
                value={newPositionTitle}
                onChange={(event) => setNewPositionTitle(event.target.value)}
                placeholder="Например, QA engineer"
                autoComplete="off"
                disabled={positionsReordering}
              />
            </Field>
            <Button
              disabled={!newPositionTitle.trim() || positionsReordering}
              onClick={() =>
                setWorkspaceFromApi(
                  requestJson("/api/settings/positions", {
                    method: "POST",
                    body: JSON.stringify({ title: newPositionTitle.trim() }),
                  }),
                  "Должность создана",
                ).then(() => setNewPositionTitle(""))
              }
            >
              <BriefcaseBusiness data-icon="inline-start" />
              Создать
            </Button>
          </div>

          <div className="grid gap-2">
            {orderedPositions.map((position) => (
              <div
                key={position.id}
                data-position-id={position.id}
                onDragOver={(event) => {
                  if (draggedPositionId !== null && draggedPositionId !== position.id && !positionsReordering) {
                    event.preventDefault();
                    event.dataTransfer.dropEffect = "move";
                    setDragOverPositionId(position.id);
                  }
                }}
                onDragLeave={() => setDragOverPositionId((current) => (current === position.id ? null : current))}
                onDrop={(event) => {
                  event.preventDefault();
                  handlePositionDrop(position.id);
                }}
                className={cn(
                  "grid gap-2 rounded-lg border border-border bg-background p-3 transition-colors xl:grid-cols-[auto_minmax(220px,1fr)_160px_auto] xl:items-center",
                  dragOverPositionId === position.id && draggedPositionId !== position.id
                    ? "border-primary/60 bg-primary/5"
                    : null,
                  positionsReordering ? "opacity-70" : null,
                )}
              >
                <button
                  type="button"
                  disabled={positionsReordering}
                  aria-label="Перетащить должность"
                  title="Перетащить"
                  onMouseDown={(event) => {
                    if (positionsReordering) return;
                    event.preventDefault();
                    setDraggedPositionId(position.id);
                    setDragOverPositionId(null);
                  }}
                  onDragStart={(event) => {
                    setDraggedPositionId(position.id);
                    event.dataTransfer.effectAllowed = "move";
                    event.dataTransfer.setData("text/plain", String(position.id));
                  }}
                  onDragEnd={() => {
                    setDraggedPositionId(null);
                    setDragOverPositionId(null);
                  }}
                  className="inline-flex size-9 cursor-grab items-center justify-center rounded-md border border-border bg-muted/45 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50 active:cursor-grabbing"
                >
                  <GripVertical className="size-4" />
                </button>
                <Input
                  value={position.title}
                  onChange={(event) => updatePositionLocal(position.id, { title: event.target.value })}
                  aria-label="Название должности"
                  autoComplete="off"
                  disabled={positionsReordering}
                />
                <div className="grid gap-1">
                  <AppSelect
                    value={position.is_active ? "true" : "false"}
                    onChange={(value) => updatePositionLocal(position.id, { is_active: value === "true" })}
                    options={activeOptions}
                    allowEmpty={false}
                    disabled={positionsReordering}
                  />
                  <span className="px-1 text-xs text-muted-foreground">sort_order {position.sort_order}</span>
                </div>
                <div className="flex gap-2 xl:justify-end">
                  <Button
                    variant="secondary"
                    size="icon"
                    aria-label="Сохранить должность"
                    disabled={!position.title.trim() || positionsReordering}
                    onClick={() =>
                      setWorkspaceFromApi(
                        requestJson(`/api/settings/positions/${position.id}`, {
                          method: "PATCH",
                          body: JSON.stringify(positionPayload(position)),
                        }),
                        "Должность сохранена",
                      )
                    }
                  >
                    <Save />
                  </Button>
                  <ConfirmAction
                    title="Удалить должность?"
                    description="Должность будет отключена в справочнике. Уже выбранные legacy-значения в карточках сохранятся."
                    actionLabel="Отключить"
                    onConfirm={() =>
                      setWorkspaceFromApi(
                        requestJson(`/api/settings/positions/${position.id}`, { method: "DELETE" }),
                        "Должность отключена",
                      )
                    }
                  >
                    <Button variant="outline" size="icon" aria-label="Удалить должность" disabled={positionsReordering}>
                      <Trash2 />
                    </Button>
                  </ConfirmAction>
                </div>
              </div>
            ))}
          </div>
        </SettingsCard>
      ) : null}

      {isAdmin ? (
        <SettingsCard title="Доступ в админку">
          <div className="grid gap-3 rounded-lg border border-border bg-muted/35 p-3 xl:grid-cols-[1fr_1fr_0.7fr_0.6fr_auto] xl:items-end">
            <Field>
              <FieldLabel>Логин</FieldLabel>
              <Input value={newAccount.login} onChange={(event) => setNewAccount((current) => ({ ...current, login: event.target.value }))} placeholder="Логин" autoComplete="username" />
            </Field>
            <Field>
              <FieldLabel>Пароль</FieldLabel>
              <Input type="password" value={newAccount.password} onChange={(event) => setNewAccount((current) => ({ ...current, password: event.target.value }))} placeholder="Пароль" autoComplete="new-password" />
            </Field>
            <Field>
              <FieldLabel>Роль</FieldLabel>
              <AppSelect value={newAccount.role} onChange={(value) => setNewAccount((current) => ({ ...current, role: value }))} options={roles} allowEmpty={false} />
            </Field>
            <Field>
              <FieldLabel>Статус</FieldLabel>
              <AppSelect value={newAccount.is_active ? "true" : "false"} onChange={(value) => setNewAccount((current) => ({ ...current, is_active: value === "true" }))} options={activeOptions} allowEmpty={false} />
            </Field>
            <Button
              onClick={() =>
                setWorkspaceFromApi(requestJson("/api/accounts", { method: "POST", body: JSON.stringify(newAccount) }), "Аккаунт создан").then(() =>
                  setNewAccount({ login: "", password: "", role: "hr", is_active: true }),
                )
              }
            >
              <Shield data-icon="inline-start" />
              Создать
            </Button>
          </div>

          <div className="grid gap-2">
            {workspace.accounts.map((account) => (
              <div key={account.id} className="grid gap-2 rounded-lg border border-border bg-background p-3 xl:grid-cols-[1fr_0.7fr_0.6fr_1fr_auto]">
                <Input value={account.login} onChange={(event) => updateAccountLocal(account.id, { login: event.target.value })} autoComplete="username" />
                <AppSelect value={account.role} onChange={(value) => updateAccountLocal(account.id, { role: value })} options={roles} allowEmpty={false} />
                <AppSelect value={account.is_active ? "true" : "false"} onChange={(value) => updateAccountLocal(account.id, { is_active: value === "true" })} options={activeOptions} allowEmpty={false} />
                <Input
                  type="password"
                  value={accountPasswords[account.id] || ""}
                  placeholder="Новый пароль"
                  autoComplete="new-password"
                  onChange={(event) => setAccountPasswords((current) => ({ ...current, [account.id]: event.target.value }))}
                />
                <div className="flex gap-2 xl:justify-end">
                  <Button
                    variant="secondary"
                    size="icon"
                    aria-label="Сохранить аккаунт"
                    onClick={() =>
                      setWorkspaceFromApi(
                        requestJson(`/api/accounts/${account.id}`, {
                          method: "POST",
                          body: JSON.stringify({ ...account, password: accountPasswords[account.id] || "" }),
                        }),
                        "Аккаунт сохранен",
                      ).then(() => setAccountPasswords((current) => ({ ...current, [account.id]: "" })))
                    }
                  >
                    <Save />
                  </Button>
                  {account.id !== workspace.current_user.id ? (
                    <ConfirmAction
                      title="Удалить аккаунт?"
                      description="Аккаунт потеряет доступ к админке. Это действие нельзя отменить."
                      onConfirm={() => setWorkspaceFromApi(requestJson(`/api/accounts/${account.id}`, { method: "DELETE" }), "Аккаунт удален")}
                    >
                      <Button variant="outline" size="icon" aria-label="Удалить аккаунт">
                        <Trash2 />
                      </Button>
                    </ConfirmAction>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        </SettingsCard>
      ) : null}
    </div>
  );
}
