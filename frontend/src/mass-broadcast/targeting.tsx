import React from "react";

import { Checkbox } from "@/components/ui/checkbox";
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

/**
 * Выбор аудитории массовой рассылки.
 *
 * Модуль общий для страницы сообщений и диалога рассылки в детали сценария
 * или опроса: аудитория, предпросмотр охвата и контракт «сначала preview,
 * затем confirmed=true» должны быть одинаковыми везде, где есть массовая
 * отправка. Раньше всё это жило внутри страницы массовых действий.
 */

export type Option = { value: string; label: string };
export type EmployeeOption = { id: number; label: string; kind: string };
export type ScenarioOption = { id: number; scenario_key: string; title: string; scenario_kind: string };

export type TargetState = {
  target_role_scope: string;
  target_employee_id: string;
  target_employee_stages: string[];
  target_candidate_stages: string[];
};

export type Preview = {
  recipient_count: number;
  recipient_scope: string;
};

/** Опции аудитории из payload `/api/bulk-actions/workspace`. */
export type TargetingWorkspace = {
  employee_options: EmployeeOption[];
  role_scope_options: Option[];
  employee_stage_options: Option[];
  candidate_stage_options: Option[];
};

export const defaultTargets: TargetState = {
  target_role_scope: "",
  target_employee_id: "",
  target_employee_stages: [],
  target_candidate_stages: [],
};

/** Тело запроса рассылки: null вместо пустых строк, id числом. */
export function targetPayload(targets: TargetState) {
  return {
    target_role_scope: targets.target_role_scope || null,
    target_employee_id: targets.target_employee_id ? Number(targets.target_employee_id) : null,
    target_employee_stages: targets.target_employee_stages,
    target_candidate_stages: targets.target_candidate_stages,
  };
}

export async function requestJson<T>(path: string, options: RequestInit = {}) {
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
    throw new Error((payload as { detail?: string }).detail || "Запрос не выполнен");
  }
  return response.json() as Promise<T>;
}

const EMPTY_SELECT_VALUE = "__empty__";

export function AppSelect({
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
          {/*
            Колонки от ширины самого блока, а не вьюпорта: sm:grid-cols-2
            делил список пополам даже в диалоге, где блоку достаётся ~290px,
            и подписи этапов переносились посреди слова. Колонка появляется,
            только когда ей есть 11rem — самая длинная подпись («Заключение
            договора») укладывается в неё целиком.
          */}
          <FieldGroup className="grid grid-cols-[repeat(auto-fill,minmax(11rem,1fr))] gap-2">
            {options.map((option) => {
              const checked = values.includes(option.value);
              return (
                <Field orientation="horizontal" key={option.value}>
                  <Checkbox
                    checked={checked}
                    onCheckedChange={() =>
                      onChange(checked ? values.filter((value) => value !== option.value) : values.concat(option.value))
                    }
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

export function TargetPicker({
  workspace,
  targets,
  onChange,
}: {
  workspace: TargetingWorkspace;
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
          <AppSelect
            value={targets.target_role_scope}
            onChange={(value) => onChange({ ...targets, target_role_scope: value })}
            options={roleOptions}
            placeholder="Все должности"
          />
        </Field>
        <Field>
          <FieldLabel>Конкретный сотрудник/кандидат</FieldLabel>
          <AppSelect
            value={targets.target_employee_id}
            onChange={(value) => onChange({ ...targets, target_employee_id: value })}
            options={employeeOptions}
            placeholder="Не выбран"
          />
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
