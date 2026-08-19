import { apiFetch } from "@/lib/api";

type Paginated<T> = { count: number; next: string | null; previous: string | null; results: T[] };

async function detail(res: Response, fallback: string): Promise<string> {
  const data = (await res.json().catch(() => ({}))) as { detail?: unknown };
  return typeof data.detail === "string" ? data.detail : fallback;
}

export type Platform = {
  id: string;
  entity: string;
  name: string;
  commission_pct: string;
  settlement_cycle: "daily" | "weekly" | "monthly" | "";
  revenue_account: string;
  revenue_account_code: string;
  commission_account: string;
  commission_account_code: string;
  clearing_account: string;
  clearing_account_code: string;
  is_active: boolean;
};

export async function listPlatforms(entityId?: string | null): Promise<Platform[]> {
  const params = new URLSearchParams({ limit: "200", ordering: "name" });
  if (entityId) params.set("entity", entityId);
  const res = await apiFetch(`/platforms/?${params.toString()}`);
  if (!res.ok) throw new Error(`Failed to load platforms (${res.status})`);
  return ((await res.json()) as Paginated<Platform>).results;
}

export type EarningImport = {
  id: string;
  entity: string;
  platform: string;
  platform_name: string;
  settlement: string | null;
  trip_ref: string;
  driver_ref: string;
  earning_date: string;
  gross: string;
  commission: string;
  net: string;
  matched: boolean;
};

export async function listEarningImports(filters: {
  entityId?: string | null;
  platformId?: string;
}): Promise<EarningImport[]> {
  const params = new URLSearchParams({ limit: "200", ordering: "-earning_date" });
  if (filters.entityId) params.set("entity", filters.entityId);
  if (filters.platformId) params.set("platform", filters.platformId);
  const res = await apiFetch(`/earning-imports/?${params.toString()}`);
  if (!res.ok) throw new Error(`Failed to load earning imports (${res.status})`);
  return ((await res.json()) as Paginated<EarningImport>).results;
}

export async function createEarningImport(payload: {
  entity: string;
  platform: string;
  trip_ref: string;
  driver_ref: string;
  earning_date: string;
  gross: string;
  commission: string;
  net: string;
}): Promise<EarningImport> {
  const res = await apiFetch("/earning-imports/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await detail(res, "Could not save this earning row."));
  return (await res.json()) as EarningImport;
}

export type PlatformSettlement = {
  id: string;
  entity: string;
  platform: string;
  platform_name: string;
  settlement_no: string;
  period_start: string;
  period_end: string;
  settlement_date: string;
  gross_earnings: string;
  commission: string;
  adjustments: string;
  net_received: string;
  variance: string;
  bank_account: string | null;
  adjustment_account: string | null;
  status: "draft" | "reconciled" | "posted" | "reversed";
  journal_entry: string | null;
};

export async function listPlatformSettlements(
  entityId?: string | null,
): Promise<PlatformSettlement[]> {
  const params = new URLSearchParams({ limit: "100", ordering: "-settlement_date" });
  if (entityId) params.set("entity", entityId);
  const res = await apiFetch(`/platform-settlements/?${params.toString()}`);
  if (!res.ok) throw new Error(`Failed to load settlements (${res.status})`);
  return ((await res.json()) as Paginated<PlatformSettlement>).results;
}

export async function createPlatformSettlement(payload: {
  entity: string;
  platform: string;
  period_start: string;
  period_end: string;
  settlement_date: string;
  net_received: string;
  bank_account: string;
  adjustment_account: string;
  adjustments: string;
}): Promise<PlatformSettlement> {
  const res = await apiFetch("/platform-settlements/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await detail(res, "Could not create this settlement."));
  return (await res.json()) as PlatformSettlement;
}

export async function reconcileSettlement(id: string): Promise<PlatformSettlement> {
  const res = await apiFetch(`/platform-settlements/${id}/reconcile/`, {
    method: "POST",
    body: JSON.stringify({}),
  });
  if (!res.ok) throw new Error(await detail(res, "Could not reconcile this settlement."));
  return (await res.json()) as PlatformSettlement;
}

export async function postSettlement(id: string): Promise<PlatformSettlement> {
  const res = await apiFetch(`/platform-settlements/${id}/post/`, {
    method: "POST",
    body: JSON.stringify({}),
  });
  if (!res.ok) throw new Error(await detail(res, "Could not post this settlement."));
  return (await res.json()) as PlatformSettlement;
}
