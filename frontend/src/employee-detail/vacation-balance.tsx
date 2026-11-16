import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Feedback, useAction } from "@/grades/components";
import { errorMessage, request } from "@/grades/data";

type Balance = {year: number; used_days: number | null; remaining_days: number | null};
type VacationRequest = {id: number; starts_on: string; ends_on: string; workdays: number; status: string; manager_notice: string; hr_notice: string; manager_issue?: string | null; can_route?: boolean};
const statuses: Record<string, string> = {pending: "У руководителя", pending_hr: "У HR", approved: "Согласована", rejected: "Отклонена"};
const notices: Record<string, string> = {
  pending: "Уведомление в очереди", unavailable: "Telegram получателя недоступен",
  sending: "Отправка не подтверждена", failed: "Не удалось отправить уведомление",
};
const dateLabel = (value: string) => value.split("-").reverse().join(".");

export function VacationBalance({employeeId}: {employeeId: number}) {
  const endpoint = `/api/employees/${employeeId}/vacation`;
  const [balance, setBalance] = useState<Balance | null>(null);
  const [error, setError] = useState("");
  const [requests, setRequests] = useState<VacationRequest[] | null>(null);
  const [requestsError, setRequestsError] = useState("");
  const action = useAction();
  function routeToManager(row: VacationRequest) {
    if (!window.confirm("Передать заявку текущему руководителю? Старые кнопки согласования перестанут работать.")) return;
    void action.run(async () => {
      const updated = await request<VacationRequest>(`${endpoint}/requests/${row.id}/route-to-manager`, "POST");
      setRequests(previous => previous?.map(item => item.id === updated.id ? updated : item) ?? null);
    });
  }
  function decide(row: VacationRequest, approved: boolean) {
    if (!window.confirm(approved ? "Согласовать заявку на отпуск?" : "Отклонить заявку на отпуск?")) return;
    void action.run(async () => {
      const updated = await request<VacationRequest>(`${endpoint}/requests/${row.id}/decision`, "POST", {approved});
      setRequests(previous => previous?.map(item => item.id === updated.id ? updated : item) ?? null);
    });
  }
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
        <div>
          <p className="text-muted-foreground">Рабочих дней: {row.workdays} · {statuses[row.status] ?? row.status}</p>
          <p className="text-muted-foreground">{row.manager_issue || notices[row.status === "pending" ? row.manager_notice : row.status === "pending_hr" ? row.hr_notice : "sent"]}</p>
        </div>
        {(row.status === "pending" || row.status === "pending_hr") && <div className="flex flex-wrap gap-2">
          {row.status === "pending_hr" && <Button size="sm" disabled={action.busy} onClick={() => decide(row, true)}>Согласовать</Button>}
          {row.can_route && <Button size="sm" disabled={action.busy} onClick={() => routeToManager(row)}>Передать текущему руководителю</Button>}
          <Button size="sm" variant="outline" disabled={action.busy} onClick={() => decide(row, false)}>Отклонить</Button>
        </div>}
      </li>)}
    </ul>}
  </section>;
}
