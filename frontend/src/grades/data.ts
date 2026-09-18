import type { Profile } from "./types";

export async function request<T>(url: string, method = "GET", body?: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch(url, {
    method, credentials: "same-origin", signal,
    headers: { Accept: "application/json", ...(body === undefined ? {} : { "Content-Type": "application/json" }) },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = payload?.detail;
    throw new Error(typeof detail === "string" ? detail : detail ? JSON.stringify(detail) : `Ошибка запроса (${response.status})`);
  }
  if (!payload || response.redirected) throw new Error("Сессия истекла или сервер вернул неверный ответ. Обновите страницу.");
  return payload as T;
}

export function goalKey(profile: Profile): string {
  if (!profile.target_grade_id) return "none";
  return profile.target_specialization_id ? `spec:${profile.target_specialization_id}` : `grade:${profile.target_grade_id}`;
}

export function goalFields(value: string, currentGradeId: number | null): Pick<Profile, "target_grade_id" | "target_specialization_id"> {
  if (value.startsWith("grade:")) return { target_grade_id: Number(value.slice(6)), target_specialization_id: null };
  if (value.startsWith("spec:")) return { target_grade_id: currentGradeId, target_specialization_id: Number(value.slice(5)) };
  return { target_grade_id: null, target_specialization_id: null };
}

export const errorMessage = (error: unknown) => error instanceof Error ? error.message : "Не удалось выполнить действие";
// Backend timestamps are UTC, including ISO strings without an explicit suffix.
export const dateLabel = (value: string) => new Date(/(?:Z|[+-]\d\d:\d\d)$/i.test(value) ? value : `${value}Z`).toLocaleString("ru-RU");
