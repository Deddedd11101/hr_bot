import React from "react";
import { AlertTriangle, CalendarClock, ExternalLink, Play, Send, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

type Option = { value: string; label: string };
type EmployeeOption = { id: number; label: string; kind: string };
type ScenarioOption = { id: number; scenario_key: string; title: string; scenario_kind: string };
type BulkAction = {
  id: number;
  flow_key?: string;
  title?: string;
  message_text?: string;
  requested_at_label: string;
  processed_at_label: string;
  recipient_count: number;
  recipient_scope: string;
};
type Workspace = {
  scenarios: ScenarioOption[];
  surveys: ScenarioOption[];
  employee_options: EmployeeOption[];
  role_scope_options: Option[];
  employee_stage_options: Option[];
  candidate_stage_options: Option[];
  document_tag_titles: string[];
  scheduled_scenario_actions: BulkAction[];
  manual_scenario_history: BulkAction[];
  scheduled_survey_actions: BulkAction[];
  manual_survey_history: BulkAction[];
  scheduled_message_actions: BulkAction[];
  manual_message_history: BulkAction[];
};
type TargetState = {
  target_role_scope: string;
  target_employee_id: string;
  target_employee_stages: string[];
  target_candidate_stages: string[];
};
type Preview = {
  recipient_count: number;
  recipient_scope: string;
};

export type BulkActionsPageProps = {
  apiUrl: string;
  classicUrl: string;
};

const defaultTargets: TargetState = {
  target_role_scope: "",
  target_employee_id: "",
  target_employee_stages: [],
  target_candidate_stages: [],
};

async function requestJson<T>(path: string, options: RequestInit = {}) {
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
  return response.json() as Promise<T>;
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
      className="h-10 w-full min-w-0 rounded-[10px] border border-[var(--color-border)] bg-white px-3 text-sm transition-all duration-200 hover:rounded-[18px] focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]/20"
    >
      {children}
    </select>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="bulk-field">
      <span className="text-sm font-semibold text-[var(--color-foreground)]/75">{label}</span>
      {children}
    </label>
  );
}

function Panel({
  title,
  subtitle,
  children,
  className = "",
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={`bulk-panel ${className}`}>
      <div className="mb-5">
        <h2 className="text-xl font-semibold">{title}</h2>
        <p className="mt-1 text-sm text-[var(--color-muted-foreground)]">{subtitle}</p>
      </div>
      {children}
    </section>
  );
}

function MultiCheck({
  label,
  options,
  values,
  onChange,
}: {
  label: string;
  options: Option[];
  values: string[];
  onChange: (values: string[]) => void;
}) {
  return (
    <div className="bulk-choice-field">
      <span className="text-sm font-semibold text-[var(--color-foreground)]/75">{label}</span>
      <div className="bulk-chip-list">
        {options.map((option) => {
          const checked = values.includes(option.value);
          return (
            <button
              key={option.value}
              type="button"
              onClick={() => onChange(checked ? values.filter((value) => value !== option.value) : values.concat(option.value))}
              className={`rounded-[10px] border px-3 py-2 text-sm font-medium transition-all duration-200 hover:rounded-[18px] ${
                checked ? "border-[var(--color-accent)] bg-[var(--color-panel-muted)]" : "border-[var(--color-border)] bg-white"
              }`}
            >
              {option.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function TargetPicker({
  workspace,
  targets,
  onChange,
}: {
  workspace: Workspace;
  targets: TargetState;
  onChange: (targets: TargetState) => void;
}) {
  return (
    <div className="bulk-target-picker">
      <div className="bulk-target-row">
        <Field label="Привязка к должности">
          <SelectField value={targets.target_role_scope} onChange={(value) => onChange({ ...targets, target_role_scope: value })}>
            <option value="">Все должности</option>
            {workspace.role_scope_options
              .filter((option) => option.value !== "all")
              .map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
          </SelectField>
        </Field>
        <Field label="Конкретный сотрудник/кандидат">
          <SelectField value={targets.target_employee_id} onChange={(value) => onChange({ ...targets, target_employee_id: value })}>
            <option value="">Не выбран</option>
            {workspace.employee_options.map((employee) => (
              <option key={employee.id} value={employee.id}>
                {employee.label}
              </option>
            ))}
          </SelectField>
        </Field>
      </div>
      <div className="bulk-stage-row">
        <MultiCheck
          label="Этапы сотрудников"
          options={workspace.employee_stage_options}
          values={targets.target_employee_stages}
          onChange={(values) => onChange({ ...targets, target_employee_stages: values })}
        />
        <MultiCheck
          label="Этапы кандидатов"
          options={workspace.candidate_stage_options}
          values={targets.target_candidate_stages}
          onChange={(values) => onChange({ ...targets, target_candidate_stages: values })}
        />
      </div>
    </div>
  );
}

function ActionTable({
  title,
  actions,
  onDelete,
}: {
  title: string;
  actions: BulkAction[];
  onDelete?: (id: number) => void;
}) {
  return (
    <div className="rounded-[10px] border border-[var(--color-border)] bg-white p-3">
      <h3 className="mb-3 text-sm font-semibold text-[var(--color-foreground)]/80">{title}</h3>
      {actions.length ? (
        <div className="bulk-table-list">
          {actions.map((action) => (
            <div key={action.id} className="bulk-action-row">
              <div className="min-w-0">
                <div className="truncate font-semibold">{action.title || action.message_text || "—"}</div>
                <div className="mt-1 truncate text-[var(--color-muted-foreground)]">{action.recipient_scope}</div>
              </div>
              <div className="text-[var(--color-muted-foreground)]">{action.requested_at_label || action.processed_at_label}</div>
              <div className="whitespace-nowrap font-medium">{action.recipient_count} получ.</div>
              {onDelete ? (
                <Button variant="outline" size="sm" onClick={() => window.confirm("Удалить запланированное действие?") && onDelete(action.id)}>
                  <Trash2 className="size-4" />
                </Button>
              ) : null}
            </div>
          ))}
        </div>
      ) : (
        <p className="text-sm text-[var(--color-muted-foreground)]">Пока пусто.</p>
      )}
    </div>
  );
}

export function BulkActionsPage({ apiUrl, classicUrl }: BulkActionsPageProps) {
  const [workspace, setWorkspace] = React.useState<Workspace | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [message, setMessage] = React.useState("");
  const [error, setError] = React.useState("");
  const [targets, setTargets] = React.useState<TargetState>(defaultTargets);
  const [preview, setPreview] = React.useState<Preview | null>(null);
  const [scenarioKey, setScenarioKey] = React.useState("");
  const [surveyKey, setSurveyKey] = React.useState("");
  const [requestedAt, setRequestedAt] = React.useState("");
  const [messageText, setMessageText] = React.useState("");

  React.useEffect(() => {
    requestJson<Workspace>(apiUrl)
      .then((payload) => {
        setWorkspace(payload);
        setScenarioKey(payload.scenarios[0]?.scenario_key || "");
        setSurveyKey(payload.surveys[0]?.scenario_key || "");
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Не удалось загрузить массовые действия"))
      .finally(() => setLoading(false));
  }, [apiUrl]);

  const refreshWorkspace = async () => {
    const payload = await requestJson<Workspace>(apiUrl);
    setWorkspace(payload);
    return payload;
  };

  const buildPreview = async (nextTargets: TargetState) => {
    try {
      const nextPreview = await requestJson<Preview>("/api/bulk-actions/preview", {
        method: "POST",
        body: JSON.stringify(nextTargets),
      });
      setPreview(nextPreview);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось построить preview");
    }
  };

  const updateTargets = (nextTargets: TargetState) => {
    setTargets(nextTargets);
    void buildPreview(nextTargets);
  };

  const payloadBase = () => ({
    target_role_scope: targets.target_role_scope || null,
    target_employee_id: targets.target_employee_id ? Number(targets.target_employee_id) : null,
    target_employee_stages: targets.target_employee_stages,
    target_candidate_stages: targets.target_candidate_stages,
  });

  const runMutation = async (path: string, body: Record<string, unknown>, successMessage: string, method = "POST") => {
    setError("");
    setMessage("");
    try {
      await requestJson(path, { method, body: JSON.stringify(body) });
      await refreshWorkspace();
      await buildPreview(targets);
      setMessage(successMessage);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Операция не выполнена");
    }
  };

  const canRunImmediate = preview ? preview.recipient_count > 0 : true;

  if (loading) {
    return <div className="rounded-[10px] border border-[var(--color-border)] bg-white p-8 text-sm text-[var(--color-muted-foreground)]">Загружаю массовые действия...</div>;
  }

  if (!workspace) {
    return <div className="rounded-[10px] border border-[var(--color-border)] bg-white p-8 text-sm text-[var(--color-danger)]">{error || "Массовые действия не загружены"}</div>;
  }

  return (
    <div className="bulk-page">
      <header className="bulk-hero">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--color-muted-foreground)]">React admin</p>
          <h1 className="mt-2 text-3xl font-semibold">Массовые действия</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--color-muted-foreground)]">
            Единая точка для сценариев, сообщений и опросов. Classic page оставлена как fallback, но все новые действия должны жить здесь.
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

      <Panel title="Кого затронет действие" subtitle="Фильтры применяются ко всем типам действий ниже." className="bulk-audience-panel">
        <TargetPicker workspace={workspace} targets={targets} onChange={updateTargets} />
        {preview ? (
          <div className="mt-4 flex flex-wrap items-center gap-3 rounded-[10px] border border-[var(--color-border)] bg-white px-4 py-3 text-sm">
            <span className="font-semibold">{preview.recipient_count} получателей</span>
            <span className="text-[var(--color-muted-foreground)]">{preview.recipient_scope}</span>
          </div>
        ) : (
          <div className="mt-4 flex items-center gap-2 rounded-[10px] border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            <AlertTriangle className="size-4" />
            Preview обновится после выбора аудитории.
          </div>
        )}
      </Panel>

      <div className="bulk-actions-grid">
        <Panel title="Сценарии" subtitle="Запланировать или сразу запустить сценарий.">
          <div className="bulk-card-form">
            <Field label="Сценарий">
              <SelectField value={scenarioKey} onChange={setScenarioKey}>
                {workspace.scenarios.map((scenario) => (
                  <option key={scenario.scenario_key} value={scenario.scenario_key}>
                    {scenario.title}
                  </option>
                ))}
              </SelectField>
            </Field>
            <Field label="Дата и время для расписания">
              <Input type="datetime-local" value={requestedAt} onChange={(event) => setRequestedAt(event.target.value)} />
            </Field>
            <div className="flex flex-wrap gap-2">
              <Button onClick={() => runMutation("/api/bulk-actions/scenarios/schedule", { ...payloadBase(), flow_key: scenarioKey, requested_at: requestedAt }, "Сценарий запланирован")}>
                <CalendarClock className="size-4" />
                Запланировать
              </Button>
              <Button variant="destructive" disabled={!canRunImmediate} onClick={() => runMutation("/api/bulk-actions/scenarios/launch", { ...payloadBase(), flow_key: scenarioKey, confirmed: true }, "Сценарий запущен")}>
                <Play className="size-4" />
                Запустить сейчас
              </Button>
            </div>
          </div>
        </Panel>

        <Panel title="Сообщения" subtitle="Свободный текст для выбранной аудитории.">
          <div className="bulk-card-form">
            <Field label="Текст сообщения">
              <Textarea value={messageText} onChange={(event) => setMessageText(event.target.value)} rows={5} placeholder="Введите сообщение" />
            </Field>
            <div className="flex flex-wrap gap-2">
              {["{name}", "{full_name}"].concat(workspace.document_tag_titles.map((title) => `{doc:${title}}`)).map((token) => (
                <button key={token} type="button" className="rounded-[10px] border border-[var(--color-border)] px-2.5 py-1.5 text-xs font-semibold" onClick={() => setMessageText((current) => `${current}${token}`)}>
                  {token}
                </button>
              ))}
            </div>
            <Field label="Дата и время для расписания">
              <Input type="datetime-local" value={requestedAt} onChange={(event) => setRequestedAt(event.target.value)} />
            </Field>
            <div className="flex flex-wrap gap-2">
              <Button onClick={() => runMutation("/api/bulk-actions/messages/schedule", { ...payloadBase(), message_text: messageText, requested_at: requestedAt }, "Сообщение запланировано")}>
                <CalendarClock className="size-4" />
                Запланировать
              </Button>
              <Button variant="destructive" disabled={!canRunImmediate} onClick={() => runMutation("/api/bulk-actions/messages/send", { ...payloadBase(), message_text: messageText, confirmed: true }, "Сообщение отправлено")}>
                <Send className="size-4" />
                Отправить сейчас
              </Button>
            </div>
          </div>
        </Panel>

        <Panel title="Опросы" subtitle="Запланировать или сразу запустить опрос.">
          <div className="bulk-card-form">
            <Field label="Опрос">
              <SelectField value={surveyKey} onChange={setSurveyKey}>
                {workspace.surveys.map((survey) => (
                  <option key={survey.scenario_key} value={survey.scenario_key}>
                    {survey.title}
                  </option>
                ))}
              </SelectField>
            </Field>
            <Field label="Дата и время для расписания">
              <Input type="datetime-local" value={requestedAt} onChange={(event) => setRequestedAt(event.target.value)} />
            </Field>
            <div className="flex flex-wrap gap-2">
              <Button onClick={() => runMutation("/api/bulk-actions/surveys/schedule", { ...payloadBase(), flow_key: surveyKey, requested_at: requestedAt }, "Опрос запланирован")}>
                <CalendarClock className="size-4" />
                Запланировать
              </Button>
              <Button variant="destructive" disabled={!canRunImmediate} onClick={() => runMutation("/api/bulk-actions/surveys/launch", { ...payloadBase(), flow_key: surveyKey, confirmed: true }, "Опрос запущен")}>
                <Play className="size-4" />
                Запустить сейчас
              </Button>
            </div>
          </div>
        </Panel>
      </div>

      <div className="bulk-history-grid">
        <Panel title="История сценариев" subtitle="Запланированные и последние ручные запуски.">
          <div className="bulk-card-form">
            <ActionTable title="Запланировано" actions={workspace.scheduled_scenario_actions} onDelete={(id) => runMutation(`/api/bulk-actions/scenarios/${id}`, {}, "Запланированный запуск удален", "DELETE")} />
            <ActionTable title="История" actions={workspace.manual_scenario_history} />
          </div>
        </Panel>
        <Panel title="История сообщений" subtitle="Запланированные и последние ручные отправки.">
          <div className="bulk-card-form">
            <ActionTable title="Запланировано" actions={workspace.scheduled_message_actions} onDelete={(id) => runMutation(`/api/bulk-actions/messages/${id}`, {}, "Запланированная отправка удалена", "DELETE")} />
            <ActionTable title="История" actions={workspace.manual_message_history} />
          </div>
        </Panel>
        <Panel title="История опросов" subtitle="Запланированные и последние ручные запуски.">
          <div className="bulk-card-form">
            <ActionTable title="Запланировано" actions={workspace.scheduled_survey_actions} onDelete={(id) => runMutation(`/api/bulk-actions/scenarios/${id}`, {}, "Запланированный запуск удален", "DELETE")} />
            <ActionTable title="История" actions={workspace.manual_survey_history} />
          </div>
        </Panel>
      </div>
    </div>
  );
}
