import React from "react";
import { ExternalLink, Plus, Save, Shield, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

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
  buttons: MenuButton[];
};

type AdminAccount = {
  id: number;
  login: string;
  role: string;
  role_label: string;
  is_active: boolean;
};

type Workspace = {
  current_user: AdminAccount;
  role_labels: Record<string, string>;
  hr_settings: HrSettings;
  menu_sets: MenuSet[];
  available_scenarios: ScenarioOption[];
  accounts: AdminAccount[];
};

type DraftButton = {
  label: string;
  action_type: string;
  scenario_key: string;
  target_menu_set_id: string;
};

export type SettingsPageProps = {
  apiUrl: string;
  classicUrl: string;
};

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

function cloneWorkspace(workspace: Workspace): Workspace {
  return {
    ...workspace,
    hr_settings: { ...workspace.hr_settings },
    menu_sets: workspace.menu_sets.map((menuSet) => ({
      ...menuSet,
      buttons: menuSet.buttons.map((button) => ({ ...button })),
    })),
    accounts: workspace.accounts.map((account) => ({ ...account })),
  };
}

function FieldLabel({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="grid gap-2">
      <span className="text-sm font-semibold text-[var(--color-foreground)]/75">{label}</span>
      {children}
    </label>
  );
}

function SelectField({
  value,
  onChange,
  children,
}: {
  value: string;
  onChange: (value: string) => void;
  children: React.ReactNode;
}) {
  return (
    <select
      value={value}
      onChange={(event) => onChange(event.target.value)}
      className="h-10 rounded-[10px] border border-[var(--color-border)] bg-white px-3 text-sm transition-all duration-200 hover:rounded-[18px] focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]/20"
    >
      {children}
    </select>
  );
}

function Panel({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) {
  return (
    <section className="rounded-[10px] border border-[var(--color-border)] bg-[var(--color-panel)] p-5 shadow-[var(--shadow-soft)]">
      <div className="mb-5">
        <h2 className="text-xl font-semibold">{title}</h2>
        <p className="mt-1 text-sm text-[var(--color-muted-foreground)]">{subtitle}</p>
      </div>
      {children}
    </section>
  );
}

export function SettingsPage({ apiUrl, classicUrl }: SettingsPageProps) {
  const [workspace, setWorkspace] = React.useState<Workspace | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [message, setMessage] = React.useState("");
  const [error, setError] = React.useState("");
  const [newMenuSetTitle, setNewMenuSetTitle] = React.useState("");
  const [newAccount, setNewAccount] = React.useState({ login: "", password: "", role: "hr", is_active: true });
  const [accountPasswords, setAccountPasswords] = React.useState<Record<number, string>>({});
  const [buttonDrafts, setButtonDrafts] = React.useState<Record<number, DraftButton>>({});

  React.useEffect(() => {
    requestJson(apiUrl)
      .then(setWorkspace)
      .catch((err) => setError(err instanceof Error ? err.message : "Не удалось загрузить настройки"))
      .finally(() => setLoading(false));
  }, [apiUrl]);

  const setWorkspaceFromApi = async (promise: Promise<Workspace>, successMessage: string) => {
    setError("");
    setMessage("");
    try {
      const nextWorkspace = await promise;
      setWorkspace(nextWorkspace);
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

  const updateMenuSetLocal = (menuSetId: number, patch: Partial<MenuSet>) => {
    setWorkspace((current) => {
      if (!current) return current;
      const next = cloneWorkspace(current);
      next.menu_sets = next.menu_sets.map((menuSet) => (menuSet.id === menuSetId ? { ...menuSet, ...patch } : menuSet));
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

  const updateAccountLocal = (accountId: number, patch: Partial<AdminAccount>) => {
    setWorkspace((current) => {
      if (!current) return current;
      const next = cloneWorkspace(current);
      next.accounts = next.accounts.map((account) => (account.id === accountId ? { ...account, ...patch } : account));
      return next;
    });
  };

  if (loading) {
    return <div className="rounded-[10px] border border-[var(--color-border)] bg-white p-8 text-sm text-[var(--color-muted-foreground)]">Загружаю настройки...</div>;
  }

  if (!workspace) {
    return <div className="rounded-[10px] border border-[var(--color-border)] bg-white p-8 text-sm text-[var(--color-danger)]">{error || "Настройки не загружены"}</div>;
  }

  const isAdmin = workspace.current_user.role === "admin";

  return (
    <div className="mx-auto grid w-full max-w-[1680px] gap-5">
      <header className="flex flex-wrap items-start justify-between gap-4 rounded-[10px] border border-[var(--color-border)] bg-[var(--color-panel)] p-5 shadow-[var(--shadow-soft)]">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--color-muted-foreground)]">React admin</p>
          <h1 className="mt-2 text-3xl font-semibold">Настройки</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--color-muted-foreground)]">
            HR notifications, меню мессенджера и доступ в админку. Classic page оставлена как fallback на время миграции.
          </p>
        </div>
        <Button asChild variant="secondary">
          <a href={classicUrl}>
            <ExternalLink className="size-4" />
            Classic fallback
          </a>
        </Button>
      </header>

      {message ? <div className="rounded-[10px] border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{message}</div> : null}
      {error ? <div className="rounded-[10px] border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div> : null}

      <Panel title="HR notifications" subtitle="Кому бот отправляет служебные уведомления и какие события включены.">
        <div className="grid gap-4 md:grid-cols-2">
          <FieldLabel label="Имя HR">
            <Input value={workspace.hr_settings.hr_name} onChange={(event) => updateHrSettings({ hr_name: event.target.value })} placeholder="Иван Петров" />
          </FieldLabel>
          <FieldLabel label="Основной ID получателя">
            <Input value={workspace.hr_settings.telegram_user_id} onChange={(event) => updateHrSettings({ telegram_user_id: event.target.value })} placeholder="123456789" />
          </FieldLabel>
          <div className="md:col-span-2">
            <FieldLabel label="Дополнительные ID получателей">
              <Textarea
                value={workspace.hr_settings.notification_recipient_ids}
                onChange={(event) => updateHrSettings({ notification_recipient_ids: event.target.value })}
                rows={3}
                placeholder={"123456789\n987654321"}
              />
            </FieldLabel>
          </div>
          <FieldLabel label="Главный набор меню">
            <SelectField
              value={workspace.hr_settings.default_menu_set_id ? String(workspace.hr_settings.default_menu_set_id) : ""}
              onChange={(value) => updateHrSettings({ default_menu_set_id: value ? Number(value) : null })}
            >
              <option value="">Не выбран</option>
              {workspace.menu_sets.map((menuSet) => (
                <option key={menuSet.id} value={menuSet.id}>
                  {menuSet.title}
                </option>
              ))}
            </SelectField>
          </FieldLabel>
          <div className="grid gap-3 rounded-[10px] bg-[var(--color-panel-muted)] p-4">
            {[
              ["notify_scenario_completed", "По завершению сценариев"],
              ["notify_test_task_received", "По получению тестового задания"],
              ["notify_user_actions", "По действиям других пользователей"],
            ].map(([key, label]) => (
              <label key={key} className="flex items-center gap-3 text-sm font-medium">
                <input
                  type="checkbox"
                  checked={Boolean(workspace.hr_settings[key as keyof HrSettings])}
                  onChange={(event) => updateHrSettings({ [key]: event.target.checked } as Partial<HrSettings>)}
                />
                {label}
              </label>
            ))}
          </div>
        </div>
        <div className="mt-5 flex justify-end">
          <Button onClick={() => setWorkspaceFromApi(requestJson("/api/settings/hr", { method: "POST", body: JSON.stringify(workspace.hr_settings) }), "HR settings сохранены")}>
            <Save className="size-4" />
            Сохранить настройки
          </Button>
        </div>
      </Panel>

      <Panel title="Меню мессенджера" subtitle="Наборы кнопок, запуск сценариев и переходы между наборами.">
        <div className="mb-5 flex flex-wrap items-end gap-3 rounded-[10px] bg-[var(--color-panel-muted)] p-4">
          <FieldLabel label="Новый набор кнопок">
            <Input value={newMenuSetTitle} onChange={(event) => setNewMenuSetTitle(event.target.value)} placeholder="Главное меню" />
          </FieldLabel>
          <Button
            onClick={() =>
              setWorkspaceFromApi(
                requestJson("/api/settings/menu-sets", { method: "POST", body: JSON.stringify({ title: newMenuSetTitle }) }),
                "Набор кнопок создан",
              ).then(() => setNewMenuSetTitle(""))
            }
          >
            <Plus className="size-4" />
            Создать
          </Button>
        </div>

        <div className="grid gap-4">
          {workspace.menu_sets.map((menuSet) => {
            const draft = buttonDrafts[menuSet.id] || { label: "", action_type: "inactive", scenario_key: "", target_menu_set_id: "" };
            return (
              <article key={menuSet.id} className="rounded-[10px] border border-[var(--color-border)] bg-white p-4">
                <div className="grid gap-3 md:grid-cols-[1fr_1fr_auto]">
                  <FieldLabel label="Название набора">
                    <Input value={menuSet.title} onChange={(event) => updateMenuSetLocal(menuSet.id, { title: event.target.value })} />
                  </FieldLabel>
                  <FieldLabel label="Описание">
                    <Input value={menuSet.description} onChange={(event) => updateMenuSetLocal(menuSet.id, { description: event.target.value })} />
                  </FieldLabel>
                  <div className="flex items-end gap-2">
                    <Button variant="secondary" onClick={() => setWorkspaceFromApi(requestJson(`/api/settings/menu-sets/${menuSet.id}`, { method: "POST", body: JSON.stringify(menuSet) }), "Набор сохранен")}>
                      <Save className="size-4" />
                      Сохранить
                    </Button>
                    <Button variant="outline" onClick={() => window.confirm("Удалить набор кнопок?") && setWorkspaceFromApi(requestJson(`/api/settings/menu-sets/${menuSet.id}`, { method: "DELETE" }), "Набор удален")}>
                      <Trash2 className="size-4" />
                    </Button>
                  </div>
                </div>

                <div className="mt-4 grid gap-2">
                  {menuSet.buttons.map((button) => (
                    <div key={button.id} className="grid gap-2 rounded-[10px] bg-[var(--color-panel-muted)] p-3 md:grid-cols-[1.1fr_0.8fr_1fr_1fr_auto]">
                      <Input value={button.label} onChange={(event) => updateMenuButtonLocal(button.id, { label: event.target.value })} placeholder="Кнопка" />
                      <SelectField value={button.action_type} onChange={(value) => updateMenuButtonLocal(button.id, { action_type: value })}>
                        <option value="inactive">Неактивна</option>
                        <option value="launch_scenario">Запуск сценария</option>
                        <option value="open_set">Переход к набору</option>
                      </SelectField>
                      <SelectField value={button.scenario_key} onChange={(value) => updateMenuButtonLocal(button.id, { scenario_key: value })}>
                        <option value="">Сценарий</option>
                        {workspace.available_scenarios.map((scenario) => (
                          <option key={scenario.scenario_key} value={scenario.scenario_key}>
                            {scenario.title}
                          </option>
                        ))}
                      </SelectField>
                      <SelectField value={button.target_menu_set_id ? String(button.target_menu_set_id) : ""} onChange={(value) => updateMenuButtonLocal(button.id, { target_menu_set_id: value ? Number(value) : null })}>
                        <option value="">Набор</option>
                        {workspace.menu_sets.map((targetSet) => (
                          <option key={targetSet.id} value={targetSet.id}>
                            {targetSet.title}
                          </option>
                        ))}
                      </SelectField>
                      <div className="flex gap-2">
                        <Button variant="secondary" onClick={() => setWorkspaceFromApi(requestJson(`/api/settings/menu-buttons/${button.id}`, { method: "POST", body: JSON.stringify(button) }), "Кнопка сохранена")}>
                          <Save className="size-4" />
                        </Button>
                        <Button variant="outline" onClick={() => window.confirm("Удалить кнопку?") && setWorkspaceFromApi(requestJson(`/api/settings/menu-buttons/${button.id}`, { method: "DELETE" }), "Кнопка удалена")}>
                          <Trash2 className="size-4" />
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="mt-4 grid gap-2 rounded-[10px] border border-dashed border-[var(--color-border)] p-3 md:grid-cols-[1.1fr_0.8fr_1fr_1fr_auto]">
                  <Input value={draft.label} onChange={(event) => setButtonDrafts((current) => ({ ...current, [menuSet.id]: { ...draft, label: event.target.value } }))} placeholder="Новая кнопка" />
                  <SelectField value={draft.action_type} onChange={(value) => setButtonDrafts((current) => ({ ...current, [menuSet.id]: { ...draft, action_type: value } }))}>
                    <option value="inactive">Неактивна</option>
                    <option value="launch_scenario">Запуск сценария</option>
                    <option value="open_set">Переход к набору</option>
                  </SelectField>
                  <SelectField value={draft.scenario_key} onChange={(value) => setButtonDrafts((current) => ({ ...current, [menuSet.id]: { ...draft, scenario_key: value } }))}>
                    <option value="">Сценарий</option>
                    {workspace.available_scenarios.map((scenario) => (
                      <option key={scenario.scenario_key} value={scenario.scenario_key}>
                        {scenario.title}
                      </option>
                    ))}
                  </SelectField>
                  <SelectField value={draft.target_menu_set_id} onChange={(value) => setButtonDrafts((current) => ({ ...current, [menuSet.id]: { ...draft, target_menu_set_id: value } }))}>
                    <option value="">Набор</option>
                    {workspace.menu_sets.map((targetSet) => (
                      <option key={targetSet.id} value={targetSet.id}>
                        {targetSet.title}
                      </option>
                    ))}
                  </SelectField>
                  <Button
                    onClick={() =>
                      setWorkspaceFromApi(
                        requestJson(`/api/settings/menu-sets/${menuSet.id}/buttons`, { method: "POST", body: JSON.stringify(draft) }),
                        "Кнопка создана",
                      ).then(() => setButtonDrafts((current) => ({ ...current, [menuSet.id]: { label: "", action_type: "inactive", scenario_key: "", target_menu_set_id: "" } })))
                    }
                  >
                    <Plus className="size-4" />
                  </Button>
                </div>
              </article>
            );
          })}
        </div>
      </Panel>

      {isAdmin ? (
        <Panel title="Доступ в админку" subtitle="Управление аккаунтами доступно только администраторам.">
          <div className="mb-5 grid gap-3 rounded-[10px] bg-[var(--color-panel-muted)] p-4 md:grid-cols-[1fr_1fr_0.7fr_0.6fr_auto]">
            <Input value={newAccount.login} onChange={(event) => setNewAccount((current) => ({ ...current, login: event.target.value }))} placeholder="Логин" />
            <Input type="password" value={newAccount.password} onChange={(event) => setNewAccount((current) => ({ ...current, password: event.target.value }))} placeholder="Пароль" />
            <SelectField value={newAccount.role} onChange={(value) => setNewAccount((current) => ({ ...current, role: value }))}>
              {Object.entries(workspace.role_labels).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </SelectField>
            <SelectField value={newAccount.is_active ? "true" : "false"} onChange={(value) => setNewAccount((current) => ({ ...current, is_active: value === "true" }))}>
              <option value="true">Активен</option>
              <option value="false">Отключен</option>
            </SelectField>
            <Button
              onClick={() =>
                setWorkspaceFromApi(requestJson("/api/accounts", { method: "POST", body: JSON.stringify(newAccount) }), "Аккаунт создан").then(() =>
                  setNewAccount({ login: "", password: "", role: "hr", is_active: true }),
                )
              }
            >
              <Shield className="size-4" />
              Создать
            </Button>
          </div>

          <div className="grid gap-2">
            {workspace.accounts.map((account) => (
              <div key={account.id} className="grid gap-2 rounded-[10px] border border-[var(--color-border)] bg-white p-3 md:grid-cols-[1fr_0.7fr_0.6fr_1fr_auto]">
                <Input value={account.login} onChange={(event) => updateAccountLocal(account.id, { login: event.target.value })} />
                <SelectField value={account.role} onChange={(value) => updateAccountLocal(account.id, { role: value })}>
                  {Object.entries(workspace.role_labels).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </SelectField>
                <SelectField value={account.is_active ? "true" : "false"} onChange={(value) => updateAccountLocal(account.id, { is_active: value === "true" })}>
                  <option value="true">Активен</option>
                  <option value="false">Отключен</option>
                </SelectField>
                <Input
                  type="password"
                  value={accountPasswords[account.id] || ""}
                  placeholder="Новый пароль"
                  onChange={(event) => setAccountPasswords((current) => ({ ...current, [account.id]: event.target.value }))}
                />
                <div className="flex gap-2">
                  <Button
                    variant="secondary"
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
                    <Save className="size-4" />
                  </Button>
                  {account.id !== workspace.current_user.id ? (
                    <Button variant="outline" onClick={() => window.confirm("Удалить аккаунт?") && setWorkspaceFromApi(requestJson(`/api/accounts/${account.id}`, { method: "DELETE" }), "Аккаунт удален")}>
                      <Trash2 className="size-4" />
                    </Button>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        </Panel>
      ) : null}
    </div>
  );
}
