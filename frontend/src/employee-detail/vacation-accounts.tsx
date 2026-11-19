import { useEffect, useId, useState } from "react";
import { Calculator, Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { DatePicker } from "@/components/ui/date-picker";
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Choice, Feedback, useAction, useUnsaved } from "@/grades/components";
import { errorMessage, request } from "@/grades/data";

type Account = {contract_key: string; employed_on: string; reviewed_through: string | null;
  month_end_policy: string | null; revision: number;
  balances: {kind: string; unit: string; available: string | null; reserved: string; used: string}[]};
type Preview = {opening_through: string; new_total: string;
  items: {month_start: string; earned_on: string; amount: string; posted: boolean}[]};
const names: Record<string, string> = {annual: "Ежегодный отпуск", force_majeure: "Форс-мажор", day_off: "Day off"};
const blank = {contract_key: "primary", employed_on: "", reviewed_through: "", month_end_policy: "none", revision: 0, reason: ""};
const formatDate = (value: string) => value.split("-").reverse().join(".");

export function VacationAccounts({employeeId}: {employeeId: number}) {
  const endpoint = `/api/employees/${employeeId}/leave-accounts`;
  const [accounts, setAccounts] = useState<Account[] | null>(null);
  const [error, setError] = useState("");
  const [form, setForm] = useState(blank);
  const [dirty, setDirty] = useState(false);
  const [preview, setPreview] = useState<Preview | null>(null);
  const action = useAction();
  const id = useId();
  useUnsaved(dirty);
  useEffect(() => {
    const controller = new AbortController();
    request<Account[]>(endpoint, "GET", undefined, controller.signal).then(rows => {
      setAccounts(rows);
      if (rows.length) edit(rows[0]);
    }).catch(e => {if (!controller.signal.aborted) setError(errorMessage(e));});
    return () => controller.abort();
  }, [endpoint]);
  function edit(row?: Account) {
    setForm(row ? {contract_key: row.contract_key, employed_on: row.employed_on, revision: row.revision,
      reviewed_through: row.reviewed_through ?? "", month_end_policy: row.month_end_policy ?? "none", reason: ""} : blank);
    setDirty(false); setPreview(null); action.setError(""); action.setMessage("");
  }
  function change(key: keyof typeof blank, value: string) {
    setForm(previous => ({...previous, [key]: value})); setDirty(true); setPreview(null);
  }
  const selected = accounts?.find(row => row.contract_key === form.contract_key);
  return <section className="space-y-4 border-b pb-5">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <div><h2 className="font-medium">Отпускной учёт</h2>
        <p className="text-sm text-muted-foreground">Автоматические начисления не включены</p></div>
    </div>
    <Feedback error={error || action.error} message={action.message} />
    {!accounts && !error && <p role="status" className="text-sm text-muted-foreground">Загрузка настроек…</p>}
    {accounts && <>
      {selected && <div className="grid gap-4 sm:grid-cols-3">{selected.balances.map(item => <div key={item.kind} className="space-y-1 border-l-2 pl-3">
        <p className="text-sm text-muted-foreground">{names[item.kind]}</p>
        <p className="text-lg font-medium tabular-nums">{item.available ?? "Не указан"}{item.available !== null && <span className="ml-1 text-sm font-normal text-muted-foreground">{item.unit === "hours" ? "ч" : "дн."}</span>}</p>
        {item.available !== null && <p className="text-xs text-muted-foreground">В резерве: {item.reserved} · Использовано: {item.used}</p>}
      </div>)}</div>}
      <form className="space-y-4" onSubmit={event => {
        event.preventDefault();
        void action.run(async () => {
          const rows = await request<Account[]>(endpoint, "PUT", {...form,
            reviewed_through: form.reviewed_through || null, month_end_policy: form.month_end_policy === "none" ? null : form.month_end_policy});
          setAccounts(rows); edit(rows.find(row => row.contract_key === form.contract_key));
        }, "Настройки сохранены. Начисления не запускались.");
      }}>
        <FieldGroup className="grid gap-4 sm:grid-cols-2">
          <Field><FieldLabel>Дата трудоустройства по договору</FieldLabel><DatePicker value={form.employed_on}
            onValueChange={value => change("employed_on", value)} disabled={action.busy} />
            <FieldDescription>Не меняет дату выхода для адаптации</FieldDescription></Field>
          <Choice label="Короткий месяц" value={form.month_end_policy} disabled={action.busy}
            options={[{value: "none", label: "Правило не подтверждено"}, {value: "clamp_to_last_day", label: "Последний день, затем исходное число"}]}
            onChange={value => change("month_end_policy", value)} />
          <Field><FieldLabel>Исключаемых периодов нет по дату</FieldLabel><DatePicker value={form.reviewed_through}
            onValueChange={value => change("reviewed_through", value)} disabled={action.busy} />
            <FieldDescription>Заполняется после проверки HR</FieldDescription></Field>
          <Field className="sm:col-span-2"><FieldLabel htmlFor={`${id}-reason`}>Основание подтверждения</FieldLabel>
            <Input id={`${id}-reason`} value={form.reason} onChange={e => change("reason", e.target.value)}
              required maxLength={1024} disabled={action.busy} placeholder="Документ или подтверждение HR" /></Field>
        </FieldGroup>
        <div className="flex flex-wrap gap-2">
          <Button type="submit" disabled={action.busy || !dirty || !form.employed_on || !form.contract_key || !form.reason.trim()}><Save />Сохранить настройки</Button>
          {dirty && <Button type="button" variant="ghost" disabled={action.busy} onClick={() => edit(selected)}>Отменить изменения</Button>}
          <Button type="button" variant="outline" disabled={action.busy || dirty || !selected || !form.reviewed_through}
            onClick={() => {void action.run(async () => setPreview(await request<Preview>(`${endpoint}/accrual-preview`, "POST", {
              contract_key: form.contract_key, through: form.reviewed_through,
            })), "Расчёт без записи операций");}}><Calculator />Проверить начисления</Button>
        </div>
      </form>
      {selected?.balances.some(item => item.available === null) && <p className="text-sm text-muted-foreground">Входящие остатки ещё не подтверждены. Старый ручной баланс не переносится автоматически.</p>}
      {preview && <div className="space-y-2">
        <p className="text-sm">Срез: {formatDate(preview.opening_through)} · К начислению: <strong>{preview.new_total} дн.</strong></p>
        <Table><TableHeader><TableRow><TableHead>Рабочий месяц с</TableHead><TableHead>Начисление</TableHead><TableHead>Дни</TableHead><TableHead>Статус</TableHead></TableRow></TableHeader>
          <TableBody>{preview.items.map(item => <TableRow key={item.month_start}><TableCell>{formatDate(item.month_start)}</TableCell><TableCell>{formatDate(item.earned_on)}</TableCell>
            <TableCell>{item.amount}</TableCell><TableCell>{item.posted ? "Уже учтено" : "Предпросмотр"}</TableCell></TableRow>)}</TableBody></Table>
        {preview.items.length === 0 && <p className="text-sm text-muted-foreground">Новых начислений за период нет.</p>}
      </div>}
    </>}
  </section>;
}
