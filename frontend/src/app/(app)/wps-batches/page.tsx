"use client";

import { Fragment, useEffect, useState } from "react";
import { useEntity } from "@/lib/entity-context";
import {
  downloadSifExport,
  generateWpsBatch,
  listRuns,
  listWpsBatches,
  type Run,
  type WpsBatch,
} from "@/lib/payroll";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";

const fieldClass =
  "h-9 rounded-md border border-border bg-background px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40";

const money = (v: string) =>
  Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function WpsBatchesPage() {
  const { selectedId, selectedEntity } = useEntity();
  const [runs, setRuns] = useState<Run[]>([]);
  const [batches, setBatches] = useState<WpsBatch[]>([]);
  const [loadError, setLoadError] = useState("");
  const [error, setError] = useState("");
  const [expanded, setExpanded] = useState("");
  const [exportingId, setExportingId] = useState("");

  const [form, setForm] = useState({ run: "", employer_eid: "", employer_bank_routing: "" });
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    if (!selectedId) return;
    let active = true;
    Promise.all([listRuns(selectedId), listWpsBatches()])
      .then(([r, b]) => {
        if (!active) return;
        setRuns(r);
        setBatches(b.filter((batch) => r.some((run) => run.id === batch.run)));
      })
      .catch(() => {
        if (active) setLoadError("Couldn't load WPS batches.");
      });
    return () => {
      active = false;
    };
  }, [selectedId]);

  const eligibleRuns = runs.filter((r) => r.status === "posted" || r.status === "paid");

  async function create() {
    if (!form.run || !form.employer_eid || !form.employer_bank_routing) {
      return setError("Run, employer EID, and employer bank routing are required.");
    }
    setCreating(true);
    setError("");
    try {
      const batch = await generateWpsBatch(form);
      setBatches((prev) => [batch, ...prev]);
      setForm((p) => ({ ...p, run: "" }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setCreating(false);
    }
  }

  async function exportSif(batch: WpsBatch) {
    setExportingId(batch.id);
    setError("");
    try {
      await downloadSifExport(batch);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setExportingId("");
    }
  }

  if (!selectedId) {
    return (
      <Card>
        <CardContent className="py-12 text-center text-sm text-muted-foreground">
          Pick an entity from the switcher above to manage WPS batches.
        </CardContent>
      </Card>
    );
  }
  if (loadError) return <p className="text-sm text-destructive">{loadError}</p>;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">WPS / SIF Export</h1>
        <p className="text-sm text-muted-foreground">
          {selectedEntity?.numeric_code} ·{" "}
          {selectedEntity?.trade_name || selectedEntity?.legal_name} — generate a Wage
          Protection System batch from a posted run, then export its SIF file for the bank.
        </p>
      </div>

      <Card className="max-w-2xl">
        <CardContent className="flex flex-col gap-4 py-5">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div className="flex flex-col gap-1.5 sm:col-span-2">
              <Label>Payroll run</Label>
              <select
                value={form.run}
                onChange={(e) => setForm((p) => ({ ...p, run: e.target.value }))}
                className={fieldClass}
              >
                <option value="">Select…</option>
                {eligibleRuns.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.salary_month} · {r.status}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Employer EID</Label>
              <Input
                value={form.employer_eid}
                onChange={(e) => setForm((p) => ({ ...p, employer_eid: e.target.value }))}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Employer bank routing</Label>
              <Input
                value={form.employer_bank_routing}
                onChange={(e) =>
                  setForm((p) => ({ ...p, employer_bank_routing: e.target.value }))
                }
              />
            </div>
          </div>
          <div>
            <Button size="sm" onClick={create} disabled={creating}>
              {creating ? "Generating…" : "Generate batch"}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          <table className="w-full text-sm">
            <thead className="border-b border-border text-left text-xs text-muted-foreground">
              <tr>
                <th className="px-4 py-2 font-medium">Salary month</th>
                <th className="px-4 py-2 font-medium">Employer EID</th>
                <th className="px-4 py-2 text-right font-medium">Records</th>
                <th className="px-4 py-2 text-right font-medium">Total salary</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 text-right font-medium" />
              </tr>
            </thead>
            <tbody>
              {batches.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">
                    No WPS batches yet.
                  </td>
                </tr>
              ) : (
                batches.map((b) => (
                  <Fragment key={b.id}>
                    <tr
                      className="cursor-pointer border-b border-border/60 last:border-0 hover:bg-accent/30"
                      onClick={() => setExpanded(expanded === b.id ? "" : b.id)}
                    >
                      <td className="px-4 py-2 font-medium">{b.salary_month}</td>
                      <td className="px-4 py-2 text-muted-foreground">{b.employer_eid}</td>
                      <td className="px-4 py-2 text-right tabular-nums">{b.total_records}</td>
                      <td className="px-4 py-2 text-right font-medium tabular-nums">
                        {money(b.total_salary)}
                      </td>
                      <td className="px-4 py-2">
                        <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium capitalize text-primary">
                          {b.status}
                        </span>
                      </td>
                      <td className="px-4 py-2 text-right" onClick={(e) => e.stopPropagation()}>
                        <Button
                          size="sm"
                          disabled={exportingId === b.id}
                          onClick={() => exportSif(b)}
                        >
                          {exportingId === b.id ? "Exporting…" : "Export SIF"}
                        </Button>
                      </td>
                    </tr>
                    {expanded === b.id && b.records.length > 0 && (
                      <tr className="border-b border-border/60 bg-muted/30">
                        <td colSpan={6} className="px-4 py-3">
                          <table className="w-full text-xs">
                            <thead className="text-muted-foreground">
                              <tr>
                                <th className="py-1 text-left font-medium">Employee</th>
                                <th className="py-1 text-left font-medium">IBAN</th>
                                <th className="py-1 text-right font-medium">Fixed</th>
                                <th className="py-1 text-right font-medium">Variable</th>
                              </tr>
                            </thead>
                            <tbody>
                              {b.records.map((r) => (
                                <tr key={r.id}>
                                  <td className="py-1">
                                    {r.employee_code} · {r.employee_name}
                                  </td>
                                  <td className="py-1">{r.iban}</td>
                                  <td className="py-1 text-right tabular-nums">
                                    {money(r.fixed_amount)}
                                  </td>
                                  <td className="py-1 text-right tabular-nums">
                                    {money(r.variable_amount)}
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
        A batch totals must reconcile to its records before export is allowed. Click a batch to
        see its employee-level breakdown.
      </p>

      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  );
}
