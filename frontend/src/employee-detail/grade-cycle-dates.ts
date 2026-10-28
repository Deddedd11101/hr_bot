export function cycleDates(anchor: string): Record<string, string> {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(anchor)) return {};
  const [year, month, day] = anchor.split("-").map(Number);
  const source = new Date(Date.UTC(year, month - 1, day));
  if (source.getUTCFullYear() !== year || source.getUTCMonth() !== month - 1 || source.getUTCDate() !== day) return {};
  function after(months: number, time: string) {
    const target = new Date(Date.UTC(year, month - 1 + months, 1));
    const last = new Date(Date.UTC(target.getUTCFullYear(), target.getUTCMonth() + 1, 0)).getUTCDate();
    target.setUTCDate(Math.min(day, last));
    return `${target.toISOString().slice(0, 10)}T${time}`;
  }
  return {ipr6: after(6, "10:00"), ipr12: after(12, "10:00"), review12: after(12, "10:10")};
}
