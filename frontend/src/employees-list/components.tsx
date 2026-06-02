import * as React from "react";
import {
  BriefcaseBusiness,
  ExternalLink,
  FileClock,
  MessageCircle,
  Sparkles,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";

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
  const selected = options.find((option) => option.value === value) || options[0];

  return (
    <Select items={options} value={selected?.value || value} onValueChange={onChange}>
      <SelectTrigger
        className="min-w-48 border-transparent bg-secondary text-secondary-foreground hover:bg-border"
        size="default"
      >
        <span className="inline-flex min-w-0 items-center gap-2 truncate">
          {icon}
          <SelectValue className="truncate" />
        </span>
      </SelectTrigger>
      <SelectContent align="start" alignItemWithTrigger={false} className="w-48">
        <SelectGroup>
          {options.map((option) => (
            <SelectItem value={option.value} key={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </SelectGroup>
      </SelectContent>
    </Select>
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
    <Badge variant="secondary" className="h-6 px-2.5">
      {icon}
      {label}
    </Badge>
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
          className={cn(buttonVariants({ variant: "outline", size: "icon" }))}
          title="Открыть чат"
          aria-label="Открыть чат"
        >
          <MessageCircle />
        </a>
      ) : null}
      <a
        href={item.react_edit_url || item.edit_url}
        className={cn(buttonVariants({ variant: "outline", size: "icon" }))}
        title="Открыть карточку"
        aria-label="Открыть карточку"
      >
        <ExternalLink />
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
    <Card size="sm" className="w-full min-w-0 rounded-lg border border-border bg-card shadow-none ring-0 transition-colors hover:bg-accent/60">
      <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 space-y-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="truncate text-[1rem] font-semibold">{item.full_name || "Без имени"}</h3>
            <MetaChip
              icon={isCandidate ? <FileClock className="size-3.5" /> : <Sparkles className="size-3.5" />}
              label={statusValue || "Без статуса"}
            />
          </div>
          <div className="flex flex-wrap items-center gap-2 text-[0.92rem] text-muted-foreground">
            {item.position ? <span>{item.position}</span> : <span>Без должности</span>}
          </div>
        </div>
        <ItemActions item={item} />
      </CardHeader>

      <CardContent className="flex flex-wrap items-center gap-2">
        <MetaChip icon={<MessageCircle className="size-3.5" />} label={item.chat_id || item.chat_handle || "Канал не привязан"} />
        <MetaChip icon={<BriefcaseBusiness className="size-3.5" />} label={`${dateTitle}: ${dateLabel || "—"}`} />
        {item.planned_scenario_title && item.planned_scenario_title !== "—" ? (
          <MetaChip icon={<Sparkles className="size-3.5" />} label={item.planned_scenario_title} />
        ) : null}
      </CardContent>
    </Card>
  );
}

export function EmployeeTableRow({ item }: { item: EmployeeItem }) {
  const isCandidate = item.list_kind === "candidates";
  const statusValue = isCandidate ? item.candidate_work_stage_label : item.status_label;
  const dateLabel = isCandidate ? item.test_task_due_at_label : item.first_workday_label;

  return (
    <article className="flex w-full min-w-0 items-center gap-3 rounded-lg border border-border bg-card px-4 py-3 text-sm transition-colors hover:bg-accent/60">
      <div className="min-w-0 flex-[1.6]">
        <div className="truncate font-semibold">{item.full_name || "Без имени"}</div>
        <div className="truncate text-[0.86rem] text-muted-foreground">{item.position || "Без должности"}</div>
      </div>
      <div className="min-w-0 flex-1 truncate text-muted-foreground">{statusValue || "—"}</div>
      <div className="min-w-0 flex-1 truncate text-muted-foreground">{item.chat_id || item.chat_handle || "—"}</div>
      <div className="min-w-0 flex-[0.9] truncate text-muted-foreground">{dateLabel || "—"}</div>
      <div className="min-w-0 flex-[1.2] truncate text-muted-foreground">{item.planned_scenario_title || "—"}</div>
      <div className="flex shrink-0 items-center gap-2">
        <ItemActions item={item} />
      </div>
    </article>
  );
}
