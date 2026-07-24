import { apiFetch } from "@/lib/api";

export type TaxCode = {
  id: string;
  code: string;
  name: string;
  rate: string;
  treatment: string;
  direction: "input" | "output" | "both";
  is_active: boolean;
};

type Paginated<T> = { count: number; results: T[] };

/**
 * Active tax codes for an entity. Pass a `direction` to narrow to sales (`output`)
 * or purchase (`input`) codes — `both`-direction codes always match.
 */
export async function listTaxCodes(
  entityId?: string | null,
  direction?: "input" | "output",
): Promise<TaxCode[]> {
  const params = new URLSearchParams({ limit: "200", ordering: "code", is_active: "true" });
  if (entityId) params.set("entity", entityId);
  const res = await apiFetch(`/tax-codes/?${params.toString()}`);
  if (!res.ok) throw new Error(`Failed to load tax codes (${res.status})`);
  const rows = ((await res.json()) as Paginated<TaxCode>).results;
  if (!direction) return rows;
  return rows.filter((t) => t.direction === direction || t.direction === "both");
}
