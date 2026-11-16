import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Feedback, useAction } from "@/grades/components";
import { errorMessage, request } from "@/grades/data";

type Balance = {year: number; used_days: number | null; remaining_days: number | null};
type VacationRequest = {id: number; starts_on: string; ends_on: string; workdays: number; status: string};
const statuses: Record<string, string> = {pending: "Ожидает рассмотрения", approved: "Согласована", rejected: "Отклонена"};
const dateLabel = (value: string) => value.split("-").reverse().join(".");

export function VacationBalance({employeeId}: {employeeId: number}) {
  const endpoint = `/api/employees/${employeeId}/vacation`;
  const [balance, setBalance] = useState<Balance | null>(null);
  const [error, setError] = useState("");
  const [requests, setRequests] = useState<VacationRequest[] | null>(null);
  const [requestsError, setRequestsError] = useState("");
  const action = useAction();
  useEffect(() => {
    const controller = new AbortController();
    request<Balance>(endpoint, "GET", undefined, controller.signal).then(setBalance).catch(error => {
      if (!controller.signal.aborted) setError(errorMessage(error));
    });
    request<VacationRequest[]>(`${endpoint}/requests`, "GET", undefined, controller.signal).then(setRequests).catch(error => {
      if (!controller.signal.aborted) setRequestsError(errorMessage(error));
    });
    return () => controller.abort();
  }, [endpoint]);
  return <section className="space-y-3">
    <h2 className="font-medium">Баланс отпуска{balance ? ` · ${balance.year}` : ""}</h2>
    <Feedback error={error || action.error} message={action.message} />
    {!balance && !error && <p role="status">Загрузка…</p>}
    {balance && <form className="max-w-lg space-y-3" onSubmit={event => {
      event.preventDefault();
      const fields = new FormData(event.currentTarget);
      const days = (key: string) => fields.get(key) === "" ? null : Number(fields.get(key));
      void action.run(async () => {
        setBalance(await request<Balance>(endpoint, "PUT", {
          year: balance.year, used_days: days("used_days"), remaining_days: days("remaining_days"),
        }));
      });
    }}>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="space-y-1 text-sm">Использовано в этом году<Input name="used_days" type="number" min={0} max={9999} step={1} defaultValue={balance.used_days ?? ""} disabled={action.busy} /></label>
        <label className="space-y-1 text-sm">Осталось<Input name="remaining_days" type="number" min={0} max={9999} step={1} defaultValue={balance.remaining_days ?? ""} disabled={action.busy} /></label>
      </div>
      <Button type="submit" disabled={action.busy}>Сохранить баланс</Button>
    </form>}
    <h3 className="border-t pt-3 font-medium">Заявки на отпуск</h3>
    <Feedback error={requestsError} />
    {!requests && !requestsError && <p role="status">Загрузка заявок…</p>}
    {requests?.length === 0 && <p className="text-sm text-muted-foreground">Заявок пока нет.</p>}
    {!!requests?.length && <ul className="divide-y">
      {requests.map(row => <li key={row.id} className="flex flex-wrap justify-between gap-2 py-2 text-sm">
        <span>{dateLabel(row.starts_on)} – {dateLabel(row.ends_on)}</span>
        <span className="text-muted-foreground">Рабочих дней: {row.workdays} · {statuses[row.status] ?? row.status}</span>
      </li>)}
    </ul>}
  </section>;
}
