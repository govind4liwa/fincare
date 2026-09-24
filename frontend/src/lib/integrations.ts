import { apiFetch } from "@/lib/api";

type Paginated<T> = { count: number; next: string | null; previous: string | null; results: T[] };

/** Turn a DRF error body into a readable one-line message (detail or field errors). */
async function errorMessage(res: Response, fallback: string): Promise<string> {
  const data = (await res.json().catch(() => null)) as unknown;
  if (data && typeof data === "object") {
    const d = data as Record<string, unknown>;
    if (typeof d.detail === "string") return d.detail;
    const parts: string[] = [];
    for (const [key, value] of Object.entries(d)) {
      const msg = Array.isArray(value) ? value.join(" ") : String(value);
      parts.push(key === "non_field_errors" ? msg : `${key}: ${msg}`);
    }
    if (parts.length) return parts.join(" · ");
  }
  return fallback;
}

export type ImportKind = "bank_statement" | "platform_earning";

/** Canonical mappable fields per kind — mirrors the backend serializer. */
export const BANK_FIELDS = [
  "txn_date",
  "description",
  "reference",
  "deposit",
  "withdrawal",
  "running_balance",
] as const;
export const PLATFORM_FIELDS = [
  "earning_date",
  "trip_ref",
  "driver_ref",
  "gross",
  "commission",
  "net",
] as const;
export const REQUIRED_FIELDS: Record<ImportKind, readonly string[]> = {
  bank_statement: ["txn_date"],
  platform_earning: ["earning_date", "gross"],
};

export type ImportProfile = {
  id: string;
  entity: string | null;
  kind: ImportKind;
  name: string;
  source_key: string;
  column_map: Record<string, string>;
  date_format: string;
  skip_rows: number;
  sheet: string;
  is_active: boolean;
};

export type ImportBatch = {
  id: string;
  entity: string;
  profile: string | null;
  profile_name: string;
  kind: ImportKind;
  filename: string;
  file_hash: string;
  bank_account: string | null;
  bank_account_code: string;
  platform: string | null;
  platform_name: string;
  bank_statement: string | null;
  row_count: number;
  created_count: number;
  skipped_count: number;
  error_count: number;
  status: "done" | "error";
  message: string;
  imported_at: string | null;
  imported_by_email: string;
};

// No entity filter param: entity-scoped profiles for other entities are already
// hidden server-side, and group-wide (entity=null) profiles must stay visible.
export async function listProfiles(): Promise<ImportProfile[]> {
  const params = new URLSearchParams({ limit: "200" });
  const res = await apiFetch(`/import-profiles/?${params.toString()}`);
  if (!res.ok) throw new Error(`Failed to load import profiles (${res.status})`);
  return ((await res.json()) as Paginated<ImportProfile>).results;
}

export type ProfileInput = {
  entity: string | null;
  kind: ImportKind;
  name: string;
  source_key: string;
  column_map: Record<string, string>;
  date_format: string;
  skip_rows: number;
  sheet: string;
};

export async function createProfile(payload: ProfileInput): Promise<ImportProfile> {
  const res = await apiFetch("/import-profiles/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await errorMessage(res, "Could not save this profile."));
  return (await res.json()) as ImportProfile;
}

export async function updateProfile(
  id: string,
  payload: Partial<ProfileInput> & { is_active?: boolean },
): Promise<ImportProfile> {
  const res = await apiFetch(`/import-profiles/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await errorMessage(res, "Could not update this profile."));
  return (await res.json()) as ImportProfile;
}

export async function listBatches(entityId?: string | null): Promise<ImportBatch[]> {
  const params = new URLSearchParams({ limit: "50", ordering: "-created_at" });
  if (entityId) params.set("entity", entityId);
  const res = await apiFetch(`/import-batches/?${params.toString()}`);
  if (!res.ok) throw new Error(`Failed to load import history (${res.status})`);
  return ((await res.json()) as Paginated<ImportBatch>).results;
}

export async function uploadBankStatement(input: {
  file: File;
  bank_account: string;
  profile: string;
  statement_no?: string;
}): Promise<ImportBatch> {
  const form = new FormData();
  form.append("file", input.file);
  form.append("bank_account", input.bank_account);
  form.append("profile", input.profile);
  if (input.statement_no) form.append("statement_no", input.statement_no);
  const res = await apiFetch("/import-batches/bank-statement/", { method: "POST", body: form });
  if (!res.ok) throw new Error(await errorMessage(res, "Import failed."));
  return (await res.json()) as ImportBatch;
}

export async function uploadPlatformEarnings(input: {
  file: File;
  platform: string;
  profile: string;
}): Promise<ImportBatch> {
  const form = new FormData();
  form.append("file", input.file);
  form.append("platform", input.platform);
  form.append("profile", input.profile);
  const res = await apiFetch("/import-batches/platform-earnings/", { method: "POST", body: form });
  if (!res.ok) throw new Error(await errorMessage(res, "Import failed."));
  return (await res.json()) as ImportBatch;
}
