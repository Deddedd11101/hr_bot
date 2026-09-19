import { useEffect, useId, useRef, useState } from "react";
import { Zap } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Field, FieldLabel } from "@/components/ui/field";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { errorMessage } from "./data";

export function Choice({ label, value, options, onChange, disabled = false }: {
  label: string; value: string; options: { value: string; label: string }[]; onChange: (value: string) => void; disabled?: boolean;
}) {
  const id = useId();
  return <Field className="min-w-0 gap-1"><FieldLabel htmlFor={id}>{label}</FieldLabel>
    <Select value={value} onValueChange={v => { if (v !== null) onChange(v); }} disabled={disabled} items={options}>
      <SelectTrigger id={id} className="w-full min-w-0"><SelectValue /></SelectTrigger>
      <SelectContent><SelectGroup>{options.map(o => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}</SelectGroup></SelectContent>
    </Select>
  </Field>;
}

export const LEVEL_LABELS = ["Нет", "Понимание", "Умение", "Экспертиза", "Лидерство"] as const;
export const levelLabel = (n: number) => LEVEL_LABELS[n] ?? String(n);

export function LevelChoice({ label, value, onChange, disabled }: { label: string; value: number; onChange: (v: number) => void; disabled?: boolean }) {
  return <div className="flex flex-col items-end gap-1">
    <ToggleGroup aria-label={label} value={[String(value)]} onValueChange={v => { if (v.length) onChange(Number(v[0])); }} disabled={disabled} variant="outline" size="sm">
      {[0, 1, 2, 3, 4].map(n => <ToggleGroupItem key={n} value={String(n)} aria-label={`${label}: ${n} — ${levelLabel(n)}`} title={levelLabel(n)}>{n}</ToggleGroupItem>)}
    </ToggleGroup>
    {/* Выбранный уровень словами: тонкий tint нажатой кнопки сам по себе читается плохо. Для screen reader состояние уже есть в aria-pressed. */}
    <span aria-hidden="true" className="text-xs text-muted-foreground tabular-nums">{value} · {levelLabel(value)}</span>
  </div>;
}

/*
 * Зафиксированный уровень завершённой оценки. Это текст, а не disabled-контрол:
 * disabled-переключатели у всех пяти значений выглядели одинаково бледно, и
 * выбранный уровень не читался. Для screen reader «Уровень: 2 · Умение» —
 * обычное значение, без обещания редактирования.
 */
export function LevelValue({ value }: { value: number }) {
  return <span className="inline-flex shrink-0 items-baseline gap-1.5 rounded-md border bg-card px-2.5 py-1 text-sm">
    <span className="sr-only">Уровень: </span>
    <span className="font-semibold tabular-nums">{value}</span>
    <span className="text-muted-foreground">· {levelLabel(value)}</span>
  </span>;
}

export function Importance({ value }: { value: number }) {
  return <span className="inline-flex gap-0.5 text-warning" aria-label={`Важность: ${value}`} title={`Важность: ${value}`}>
    {Array.from({ length: value }, (_, i) => <Zap key={i} className="size-3 fill-current" aria-hidden="true" />)}
  </span>;
}

export function Feedback({ error, message }: { error?: string; message?: string }) {
  return <>{error && <div role="alert" className="rounded-md border border-destructive/40 p-3 text-sm text-destructive">{error}</div>}
    {message && <div role="status" className="text-sm text-success">{message}</div>}</>;
}

export function LoadingError({ loading, error, retry }: { loading: boolean; error: string; retry: () => void }) {
  return loading ? <div role="status" className="p-6 text-muted-foreground">Загрузка...</div> :
    <div className="space-y-3 p-6"><Feedback error={error} /><Button variant="outline" onClick={retry}>Повторить</Button></div>;
}

export function useAction() {
  const lock = useRef(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  async function run(action: () => Promise<void>, success = "Сохранено") {
    if (lock.current) return;
    lock.current = true; setBusy(true); setError(""); setMessage("");
    try { await action(); setMessage(success); } catch (e) { setError(errorMessage(e)); }
    finally { lock.current = false; setBusy(false); }
  }
  return { busy, error, message, run, setError, setMessage };
}

export function useUnsaved(dirty: boolean) {
  useEffect(() => {
    if (!dirty) return;
    const prevent = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ""; };
    window.addEventListener("beforeunload", prevent);
    return () => window.removeEventListener("beforeunload", prevent);
  }, [dirty]);
}
