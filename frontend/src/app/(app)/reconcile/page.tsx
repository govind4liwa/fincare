"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Plus } from "lucide-react";
import { useEntity } from "@/lib/entity-context";
import {
  autoMatch,
  createReconciliation,
  listBankAccounts,
  listReconciliations,
  listStatements,
  type BankAccount,
  type BankStatement,
  type Reconciliation,
  type Workspace,
} from "@/lib/banking";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const money = (v: string | number) =>
  Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const today = () => new Date().toISOString().slice(0, 10);

export default function ReconcilePage() {
  const { selectedId, selectedEntity } = useEntity();
  const [banks, setBanks] = useState<BankAccount[]>([]);
  const [statements, setStatements] = useState<BankStatement[]>([]);
  const [recons, setRecons] = useState<Reconciliation[]>([]);
  const [bankAccount, setBankAccount] = useState("");
  const [statementId, setStatementId] = useState("");
  const [reconDate, setReconDate] = useState(today);
  const [currentReconId, setCurrentReconId] = useState<string | null>(null);
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!selectedId) return;
    let active = true;
    listBankAccounts(selectedId)
      .then((rows) => {
        if (active) setBanks(rows.filter((b) => b.is_active));
      })
      .catch(() => {
        if (active) setError("Couldn't load bank accounts.");
      });
    return () => {
      active = false;
    };
  }, [selectedId]);

  useEffect(() => {
    if (!bankAccount) return;
    let active = true;
    Promise.all([listStatements(bankAccount), listReconciliations(bankAccount)])
      .then(([st, rc]) => {
        if (!active) return;
        setStatements(st);
        setRecons(rc);
      })
      .catch(() => {
        if (active) setError("Couldn't load statements.");
      });
    return () => {
      active = false;
    };
  }, [bankAccount]);

  function pickStatement(value: string) {
    setStatementId(value);
    setCurrentReconId(null);
    setWorkspace(null);
  }

  async function reconcile() {
    if (!statementId) return setError("Select a statement.");
    setRunning(true);
    setError("");
    try {
      let rid = currentReconId ?? recons.find((r) => r.statement === statementId)?.id ?? null;
      if (!rid) {
        rid = (
          await createReconciliation({
            entity: selectedId!,
            bank_account: bankAccount,
            statement: statementId,
            recon_date: reconDate,
          })
        ).id;
      }
      setCurrentReconId(rid);
      setWorkspace(await autoMatch(rid, { date_window_days: 3 }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setRunning(false);
    }
  }

  const fieldClass =
    "h-9 rounded-md border border-border bg-background px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40";

  if (!selectedId) {
    return (
      <Card>
        <CardContent className="py-12 text-center text-sm text-muted-foreground">
          Pick an entity from the switcher above to reconcile a bank account.
        </CardContent>
      </Card>
    );
  }

  const totals = workspace?.totals;
  const reconciled = totals && Number(totals.difference) === 0 && totals.unmatched_count === 0;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Bank Reconciliation</h1>
          <p className="text-sm text-muted-foreground">
            {selectedEntity?.numeric_code} ·{" "}
            {selectedEntity?.trade_name || selectedEntity?.legal_name}
          </p>
        </div>
        <Link href="/banking/statements/new">
          <Button variant="outline" size="sm">
            <Plus className="h-4 w-4" />
            New statement
          </Button>
        </Link>
      </div>

      <Card>
        <CardContent className="grid grid-cols-1 items-end gap-4 py-5 sm:grid-cols-2 lg:grid-cols-4">
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium">Bank account</label>
            <select
              value={bankAccount}
              onChange={(e) => {
                const value = e.target.value;
                setBankAccount(value);
                pickStatement("");
                if (!value) {
                  setStatements([]);
                  setRecons([]);
                }
              }}
              className={fieldClass}
            >
              <option value="">Select…</option>
              {banks.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.code} · {b.name}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium">Statement</label>
            <select
              value={statementId}
              onChange={(e) => pickStatement(e.target.value)}
              className={fieldClass}
              disabled={!bankAccount}
            >
              <option value="">Select…</option>
              {statements.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.statement_date} · closing {money(s.closing_balance)}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium">Reconcile as of</label>
            <input
              type="date"
              value={reconDate}
              onChange={(e) => setReconDate(e.target.value)}
              className={fieldClass}
            />
          </div>
          <Button size="sm" onClick={reconcile} disabled={running || !statementId}>
            {running ? "Matching…" : "Run auto-match"}
          </Button>
        </CardContent>
      </Card>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {totals && (
        <>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <SummaryCard label="Statement balance" value={money(totals.statement_balance)} />
            <SummaryCard label="GL balance" value={money(totals.gl_balance)} />
            <SummaryCard
              label="Difference"
              value={money(totals.difference)}
              tone={Number(totals.difference) === 0 ? "good" : "warn"}
            />
            <SummaryCard
              label="Matched / Unmatched"
              value={`${totals.matched_count} / ${totals.unmatched_count}`}
            />
          </div>

          {reconciled && (
            <p className="rounded-md bg-emerald-500/10 px-3 py-2 text-sm text-emerald-700 dark:text-emerald-400">
              Fully matched and the balances agree. (Marking a reconciliation “complete” arrives in a
              later slice.)
            </p>
          )}

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <TableCard title={`Unmatched statement lines (${workspace!.unmatched_lines.length})`}>
              {workspace!.unmatched_lines.length === 0 ? (
                <Empty>All statement lines matched.</Empty>
              ) : (
                <table className="w-full text-sm">
                  <Head cols={["Date", "Description", "Deposit", "Withdrawal"]} />
                  <tbody>
                    {workspace!.unmatched_lines.map((l) => (
                      <tr key={l.id} className="border-b border-border/60 last:border-0">
                        <td className="whitespace-nowrap px-3 py-1.5">{l.txn_date}</td>
                        <td className="px-3 py-1.5 text-muted-foreground">
                          {l.description || l.reference || "—"}
                        </td>
                        <td className="px-3 py-1.5 text-right tabular-nums">
                          {Number(l.deposit) > 0 ? money(l.deposit) : "—"}
                        </td>
                        <td className="px-3 py-1.5 text-right tabular-nums">
                          {Number(l.withdrawal) > 0 ? money(l.withdrawal) : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </TableCard>

            <TableCard title={`Bank GL lines (${workspace!.gl_lines.length})`}>
              {workspace!.gl_lines.length === 0 ? (
                <Empty>No posted GL movement on this account.</Empty>
              ) : (
                <table className="w-full text-sm">
                  <Head cols={["Date", "Entry", "Debit", "Credit", ""]} />
                  <tbody>
                    {workspace!.gl_lines.map((l) => (
                      <tr key={l.id} className="border-b border-border/60 last:border-0">
                        <td className="whitespace-nowrap px-3 py-1.5">{l.entry_date}</td>
                        <td className="px-3 py-1.5 font-mono text-xs text-muted-foreground">
                          {l.entry_no}
                        </td>
                        <td className="px-3 py-1.5 text-right tabular-nums">
                          {Number(l.debit) > 0 ? money(l.debit) : "—"}
                        </td>
                        <td className="px-3 py-1.5 text-right tabular-nums">
                          {Number(l.credit) > 0 ? money(l.credit) : "—"}
                        </td>
                        <td className="px-3 py-1.5 text-center">
                          {l.is_matched ? (
                            <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                              matched
                            </span>
                          ) : (
                            <span className="text-xs text-muted-foreground">—</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </TableCard>
          </div>

          {workspace!.matched.length > 0 && (
            <TableCard title={`Matched (${workspace!.matched.length})`}>
              <table className="w-full text-sm">
                <Head cols={["Stmt date", "Statement line", "GL entry", "Amount", "Match"]} />
                <tbody>
                  {workspace!.matched.map((m) => (
                    <tr key={m.id} className="border-b border-border/60 last:border-0">
                      <td className="whitespace-nowrap px-3 py-1.5">{m.statement_line.txn_date}</td>
                      <td className="px-3 py-1.5 text-muted-foreground">
                        {m.statement_line.description || m.statement_line.reference || "—"}
                      </td>
                      <td className="px-3 py-1.5 font-mono text-xs text-muted-foreground">
                        {m.entry_no}
                      </td>
                      <td className="px-3 py-1.5 text-right tabular-nums">{money(m.amount)}</td>
                      <td className="px-3 py-1.5 text-center text-xs capitalize text-muted-foreground">
                        {m.match_type}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </TableCard>
          )}
        </>
      )}
    </div>
  );
}

function SummaryCard({ label, value, tone }: { label: string; value: string; tone?: "good" | "warn" }) {
  return (
    <Card>
      <CardContent className="py-4">
        <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
        <p
          className={cn(
            "text-lg font-semibold tabular-nums",
            tone === "good" && "text-emerald-600 dark:text-emerald-400",
            tone === "warn" && "text-amber-600 dark:text-amber-400",
          )}
        >
          {value}
        </p>
      </CardContent>
    </Card>
  );
}

function TableCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card>
      <CardContent className="p-0">
        <div className="border-b border-border px-4 py-2.5 text-sm font-medium">{title}</div>
        <div className="overflow-x-auto">{children}</div>
      </CardContent>
    </Card>
  );
}

function Head({ cols }: { cols: string[] }) {
  return (
    <thead className="text-left text-xs text-muted-foreground">
      <tr className="border-b border-border">
        {cols.map((c, i) => (
          <th
            key={i}
            className={cn("px-3 py-2 font-medium", (c === "Debit" || c === "Credit" || c === "Deposit" || c === "Withdrawal" || c === "Amount") && "text-right")}
          >
            {c}
          </th>
        ))}
      </tr>
    </thead>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return <p className="px-4 py-6 text-center text-sm text-muted-foreground">{children}</p>;
}
