import { apiFetch } from "@/lib/api";
import type { Account } from "@/lib/accounts";

type Paginated<T> = { count: number; next: string | null; previous: string | null; results: T[] };

/**
 * The entity's approved Driver Receivable account. Configuring it *is* the
 * approval to post driver receivables — there is no per-account flag — so this
 * is administration, not a per-document choice.
 */
export type DriverAccountingConfig = {
  id: string;
  entity: string;
  default_receivable_account: string;
  account_code: string;
  account_name: string;
};

/** Account types that can never hold a driver receivable, whatever their nature. */
const FORBIDDEN_TYPES = ["bank", "cash", "fixed_asset"];

/**
 * Mirrors `apps.settings.services.driver_accounting.validate_receivable_account`
 * so the picker only offers accounts the server will accept. The server stays the
 * authority; this just avoids presenting choices that would be rejected.
 */
export function isEligibleReceivableAccount(account: Account): boolean {
  return (
    account.is_active &&
    account.is_postable &&
    account.allow_manual_posting &&
    account.nature === "asset" &&
    // Debit-normal excludes contra-assets such as accumulated depreciation.
    account.normal_balance === "D" &&
    !account.is_bank_account &&
    !FORBIDDEN_TYPES.includes(account.account_type) &&
    // Settlement lines carry the driver dimension, not a party subledger.
    !account.is_control_account &&
    !account.subledger
  );
}

async function detail(res: Response, fallback: string): Promise<string> {
  const data = (await res.json().catch(() => ({}))) as Record<string, unknown>;
  if (typeof data.detail === "string") return data.detail;
  const parts: string[] = [];
  for (const [key, value] of Object.entries(data)) {
    const msg = Array.isArray(value) ? value.join(" ") : String(value);
    parts.push(key === "non_field_errors" ? msg : `${key}: ${msg}`);
  }
  return parts.length ? parts.join(" · ") : fallback;
}

/** `null` when the entity has no configuration — negative net cannot be posted. */
export async function getDriverAccountingConfig(
  entityId: string,
): Promise<DriverAccountingConfig | null> {
  const res = await apiFetch(`/driver-accounting-config/?entity=${entityId}`);
  if (!res.ok) throw new Error(`Failed to load driver accounting configuration (${res.status})`);
  const page = (await res.json()) as Paginated<DriverAccountingConfig>;
  return page.results[0] ?? null;
}

/**
 * Whether this user may change the configuration (manager/admin).
 *
 * Read from the endpoint's own OPTIONS metadata, which lists `actions.POST` only
 * when the caller passes the write permission — so the answer comes from the
 * server that enforces it, not from a guess about the user's roles.
 */
export async function canConfigureDriverAccounting(): Promise<boolean> {
  const res = await apiFetch("/driver-accounting-config/", { method: "OPTIONS" });
  if (!res.ok) return false;
  const meta = (await res.json().catch(() => ({}))) as { actions?: Record<string, unknown> };
  return Boolean(meta.actions?.POST);
}

/** Create or repoint the entity's configuration. */
export async function saveDriverReceivableAccount(
  entityId: string,
  accountId: string,
  existing: DriverAccountingConfig | null,
): Promise<DriverAccountingConfig> {
  const res = existing
    ? await apiFetch(`/driver-accounting-config/${existing.id}/`, {
        method: "PATCH",
        body: JSON.stringify({ default_receivable_account: accountId }),
      })
    : await apiFetch("/driver-accounting-config/", {
        method: "POST",
        body: JSON.stringify({ entity: entityId, default_receivable_account: accountId }),
      });
  if (!res.ok) throw new Error(await detail(res, "Could not save the configuration."));
  return (await res.json()) as DriverAccountingConfig;
}
