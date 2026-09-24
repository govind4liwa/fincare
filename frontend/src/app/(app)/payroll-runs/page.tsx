"use client";

import { Fragment, useEffect, useState } from "react";
import { useEntity } from "@/lib/entity-context";
import { listBankAccounts, type BankAccount } from "@/lib/banking";
import { buildRun, createRun, listRuns, payRun, postRun, type Run } from "@/lib/payroll";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const fieldClass =
  "h-9 rounded-md border border-border bg-background px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40";

const money = (v: string) =>
  Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const STATUS_STYLE: Record<Run["status"], string> = {
  draft: "bg-muted text-muted-foreground",
  approved: "bg-amber-500/10 text-amber-700 dark:text-amber-400",
  posted: "bg-primary/10 text-primary",
  paid: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
};

export default function PayrollRunsPage() {
  const { selectedId, selectedEntity } = useEntity();
  const [runs, setRuns] = useState<Run[]>([]);
  const [banks, setBanks] = useState<BankAccount[]>([]);
  const [loadError, setLoadError] = useState("");
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState("");
  const [expanded, setExpanded] = useState("");
  const [bankChoice, setBankChoice] = useState<Record<string, string>>({});

  const [salaryMonth, setSalaryMonth] = useState("");
  const [runDate, setRunDate] = useState("");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    if (!selectedId) return;
    let active = true;
    Promise.all([listRuns(selectedId), listBankAccounts(selectedId)])
      .then(([r, b]) => {
        if (!active) return;
        setRuns(r);
        setBanks(b);
      })
      .catch(() => {
        if (active) setLoadError("Couldn't load payroll runs.");
      });
    return () => {
      active = false;
    };
  }, [selectedId]);

  async function create() {
    if (!selectedId || !salaryMonth || !runDate) return setError("Pick a salary month and run date.");
    setCreating(true);
    setError("");
    try {
      const run = await createRun({ entity: selectedId, salary_month: salaryMonth, run_date: runDate });
      setRuns((prev) => [run, ...prev]);
      setSalaryMonth("");
      setRunDate("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setCreating(false);
    }
  }

  async function build(id: string) {
    setBusyId(id);
    setError("");
    try {
      const updated = await buildRun(id);
      setRuns((prev) => prev.map((r) => (r.id === id ? updated : r)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setBusyId("");
    }
  }

  async function post(id: string) {
    setBusyId(id);
    setError("");
    try {
      const updated = await postRun(id);
      setRuns((prev) => prev.map((r) => (r.id === id ? updated : r)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setBusyId("");
    }
  }

  async function pay(id: string) {
    const bankAccount = bankChoice[id];
    if (!bankAccount) return setError("Pick a bank account to pay from.");
    setBusyId(id);
    setError("");
    try {
      const updated = await payRun(id, bankAccount);
      setRuns((prev) => prev.map((r) => (r.id === id ? updated : r)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setBusyId("");
    }
  }

  if (!selectedId) {
    return (
      <Card>
        <CardContent className="py-12 text-center text-sm text-muted-foreground">
          Pick an entity from the switcher above to run payroll.
        </CardContent>
      </Card>
    );
  }
  if (loadError) return <p className="text-sm text-destructive">{loadError}</p>;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">Payroll Runs</h1>
        <p className="text-sm text-muted-foreground">
          {selectedEntity?.numeric_code} ·{" "}
          {selectedEntity?.trade_name || selectedEntity?.legal_name}
        </p>
      </div>

      <Card className="max-w-xl">
        <CardContent className="flex flex-wrap items-end gap-3 py-5">
          <div className="flex flex-col gap-1.5">
            <Label>Salary month</Label>
            <Input
              type="month"
              value={salaryMonth}
              onChange={(e) => setSalaryMonth(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Run date</Label>
            <Input type="date" value={runDate} onChange={(e) => setRunDate(e.target.value)} />
          </div>
          <Button size="sm" onClick={create} disabled={creating}>
            {creating ? "Creating…" : "New run"}
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          <table className="w-full text-sm">
            <thead className="border-b border-border text-left text-xs text-muted-foreground">
              <tr>
                <th className="px-4 py-2 font-medium">Month</th>
                <th className="px-4 py-2 text-right font-medium">Gross</th>
                <th className="px-4 py-2 text-right font-medium">Deductions</th>
                <th className="px-4 py-2 text-right font-medium">Net</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 text-right font-medium" />
              </tr>
            </thead>
            <tbody>
              {runs.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">
                    No payroll runs yet.
                  </td>
                </tr>
              ) : (
                runs.map((r) => (
                  <Fragment key={r.id}>
                    <tr
                      className="cursor-pointer border-b border-border/60 last:border-0 hover:bg-accent/30"
                      onClick={() => setExpanded(expanded === r.id ? "" : r.id)}
                    >
                      <td className="px-4 py-2 font-medium">{r.salary_month}</td>
                      <td className="px-4 py-2 text-right tabular-nums">{money(r.gross_total)}</td>
                      <td className="px-4 py-2 text-right tabular-nums">
                        {money(r.deduction_total)}
                      </td>
                      <td className="px-4 py-2 text-right font-medium tabular-nums">
                        {money(r.net_total)}
                      </td>
                      <td className="px-4 py-2">
                        <span
                          className={cn(
                            "rounded-full px-2 py-0.5 text-xs font-medium capitalize",
                            STATUS_STYLE[r.status],
                          )}
                        >
                          {r.status}
                        </span>
                      </td>
                      <td className="px-4 py-2 text-right" onClick={(e) => e.stopPropagation()}>
                        {r.status === "draft" && (
                          <Button size="sm" disabled={busyId === r.id} onClick={() => build(r.id)}>
                            {busyId === r.id ? "Building…" : r.payslips.length ? "Rebuild" : "Build"}
                          </Button>
                        )}
                        {r.status === "draft" && r.payslips.length > 0 && (
                          <Button
                            size="sm"
                            className="ml-2"
                            disabled={busyId === r.id}
                            onClick={() => post(r.id)}
                          >
                            {busyId === r.id ? "Posting…" : "Post"}
                          </Button>
                        )}
                        {r.status === "posted" && (
                          <div className="flex items-center justify-end gap-2">
                            <select
                              value={bankChoice[r.id] ?? ""}
                              onChange={(e) =>
                                setBankChoice((prev) => ({ ...prev, [r.id]: e.target.value }))
                              }
                              className={cn(fieldClass, "h-8")}
                            >
                              <option value="">Bank…</option>
                              {banks.map((b) => (
                                <option key={b.id} value={b.id}>
                                  {b.code}
                                </option>
                              ))}
                            </select>
                            <Button size="sm" disabled={busyId === r.id} onClick={() => pay(r.id)}>
                              {busyId === r.id ? "Paying…" : "Pay"}
                            </Button>
                          </div>
                        )}
                      </td>
                    </tr>
                    {expanded === r.id && r.payslips.length > 0 && (
                      <tr className="border-b border-border/60 bg-muted/30">
                        <td colSpan={6} className="px-4 py-3">
                          <table className="w-full text-xs">
                            <thead className="text-muted-foreground">
                              <tr>
                                <th className="py-1 text-left font-medium">Employee</th>
                                <th className="py-1 text-right font-medium">Gross</th>
                                <th className="py-1 text-right font-medium">Deductions</th>
                                <th className="py-1 text-right font-medium">Advance recovery</th>
                                <th className="py-1 text-right font-medium">Net pay</th>
                              </tr>
                            </thead>
                            <tbody>
                              {r.payslips.map((p) => (
                                <tr key={p.id}>
                                  <td className="py-1">
                                    {p.employee_code} · {p.employee_name}
                                  </td>
                                  <td className="py-1 text-right tabular-nums">
                                    {money(p.gross_earnings)}
                                  </td>
                                  <td className="py-1 text-right tabular-nums">
                                    {money(p.total_deductions)}
                                  </td>
                                  <td className="py-1 text-right tabular-nums">
                                    {money(p.advance_recovery)}
                                  </td>
                                  <td className="py-1 text-right font-medium tabular-nums">
                                    {money(p.net_pay)}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))
              )}
            </tbody>
          </table>
        </CardContent>
      </Card>

      <p className="text-xs text-muted-foreground">
        Build derives payslips from each employee&apos;s current salary structure (and recovers
        any open advances). Post books the accrual entry; Pay books a separate payment entry once
        posted. Click a run to see its payslip breakdown.
      </p>

      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  );
}
