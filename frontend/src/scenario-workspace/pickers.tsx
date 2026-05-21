import * as React from "react";
import { Check, ChevronsUpDown, Search } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { ScrollArea } from "@/components/ui/scroll-area";

import { parseRecipientIds } from "./model";
import type { SingleOption, WorkspaceData } from "./types";

export function NotificationRecipientsPicker({
  employeeOptions,
  value,
  onChange,
}: {
  employeeOptions: WorkspaceData["employee_options"];
  value: string;
  onChange: (next: string) => void;
}) {
  const [open, setOpen] = React.useState(false);
  const [search, setSearch] = React.useState("");
  const selectedIds = React.useMemo(() => parseRecipientIds(value), [value]);

  const filteredEmployees = React.useMemo(() => {
    if (!search.trim()) return employeeOptions;
    const query = search.toLowerCase();
    return employeeOptions.filter((option) => option.label.toLowerCase().includes(query));
  }, [employeeOptions, search]);

  const toggleRecipient = (employeeId: string) => {
    const nextIds = selectedIds.includes(employeeId)
      ? selectedIds.filter((value) => value !== employeeId)
      : selectedIds.concat(employeeId);
    onChange(nextIds.join(","));
  };

  const summary = selectedIds.length === 0 ? "Выбери сотрудников" : `${selectedIds.length} выбр.`;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="secondary" className="w-full justify-between">
          <span className="truncate">{summary}</span>
          <ChevronsUpDown className="size-4 opacity-60" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[360px] p-0" align="start">
        <div className="border-b border-[var(--color-border)] p-3">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-[var(--color-muted-foreground)]" />
            <Input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Найти сотрудника"
              className="pl-9"
            />
          </div>
        </div>
        <ScrollArea className="h-72">
          <div className="flex flex-col gap-1 p-2">
            {filteredEmployees.map((option) => {
              const checked = selectedIds.includes(String(option.id));
              return (
                <button
                  key={option.id}
                  type="button"
                  onClick={() => toggleRecipient(String(option.id))}
                  className="flex items-center justify-between gap-3 rounded-xl px-3 py-2 text-left hover:bg-black/5"
                >
                  <div className="min-w-0">
                    <div className="truncate text-sm font-medium">{option.label}</div>
                    <div className="text-xs text-[var(--color-muted-foreground)]">
                      {option.kind === "candidates" ? "Кандидат" : "Сотрудник"}
                    </div>
                  </div>
                  <div
                    className={`flex size-5 shrink-0 items-center justify-center rounded-md border ${
                      checked
                        ? "border-[var(--color-accent)] bg-[var(--color-accent)] text-white"
                        : "border-[var(--color-border)] bg-white text-transparent"
                    }`}
                  >
                    <Check className="size-3.5" />
                  </div>
                </button>
              );
            })}
          </div>
        </ScrollArea>
      </PopoverContent>
    </Popover>
  );
}

export function SingleSelectPicker({
  options,
  value,
  onChange,
  placeholder,
}: {
  options: SingleOption[];
  value: string;
  onChange: (next: string) => void;
  placeholder: string;
}) {
  const [open, setOpen] = React.useState(false);
  const selected = options.find((option) => option.value === value);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="secondary" className="w-full justify-between">
          <span className="truncate text-left">{selected?.label || placeholder}</span>
          <ChevronsUpDown className="size-4 opacity-60" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="p-1.5" style={{ width: "var(--radix-popover-trigger-width)" }}>
        <div className="flex flex-col gap-1">
          {options.map((option) => {
            const checked = option.value === value;
            return (
              <button
                key={`${option.value || "__empty__"}-${option.label}`}
                type="button"
                onClick={() => {
                  onChange(option.value);
                  setOpen(false);
                }}
                className="flex items-center justify-between gap-3 rounded-[10px] px-3 py-2 text-left text-sm transition-all duration-200 hover:rounded-[16px] hover:bg-black/5"
              >
                <span className="min-w-0 flex-1 truncate">{option.label}</span>
                <div
                  className={`flex size-5 shrink-0 items-center justify-center rounded-md border ${
                    checked
                      ? "border-[var(--color-accent)] bg-[var(--color-accent)] text-white"
                      : "border-[var(--color-border)] bg-white text-transparent"
                  }`}
                >
                  <Check className="size-3.5" />
                </div>
              </button>
            );
          })}
        </div>
      </PopoverContent>
    </Popover>
  );
}
