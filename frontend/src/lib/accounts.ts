import { apiFetch } from "@/lib/api";

export type Nature = "asset" | "liability" | "equity" | "income" | "expense";

export type Account = {
  id: string;
  entity: string;
  code: string;
  name: string;
  nature: Nature;
  account_type: string;
  account_type_display: string;
  normal_balance: "D" | "C";
  sub_group_code: string;
  sub_group_name: string;
  is_control_account: boolean;
  is_bank_account: boolean;
  is_postable: boolean;
  is_active: boolean;
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
