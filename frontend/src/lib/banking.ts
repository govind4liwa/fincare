import { apiFetch } from "@/lib/api";

export type BankAccount = {
  id: string;
  entity: string;
  code: string;
  name: string;
  gl_account: string;
  gl_account_code: string;
  gl_account_name: string;
  bank_name: string;
  account_number: string;
  iban: string;
  swift: string;
  branch_name: string;
  is_active: boolean;
};

export type StatementLine = {
  id?: string;
  line_no?: number;
  txn_date: string;
  description: string;
  reference: string;
  deposit: string;
  withdrawal: string;
  is_matched?: boolean;
};

export type BankStatement = {
  id: string;
  bank_account: string;
  bank_account_code: string;
  statement_date: string;
  opening_balance: string;
  closing_balance: string;
  status: string;
};

export type Reconciliation = {
  id: string;
  bank_account: string;
  bank_account_code: string;
  statement: string | null;
  recon_date: string;
  statement_balance: string;
  gl_balance: string;
  difference: string;
  status: string;
};

export type ReconTotals = {
  statement_balance: string;
  gl_balance: string;
  difference: string;
  matched_count: number;
  matched_total: string;
  unmatched_count: number;
  unmatched_deposits: string;
  unmatched_withdrawals: string;
};

export type MatchedItem = {
  id: string;
  match_type: string;
  amount: string;
  statement_line: StatementLine;
  entry_no: string;
  entry_date: string;
  gl_debit: string;
  gl_credit: string;
};

export type GlLine = {
  id: string;
  entry_no: string;
  entry_date: string;
  description: string;
  debit: string;
  credit: string;
  is_matched: boolean;
};

export type Workspace = {
  reconciliation: Reconciliation;
  matched: MatchedItem[];
  unmatched_lines: StatementLine[];
  gl_lines: GlLine[];
  totals: ReconTotals;
};

type Paginated<T> = { count: number; next: string | null; previous: string | null; results: T[] };

async function detail(res: Response, fallback: string): Promise<string> {
  const data = (await res.json().catch(() => ({}))) as { detail?: unknown };
  return typeof data.detail === "string" ? data.detail : fallback;
}

async function list<T>(resource: string, params: Record<string, string>): Promise<T[]> {
  const qs = new URLSearchParams({ limit: "200", ...params });
  const res = await apiFetch(`/${resource}/?${qs.toString()}`);
  if (!res.ok) throw new Error(`Failed to load ${resource} (${res.status})`);
  return ((await res.json()) as Paginated<T>).results;
}

export function listBankAccounts(entityId?: string | null): Promise<BankAccount[]> {
  return list<BankAccount>("bank-accounts", entityId ? { entity: entityId, ordering: "code" } : {});
}

export function listStatements(bankAccountId?: string): Promise<BankStatement[]> {
  return list<BankStatement>("bank-statements", bankAccountId ? { bank_account: bankAccountId } : {});
}

export function listReconciliations(bankAccountId?: string): Promise<Reconciliation[]> {
  return list<Reconciliation>(
    "reconciliations",
    bankAccountId ? { bank_account: bankAccountId } : {},
  );
}

export type StatementCreateInput = {
  entity: string;
  bank_account: string;
  statement_date: string;
  opening_balance: string;
  closing_balance: string;
  lines: Omit<StatementLine, "id" | "is_matched">[];
};

export async function createStatement(payload: StatementCreateInput): Promise<{ id: string }> {
  const res = await apiFetch("/bank-statements/", { method: "POST", body: JSON.stringify(payload) });
  if (!res.ok) throw new Error(await detail(res, "Could not save the statement."));
  return (await res.json()) as { id: string };
}

export async function createReconciliation(payload: {
  entity: string;
  bank_account: string;
  statement: string;
  recon_date: string;
}): Promise<{ id: string }> {
  const res = await apiFetch("/reconciliations/", { method: "POST", body: JSON.stringify(payload) });
  if (!res.ok) throw new Error(await detail(res, "Could not create the reconciliation."));
  return (await res.json()) as { id: string };
}

export async function autoMatch(
  reconId: string,
  params: { amount_tolerance?: string; date_window_days?: number; match_reference?: boolean } = {},
): Promise<Workspace> {
  const res = await apiFetch(`/reconciliations/${reconId}/auto-match/`, {
    method: "POST",
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error(await detail(res, "Auto-match could not run."));
  return (await res.json()) as Workspace;
}

export async function getWorkspace(reconId: string): Promise<Workspace> {
  const res = await apiFetch(`/reconciliations/${reconId}/workspace/`);
  if (!res.ok) throw new Error(`Failed to load the reconciliation (${res.status})`);
  return (await res.json()) as Workspace;
}

async function reconAction(reconId: string, path: string, body: object, fallback: string): Promise<Workspace> {
  const res = await apiFetch(`/reconciliations/${reconId}/${path}/`, {
    method: "POST",
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await detail(res, fallback));
  return (await res.json()) as Workspace;
}

export function manualMatch(reconId: string, statementLine: string, journalLine: string) {
  return reconAction(
    reconId,
    "manual-match",
    { statement_line: statementLine, journal_line: journalLine },
    "Could not match those lines.",
  );
}

export function unmatch(reconId: string, item: string) {
  return reconAction(reconId, "unmatch", { item }, "Could not unmatch.");
}

export function completeReconciliation(reconId: string) {
  return reconAction(reconId, "complete", {}, "Could not complete the reconciliation.");
}

export function reopenReconciliation(reconId: string) {
  return reconAction(reconId, "reopen", {}, "Could not reopen the reconciliation.");
}
