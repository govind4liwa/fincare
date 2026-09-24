import { apiFetch } from "@/lib/api";

export type Vehicle = {
  id: string;
  code: string;
  plate_no: string;
  plate_emirate: string;
  make: string;
  model: string;
  model_year: number | null;
  vin: string;
  ownership: string;
  acquisition_date: string | null;
  acquisition_cost: string;
  is_active: boolean;
};

export type Driver = {
  id: string;
  code: string;
  name: string;
  nationality: string;
  licence_no: string;
  emirates_id: string;
  phone: string;
  basic_salary: string;
  commission_rate: string;
  is_active: boolean;
};

type Paginated<T> = { count: number; next: string | null; previous: string | null; results: T[] };

async function listResource<T>(resource: string, entityId?: string | null): Promise<T[]> {
  const params = new URLSearchParams({ limit: "500", ordering: "code" });
  if (entityId) params.set("entity", entityId);
  const res = await apiFetch(`/${resource}/?${params.toString()}`);
  if (!res.ok) throw new Error(`Failed to load ${resource} (${res.status})`);
  return ((await res.json()) as Paginated<T>).results;
}

export const listVehicles = (entityId?: string | null) =>
  listResource<Vehicle>("vehicles", entityId);
export const listDrivers = (entityId?: string | null) => listResource<Driver>("drivers", entityId);

async function detail(res: Response, fallback: string): Promise<string> {
  const data = (await res.json().catch(() => ({}))) as { detail?: unknown };
  return typeof data.detail === "string" ? data.detail : fallback;
}

export type VehicleDocument = {
  id: string;
  vehicle: string;
  vehicle_code: string;
  doc_type: "registration" | "insurance" | "salik_tag" | "permit" | "other";
  doc_no: string;
  issue_date: string | null;
  expiry_date: string | null;
  note: string;
  days_to_expiry: number | null;
};

export async function listVehicleDocuments(vehicleId: string): Promise<VehicleDocument[]> {
  const res = await apiFetch(`/vehicle-documents/?vehicle=${vehicleId}&limit=100`);
  if (!res.ok) throw new Error(`Failed to load documents (${res.status})`);
  return ((await res.json()) as Paginated<VehicleDocument>).results;
}

export async function createVehicleDocument(payload: {
  vehicle: string;
  doc_type: string;
  doc_no: string;
  issue_date: string | null;
  expiry_date: string | null;
  note: string;
}): Promise<VehicleDocument> {
  const res = await apiFetch("/vehicle-documents/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await detail(res, "Could not save this document."));
  return (await res.json()) as VehicleDocument;
}

export type DepreciationLine = { id: string; vehicle: string; vehicle_code: string; amount: string };

export type DepreciationRun = {
  id: string;
  entity: string;
  run_no: string;
  run_date: string;
  period_label: string;
  total_amount: string;
  status: "draft" | "posted" | "reversed" | "cancelled";
  journal_entry: string | null;
  lines: DepreciationLine[];
};

export async function listDepreciationRuns(entityId?: string | null): Promise<DepreciationRun[]> {
  const params = new URLSearchParams({ limit: "100", ordering: "-run_date" });
  if (entityId) params.set("entity", entityId);
  const res = await apiFetch(`/depreciation-runs/?${params.toString()}`);
  if (!res.ok) throw new Error(`Failed to load depreciation runs (${res.status})`);
  return ((await res.json()) as Paginated<DepreciationRun>).results;
}

export async function createDepreciationRun(payload: {
  entity: string;
  run_date: string;
  period_label: string;
}): Promise<DepreciationRun> {
  const res = await apiFetch("/depreciation-runs/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await detail(res, "Could not create this run."));
  return (await res.json()) as DepreciationRun;
}

export async function postDepreciationRun(id: string): Promise<DepreciationRun> {
  const res = await apiFetch(`/depreciation-runs/${id}/post/`, {
    method: "POST",
    body: JSON.stringify({}),
  });
  if (!res.ok) throw new Error(await detail(res, "Could not post this run."));
  return (await res.json()) as DepreciationRun;
}
