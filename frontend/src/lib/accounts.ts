import { apiFetch } from "@/lib/api";

export type Nature = "asset" | "liability" | "equity" | "income" | "expense";

export type Account = {
  id: string;
  entity: string;
  sub_group: string;
  code: string;
  charge_segment: string;
  name: string;
  nature: Nature;
  account_type: string;
  account_type_display: string;
  normal_balance: "D" | "C";
  sub_group_code: string;
  sub_group_name: string;
  currency: string | null;
  is_control_account: boolean;
  subledger: string;
  is_bank_account: boolean;
  allow_manual_posting: boolean;
  is_postable: boolean;
  is_active: boolean;
};

export type AccountGroup = {
  id: string;
  level: number;
  segment: string;
  code: string;
  name: string;
  nature: Nature;
};

type Paginated<T> = { count: number; next: string | null; previous: string | null; results: T[] };

/** Accounts for the given entity (or all accessible entities when omitted). */
export async function listAccounts(entityId?: string | null): Promise<Account[]> {
  const params = new URLSearchParams({ limit: "1000", ordering: "code" });
  if (entityId) params.set("entity", entityId);
  const res = await apiFetch(`/accounts/?${params.toString()}`);
  if (!res.ok) throw new Error("Failed to load accounts");
  const data = (await res.json()) as Paginated<Account>;
  return data.results;
}

/** Account groups for an entity, optionally narrowed to a tier (1=Main, 2=Sub). */
export async function listAccountGroups(
  entityId?: string | null,
  level?: number,
): Promise<AccountGroup[]> {
  const params = new URLSearchParams({ limit: "1000", ordering: "code" });
  if (entityId) params.set("entity", entityId);
  if (level) params.set("level", String(level));
  const res = await apiFetch(`/account-groups/?${params.toString()}`);
  if (!res.ok) throw new Error("Failed to load account groups");
  const data = (await res.json()) as Paginated<AccountGroup>;
  return data.results;
}
