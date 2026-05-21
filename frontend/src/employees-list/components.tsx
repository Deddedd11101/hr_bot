import * as React from "react";
import {
  BriefcaseBusiness,
  ChevronsUpDown,
  ExternalLink,
  FileClock,
  MessageCircle,
  Sparkles,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

import type { EmployeeItem, Option } from "./types";

export function SinglePicker({
  value,
  options,
  onChange,
  icon,
}: {
  value: string;
  options: Option[];
  onChange: (next: string) => void;
  icon?: React.ReactNode;
}) {
  const [open, setOpen] = React.useState(false);
  const selected = options.find((option) => option.value === value) || options[0];

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="secondary" className="justify-between gap-3">
          <span className="inline-flex min-w-0 items-center gap-2 truncate">
            {icon}
            <span className="truncate">{selected?.label}</span>
          </span>
          <ChevronsUpDown className="size-4 opacity-60" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[var(--radix-popover-trigger-width)] p-1.5" align="start">
        <div className="flex flex-col gap-1">
          {options.map((option) => {
            const active = option.value === value;
            return (
              <button
                key={option.value}
                type="button"
                onClick={() => {
                  onChange(option.value);
                  setOpen(false);
                }}
                className={`flex items-center justify-between gap-3 rounded-[10px] px-3 py-2 text-left text-sm transition-all duration-200 hover:rounded-[16px] hover:bg-black/5 ${
                  active ? "bg-[var(--color-panel-muted)]" : ""
                }`}
              >
                <span className="truncate">{option.label}</span>
                {active ? <span className="size-2 rounded-full bg-[var(--color-accent)]" /> : null}
              </button>
            );
          })}
        </div>
      </PopoverContent>
    </Popover>
  );
}

export function MetaChip({
  icon,
  label,
}: {
  icon: React.ReactNode;
  label: string;
}) {
  return (
    <span className="inline-flex items-center gap-2 rounded-[10px] bg-black/5 px-2.5 py-1.5 text-[0.72rem] font-medium text-[var(--color-muted-foreground)] transition-all duration-200 hover:rounded-[18px]">
      {icon}
      {label}
    </span>
  );
}

function ItemActions({ item }: { item: EmployeeItem }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      {item.chat_link ? (
        <a
          href={item.chat_link}
          target="_blank"
          rel="noreferrer noopener"
          className="inline-flex items-center justify-center rounded-[10px] border border-[var(--color-border)] bg-white px-3 py-2 text-sm font-medium transition-all duration-200 hover:rounded-[20px] hover:bg-[var(--color-panel-muted)]"
          title="Открыть чат"
        >
          <MessageCircle className="size-4" />
        </a>
      ) : null}
      <a
        href={item.react_edit_url || item.edit_url}
        className="inline-flex items-center justify-center rounded-[10px] border border-[var(--color-border)] bg-white px-3 py-2 text-sm font-medium transition-all duration-200 hover:rounded-[20px] hover:bg-[var(--color-panel-muted)]"
        title="Открыть карточку"
      >
        <ExternalLink className="size-4" />
      </a>
    </div>
  );
}

export function EmployeeCard({ item }: { item: EmployeeItem }) {
  const isCandidate = item.list_kind === "candidates";
  const statusValue = isCandidate ? item.candidate_work_stage_label : item.status_label;
  const dateLabel = isCandidate ? item.test_task_due_at_label : item.first_workday_label;
  const dateTitle = isCandidate ? "Дедлайн" : "Выход";

  return (
    <article className="flex w-full min-w-0 flex-col gap-3 rounded-[10px] border border-[var(--color-border)] bg-white p-3 transition-all duration-200 hover:rounded-[22px] hover:bg-[var(--color-panel-muted)]">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 space-y-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="truncate text-[1rem] font-semibold">{item.full_name || "Без имени"}</h3>
            <MetaChip
              icon={isCandidate ? <FileClock className="size-3.5" /> : <Sparkles className="size-3.5" />}
              label={statusValue || "Без статуса"}
            />
          </div>
          <div className="flex flex-wrap items-center gap-2 text-[0.92rem] text-[var(--color-muted-foreground)]">
            {item.position ? <span>{item.position}</span> : <span>Без должности</span>}
          </div>
        </div>
        <ItemActions item={item} />
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <MetaChip icon={<MessageCircle className="size-3.5" />} label={item.chat_id || item.chat_handle || "Канал не привязан"} />
        <MetaChip icon={<BriefcaseBusiness className="size-3.5" />} label={`${dateTitle}: ${dateLabel || "—"}`} />
        {item.planned_scenario_title && item.planned_scenario_title !== "—" ? (
          <MetaChip icon={<Sparkles className="size-3.5" />} label={item.planned_scenario_title} />
        ) : null}
      </div>
    </article>
  );
}

export function EmployeeTableRow({ item }: { item: EmployeeItem }) {
  const isCandidate = item.list_kind === "candidates";
  const statusValue = isCandidate ? item.candidate_work_stage_label : item.status_label;
  const dateLabel = isCandidate ? item.test_task_due_at_label : item.first_workday_label;

  return (
    <article className="flex w-full min-w-0 items-center gap-3 rounded-[10px] border border-[var(--color-border)] bg-white px-4 py-3 text-sm transition-all duration-200 hover:rounded-[22px] hover:bg-[var(--color-panel-muted)]">
      <div className="min-w-0 flex-[1.6]">
        <div className="truncate font-semibold">{item.full_name || "Без имени"}</div>
        <div className="truncate text-[0.86rem] text-[var(--color-muted-foreground)]">{item.position || "Без должности"}</div>
      </div>
      <div className="min-w-0 flex-1 truncate text-[var(--color-muted-foreground)]">{statusValue || "—"}</div>
      <div className="min-w-0 flex-1 truncate text-[var(--color-muted-foreground)]">{item.chat_id || item.chat_handle || "—"}</div>
      <div className="min-w-0 flex-[0.9] truncate text-[var(--color-muted-foreground)]">{dateLabel || "—"}</div>
      <div className="min-w-0 flex-[1.2] truncate text-[var(--color-muted-foreground)]">{item.planned_scenario_title || "—"}</div>
      <div className="flex shrink-0 items-center gap-2">
        <ItemActions item={item} />
      </div>
    </article>
  );
}
