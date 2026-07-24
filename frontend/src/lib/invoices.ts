import { apiFetch } from "@/lib/api";

export type InvoiceStatus = "draft" | "posted" | "partially_paid" | "paid" | "cancelled";

export type SalesInvoice = {
  id: string;
  entity: string;
  customer: string;
  customer_code: string;
  customer_name: string;
  invoice_no: string;
  invoice_date: string;
  due_date: string | null;
  place_of_supply: string;
  subtotal: string;
  tax_total: string;
  total: string;
  balance: string;
  status: InvoiceStatus;
  narration: string;
};

type Paginated<T> = { count: number; next: string | null; previous: string | null; results: T[] };

export type InvoiceLineInput = {
  revenue_account: string;
  description: string;
  quantity: string;
  unit_price: string;
  tax_code: string | null;
};

export type InvoiceCreateInput = {
  entity: string;
  customer: string;
  invoice_date: string;
  due_date: string | null;
  place_of_supply: string;
  narration: string;
  lines: InvoiceLineInput[];
};

export type InvoiceFilters = { entityId?: string | null; status?: string };

export async function listInvoices(
  filters: InvoiceFilters = {},
): Promise<{ count: number; results: SalesInvoice[] }> {
  const params = new URLSearchParams({ limit: "100", ordering: "-invoice_date" });
  if (filters.entityId) params.set("entity", filters.entityId);
  if (filters.status) params.set("status", filters.status);
  const res = await apiFetch(`/invoices/?${params.toString()}`);
  if (!res.ok) throw new Error(`Failed to load invoices (${res.status})`);
  const data = (await res.json()) as Paginated<SalesInvoice>;
  return { count: data.count, results: data.results };
}

async function detail(res: Response, fallback: string): Promise<string> {
  const data = (await res.json().catch(() => ({}))) as { detail?: unknown };
  return typeof data.detail === "string" ? data.detail : fallback;
}

export async function createInvoice(payload: InvoiceCreateInput): Promise<{ id: string }> {
  const res = await apiFetch("/invoices/", { method: "POST", body: JSON.stringify(payload) });
  if (!res.ok) throw new Error(await detail(res, "Could not save the invoice."));
  return (await res.json()) as { id: string };
}

export async function postInvoice(id: string): Promise<void> {
  const res = await apiFetch(`/invoices/${id}/post/`, { method: "POST", body: JSON.stringify({}) });
  if (!res.ok) throw new Error(await detail(res, "Could not post the invoice."));
}
