import * as React from "react";
import { CalendarIcon } from "lucide-react";

import { buttonVariants } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";

const EMPTY_TIME_VALUE = "__empty_time__";

function parseDate(value: string) {
  if (!value) return undefined;
  const [year, month, day] = value.split("-").map(Number);
  if (!year || !month || !day) return undefined;
  return new Date(year, month - 1, day);
}

function formatDateValue(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function formatDisplayDate(value: string, placeholder: string) {
  const date = parseDate(value);
  if (!date) return placeholder;
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(date);
}

function splitDateTime(value: string) {
  const [date = "", time = ""] = value.split("T");
  return { date, time };
}

type DatePickerProps = {
  value: string;
  onValueChange: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
};

function DatePicker({
  value,
  onValueChange,
  placeholder = "Выбрать дату",
  disabled,
  className,
}: DatePickerProps) {
  const selectedDate = parseDate(value);

  return (
    <Popover>
      <PopoverTrigger
        render={
          <button
            type="button"
            disabled={disabled}
            data-empty={!value}
            className={cn(
              buttonVariants({ variant: "outline" }),
              "w-full justify-start text-left font-normal data-[empty=true]:text-muted-foreground",
              className,
            )}
          />
        }
      >
        <CalendarIcon data-icon="inline-start" />
        {formatDisplayDate(value, placeholder)}
      </PopoverTrigger>
      <PopoverContent align="start" className="w-auto p-0">
        <Calendar
          mode="single"
          selected={selectedDate}
          onSelect={(date) => {
            if (date) onValueChange(formatDateValue(date));
          }}
        />
      </PopoverContent>
    </Popover>
  );
}

function buildTimeOptions(stepMinutes = 15) {
  const items = [{ value: EMPTY_TIME_VALUE, label: "Выбрать время" }];
  for (let minutes = 0; minutes < 24 * 60; minutes += stepMinutes) {
    const hours = String(Math.floor(minutes / 60)).padStart(2, "0");
    const mins = String(minutes % 60).padStart(2, "0");
    items.push({ value: `${hours}:${mins}`, label: `${hours}:${mins}` });
  }
  return items;
}

type TimeSelectProps = {
  value: string;
  onValueChange: (value: string) => void;
  disabled?: boolean;
  stepMinutes?: 15 | 30 | 60;
  placeholder?: string;
};

function TimeSelect({
  value,
  onValueChange,
  disabled,
  stepMinutes = 15,
  placeholder = "Выбрать время",
}: TimeSelectProps) {
  const items = React.useMemo(() => buildTimeOptions(stepMinutes), [stepMinutes]);

  return (
    <Select
      items={items}
      value={value || EMPTY_TIME_VALUE}
      onValueChange={(nextValue) => {
        onValueChange(nextValue === EMPTY_TIME_VALUE ? "" : nextValue);
      }}
    >
      <SelectTrigger className="w-full" disabled={disabled}>
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

type DateTimePickerProps = {
  value: string;
  onValueChange: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
};

function DateTimePicker({
  value,
  onValueChange,
  placeholder = "Выбрать дату",
  disabled,
}: DateTimePickerProps) {
  const parts = splitDateTime(value);

  function update(nextDate: string, nextTime: string) {
    if (!nextDate && !nextTime) {
      onValueChange("");
      return;
    }
    onValueChange(`${nextDate}${nextTime ? `T${nextTime}` : ""}`);
  }

  return (
    <div className="grid gap-2">
      <DatePicker
        value={parts.date}
        onValueChange={(nextDate) => update(nextDate, parts.time)}
        placeholder={placeholder}
        disabled={disabled}
      />
      <TimeSelect
        value={parts.time}
        onValueChange={(nextTime) => update(parts.date, nextTime)}
        disabled={disabled}
      />
    </div>
  );
}

export { DatePicker, DateTimePicker, TimeSelect };
