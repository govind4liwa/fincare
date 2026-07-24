import { apiFetch } from "@/lib/api";

export type Entity = {
  id: string;
  code: string;
  numeric_code: string;
  legal_name: string;
  trade_name: string;
  accounting_basis: "cash" | "accrual";
  effective_trn: string | null;
  is_active: boolean;
};

type Paginated<T> = { count: number; next: string | null; previous: string | null; results: T[] };

/** The entities the current user may access (membership-scoped by the API). */
export async function listEntities(): Promise<Entity[]> {
  const res = await apiFetch("/tenants/entities/?limit=100&is_active=true");
  if (!res.ok) throw new Error("Failed to load entities");
  const data = (await res.json()) as Paginated<Entity>;
  return data.results;
}
