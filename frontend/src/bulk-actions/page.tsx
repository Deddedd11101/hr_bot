import React from "react";
import { AlertTriangle, CalendarClock, Play, Send, Trash2 } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { ConfirmAction } from "@/components/ui/confirm-action";
import { DateTimePicker } from "@/components/ui/date-picker";
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { Field, FieldContent, FieldGroup, FieldLabel, FieldTitle } from "@/components/ui/field";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

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
};

const EMPTY_SELECT_VALUE = "__empty__";

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

function AppSelect({
  value,
  onChange,
  options,
  placeholder = "Не выбрано",
  allowEmpty = true,
}: {
  value: string;
  onChange: (value: string) => void;
  options: Option[];
  placeholder?: string;
  allowEmpty?: boolean;
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
      <SelectTrigger className="w-full">
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

function SurfaceCard({
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
      <CardContent className="grid gap-4 pt-5">{children}</CardContent>
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
      <AlertTitle>{type === "success" ? "Готово" : "Ошибка"}</AlertTitle>
      <AlertDescription>{message}</AlertDescription>
    </Alert>
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
    <Field>
      <FieldLabel>{label}</FieldLabel>
      <div className="rounded-lg border border-border bg-muted/35 p-3">
        <ScrollArea className="max-h-48 pr-2">
          <FieldGroup className="grid gap-2 sm:grid-cols-2">
            {options.map((option) => {
              const checked = values.includes(option.value);
              return (
                <Field orientation="horizontal" key={option.value}>
                  <Checkbox
                    checked={checked}
                    onCheckedChange={() => onChange(checked ? values.filter((value) => value !== option.value) : values.concat(option.value))}
                  />
                  <FieldContent>
                    <FieldTitle>{option.label}</FieldTitle>
                  </FieldContent>
                </Field>
              );
            })}
          </FieldGroup>
        </ScrollArea>
      </div>
    </Field>
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
  const roleOptions = workspace.role_scope_options.filter((option) => option.value !== "all");
  const employeeOptions = workspace.employee_options.map((employee) => ({
    value: String(employee.id),
    label: employee.label,
  }));

  return (
    <FieldGroup className="grid gap-4">
      <div className="grid gap-4 lg:grid-cols-2">
        <Field>
          <FieldLabel>Привязка к должности</FieldLabel>
          <AppSelect value={targets.target_role_scope} onChange={(value) => onChange({ ...targets, target_role_scope: value })} options={roleOptions} placeholder="Все должности" />
        </Field>
        <Field>
          <FieldLabel>Конкретный сотрудник/кандидат</FieldLabel>
          <AppSelect value={targets.target_employee_id} onChange={(value) => onChange({ ...targets, target_employee_id: value })} options={employeeOptions} placeholder="Не выбран" />
        </Field>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
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
    </FieldGroup>
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
    <Card size="sm" className="border border-border bg-background shadow-none ring-0">
      <CardHeader className="border-b border-border/70 pb-3">
        <CardTitle className="text-sm font-semibold">{title}</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-2 pt-3">
        {actions.length ? (
          actions.map((action) => (
            <div key={action.id} className="grid gap-2 rounded-lg border border-border bg-muted/35 p-3 xl:grid-cols-[minmax(0,1fr)_150px_96px_auto] xl:items-center">
              <div className="min-w-0">
                <div className="truncate text-sm font-semibold">{action.title || action.message_text || "-"}</div>
                <div className="mt-1 truncate text-xs text-muted-foreground">{action.recipient_scope}</div>
              </div>
              <div className="text-xs text-muted-foreground">{action.requested_at_label || action.processed_at_label}</div>
              <Badge variant="secondary" className="justify-self-start whitespace-nowrap">
                {action.recipient_count} получ.
              </Badge>
              {onDelete ? (
                <ConfirmAction
                  title="Удалить запланированное действие?"
                  description="Действие будет удалено из расписания. Уже выполненные запуски не затрагиваются."
                  actionLabel="Удалить"
                  onConfirm={() => onDelete(action.id)}
                >
                  <Button variant="outline" size="icon-sm" aria-label="Удалить запланированное действие">
                    <Trash2 />
                  </Button>
                </ConfirmAction>
              ) : null}
            </div>
          ))
        ) : (
          <Empty className="min-h-24 border border-dashed border-border bg-muted/20">
            <EmptyHeader>
              <EmptyTitle>Пока пусто</EmptyTitle>
              <EmptyDescription>Действия появятся после запуска или планирования.</EmptyDescription>
            </EmptyHeader>
          </Empty>
        )}
      </CardContent>
    </Card>
  );
}

function scenarioOptions(items: ScenarioOption[]): Option[] {
  return items.map((item) => ({ value: item.scenario_key, label: item.title }));
}

export function BulkActionsPage({ apiUrl }: BulkActionsPageProps) {
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
    return (
      <Card className="admin-page-shell border border-border/80 bg-card shadow-none ring-0">
        <CardContent className="p-8 text-sm text-muted-foreground">Загружаю массовые действия...</CardContent>
      </Card>
    );
  }

  if (!workspace) {
    return (
      <div className="admin-page-stack gap-4">
        <StatusAlert type="error" message={error || "Массовые действия не загружены"} />
      </div>
    );
  }

  const scenarioItems = scenarioOptions(workspace.scenarios);
  const surveyItems = scenarioOptions(workspace.surveys);

  return (
    <div className="admin-page-stack gap-5">
      <header className="admin-page-surface border border-border/80 bg-card p-5 shadow-none ring-0">
        <h1 className="text-3xl font-semibold tracking-tight">Массовые действия</h1>
      </header>

      <StatusAlert type="success" message={message} />
      <StatusAlert type="error" message={error} />

      <SurfaceCard title="Кого затронет действие">
        <TargetPicker workspace={workspace} targets={targets} onChange={updateTargets} />
        {preview ? (
          <Alert className="border-primary/30 bg-primary/5">
            <AlertTitle>{preview.recipient_count} получателей</AlertTitle>
            <AlertDescription>{preview.recipient_scope}</AlertDescription>
          </Alert>
        ) : (
          <Alert className="border-warning/40 bg-warning/10">
            <AlertTriangle />
            <AlertTitle>Preview не построен</AlertTitle>
            <AlertDescription>Preview обновится после выбора аудитории.</AlertDescription>
          </Alert>
        )}
      </SurfaceCard>

      <div className="grid gap-5 xl:grid-cols-3">
        <SurfaceCard title="Сценарии">
          <Field>
            <FieldLabel>Сценарий</FieldLabel>
            <AppSelect value={scenarioKey} onChange={setScenarioKey} options={scenarioItems} allowEmpty={false} />
          </Field>
          <Field>
            <FieldLabel>Дата и время для расписания</FieldLabel>
            <DateTimePicker value={requestedAt} onValueChange={setRequestedAt} />
          </Field>
          <div className="flex flex-wrap justify-end gap-2">
            <Button variant="secondary" onClick={() => runMutation("/api/bulk-actions/scenarios/schedule", { ...payloadBase(), flow_key: scenarioKey, requested_at: requestedAt }, "Сценарий запланирован")}>
              <CalendarClock data-icon="inline-start" />
              Запланировать
            </Button>
            <Button disabled={!canRunImmediate} onClick={() => runMutation("/api/bulk-actions/scenarios/launch", { ...payloadBase(), flow_key: scenarioKey, confirmed: true }, "Сценарий запущен")}>
              <Play data-icon="inline-start" />
              Сейчас
            </Button>
          </div>
        </SurfaceCard>

        <SurfaceCard title="Сообщения">
          <Field>
            <FieldLabel>Текст сообщения</FieldLabel>
            <Textarea value={messageText} onChange={(event) => setMessageText(event.target.value)} rows={5} placeholder="Введите сообщение" autoComplete="off" />
          </Field>
          <div className="flex flex-wrap gap-2">
            {["{name}", "{full_name}"].concat(workspace.document_tag_titles.map((title) => `{doc:${title}}`)).map((token) => (
              <Button key={token} type="button" variant="secondary" size="xs" onClick={() => setMessageText((current) => `${current}${token}`)}>
                {token}
              </Button>
            ))}
          </div>
          <Field>
            <FieldLabel>Дата и время для расписания</FieldLabel>
            <DateTimePicker value={requestedAt} onValueChange={setRequestedAt} />
          </Field>
          <div className="flex flex-wrap justify-end gap-2">
            <Button variant="secondary" onClick={() => runMutation("/api/bulk-actions/messages/schedule", { ...payloadBase(), message_text: messageText, requested_at: requestedAt }, "Сообщение запланировано")}>
              <CalendarClock data-icon="inline-start" />
              Запланировать
            </Button>
            <Button disabled={!canRunImmediate} onClick={() => runMutation("/api/bulk-actions/messages/send", { ...payloadBase(), message_text: messageText, confirmed: true }, "Сообщение отправлено")}>
              <Send data-icon="inline-start" />
              Сейчас
            </Button>
          </div>
        </SurfaceCard>

        <SurfaceCard title="Опросы">
          <Field>
            <FieldLabel>Опрос</FieldLabel>
            <AppSelect value={surveyKey} onChange={setSurveyKey} options={surveyItems} allowEmpty={false} />
          </Field>
          <Field>
            <FieldLabel>Дата и время для расписания</FieldLabel>
            <DateTimePicker value={requestedAt} onValueChange={setRequestedAt} />
          </Field>
          <div className="flex flex-wrap justify-end gap-2">
            <Button variant="secondary" onClick={() => runMutation("/api/bulk-actions/surveys/schedule", { ...payloadBase(), flow_key: surveyKey, requested_at: requestedAt }, "Опрос запланирован")}>
              <CalendarClock data-icon="inline-start" />
              Запланировать
            </Button>
            <Button disabled={!canRunImmediate} onClick={() => runMutation("/api/bulk-actions/surveys/launch", { ...payloadBase(), flow_key: surveyKey, confirmed: true }, "Опрос запущен")}>
              <Play data-icon="inline-start" />
              Сейчас
            </Button>
          </div>
        </SurfaceCard>
      </div>

      <div className="grid gap-5 xl:grid-cols-3">
        <SurfaceCard title="История сценариев">
          <ActionTable title="Запланировано" actions={workspace.scheduled_scenario_actions} onDelete={(id) => runMutation(`/api/bulk-actions/scenarios/${id}`, {}, "Запланированный запуск удален", "DELETE")} />
          <ActionTable title="История" actions={workspace.manual_scenario_history} />
        </SurfaceCard>
        <SurfaceCard title="История сообщений">
          <ActionTable title="Запланировано" actions={workspace.scheduled_message_actions} onDelete={(id) => runMutation(`/api/bulk-actions/messages/${id}`, {}, "Запланированная отправка удалена", "DELETE")} />
          <ActionTable title="История" actions={workspace.manual_message_history} />
        </SurfaceCard>
        <SurfaceCard title="История опросов">
          <ActionTable title="Запланировано" actions={workspace.scheduled_survey_actions} onDelete={(id) => runMutation(`/api/bulk-actions/surveys/${id}`, {}, "Запланированный запуск удален", "DELETE")} />
          <ActionTable title="История" actions={workspace.manual_survey_history} />
        </SurfaceCard>
      </div>
    </div>
  );
}
