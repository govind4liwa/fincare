import { apiFetch } from "@/lib/api";

export type NoteStatus = "draft" | "posted" | "partially_paid" | "paid" | "cancelled";

export type CreditNote = {
  id: string;
  entity: string;
  customer: string;
  customer_code: string;
  customer_name: string;
  credit_note_no: string;
  credit_note_date: string;
  original_invoice: string | null;
  reason: string;
  subtotal: string;
  tax_total: string;
  total: string;
  status: NoteStatus;
};

type Paginated<T> = { count: number; next: string | null; previous: string | null; results: T[] };

export type CreditNoteLineInput = {
  revenue_account: string;
  description: string;
  line_amount: string;
  tax_code: string | null;
};

export type CreditNoteCreateInput = {
  entity: string;
  customer: string;
  credit_note_date: string;
  original_invoice: string | null;
  reason: string;
  lines: CreditNoteLineInput[];
};

export async function listCreditNotes(
  filters: { entityId?: string | null; status?: string } = {},
): Promise<{ count: number; results: CreditNote[] }> {
  const params = new URLSearchParams({ limit: "100", ordering: "-credit_note_date" });
  if (filters.entityId) params.set("entity", filters.entityId);
  if (filters.status) params.set("status", filters.status);
  const res = await apiFetch(`/credit-notes/?${params.toString()}`);
  if (!res.ok) throw new Error(`Failed to load credit notes (${res.status})`);
  const data = (await res.json()) as Paginated<CreditNote>;
  return { count: data.count, results: data.results };
}

async function detail(res: Response, fallback: string): Promise<string> {
  const data = (await res.json().catch(() => ({}))) as { detail?: unknown };
  return typeof data.detail === "string" ? data.detail : fallback;
}

export async function createCreditNote(payload: CreditNoteCreateInput): Promise<{ id: string }> {
  const res = await apiFetch("/credit-notes/", { method: "POST", body: JSON.stringify(payload) });
  if (!res.ok) throw new Error(await detail(res, "Could not save the credit note."));
  return (await res.json()) as { id: string };
}

export async function postCreditNote(id: string): Promise<void> {
  const res = await apiFetch(`/credit-notes/${id}/post/`, {
    method: "POST",
    body: JSON.stringify({}),
  });
  if (!res.ok) throw new Error(await detail(res, "Could not post the credit note."));
}
