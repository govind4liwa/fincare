import { apiFetch } from "@/lib/api";

export type BillStatus = "draft" | "posted" | "partially_paid" | "paid" | "cancelled";

export type PurchaseBill = {
  id: string;
  entity: string;
  supplier: string;
  supplier_code: string;
  supplier_name: string;
  bill_no: string;
  supplier_invoice_no: string;
  bill_date: string;
  due_date: string | null;
  subtotal: string;
  tax_total: string;
  total: string;
  balance: string;
  is_reverse_charge: boolean;
  status: BillStatus;
};

type Paginated<T> = { count: number; next: string | null; previous: string | null; results: T[] };

export type BillLineInput = {
  account: string;
  description: string;
  quantity: string;
  unit_price: string;
  tax_code: string | null;
  recoverable: boolean;
};

export type BillCreateInput = {
  entity: string;
  supplier: string;
  bill_date: string;
  due_date: string | null;
  supplier_invoice_no: string;
  is_reverse_charge: boolean;
  lines: BillLineInput[];
};

export type BillFilters = { entityId?: string | null; status?: string };

export async function listBills(
  filters: BillFilters = {},
): Promise<{ count: number; results: PurchaseBill[] }> {
  const params = new URLSearchParams({ limit: "100", ordering: "-bill_date" });
  if (filters.entityId) params.set("entity", filters.entityId);
  if (filters.status) params.set("status", filters.status);
  const res = await apiFetch(`/bills/?${params.toString()}`);
  if (!res.ok) throw new Error(`Failed to load bills (${res.status})`);
  const data = (await res.json()) as Paginated<PurchaseBill>;
  return { count: data.count, results: data.results };
}

async function detail(res: Response, fallback: string): Promise<string> {
  const data = (await res.json().catch(() => ({}))) as { detail?: unknown };
  return typeof data.detail === "string" ? data.detail : fallback;
}

export async function createBill(payload: BillCreateInput): Promise<{ id: string }> {
  const res = await apiFetch("/bills/", { method: "POST", body: JSON.stringify(payload) });
  if (!res.ok) throw new Error(await detail(res, "Could not save the bill."));
  return (await res.json()) as { id: string };
}

export async function postBill(id: string): Promise<void> {
  const res = await apiFetch(`/bills/${id}/post/`, { method: "POST", body: JSON.stringify({}) });
  if (!res.ok) throw new Error(await detail(res, "Could not post the bill."));
}

export type AllocationSource = {
  source_type: string;
  source_id: string;
  label: string;
  date: string;
  total: string;
  available: string;
};

export type Allocation = { source_type: string; amount: string; date: string };

export async function listBillSources(supplierId: string): Promise<AllocationSource[]> {
  const res = await apiFetch(`/bills/allocatable-sources/?supplier=${supplierId}`);
  if (!res.ok) throw new Error(`Failed to load sources (${res.status})`);
  return ((await res.json()) as { sources: AllocationSource[] }).sources;
}

export async function listBillAllocations(id: string): Promise<Allocation[]> {
  const res = await apiFetch(`/bills/${id}/allocations/`);
  if (!res.ok) throw new Error(`Failed to load allocations (${res.status})`);
  return ((await res.json()) as { allocations: Allocation[] }).allocations;
}

export async function allocateBill(
  id: string,
  payload: { source_type: string; source_id: string; amount: string },
): Promise<void> {
  const res = await apiFetch(`/bills/${id}/allocate/`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await detail(res, "Could not apply the allocation."));
}
