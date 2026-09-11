import React from "react";
import {
  BriefcaseBusiness,
  Check,
  Clock3,
  Copy,
  ExternalLink,
  GripVertical,
  Link2,
  RefreshCw,
  Save,
  Shield,
  Trash2,
  Unlink,
} from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmAction } from "@/components/ui/confirm-action";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Field,
  FieldContent,
  FieldDescription,
  FieldGroup,
  FieldLabel,
  FieldTitle,
} from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ThemeSwitch } from "@/components/ui/theme-switch";
import { cn } from "@/lib/utils";

type HrSettings = {
  hr_name: string;
  telegram_user_id: string;
  telegram_username?: string;
  telegram_connection_state: "disconnected" | "pending" | "connected";
  telegram_link_expires_at: string | null;
  notification_recipient_ids: string;
  notify_scenario_completed: boolean;
  notify_test_task_received: boolean;
  notify_user_actions: boolean;
  default_menu_set_id: number | null;
  default_employee_menu_set_id: number | null;
  default_candidate_menu_set_id: number | null;
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

type CustomEmoji = {
  id: number;
  title: string;
  emoji_id: string;
  fallback: string;
  is_active: boolean;
};

type Workspace = {
  current_user: AdminAccount;
  role_labels: Record<string, string>;
  menu_role_scope_labels: Record<string, string>;
  menu_employee_scope_labels: Record<string, string>;
  positions: Position[];
  custom_emojis: CustomEmoji[];
  hr_settings: HrSettings;
  menu_sets: MenuSet[];
  available_scenarios: ScenarioOption[];
  employee_options: { id: number; label: string }[];
  employee_stage_options: SelectOption[];
  candidate_stage_options: SelectOption[];
  accounts: AdminAccount[];
};

type HrLinkResponse = {
  workspace: Workspace;
  deep_link: string | null;
  expires_at: string;
  requires_telegram_bot_username: boolean;
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
    custom_emojis: Array.isArray(workspace.custom_emojis) ? workspace.custom_emojis : [],
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
    custom_emojis: workspace.custom_emojis.map((emoji) => ({ ...emoji })),
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
  const [newEmoji, setNewEmoji] = React.useState({ title: "", emoji_id: "", fallback: "✨" });
  const [emojiDrafts, setEmojiDrafts] = React.useState<Record<number, { title: string; emoji_id: string; fallback: string }>>({});
  const [hrLink, setHrLink] = React.useState<{ url: string; expiresAt: string } | null>(null);
  const [hrLinkBusy, setHrLinkBusy] = React.useState(false);
  const [hrLinkCopied, setHrLinkCopied] = React.useState(false);

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

  const createHrLink = async () => {
    setHrLinkBusy(true);
    setError("");
    setMessage("");
    setHrLink(null);
    try {
      const result = (await requestJson("/api/settings/hr/telegram-link", { method: "POST" })) as unknown as HrLinkResponse;
      setWorkspace(normalizeWorkspace(result.workspace));
      if (result.deep_link) {
        setHrLink({ url: result.deep_link, expiresAt: result.expires_at });
        setMessage("Ссылка подключения создана");
      } else {
        setError(
          result.requires_telegram_bot_username
            ? "Ссылка не создана: на сервере не настроено имя Telegram-бота. Обратитесь к администратору конфигурации."
            : "Ссылка подключения не создана: backend не вернул ссылку.",
        );
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось создать ссылку подключения");
    } finally {
      setHrLinkBusy(false);
    }
  };

  const rebindHr = async () => {
    if (await disconnectHr()) {
      await createHrLink();
    }
  };

  const disconnectHr = async () => {
    setHrLinkBusy(true);
    setError("");
    setMessage("");
    try {
      const nextWorkspace = await requestJson("/api/settings/hr/telegram-link", { method: "DELETE" });
      setWorkspace(normalizeWorkspace(nextWorkspace));
      setHrLink(null);
      setMessage("HR отключен от Telegram");
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось отключить HR");
      return false;
    } finally {
      setHrLinkBusy(false);
    }
  };

  const copyHrLink = async () => {
    if (!hrLink) return;
    try {
      await navigator.clipboard.writeText(hrLink.url);
      setHrLinkCopied(true);
      window.setTimeout(() => setHrLinkCopied(false), 1800);
    } catch {
      setError("Не удалось скопировать ссылку. Откройте ее и скопируйте вручную.");
    }
  };

  const editableHrSettingsPayload = (settings: HrSettings) => ({
    hr_name: settings.hr_name,
    notification_recipient_ids: settings.notification_recipient_ids,
    notify_scenario_completed: settings.notify_scenario_completed,
    notify_test_task_received: settings.notify_test_task_received,
    notify_user_actions: settings.notify_user_actions,
    default_menu_set_id: settings.default_menu_set_id,
    default_employee_menu_set_id: settings.default_employee_menu_set_id,
    default_candidate_menu_set_id: settings.default_candidate_menu_set_id,
  });

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
    <>
      <PageHeader title="Настройки" />
      <div className="admin-page-stack gap-5">

      <StatusAlert type="success" message={message} />
      <StatusAlert type="error" message={error} />

      <SettingsCard
        title="Интерфейс"
        description="Вид админки. Настройка личная и хранится в этом браузере."
      >
        <Field orientation="horizontal">
          <FieldContent>
            <FieldTitle>Тёмная тема</FieldTitle>
            <FieldDescription>Переключатель переехал сюда из бокового меню.</FieldDescription>
          </FieldContent>
          <ThemeSwitch />
        </Field>
      </SettingsCard>

      <SettingsCard title="HR-настройки">
        <FieldGroup className="grid gap-4 md:grid-cols-2">
          <Field>
            <FieldLabel>Имя HR</FieldLabel>
            <Input value={workspace.hr_settings.hr_name} onChange={(event) => updateHrSettings({ hr_name: event.target.value })} placeholder="Иван Петров" autoComplete="name" />
          </Field>
        </FieldGroup>
        <div className="flex justify-end">
          <Button onClick={() => setWorkspaceFromApi(requestJson("/api/settings/hr", { method: "POST", body: JSON.stringify(editableHrSettingsPayload(workspace.hr_settings)) }), "HR-настройки сохранены")}>
            <Save data-icon="inline-start" />
            Сохранить настройки
          </Button>
        </div>

        <div className="grid gap-4 rounded-lg border border-border bg-muted/35 p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex items-center gap-2 text-sm font-semibold">
                <Link2 className="size-4 text-muted-foreground" />
                Подключение HR к Telegram
              </div>
              <p className="mt-1 text-sm text-muted-foreground">
                Подключение подтверждается переходом по одноразовой ссылке в Telegram.
              </p>
            </div>
            <span
              className={cn(
                "inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium",
                workspace.hr_settings.telegram_connection_state === "connected"
                  ? "border-primary/30 bg-primary/10 text-primary"
                  : workspace.hr_settings.telegram_connection_state === "pending"
                    ? "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300"
                    : "border-border bg-background text-muted-foreground",
              )}
            >
              {workspace.hr_settings.telegram_connection_state === "connected"
                ? "Подключен"
                : workspace.hr_settings.telegram_connection_state === "pending"
                  ? "Ожидает подключения"
                  : "Не подключен"}
            </span>
          </div>

          {workspace.hr_settings.telegram_connection_state === "connected" ? (
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-primary/20 bg-primary/5 px-3 py-2 text-sm">
              <span>
                {workspace.hr_settings.telegram_username
                  ? `@${workspace.hr_settings.telegram_username}`
                  : `Telegram ID: ${workspace.hr_settings.telegram_user_id}`}
              </span>
              <div className="flex flex-wrap gap-2">
                <ConfirmAction
                  title="Перепривязать HR к другому Telegram?"
                  description="Текущий HR будет отключен сразу. После этого создастся новая одноразовая ссылка подключения. До подтверждения нового аккаунта HR-уведомления отправляться не будут."
                  onConfirm={rebindHr}
                >
                  <Button variant="outline" size="sm" disabled={hrLinkBusy}>
                    <RefreshCw data-icon="inline-start" /> Перепривязать
                  </Button>
                </ConfirmAction>
                <ConfirmAction
                  title="Отключить HR от Telegram?"
                  description="Уведомления HR перестанут отправляться, пока аккаунт не будет подключен снова."
                  onConfirm={disconnectHr}
                >
                  <Button variant="outline" size="sm" disabled={hrLinkBusy}>
                    <Unlink data-icon="inline-start" /> Отключить
                  </Button>
                </ConfirmAction>
              </div>
            </div>
          ) : (
            <div className="grid gap-3">
              {workspace.hr_settings.telegram_link_expires_at && workspace.hr_settings.telegram_connection_state === "disconnected" ? (
                <Alert variant="destructive">
                  <Clock3 />
                  <AlertTitle>Ссылка подключения истекла</AlertTitle>
                  <AlertDescription>Создайте новую ссылку и откройте ее в Telegram.</AlertDescription>
                </Alert>
              ) : null}
              <div className="flex flex-wrap gap-2">
                <Button onClick={createHrLink} disabled={hrLinkBusy}>
                  <Link2 data-icon="inline-start" /> Создать ссылку подключения
                </Button>
              </div>
            </div>
          )}

          {hrLink ? (
            <div className="grid gap-3 rounded-md border border-amber-500/30 bg-amber-500/5 p-3">
              <div className="text-sm font-medium">Откройте ссылку в Telegram в течение 15 минут</div>
              <div className="flex min-w-0 flex-wrap gap-2">
                <Input value={hrLink.url} readOnly aria-label="Ссылка подключения HR" className="min-w-0 flex-1" />
                <Button variant="outline" onClick={copyHrLink}>
                  {hrLinkCopied ? <Check data-icon="inline-start" /> : <Copy data-icon="inline-start" />}
                  {hrLinkCopied ? "Скопировано" : "Копировать"}
                </Button>
                <Button
                  variant="outline"
                  render={
                    <a href={hrLink.url} target="_blank" rel="noreferrer" />
                  }
                >
                  <ExternalLink data-icon="inline-start" /> Открыть
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                Действует до {new Date(hrLink.expiresAt).toLocaleString("ru-RU")}. После подтверждения обновите страницу, если статус не изменился.
              </p>
            </div>
          ) : null}
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
                  "relative grid gap-2 rounded-lg border border-border bg-background p-3 transition-colors xl:grid-cols-[auto_minmax(220px,1fr)_160px_auto] xl:items-center",
                  draggedPositionId === position.id ? "border-primary/40 bg-primary/5 opacity-80" : null,
                  positionsReordering ? "opacity-70" : null,
                )}
              >
                {dragOverPositionId === position.id && draggedPositionId !== position.id ? (
                  <div className="pointer-events-none absolute -top-2 left-3 right-3 z-10 flex items-center gap-2">
                    <span className="size-2 rounded-full bg-primary shadow-[0_0_0_3px_var(--card)]" />
                    <span className="h-0.5 flex-1 rounded-full bg-primary shadow-[0_0_0_3px_var(--card)]" />
                  </div>
                ) : null}
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
        <SettingsCard title="Каталог custom emoji" description="Сохранённые Telegram-иконки доступны в редакторах сообщений.">
          <div className="grid gap-3 rounded-lg border border-border bg-muted/35 p-3 md:grid-cols-[1fr_1fr_120px_auto] md:items-end">
            <Field>
              <FieldLabel>Название</FieldLabel>
              <Input value={newEmoji.title} onChange={(event) => setNewEmoji((current) => ({ ...current, title: event.target.value }))} placeholder="Например, Ура" />
            </Field>
            <Field>
              <FieldLabel>Emoji ID</FieldLabel>
              <Input value={newEmoji.emoji_id} onChange={(event) => setNewEmoji((current) => ({ ...current, emoji_id: event.target.value.replace(/\D/g, "") }))} inputMode="numeric" placeholder="Только из Telegram" />
            </Field>
            <Field>
              <FieldLabel>Предпросмотр</FieldLabel>
              <Input value={newEmoji.fallback} onChange={(event) => setNewEmoji((current) => ({ ...current, fallback: event.target.value }))} maxLength={8} />
            </Field>
            <Button
              disabled={!newEmoji.title.trim() || !/^\d+$/.test(newEmoji.emoji_id)}
              onClick={() =>
                setWorkspaceFromApi(
                  requestJson("/api/settings/custom-emojis", {
                    method: "POST",
                    body: JSON.stringify({ title: newEmoji.title.trim(), emoji_id: newEmoji.emoji_id, fallback: newEmoji.fallback || "✨" }),
                  }),
                  "Иконка добавлена",
                ).then(() => setNewEmoji({ title: "", emoji_id: "", fallback: "✨" }))
              }
            >
              Добавить
            </Button>
          </div>
          <div className="grid gap-2">
            {workspace.custom_emojis.length ? workspace.custom_emojis.map((emoji) => {
              const draft = emojiDrafts[emoji.id] || { title: emoji.title, emoji_id: emoji.emoji_id, fallback: emoji.fallback };
              return (
              <div key={emoji.id} className="grid gap-3 rounded-lg border border-border bg-background p-3 md:grid-cols-[auto_1fr_1fr_120px_auto] md:items-end">
                <span className="text-xl" aria-hidden="true">{emoji.fallback || "✨"}</span>
                <Field>
                  <FieldLabel>Название</FieldLabel>
                  <Input value={draft.title} onChange={(event) => setEmojiDrafts((current) => ({ ...current, [emoji.id]: { ...draft, title: event.target.value } }))} />
                </Field>
                <Field>
                  <FieldLabel>Emoji ID</FieldLabel>
                  <Input value={draft.emoji_id} onChange={(event) => setEmojiDrafts((current) => ({ ...current, [emoji.id]: { ...draft, emoji_id: event.target.value.replace(/\D/g, "") } }))} inputMode="numeric" />
                </Field>
                <Field>
                  <FieldLabel>Предпросмотр</FieldLabel>
                  <Input value={draft.fallback} onChange={(event) => setEmojiDrafts((current) => ({ ...current, [emoji.id]: { ...draft, fallback: event.target.value } }))} maxLength={8} />
                </Field>
                <div className="flex gap-2 md:justify-end">
                  <Button
                    variant="secondary"
                    size="icon"
                    aria-label={`Сохранить ${emoji.title}`}
                    disabled={!draft.title.trim() || !/^\d+$/.test(draft.emoji_id)}
                    onClick={() => setWorkspaceFromApi(requestJson(`/api/settings/custom-emojis/${emoji.id}`, { method: "PATCH", body: JSON.stringify(draft) }), "Иконка обновлена")}
                  >
                    <Save />
                  </Button>
                <Button
                  variant="outline"
                  size="icon"
                  aria-label={`Отключить ${emoji.title}`}
                  disabled={!emoji.is_active}
                  onClick={() => setWorkspaceFromApi(requestJson(`/api/settings/custom-emojis/${emoji.id}`, { method: "DELETE" }), "Иконка отключена")}
                >
                  <Trash2 />
                </Button>
                </div>
              </div>
              );
            }) : (
              <div className="rounded-lg border border-dashed border-border px-3 py-4 text-sm text-muted-foreground">Каталог пока пуст.</div>
            )}
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
    </>
  );
}
