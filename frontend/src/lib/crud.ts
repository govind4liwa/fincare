import { apiFetch } from "@/lib/api";

/** Turn a DRF error body into a readable one-line message (detail or field errors). */
async function errorMessage(res: Response, fallback: string): Promise<string> {
  const data = (await res.json().catch(() => null)) as unknown;
  if (data && typeof data === "object") {
    const d = data as Record<string, unknown>;
    if (typeof d.detail === "string") return d.detail;
    const parts: string[] = [];
    for (const [key, value] of Object.entries(d)) {
      const msg = Array.isArray(value) ? value.join(" ") : String(value);
      parts.push(key === "non_field_errors" ? msg : `${key}: ${msg}`);
    }
    if (parts.length) return parts.join(" · ");
  }
  return fallback;
}

export async function getRecord<T>(resource: string, id: string): Promise<T> {
  const res = await apiFetch(`/${resource}/${id}/`);
  if (!res.ok) throw new Error(`Failed to load record (${res.status})`);
  return (await res.json()) as T;
}

export async function createRecord<T>(resource: string, payload: unknown): Promise<T> {
  const res = await apiFetch(`/${resource}/`, { method: "POST", body: JSON.stringify(payload) });
  if (!res.ok) throw new Error(await errorMessage(res, "Could not save this record."));
  return (await res.json()) as T;
}

export async function updateRecord<T>(
  resource: string,
  id: string,
  payload: unknown,
): Promise<T> {
  const res = await apiFetch(`/${resource}/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await errorMessage(res, "Could not update this record."));
  return (await res.json()) as T;
}
