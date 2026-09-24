import { apiFetch } from "@/lib/api";

export type DocStatus = "draft" | "posted" | "reversed" | "cancelled";

export type Advance = {
  id: string;
  entity: string;
  driver: string;
  driver_code: string;
  driver_name: string;
  advance_no: string;
  advance_date: string;
  amount: string;
  recovered_amount: string;
  balance: string;
  advance_account: string;
  bank_account: string | null;
  status: DocStatus;
  journal_entry: string | null;
};

export type DeductionKind = "commission" | "salary" | "advance" | "salik" | "fine" | "other";

export const DEDUCTION_KINDS: { value: DeductionKind; label: string }[] = [
  { value: "commission", label: "Commission" },
  { value: "salary", label: "Salary" },
  { value: "advance", label: "Advance recovery" },
  { value: "salik", label: "Salik recovery" },
  { value: "fine", label: "Fine recovery" },
  { value: "other", label: "Other" },
];

export type SettlementDeduction = {
  id?: string;
  kind: DeductionKind;
  account: string;
  amount: string;
  advance: string | null;
  description: string;
  kind_display?: string;
};

export type Settlement = {
  id: string;
  entity: string;
  driver: string;
  driver_code: string;
  driver_name: string;
  vehicle: string | null;
  settlement_no: string;
  period_start: string;
  period_end: string;
  settlement_date: string;
  gross_amount: string;
  gross_account: string;
  pay_account: string;
  driver_receivable_account: string | null;
  total_deductions: string;
  net_amount: string;
  /** Authorises creating an amount DUE FROM the driver. Not evidence of receipt. */
  allows_negative_net: boolean;
  /** How much of the receivable has been collected or written off. */
  cleared_amount: string;
  /** What the driver still owes on this settlement. Zero unless net < 0. */
  receivable_balance: string;
  status: DocStatus;
  journal_entry: string | null;
  deductions: SettlementDeduction[];
};

type Paginated<T> = { count: number; next: string | null; previous: string | null; results: T[] };

async function detail(res: Response, fallback: string): Promise<string> {
  const data = (await res.json().catch(() => ({}))) as Record<string, unknown>;
  if (typeof data.detail === "string") return data.detail;
  // Surface DRF field errors so validation feedback is specific.
  const parts: string[] = [];
  for (const [key, value] of Object.entries(data)) {
    const msg = Array.isArray(value) ? value.join(" ") : String(value);
    parts.push(key === "non_field_errors" ? msg : `${key}: ${msg}`);
  }
  return parts.length ? parts.join(" · ") : fallback;
}

// --- advances ---------------------------------------------------------------

export async function listAdvances(entityId?: string | null): Promise<Advance[]> {
  const params = new URLSearchParams({ limit: "200" });
  if (entityId) params.set("entity", entityId);
  const res = await apiFetch(`/driver-advances/?${params.toString()}`);
  if (!res.ok) throw new Error(`Failed to load advances (${res.status})`);
  return ((await res.json()) as Paginated<Advance>).results;
}

/** Posted advances for a driver that still have a balance to recover. */
export async function listOutstandingAdvances(driverId: string): Promise<Advance[]> {
  const res = await apiFetch(`/driver-advances/outstanding/?driver=${driverId}`);
  if (!res.ok) throw new Error(`Failed to load outstanding advances (${res.status})`);
  return ((await res.json()) as { advances: Advance[] }).advances;
}

export type AdvanceCreateInput = {
  entity: string;
  driver: string;
  advance_date: string;
  amount: string;
  advance_account: string;
  bank_account: string;
};

export async function createAdvance(payload: AdvanceCreateInput): Promise<Advance> {
  const res = await apiFetch("/driver-advances/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await detail(res, "Could not save the advance."));
  return (await res.json()) as Advance;
}

export async function postAdvance(id: string): Promise<Advance> {
  const res = await apiFetch(`/driver-advances/${id}/post/`, {
    method: "POST",
    body: JSON.stringify({}),
  });
  if (!res.ok) throw new Error(await detail(res, "Could not post the advance."));
  return (await res.json()) as Advance;
}

// --- settlements ------------------------------------------------------------

export async function listSettlements(entityId?: string | null): Promise<Settlement[]> {
  const params = new URLSearchParams({ limit: "200" });
  if (entityId) params.set("entity", entityId);
  const res = await apiFetch(`/driver-settlements/?${params.toString()}`);
  if (!res.ok) throw new Error(`Failed to load settlements (${res.status})`);
  return ((await res.json()) as Paginated<Settlement>).results;
}

export type SettlementCreateInput = {
  entity: string;
  driver: string;
  vehicle: string | null;
  period_start: string;
  period_end: string;
  settlement_date: string;
  gross_amount: string;
  gross_account: string;
  pay_account: string;
  /**
   * Only ever the entity's configured account, and only when deductions exceed
   * gross. Left null here — posting resolves and records it from configuration.
   */
  driver_receivable_account?: string | null;
  allows_negative_net: boolean;
  deductions: Omit<SettlementDeduction, "id" | "kind_display">[];
};

export async function createSettlement(payload: SettlementCreateInput): Promise<Settlement> {
  const res = await apiFetch("/driver-settlements/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await detail(res, "Could not save the settlement."));
  return (await res.json()) as Settlement;
}

export async function postSettlement(id: string): Promise<Settlement> {
  const res = await apiFetch(`/driver-settlements/${id}/post/`, {
    method: "POST",
    body: JSON.stringify({}),
  });
  if (!res.ok) throw new Error(await detail(res, "Could not post the settlement."));
  return (await res.json()) as Settlement;
}

// --- driver receivable clearing ---------------------------------------------

export type ClearingKind = "receipt" | "write_off";

export const CLEARING_KINDS: { value: ClearingKind; label: string; help: string }[] = [
  {
    value: "receipt",
    label: "Receipt from driver",
    help: "The driver paid. Debits the bank account the money landed in.",
  },
  {
    value: "write_off",
    label: "Write-off",
    help: "The balance will not be collected. Expensed to bad debts; no money moves.",
  },
];

export type DriverClearingLine = {
  id?: string;
  settlement: string;
  settlement_no?: string;
  settlement_date?: string;
  amount: string;
};

export type DriverClearing = {
  id: string;
  entity: string;
  driver: string;
  driver_code: string;
  driver_name: string;
  kind: ClearingKind;
  kind_display: string;
  clearing_no: string;
  clearing_date: string;
  amount: string;
  bank_account: string | null;
  receivable_account: string | null;
  write_off_account: string | null;
  reference: string;
  narration: string;
  status: DocStatus;
  journal_entry: string | null;
  lines: DriverClearingLine[];
};

/** Posted settlements this driver still owes on — what a clearing can apply to. */
export async function listOutstandingSettlements(driverId: string): Promise<Settlement[]> {
  const res = await apiFetch(`/driver-settlements/outstanding/?driver=${driverId}`);
  if (!res.ok) throw new Error(`Failed to load outstanding settlements (${res.status})`);
  return ((await res.json()) as { settlements: Settlement[] }).settlements;
}

export async function listClearings(entityId?: string | null): Promise<DriverClearing[]> {
  const params = new URLSearchParams({ limit: "200" });
  if (entityId) params.set("entity", entityId);
  const res = await apiFetch(`/driver-clearings/?${params.toString()}`);
  if (!res.ok) throw new Error(`Failed to load clearings (${res.status})`);
  return ((await res.json()) as Paginated<DriverClearing>).results;
}

export type ClearingCreateInput = {
  entity: string;
  driver: string;
  kind: ClearingKind;
  clearing_date: string;
  amount: string;
  /** Required for a receipt, must be null for a write-off. */
  bank_account: string | null;
  reference: string;
  narration: string;
  lines: { settlement: string; amount: string }[];
};

export async function createClearing(payload: ClearingCreateInput): Promise<DriverClearing> {
  const res = await apiFetch("/driver-clearings/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await detail(res, "Could not save the clearing."));
  return (await res.json()) as DriverClearing;
}

export async function postClearing(id: string): Promise<DriverClearing> {
  const res = await apiFetch(`/driver-clearings/${id}/post/`, {
    method: "POST",
    body: JSON.stringify({}),
  });
  if (!res.ok) throw new Error(await detail(res, "Could not post the clearing."));
  return (await res.json()) as DriverClearing;
}

/** Reverses a posted clearing and puts the receivable back. Manager/admin only. */
export async function reverseClearing(id: string): Promise<DriverClearing> {
  const res = await apiFetch(`/driver-clearings/${id}/reverse/`, {
    method: "POST",
    body: JSON.stringify({}),
  });
  if (!res.ok) throw new Error(await detail(res, "Could not reverse the clearing."));
  return (await res.json()) as DriverClearing;
}
