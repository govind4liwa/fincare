import { apiFetch } from "@/lib/api";

type Paginated<T> = { count: number; next: string | null; previous: string | null; results: T[] };

export type AuditAction = "create" | "update" | "delete" | "post" | "reverse" | "cancel" | "login";

export type AuditLog = {
  id: string;
  timestamp: string;
  actor: string | null;
  actor_email: string | null;
  action: AuditAction;
  content_type_label: string | null;
  object_id: string;
  object_repr: string;
  entity_id: string | null;
  changes: Record<string, [unknown, unknown]>;
  message: string;
};

export async function listAuditLogs(params: {
  entityId?: string | null;
  action?: string;
}): Promise<AuditLog[]> {
  const query = new URLSearchParams({ limit: "100", ordering: "-timestamp" });
  if (params.entityId) query.set("entity_id", params.entityId);
  if (params.action) query.set("action", params.action);
  const res = await apiFetch(`/audit-logs/?${query.toString()}`);
  if (!res.ok) throw new Error(`Failed to load audit logs (${res.status})`);
  return ((await res.json()) as Paginated<AuditLog>).results;
}
