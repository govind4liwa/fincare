import { apiFetch } from "@/lib/api";

type Paginated<T> = { count: number; next: string | null; previous: string | null; results: T[] };

async function detail(res: Response, fallback: string): Promise<string> {
  const data = (await res.json().catch(() => ({}))) as { detail?: unknown };
  return typeof data.detail === "string" ? data.detail : fallback;
}

export type ReturnStatus = "draft" | "computed" | "filed" | "paid";

export type TaxReturnBox = {
  id: string;
  box_code: string;
  label: string;
  emirate: string;
  amount: string;
  vat_amount: string;
  adjustment: string;
  sort_order: number;
};

export type VatReturn = {
  id: string;
  vat_group: string | null;
  vat_group_name: string;
  entity: string | null;
  entity_name: string;
  trn: string;
  period_start: string;
  period_end: string;
  status: ReturnStatus;
  total_output_vat: string;
  total_input_vat: string;
  net_vat_payable: string;
  computed_at: string | null;
  filed_at: string | null;
  filed_by_email?: string;
  filing_reference: string;
  boxes: TaxReturnBox[];
};

export async function listVatReturns(entityId?: string | null): Promise<VatReturn[]> {
  const params = new URLSearchParams({ limit: "100", ordering: "-period_end" });
  if (entityId) params.set("entity", entityId);
  const res = await apiFetch(`/vat-returns/?${params.toString()}`);
  if (!res.ok) throw new Error(`Failed to load VAT returns (${res.status})`);
  return ((await res.json()) as Paginated<VatReturn>).results;
}

export async function createVatReturn(payload: {
  vat_group: string | null;
  entity: string | null;
  period_start: string;
  period_end: string;
}): Promise<VatReturn> {
  const res = await apiFetch("/vat-returns/", { method: "POST", body: JSON.stringify(payload) });
  if (!res.ok) throw new Error(await detail(res, "Could not create this return."));
  return (await res.json()) as VatReturn;
}

export async function computeVatReturn(id: string): Promise<VatReturn> {
  const res = await apiFetch(`/vat-returns/${id}/compute/`, {
    method: "POST",
    body: JSON.stringify({}),
  });
  if (!res.ok) throw new Error(await detail(res, "Could not compute this return."));
  return (await res.json()) as VatReturn;
}

export async function fileVatReturn(id: string, reference: string): Promise<VatReturn> {
  const res = await apiFetch(`/vat-returns/${id}/file/`, {
    method: "POST",
    body: JSON.stringify({ reference }),
  });
  if (!res.ok) throw new Error(await detail(res, "Could not file this return."));
  return (await res.json()) as VatReturn;
}

export type CorporateTaxReturn = {
  id: string;
  entity: string;
  entity_name: string;
  fiscal_year: number;
  trn: string;
  period_start: string;
  period_end: string;
  accounting_net_profit: string;
  adjustments: string;
  taxable_income: string;
  zero_band_threshold: string;
  tax_rate: string;
  small_business_relief: boolean;
  tax_payable: string;
  status: ReturnStatus;
  computed_at: string | null;
  filed_at: string | null;
  filed_by_email?: string;
  filing_reference: string;
};

export async function listCorporateTaxReturns(
  entityId?: string | null,
): Promise<CorporateTaxReturn[]> {
  const params = new URLSearchParams({ limit: "100", ordering: "-fiscal_year" });
  if (entityId) params.set("entity", entityId);
  const res = await apiFetch(`/corporate-tax-returns/?${params.toString()}`);
  if (!res.ok) throw new Error(`Failed to load corporate tax returns (${res.status})`);
  return ((await res.json()) as Paginated<CorporateTaxReturn>).results;
}

export async function createCorporateTaxReturn(payload: {
  entity: string;
  fiscal_year: number;
  period_start: string;
  period_end: string;
  accounting_net_profit: string;
  adjustments: string;
  small_business_relief: boolean;
}): Promise<CorporateTaxReturn> {
  const res = await apiFetch("/corporate-tax-returns/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await detail(res, "Could not create this return."));
  return (await res.json()) as CorporateTaxReturn;
}

export async function computeCorporateTaxReturn(id: string): Promise<CorporateTaxReturn> {
  const res = await apiFetch(`/corporate-tax-returns/${id}/compute/`, {
    method: "POST",
    body: JSON.stringify({}),
  });
  if (!res.ok) throw new Error(await detail(res, "Could not compute this return."));
  return (await res.json()) as CorporateTaxReturn;
}

export async function fileCorporateTaxReturn(
  id: string,
  reference: string,
): Promise<CorporateTaxReturn> {
  const res = await apiFetch(`/corporate-tax-returns/${id}/file/`, {
    method: "POST",
    body: JSON.stringify({ reference }),
  });
  if (!res.ok) throw new Error(await detail(res, "Could not file this return."));
  return (await res.json()) as CorporateTaxReturn;
}
