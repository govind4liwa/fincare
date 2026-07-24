import { apiFetch } from "@/lib/api";

export type Customer = {
  id: string;
  code: string;
  name: string;
  trn: string;
  customer_type: string;
  receivable_account: string;
  receivable_account_code: string;
  credit_limit: string | null;
  email: string;
  phone: string;
  address: string;
  emirate: string;
  credit_days: number | null;
  is_active: boolean;
};

export type Supplier = {
  id: string;
  code: string;
  name: string;
  trn: string;
  payable_account: string;
  payable_account_code: string;
  email: string;
  phone: string;
  address: string;
  credit_days: number | null;
  is_active: boolean;
};

type Paginated<T> = { count: number; next: string | null; previous: string | null; results: T[] };

async function listParty<T>(resource: string, entityId?: string | null): Promise<T[]> {
  const params = new URLSearchParams({ limit: "500", ordering: "code" });
  if (entityId) params.set("entity", entityId);
  const res = await apiFetch(`/${resource}/?${params.toString()}`);
  if (!res.ok) throw new Error(`Failed to load ${resource} (${res.status})`);
  const data = (await res.json()) as Paginated<T>;
  return data.results;
}

export const listCustomers = (entityId?: string | null) =>
  listParty<Customer>("customers", entityId);
export const listSuppliers = (entityId?: string | null) =>
  listParty<Supplier>("suppliers", entityId);
