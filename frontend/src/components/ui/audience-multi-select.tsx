import React from "react";
import { ChevronsUpDown } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { ScrollArea } from "@/components/ui/scroll-area";

type AudienceOption = { value: string; label: string; disabled?: boolean };

export function AudienceMultiSelect({
  label,
  options,
  values,
  onChange,
  placeholder,
}: {
  label: string;
  options: AudienceOption[];
  values: string[];
  onChange: (values: string[]) => void;
  placeholder: string;
}) {
  const [search, setSearch] = React.useState("");
  const filtered = options.filter((option) => option.label.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase()));
  const selectedLabels = options.filter((option) => values.includes(option.value)).map((option) => option.label);

  return (
    <div className="min-w-0 space-y-2">
      <span className="text-sm font-medium">{label}</span>
      <Popover>
        <PopoverTrigger render={<Button type="button" variant="outline" className="w-full min-w-0 justify-between" aria-label={label} />}>
          <span className="truncate">{values.length ? `Выбрано: ${values.length}` : placeholder}</span>
          <ChevronsUpDown className="size-4 shrink-0 opacity-60" aria-hidden="true" />
        </PopoverTrigger>
        <PopoverContent className="w-[var(--anchor-width)] max-w-[min(360px,calc(100vw-32px))] p-2" align="start">
          <Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Поиск" aria-label={`Поиск: ${label}`} />
          <ScrollArea className="mt-2 h-52">
            <div className="space-y-1 pr-2">
              {filtered.map((option) => (
                <label key={option.value} className="flex min-w-0 cursor-pointer items-start gap-2 rounded px-2 py-1.5 text-sm hover:bg-muted">
                  <Checkbox
                    checked={values.includes(option.value)}
                    disabled={option.disabled}
                    onCheckedChange={(checked) => onChange(checked ? [...values, option.value] : values.filter((value) => value !== option.value))}
                    aria-label={option.label}
                  />
                  <span className="min-w-0 break-words">{option.label}</span>
                </label>
              ))}
              {!filtered.length && <p className="px-2 py-2 text-sm text-muted-foreground">Не найдено</p>}
            </div>
          </ScrollArea>
          {values.length > 0 && <Button type="button" size="sm" variant="ghost" className="self-start" onClick={() => onChange([])}>Сбросить выбор</Button>}
        </PopoverContent>
      </Popover>
      {selectedLabels.length > 0 && (
        <p className="break-words text-xs text-muted-foreground">
          {selectedLabels.slice(0, 3).join(", ")}{selectedLabels.length > 3 ? ` и ещё ${selectedLabels.length - 3}` : ""}
        </p>
      )}
    </div>
  );
}
