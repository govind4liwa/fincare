"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Check, Lock, RefreshCw, Trash2 } from "lucide-react";
import { useEntity } from "@/lib/entity-context";
import { listBankAccounts, type BankAccount } from "@/lib/banking";
import {
  approveSchedule,
  discardSchedule,
  generateSchedule,
  getLoan,
  listSchedules,
  postInstallment,
  type LoanSchedule,
  type VehicleLoan,
} from "@/lib/loans";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const money = (v: string) =>
  Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

// Rates are stored at 6 dp (monthly effective rates need it) but read better
// trimmed: "4.503853" stays, "6.500000" shows as "6.5".
const rate = (v: string) => String(Number(v));

const METHOD_LABEL: Record<string, string> = {
  reducing_balance: "Reducing balance",
  flat_rate: "Flat rate",
  flat_quoted_effective: "Flat quoted / effective split",
};

const STATUS_STYLE: Record<string, string> = {
  draft: "bg-muted text-muted-foreground",
  approved: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
  superseded: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
};

export default function LoanDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { selectedId } = useEntity();
  const [loan, setLoan] = useState<VehicleLoan | null>(null);
  const [schedules, setSchedules] = useState<LoanSchedule[]>([]);
  const [banks, setBanks] = useState<BankAccount[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [bankAccount, setBankAccount] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [loadError, setLoadError] = useState("");

  const reload = useCallback(async () => {
    const [l, s] = await Promise.all([getLoan(id), listSchedules(id)]);
    setLoan(l);
    setSchedules(s);
    setActiveId((current) => current ?? s[0]?.id ?? null);
    return s;
  }, [id]);

  useEffect(() => {
    let active = true;
    Promise.all([getLoan(id), listSchedules(id)])
      .then(([l, s]) => {
        if (!active) return;
        setLoan(l);
        setSchedules(s);
        setActiveId(s[0]?.id ?? null);
      })
      .catch(() => {
        if (active) setLoadError("Couldn't load this loan.");
      });
    return () => {
      active = false;
    };
  }, [id]);

  useEffect(() => {
    if (!selectedId) return;
    let active = true;
    listBankAccounts(selectedId)
      .then((rows) => {
        if (active) setBanks(rows.filter((b) => b.is_active));
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [selectedId]);

  async function run(fn: () => Promise<unknown>, after?: (s: LoanSchedule[]) => void) {
    setBusy(true);
    setError("");
    try {
      await fn();
      const s = await reload();
      after?.(s);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  if (loadError) return <p className="text-sm text-destructive">{loadError}</p>;
  if (!loan) return <p className="text-sm text-muted-foreground">Loading…</p>;

  const active = schedules.find((s) => s.id === activeId) ?? null;
  const fieldClass =
    "h-9 rounded-md border border-border bg-background px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40";

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">
            Loan · {loan.vehicle_code}{" "}
            <span className="text-base font-normal text-muted-foreground">{loan.lender}</span>
          </h1>
          <p className="text-sm text-muted-foreground">
            {money(loan.principal)} over {loan.term_months} months ·{" "}
            {METHOD_LABEL[loan.amortization_method] ?? loan.amortization_method} @{" "}
            {rate(loan.annual_interest_rate)}%
            {loan.quoted_flat_rate ? ` (quoted flat ${rate(loan.quoted_flat_rate)}%)` : ""}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link href="/loans">
            <Button variant="ghost" size="sm">
              Back
            </Button>
          </Link>
          <Button size="sm" onClick={() => run(() => generateSchedule(id))} disabled={busy}>
            <RefreshCw className="h-4 w-4" />
            {schedules.length ? "Regenerate (new version)" : "Generate schedule"}
          </Button>
        </div>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {schedules.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-sm text-muted-foreground">
            No schedule yet. Generate one — it starts as a draft, and must be approved before any
            EMI can be posted.
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="flex flex-wrap gap-2">
            {schedules.map((s) => (
              <button
                key={s.id}
                onClick={() => setActiveId(s.id)}
                className={cn(
                  "rounded-md border px-3 py-1.5 text-sm transition-colors",
                  s.id === activeId
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-border text-muted-foreground hover:bg-accent",
                )}
              >
                v{s.version_no}
                <span
                  className={cn(
                    "ml-2 rounded-full px-1.5 py-0.5 text-[10px] font-medium capitalize",
                    STATUS_STYLE[s.status],
                  )}
                >
                  {s.status}
                </span>
              </button>
            ))}
          </div>

          {active && (
            <>
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                <Summary label="Opening principal" value={money(active.opening_principal)} />
                <Summary label="Total interest" value={money(active.total_interest)} />
                <Summary label="Total payments" value={money(active.total_payments)} />
                <Summary
                  label="Posted"
                  value={`${active.posted_count} / ${active.installments.length}`}
                />
              </div>

              <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-border bg-card px-4 py-3 text-sm">
                <span className="text-muted-foreground">
                  {active.status === "draft"
                    ? "Draft — approve to lock this version and enable posting."
                    : active.status === "approved"
                      ? "Approved and locked. EMIs post from this version."
                      : "Superseded by a newer version."}
                </span>
                {active.status === "draft" && (
                  <div className="flex items-center gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() =>
                        run(() => discardSchedule(active.id), () => setActiveId(null))
                      }
                      disabled={busy}
                    >
                      <Trash2 className="h-4 w-4" /> Discard
                    </Button>
                    <Button
                      size="sm"
                      onClick={() => run(() => approveSchedule(active.id))}
                      disabled={busy}
                    >
                      <Check className="h-4 w-4" /> Approve &amp; lock
                    </Button>
                  </div>
                )}
                {active.status === "approved" && (
                  <div className="flex items-center gap-2">
                    <Lock className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
                    <select
                      value={bankAccount}
                      onChange={(e) => setBankAccount(e.target.value)}
                      className={fieldClass}
                    >
                      <option value="">Pay from…</option>
                      {banks.map((b) => (
                        <option key={b.id} value={b.id}>
                          {b.code} · {b.name}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
              </div>

              <Card>
                <CardContent className="p-0">
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="border-b border-border text-left text-xs text-muted-foreground">
                        <tr>
                          <th className="px-3 py-2 font-medium">#</th>
                          <th className="px-3 py-2 font-medium">Due</th>
                          <th className="px-3 py-2 text-right font-medium">Opening</th>
                          <th className="px-3 py-2 text-right font-medium">Principal</th>
                          <th className="px-3 py-2 text-right font-medium">Interest</th>
                          <th className="px-3 py-2 text-right font-medium">EMI</th>
                          <th className="px-3 py-2 text-right font-medium">Closing</th>
                          <th className="px-3 py-2 text-center font-medium">Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {active.installments.map((i) => (
                          <tr key={i.id} className="border-b border-border/60 last:border-0">
                            <td className="px-3 py-1.5 text-muted-foreground">
                              {i.installment_no}
                            </td>
                            <td className="whitespace-nowrap px-3 py-1.5">{i.due_date}</td>
                            <td className="px-3 py-1.5 text-right tabular-nums text-muted-foreground">
                              {money(i.opening_balance)}
                            </td>
                            <td className="px-3 py-1.5 text-right tabular-nums">
                              {money(i.principal_component)}
                            </td>
                            <td className="px-3 py-1.5 text-right tabular-nums">
                              {money(i.interest_component)}
                            </td>
                            <td className="px-3 py-1.5 text-right font-medium tabular-nums">
                              {money(i.total_amount)}
                            </td>
                            <td className="px-3 py-1.5 text-right tabular-nums text-muted-foreground">
                              {money(i.closing_balance)}
                            </td>
                            <td className="px-3 py-1.5 text-center">
                              {i.status === "posted" ? (
                                <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                                  posted
                                </span>
                              ) : active.status === "approved" ? (
                                <button
                                  type="button"
                                  disabled={busy || !bankAccount}
                                  onClick={() => run(() => postInstallment(i.id, bankAccount))}
                                  className="text-xs font-medium text-primary hover:underline disabled:text-muted-foreground disabled:no-underline"
                                  title={bankAccount ? "" : "Choose a bank account first"}
                                >
                                  Post
                                </button>
                              ) : (
                                <span className="text-xs text-muted-foreground">—</span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </CardContent>
              </Card>
            </>
          )}
        </>
      )}
    </div>
  );
}

function Summary({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <CardContent className="py-4">
        <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
        <p className="text-lg font-semibold tabular-nums">{value}</p>
      </CardContent>
    </Card>
  );
}
