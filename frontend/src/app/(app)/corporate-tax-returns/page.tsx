"use client";

import { useEffect, useState } from "react";
import { useEntity } from "@/lib/entity-context";
import {
  computeCorporateTaxReturn,
  createCorporateTaxReturn,
  fileCorporateTaxReturn,
  listCorporateTaxReturns,
  type CorporateTaxReturn,
} from "@/lib/tax";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const money = (v: string) =>
  Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const STATUS_STYLE: Record<CorporateTaxReturn["status"], string> = {
  draft: "bg-muted text-muted-foreground",
  computed: "bg-amber-500/10 text-amber-700 dark:text-amber-400",
  filed: "bg-primary/10 text-primary",
  paid: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
};

export default function CorporateTaxReturnsPage() {
  const { selectedId, selectedEntity } = useEntity();
  const [returns, setReturns] = useState<CorporateTaxReturn[]>([]);
  const [loadError, setLoadError] = useState("");
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState("");
  const [references, setReferences] = useState<Record<string, string>>({});

  const [form, setForm] = useState({
    fiscal_year: new Date().getFullYear().toString(),
    period_start: "",
    period_end: "",
    accounting_net_profit: "",
    adjustments: "0",
    small_business_relief: false,
  });
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    if (!selectedId) return;
    let active = true;
    listCorporateTaxReturns(selectedId)
      .then((rows) => {
        if (active) setReturns(rows);
      })
      .catch(() => {
        if (active) setLoadError("Couldn't load corporate tax returns.");
      });
    return () => {
      active = false;
    };
  }, [selectedId]);

  async function create() {
    if (!selectedId || !form.period_start || !form.period_end) {
      return setError("Pick a fiscal period.");
    }
    setCreating(true);
    setError("");
    try {
      const ret = await createCorporateTaxReturn({
        entity: selectedId,
        fiscal_year: Number(form.fiscal_year),
        period_start: form.period_start,
        period_end: form.period_end,
        accounting_net_profit: form.accounting_net_profit || "0",
        adjustments: form.adjustments || "0",
        small_business_relief: form.small_business_relief,
      });
      setReturns((prev) => [ret, ...prev]);
      setForm((p) => ({ ...p, period_start: "", period_end: "", accounting_net_profit: "" }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setCreating(false);
    }
  }

  async function compute(id: string) {
    setBusyId(id);
    setError("");
    try {
      const updated = await computeCorporateTaxReturn(id);
      setReturns((prev) => prev.map((r) => (r.id === id ? updated : r)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setBusyId("");
    }
  }

  async function file(id: string) {
    setBusyId(id);
    setError("");
    try {
      const updated = await fileCorporateTaxReturn(id, references[id] ?? "");
      setReturns((prev) => prev.map((r) => (r.id === id ? updated : r)));
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
          Pick an entity from the switcher above to manage Corporate Tax returns.
        </CardContent>
      </Card>
    );
  }
  if (loadError) return <p className="text-sm text-destructive">{loadError}</p>;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">Corporate Tax Returns</h1>
        <p className="text-sm text-muted-foreground">
          {selectedEntity?.numeric_code} ·{" "}
          {selectedEntity?.trade_name || selectedEntity?.legal_name} — filed per entity, separate
          TRN.
        </p>
      </div>

      <Card className="max-w-2xl">
        <CardContent className="flex flex-col gap-4 py-5">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
            <div className="flex flex-col gap-1.5">
              <Label>Fiscal year</Label>
              <Input
                type="number"
                value={form.fiscal_year}
                onChange={(e) => setForm((p) => ({ ...p, fiscal_year: e.target.value }))}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Period start</Label>
              <Input
                type="date"
                value={form.period_start}
                onChange={(e) => setForm((p) => ({ ...p, period_start: e.target.value }))}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Period end</Label>
              <Input
                type="date"
                value={form.period_end}
                onChange={(e) => setForm((p) => ({ ...p, period_end: e.target.value }))}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Accounting net profit</Label>
              <Input
                type="number"
                inputMode="decimal"
                value={form.accounting_net_profit}
                onChange={(e) => setForm((p) => ({ ...p, accounting_net_profit: e.target.value }))}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Adjustments</Label>
              <Input
                type="number"
                inputMode="decimal"
                value={form.adjustments}
                onChange={(e) => setForm((p) => ({ ...p, adjustments: e.target.value }))}
              />
            </div>
          </div>
          <label className="flex w-fit items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.small_business_relief}
              onChange={(e) =>
                setForm((p) => ({ ...p, small_business_relief: e.target.checked }))
              }
              className="h-4 w-4 rounded border-border"
            />
            Small Business Relief elected (zeroes the liability)
          </label>
          <div>
            <Button size="sm" onClick={create} disabled={creating}>
              {creating ? "Creating…" : "New return"}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          <table className="w-full text-sm">
            <thead className="border-b border-border text-left text-xs text-muted-foreground">
              <tr>
                <th className="px-4 py-2 font-medium">FY</th>
                <th className="px-4 py-2 text-right font-medium">Net profit</th>
                <th className="px-4 py-2 text-right font-medium">Taxable income</th>
                <th className="px-4 py-2 text-right font-medium">Tax payable</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 text-right font-medium" />
              </tr>
            </thead>
            <tbody>
              {returns.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">
                    No corporate tax returns yet.
                  </td>
                </tr>
              ) : (
                returns.map((r) => (
                  <tr key={r.id} className="border-b border-border/60 last:border-0">
                    <td className="px-4 py-2 font-medium">{r.fiscal_year}</td>
                    <td className="px-4 py-2 text-right tabular-nums">
                      {money(r.accounting_net_profit)}
                    </td>
                    <td className="px-4 py-2 text-right tabular-nums">
                      {money(r.taxable_income)}
                    </td>
                    <td className="px-4 py-2 text-right font-medium tabular-nums">
                      {money(r.tax_payable)}
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
                    <td className="px-4 py-2 text-right">
                      {r.status === "draft" && (
                        <Button size="sm" disabled={busyId === r.id} onClick={() => compute(r.id)}>
                          {busyId === r.id ? "Computing…" : "Compute"}
                        </Button>
                      )}
                      {r.status === "computed" && (
                        <div className="flex items-center justify-end gap-2">
                          <Input
                            placeholder="FTA reference"
                            className="h-8 w-36"
                            value={references[r.id] ?? ""}
                            onChange={(e) =>
                              setReferences((prev) => ({ ...prev, [r.id]: e.target.value }))
                            }
                          />
                          <Button size="sm" disabled={busyId === r.id} onClick={() => file(r.id)}>
                            {busyId === r.id ? "Filing…" : "File"}
                          </Button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </CardContent>
      </Card>

      <p className="text-xs text-muted-foreground">
        0% up to AED {selectedEntity ? "375,000" : "—"} taxable income, 9% above — statutory
        parameters stored per return so a future law change never rewrites filed history.
      </p>

      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  );
}
