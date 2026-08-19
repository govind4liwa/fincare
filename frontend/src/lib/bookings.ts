import { apiFetch } from "@/lib/api";

type Paginated<T> = { count: number; next: string | null; previous: string | null; results: T[] };

async function detail(res: Response, fallback: string): Promise<string> {
  const data = (await res.json().catch(() => ({}))) as { detail?: unknown };
  return typeof data.detail === "string" ? data.detail : fallback;
}

export type Trip = {
  id: string;
  entity: string;
  trip_date: string;
  trip_type: "platform" | "personal" | "corporate" | "contract";
  vehicle: string | null;
  vehicle_code: string;
  driver: string | null;
  driver_code: string;
  platform: string | null;
  platform_name: string;
  customer: string | null;
  customer_name: string;
  fare: string;
  commission: string;
  salik: string;
  tip: string;
  distance_km: string | null;
  net_revenue: string;
  status: "recorded" | "invoiced" | "settled";
  revenue_journal_entry: string | null;
};

export async function listTrips(filters: {
  entityId?: string | null;
  platformId?: string;
  status?: string;
}): Promise<Trip[]> {
  const params = new URLSearchParams({ limit: "200", ordering: "-trip_date" });
  if (filters.entityId) params.set("entity", filters.entityId);
  if (filters.platformId) params.set("platform", filters.platformId);
  if (filters.status) params.set("status", filters.status);
  const res = await apiFetch(`/trips/?${params.toString()}`);
  if (!res.ok) throw new Error(`Failed to load trips (${res.status})`);
  return ((await res.json()) as Paginated<Trip>).results;
}

export async function createTrip(payload: {
  entity: string;
  trip_date: string;
  trip_type: string;
  vehicle: string | null;
  driver: string | null;
  platform: string | null;
  customer: string | null;
  fare: string;
  commission: string;
  salik: string;
  tip: string;
}): Promise<Trip> {
  const res = await apiFetch("/trips/", { method: "POST", body: JSON.stringify(payload) });
  if (!res.ok) throw new Error(await detail(res, "Could not save this trip."));
  return (await res.json()) as Trip;
}

export async function postTripRevenue(
  platformId: string,
  tripIds: string[],
  date: string,
): Promise<{ entry_no: string; trips: Trip[] }> {
  const res = await apiFetch("/trips/post-revenue/", {
    method: "POST",
    body: JSON.stringify({ platform: platformId, trip_ids: tripIds, date }),
  });
  if (!res.ok) throw new Error(await detail(res, "Could not post trip revenue."));
  return (await res.json()) as { entry_no: string; trips: Trip[] };
}

export type Contract = {
  id: string;
  entity: string;
  customer: string;
  customer_name: string;
  vehicle: string | null;
  vehicle_code: string;
  driver: string | null;
  driver_code: string;
  contract_no: string;
  start_date: string;
  end_date: string | null;
  billing_cycle: "monthly" | "weekly";
  monthly_amount: string;
  revenue_account: string;
  revenue_account_code: string;
  tax_code: string;
  tax_code_code: string;
  status: "active" | "suspended" | "ended";
};

export async function listContracts(entityId?: string | null): Promise<Contract[]> {
  const params = new URLSearchParams({ limit: "200", ordering: "contract_no" });
  if (entityId) params.set("entity", entityId);
  const res = await apiFetch(`/contracts/?${params.toString()}`);
  if (!res.ok) throw new Error(`Failed to load contracts (${res.status})`);
  return ((await res.json()) as Paginated<Contract>).results;
}

export async function generateContractInvoice(
  contractId: string,
  invoiceDate: string,
  periodLabel: string,
): Promise<{ invoice_id: string; invoice_no: string }> {
  const res = await apiFetch(`/contracts/${contractId}/generate-invoice/`, {
    method: "POST",
    body: JSON.stringify({ invoice_date: invoiceDate, period_label: periodLabel }),
  });
  if (!res.ok) throw new Error(await detail(res, "Could not generate the invoice."));
  return (await res.json()) as { invoice_id: string; invoice_no: string };
}
