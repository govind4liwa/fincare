import { apiFetch } from "@/lib/api";

type Paginated<T> = { count: number; next: string | null; previous: string | null; results: T[] };

async function detail(res: Response, fallback: string): Promise<string> {
  const data = (await res.json().catch(() => ({}))) as { detail?: unknown };
  return typeof data.detail === "string" ? data.detail : fallback;
}

export type CashAccount = {
  id: string;
  entity: string;
  code: string;
  name: string;
  gl_account: string;
  gl_account_code: string;
  gl_account_name: string;
  branch: string | null;
  is_active: boolean;
};

export async function listCashAccounts(entityId?: string | null): Promise<CashAccount[]> {
  const params = new URLSearchParams({ limit: "200", ordering: "code" });
  if (entityId) params.set("entity", entityId);
  const res = await apiFetch(`/cash-accounts/?${params.toString()}`);
  if (!res.ok) throw new Error(`Failed to load cash accounts (${res.status})`);
  return ((await res.json()) as Paginated<CashAccount>).results;
}

export async function createCashAccount(payload: {
  entity: string;
  code: string;
  name: string;
  gl_account: string;
}): Promise<CashAccount> {
  const res = await apiFetch("/cash-accounts/", { method: "POST", body: JSON.stringify(payload) });
  if (!res.ok) throw new Error(await detail(res, "Could not save this cash account."));
  return (await res.json()) as CashAccount;
}

export type PettyCashFloat = {
  id: string;
  entity: string;
  cash_account: string;
  cash_account_code: string;
  code: string;
  float_amount: string;
  custodian: string;
  is_active: boolean;
};

export async function listPettyCashFloats(entityId?: string | null): Promise<PettyCashFloat[]> {
  const params = new URLSearchParams({ limit: "200", ordering: "code" });
  if (entityId) params.set("entity", entityId);
  const res = await apiFetch(`/petty-cash-floats/?${params.toString()}`);
  if (!res.ok) throw new Error(`Failed to load petty-cash floats (${res.status})`);
  return ((await res.json()) as Paginated<PettyCashFloat>).results;
}

export async function createPettyCashFloat(payload: {
  entity: string;
  cash_account: string;
  code: string;
  float_amount: string;
  custodian: string;
}): Promise<PettyCashFloat> {
  const res = await apiFetch("/petty-cash-floats/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await detail(res, "Could not save this petty-cash float."));
  return (await res.json()) as PettyCashFloat;
}

export type Replenishment = {
  id: string;
  entity: string;
  petty_cash_float: string;
  cash_account_code: string;
  bank_account: string;
  replenish_no: string;
  replenish_date: string;
  amount: string;
  reference: string;
  status: "draft" | "posted" | "reversed" | "cancelled";
  journal_entry: string | null;
};

export async function listReplenishments(entityId?: string | null): Promise<Replenishment[]> {
  const params = new URLSearchParams({ limit: "200", ordering: "-replenish_date" });
  if (entityId) params.set("entity", entityId);
  const res = await apiFetch(`/replenishments/?${params.toString()}`);
  if (!res.ok) throw new Error(`Failed to load replenishments (${res.status})`);
  return ((await res.json()) as Paginated<Replenishment>).results;
}

export async function createReplenishment(payload: {
  entity: string;
  petty_cash_float: string;
  bank_account: string;
  replenish_date: string;
  amount: string;
  reference?: string;
}): Promise<Replenishment> {
  const res = await apiFetch("/replenishments/", { method: "POST", body: JSON.stringify(payload) });
  if (!res.ok) throw new Error(await detail(res, "Could not create this replenishment."));
  return (await res.json()) as Replenishment;
}

export async function postReplenishment(id: string): Promise<Replenishment> {
  const res = await apiFetch(`/replenishments/${id}/post/`, {
    method: "POST",
    body: JSON.stringify({}),
  });
  if (!res.ok) throw new Error(await detail(res, "Could not post this replenishment."));
  return (await res.json()) as Replenishment;
}

export type Denomination = {
  id?: string;
  denomination_value: string;
  quantity: number;
  amount?: string;
};

export type CashCount = {
  id: string;
  entity: string;
  cash_account: string;
  count_no: string;
  count_date: string;
  counted_by: string;
  expected_amount: string;
  counted_amount: string;
  variance: string;
  variance_account: string | null;
  status: "draft" | "posted" | "reversed" | "cancelled";
  journal_entry: string | null;
  denominations: Denomination[];
};

export async function listCashCounts(entityId?: string | null): Promise<CashCount[]> {
  const params = new URLSearchParams({ limit: "200", ordering: "-count_date" });
  if (entityId) params.set("entity", entityId);
  const res = await apiFetch(`/cash-counts/?${params.toString()}`);
  if (!res.ok) throw new Error(`Failed to load cash counts (${res.status})`);
  return ((await res.json()) as Paginated<CashCount>).results;
}

export async function createCashCount(payload: {
  entity: string;
  cash_account: string;
  count_date: string;
  counted_by?: string;
  expected_amount: string;
  variance_account?: string;
  denominations: { denomination_value: string; quantity: number }[];
}): Promise<CashCount> {
  const res = await apiFetch("/cash-counts/", { method: "POST", body: JSON.stringify(payload) });
  if (!res.ok) throw new Error(await detail(res, "Could not create this cash count."));
  return (await res.json()) as CashCount;
}

export async function postCashCount(id: string): Promise<CashCount> {
  const res = await apiFetch(`/cash-counts/${id}/post/`, {
    method: "POST",
    body: JSON.stringify({}),
  });
  if (!res.ok) throw new Error(await detail(res, "Could not post this cash count."));
  return (await res.json()) as CashCount;
}
