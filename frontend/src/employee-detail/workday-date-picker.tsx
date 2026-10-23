import React from "react";
import { DatePicker } from "@/components/ui/date-picker";

export function WorkdayDatePicker({ value, onValueChange }: { value: string; onValueChange: (value: string) => void }) {
    const [month, setMonth] = React.useState(() => value ? new Date(`${value}T12:00:00`) : new Date());
    const [calendar, setCalendar] = React.useState<{ year: number; days: Set<string> } | null>(null);
    const [error, setError] = React.useState("");
    const year = month.getFullYear();
    React.useEffect(() => {
        let active = true;
        setError("");
        fetch(`/api/adaptation-plan/working-days/${year}`, { credentials: "same-origin" }).then(async response => {
            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || "Календарь недоступен");
            if (active) setCalendar({ year, days: new Set(data.working_days) });
        }).catch(cause => { if (active) { setCalendar(null); setError(cause.message); } });
        return () => { active = false; };
    }, [year]);
    return <><DatePicker value={value} onValueChange={onValueChange} month={month} onMonthChange={setMonth} disabledDays={day => {
        const key = `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, "0")}-${String(day.getDate()).padStart(2, "0")}`;
        return !calendar || calendar.year !== day.getFullYear() || !calendar.days.has(key);
    }} />{error && <p role="status" className="text-xs text-destructive">{error}</p>}</>;
}
