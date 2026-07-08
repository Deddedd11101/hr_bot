import * as React from "react";
import { ChevronsUpDown, Search } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import { parseRecipientIds } from "./model";
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
  const [search, setSearch] = React.useState("");
  const selectedIds = React.useMemo(() => parseRecipientIds(value), [value]);

  const filteredRecipients = React.useMemo(() => {
    if (!search.trim()) return recipientOptions;
    const query = search.toLowerCase();
    return recipientOptions.filter((option) => option.label.toLowerCase().includes(query));
  }, [recipientOptions, search]);

  const toggleRecipient = (token: string) => {
    const nextIds = selectedIds.includes(token)
      ? selectedIds.filter((value) => value !== token)
      : selectedIds.concat(token);
    onChange(nextIds.join(","));
  };

  const summary = selectedIds.length === 0 ? "Выбери получателей" : `${selectedIds.length} выбр.`;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger render={<Button variant="secondary" className="w-full justify-between" />}>
        <span className="truncate">{summary}</span>
        <ChevronsUpDown className="opacity-60" />
      </PopoverTrigger>
      <PopoverContent className="w-[360px] p-0" align="start">
        <div className="border-b border-border p-3">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Найти получателя"
              className="pl-9"
            />
          </div>
        </div>
        <div className="h-72 overflow-auto">
          <div className="flex flex-col gap-1 p-2">
            {filteredRecipients.map((option) => {
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
      onValueChange={(nextValue) => onChange(nextValue === emptyValue ? "" : nextValue)}
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
