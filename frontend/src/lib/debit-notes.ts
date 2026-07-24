import { apiFetch } from "@/lib/api";

export type NoteStatus = "draft" | "posted" | "partially_paid" | "paid" | "cancelled";

export type DebitNote = {
  id: string;
  entity: string;
  supplier: string;
  supplier_code: string;
  supplier_name: string;
  debit_note_no: string;
  debit_note_date: string;
  original_bill: string | null;
  reason: string;
  subtotal: string;
  tax_total: string;
  total: string;
  status: NoteStatus;
};

type Paginated<T> = { count: number; next: string | null; previous: string | null; results: T[] };

export type DebitNoteLineInput = {
  account: string;
  description: string;
  line_amount: string;
  tax_code: string | null;
};

export type DebitNoteCreateInput = {
  entity: string;
  supplier: string;
  debit_note_date: string;
  original_bill: string | null;
  reason: string;
  lines: DebitNoteLineInput[];
};

export async function listDebitNotes(
  filters: { entityId?: string | null; status?: string } = {},
): Promise<{ count: number; results: DebitNote[] }> {
  const params = new URLSearchParams({ limit: "100", ordering: "-debit_note_date" });
  if (filters.entityId) params.set("entity", filters.entityId);
  if (filters.status) params.set("status", filters.status);
  const res = await apiFetch(`/debit-notes/?${params.toString()}`);
  if (!res.ok) throw new Error(`Failed to load debit notes (${res.status})`);
  const data = (await res.json()) as Paginated<DebitNote>;
  return { count: data.count, results: data.results };
}

async function detail(res: Response, fallback: string): Promise<string> {
  const data = (await res.json().catch(() => ({}))) as { detail?: unknown };
  return typeof data.detail === "string" ? data.detail : fallback;
}

export async function createDebitNote(payload: DebitNoteCreateInput): Promise<{ id: string }> {
  const res = await apiFetch("/debit-notes/", { method: "POST", body: JSON.stringify(payload) });
  if (!res.ok) throw new Error(await detail(res, "Could not save the debit note."));
  return (await res.json()) as { id: string };
}

export async function postDebitNote(id: string): Promise<void> {
  const res = await apiFetch(`/debit-notes/${id}/post/`, {
    method: "POST",
    body: JSON.stringify({}),
  });
  if (!res.ok) throw new Error(await detail(res, "Could not post the debit note."));
}
