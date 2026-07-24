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
