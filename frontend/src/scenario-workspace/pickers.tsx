import * as React from "react";
import { ChevronsUpDown } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import {
  normalizeNotificationRecipientIds,
  parseRecipientIds,
  ROLE_NOTIFICATION_RECIPIENT_LABELS,
  ROLE_NOTIFICATION_RECIPIENT_TOKENS,
} from "./model";
import type { SingleOption, WorkspaceData } from "./types";

export function NotificationRecipientsPicker({
  recipientOptions,
  value,
  onChange,
}: {
  recipientOptions: WorkspaceData["notification_recipient_options"];
  value: string;
  onChange: (next: string) => void;
}) {
  const [open, setOpen] = React.useState(false);
  const selectedIds = React.useMemo(() => parseRecipientIds(normalizeNotificationRecipientIds(value)), [value]);
  const roleOptions = React.useMemo(() => {
    return ROLE_NOTIFICATION_RECIPIENT_TOKENS.map((token) => {
      const backendOption = recipientOptions.find((option) => option.token === token);
      return {
        token,
        label: ROLE_NOTIFICATION_RECIPIENT_LABELS[token],
        description: backendOption?.description || "",
      };
    });
  }, [recipientOptions]);

  const toggleRecipient = (token: string) => {
    const nextIds = selectedIds.includes(token)
      ? selectedIds.filter((value) => value !== token)
      : selectedIds.concat(token);
    onChange(normalizeNotificationRecipientIds(nextIds.join(",")));
  };

  const summary = selectedIds.length === 0 ? "Выбери получателей" : `${selectedIds.length} выбр.`;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger render={<Button variant="secondary" className="w-full justify-between" />}>
        <span className="truncate">{summary}</span>
        <ChevronsUpDown className="opacity-60" />
      </PopoverTrigger>
      <PopoverContent className="w-[360px] p-2" align="start">
        <div className="flex flex-col gap-1">
          {roleOptions.map((option) => {
            const checked = selectedIds.includes(option.token);
            return (
              <button
                key={option.token}
                type="button"
                onClick={() => toggleRecipient(option.token)}
                className="flex items-center justify-between gap-3 rounded-lg px-3 py-2 text-left transition-colors hover:bg-muted"
              >
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium">{option.label}</div>
                  <div className="text-xs text-muted-foreground">{option.description}</div>
                </div>
                <Checkbox checked={checked} aria-label={`Выбрать ${option.label}`} />
              </button>
            );
          })}
        </div>
      </PopoverContent>
    </Popover>
  );
}

export function SingleSelectPicker({
  options,
  value,
  onChange,
  placeholder,
  disabled = false,
}: {
  options: SingleOption[];
  value: string;
  onChange: (next: string) => void;
  placeholder: string;
  disabled?: boolean;
}) {
  const emptyValue = "__empty__";
  const normalizedOptions = React.useMemo(() => {
    const seen = new Set<string>();
    return options.reduce<SingleOption[]>((items, option) => {
      const normalizedValue = option.value || emptyValue;
      if (seen.has(normalizedValue)) {
        return items;
      }
      seen.add(normalizedValue);
      items.push({ ...option, value: normalizedValue });
      return items;
    }, []);
  }, [options]);
  const selected = normalizedOptions.find((option) => option.value === (value || emptyValue));
  const selectedValue = selected ? selected.value : emptyValue;

  return (
    <Select
      items={normalizedOptions}
      value={selectedValue}
      onValueChange={(nextValue) => {
        const normalizedValue = nextValue || "";
        onChange(normalizedValue === emptyValue ? "" : normalizedValue);
      }}
    >
      <SelectTrigger className="w-full" disabled={disabled}>
        <SelectValue placeholder={placeholder} className="truncate text-left" />
      </SelectTrigger>
      <SelectContent align="start" alignItemWithTrigger={false}>
        <SelectGroup>
          {normalizedOptions.map((option) => {
            return (
              <SelectItem
                key={`${option.value}-${option.label}`}
                value={option.value}
              >
                {option.label}
              </SelectItem>
            );
          })}
        </SelectGroup>
      </SelectContent>
    </Select>
  );
}

export function RoleScopesPicker({
  options,
  value,
  onChange,
}: {
  options: SingleOption[];
  value: string[];
  onChange: (next: string[]) => void;
}) {
  const [open, setOpen] = React.useState(false);
  const concreteOptions = React.useMemo(() => options.filter((option) => option.value !== "all"), [options]);
  const allLabel = "Все должности";
  const selectedValues = React.useMemo(() => {
    const concreteValues = value.filter((item) => item && item !== "all");
    return concreteValues.length ? concreteValues : ["all"];
  }, [value]);
  const selectedConcreteValues = selectedValues.filter((item) => item !== "all");
  const optionLabels = React.useMemo(() => new Map(concreteOptions.map((option) => [option.value, option.label])), [concreteOptions]);
  const selectedLabels = selectedConcreteValues.map((item) => optionLabels.get(item) || item);
  const summary = selectedConcreteValues.length ? `Выбрано: ${selectedConcreteValues.length}` : allLabel;
  const summaryItems = selectedConcreteValues.length ? selectedLabels : [allLabel];

  const selectAll = () => {
    onChange(["all"]);
  };

  const toggleConcrete = (nextValue: string) => {
    const nextConcreteValues = selectedConcreteValues.includes(nextValue)
      ? selectedConcreteValues.filter((item) => item !== nextValue)
      : selectedConcreteValues.concat(nextValue);
    onChange(nextConcreteValues.length ? nextConcreteValues : ["all"]);
  };

  return (
    <div className="grid min-w-0 gap-2">
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger render={<Button variant="secondary" className="w-full min-w-0 justify-between overflow-hidden" />}>
          <span className="min-w-0 truncate text-left">{summary}</span>
          <ChevronsUpDown className="shrink-0 opacity-60" />
        </PopoverTrigger>
        <PopoverContent className="w-[var(--anchor-width)] max-w-[min(360px,calc(100vw-48px))] p-2" align="start">
          <div className="flex max-h-72 min-w-0 flex-col gap-1 overflow-y-auto">
            <button
              type="button"
              onClick={selectAll}
              className="flex min-w-0 items-center justify-between gap-3 rounded-lg px-3 py-2 text-left transition-colors hover:bg-muted"
            >
              <span className="min-w-0 truncate text-sm font-medium">{allLabel}</span>
              <Checkbox checked={!selectedConcreteValues.length} aria-label={`Выбрать ${allLabel}`} />
            </button>
            {concreteOptions.map((option) => {
              const checked = selectedConcreteValues.includes(option.value);
              return (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => toggleConcrete(option.value)}
                  className="flex min-w-0 items-center justify-between gap-3 rounded-lg px-3 py-2 text-left transition-colors hover:bg-muted"
                >
                  <span className="min-w-0 truncate text-sm font-medium">{option.label}</span>
                  <Checkbox checked={checked} aria-label={`Выбрать ${option.label}`} />
                </button>
              );
            })}
          </div>
        </PopoverContent>
      </Popover>
      <div className="max-h-28 min-w-0 overflow-y-auto rounded-lg border border-amber-300/50 bg-amber-50/70 p-2 dark:border-amber-500/25 dark:bg-amber-500/10">
        <div className="grid min-w-0 gap-1.5">
          {summaryItems.map((item) => (
            <span
              key={item}
              className="min-w-0 break-words rounded-md bg-background/75 px-2 py-1 text-xs font-medium leading-5 text-foreground shadow-xs"
            >
              {item}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
