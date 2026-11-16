import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Feedback, useAction } from "@/grades/components";
import { errorMessage, request } from "@/grades/data";

type Balance = {year: number; used_days: number | null; remaining_days: number | null};

export function VacationBalance({employeeId}: {employeeId: number}) {
  const endpoint = `/api/employees/${employeeId}/vacation`;
  const [balance, setBalance] = useState<Balance | null>(null);
  const [error, setError] = useState("");
  const action = useAction();
  useEffect(() => {
    const controller = new AbortController();
    request<Balance>(endpoint, "GET", undefined, controller.signal).then(setBalance).catch(error => {
      if (!controller.signal.aborted) setError(errorMessage(error));
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
  </section>;
}
