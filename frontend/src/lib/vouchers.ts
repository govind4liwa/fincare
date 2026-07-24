import { apiFetch } from "@/lib/api";

export type VoucherType = "receipt" | "payment" | "contra" | "expense" | "journal";
export type VoucherStatus = "draft" | "posted" | "reversed" | "cancelled";

export type Voucher = {
  id: string;
  entity: string;
  voucher_type: VoucherType;
  voucher_no: string;
  voucher_date: string;
  reference: string;
  narration: string;
  amount: string;
  status: VoucherStatus;
};

type Paginated<T> = { count: number; next: string | null; previous: string | null; results: T[] };

export type VoucherFilters = {
  entityId?: string | null;
  type?: string;
  status?: string;
};

export async function listVouchers(
  filters: VoucherFilters = {},
): Promise<{ count: number; results: Voucher[] }> {
  const params = new URLSearchParams({ limit: "100", ordering: "-voucher_date" });
  if (filters.entityId) params.set("entity", filters.entityId);
  if (filters.type) params.set("voucher_type", filters.type);
  if (filters.status) params.set("status", filters.status);
  const res = await apiFetch(`/vouchers/?${params.toString()}`);
  if (!res.ok) throw new Error(`Failed to load vouchers (${res.status})`);
  const data = (await res.json()) as Paginated<Voucher>;
  return { count: data.count, results: data.results };
}

export type VoucherLineInput = {
  account: string;
  description: string;
  debit: string;
  credit: string;
};

export type VoucherCreateInput = {
  entity: string;
  voucher_type: string;
  voucher_date: string;
  reference: string;
  narration: string;
  party_type?: string;
  party_id?: string | null;
  lines: VoucherLineInput[];
};

async function detail(res: Response, fallback: string): Promise<string> {
  const data = (await res.json().catch(() => ({}))) as { detail?: unknown };
  return typeof data.detail === "string" ? data.detail : fallback;
}

export async function createVoucher(payload: VoucherCreateInput): Promise<{ id: string }> {
  const res = await apiFetch("/vouchers/", { method: "POST", body: JSON.stringify(payload) });
  if (!res.ok) throw new Error(await detail(res, "Could not save the voucher."));
  return (await res.json()) as { id: string };
}

export async function postVoucher(id: string): Promise<void> {
  const res = await apiFetch(`/vouchers/${id}/post/`, { method: "POST", body: JSON.stringify({}) });
  if (!res.ok) throw new Error(await detail(res, "Could not post the voucher."));
}
