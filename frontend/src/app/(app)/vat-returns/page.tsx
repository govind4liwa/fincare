"use client";

import { Fragment, useEffect, useState } from "react";
import { useEntity } from "@/lib/entity-context";
import {
  computeVatReturn,
  createVatReturn,
  fileVatReturn,
  listVatReturns,
  type VatReturn,
} from "@/lib/tax";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const money = (v: string) =>
  Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const STATUS_STYLE: Record<VatReturn["status"], string> = {
  draft: "bg-muted text-muted-foreground",
  computed: "bg-amber-500/10 text-amber-700 dark:text-amber-400",
  filed: "bg-primary/10 text-primary",
  paid: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
};

export default function VatReturnsPage() {
  const { selectedId, selectedEntity } = useEntity();
  const [returns, setReturns] = useState<VatReturn[]>([]);
  const [loadError, setLoadError] = useState("");
  const [periodStart, setPeriodStart] = useState("");
  const [periodEnd, setPeriodEnd] = useState("");
  const [creating, setCreating] = useState(false);
  const [busyId, setBusyId] = useState("");
  const [references, setReferences] = useState<Record<string, string>>({});
  const [expanded, setExpanded] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!selectedId) return;
    let active = true;
    listVatReturns(selectedId)
      .then((rows) => {
        if (active) setReturns(rows);
      })
      .catch(() => {
        if (active) setLoadError("Couldn't load VAT returns.");
      });
    return () => {
      active = false;
    };
  }, [selectedId]);

  const vatGroup = selectedEntity?.vat_group ?? null;

  async function create() {
    if (!selectedId || !periodStart || !periodEnd) return setError("Pick a period.");
    setCreating(true);
    setError("");
    try {
      const ret = await createVatReturn({
        vat_group: vatGroup?.id ?? null,
        entity: vatGroup ? null : selectedId,
        period_start: periodStart,
        period_end: periodEnd,
      });
      setReturns((prev) => [ret, ...prev]);
      setPeriodStart("");
      setPeriodEnd("");
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
      const updated = await computeVatReturn(id);
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
      const updated = await fileVatReturn(id, references[id] ?? "");
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
          Pick an entity from the switcher above to manage VAT 201 returns.
        </CardContent>
      </Card>
    );
  }
  if (loadError) return <p className="text-sm text-destructive">{loadError}</p>;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">VAT 201 Returns</h1>
        <p className="text-sm text-muted-foreground">
          {vatGroup
            ? `Filing as part of ${vatGroup.name} (TRN ${vatGroup.trn}) — aggregates all member entities`
            : `Standalone filing for ${selectedEntity?.legal_name ?? "this entity"}`}
        </p>
      </div>

      <Card className="max-w-xl">
        <CardContent className="flex flex-wrap items-end gap-3 py-5">
          <div className="flex flex-col gap-1.5">
            <Label>Period start</Label>
            <Input type="date" value={periodStart} onChange={(e) => setPeriodStart(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Period end</Label>
            <Input type="date" value={periodEnd} onChange={(e) => setPeriodEnd(e.target.value)} />
          </div>
          <Button size="sm" onClick={create} disabled={creating}>
            {creating ? "Creating…" : "New return"}
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          <table className="w-full text-sm">
            <thead className="border-b border-border text-left text-xs text-muted-foreground">
              <tr>
                <th className="px-4 py-2 font-medium">Period</th>
                <th className="px-4 py-2 text-right font-medium">Output VAT</th>
                <th className="px-4 py-2 text-right font-medium">Input VAT</th>
                <th className="px-4 py-2 text-right font-medium">Net payable</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 text-right font-medium" />
              </tr>
            </thead>
            <tbody>
              {returns.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">
                    No VAT returns yet.
                  </td>
                </tr>
              ) : (
                returns.map((r) => (
                  <Fragment key={r.id}>
                    <tr
                      className="cursor-pointer border-b border-border/60 last:border-0 hover:bg-accent/30"
                      onClick={() => setExpanded(expanded === r.id ? "" : r.id)}
                    >
                      <td className="px-4 py-2 text-muted-foreground">
                        {r.period_start} – {r.period_end}
                      </td>
                      <td className="px-4 py-2 text-right tabular-nums">
                        {money(r.total_output_vat)}
                      </td>
                      <td className="px-4 py-2 text-right tabular-nums">
                        {money(r.total_input_vat)}
                      </td>
                      <td className="px-4 py-2 text-right font-medium tabular-nums">
                        {money(r.net_vat_payable)}
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
                    {expanded === r.id && r.boxes.length > 0 && (
                      <tr className="border-b border-border/60 bg-muted/30">
                        <td colSpan={6} className="px-4 py-3">
                          <table className="w-full text-xs">
                            <thead className="text-muted-foreground">
                              <tr>
                                <th className="py-1 text-left font-medium">Box</th>
                                <th className="py-1 text-left font-medium">Label</th>
                                <th className="py-1 text-right font-medium">Amount</th>
                                <th className="py-1 text-right font-medium">VAT</th>
                              </tr>
                            </thead>
                            <tbody>
                              {r.boxes.map((b) => (
                                <tr key={b.id}>
                                  <td className="py-1 font-mono">{b.box_code}</td>
                                  <td className="py-1">{b.label}</td>
                                  <td className="py-1 text-right tabular-nums">{money(b.amount)}</td>
                                  <td className="py-1 text-right tabular-nums">
                                    {money(b.vat_amount)}
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
        Output/input VAT are read straight from the GL&apos;s VAT control accounts for posted
        entries in the period — the return always ties to the ledger. Click a row to see the box
        breakdown.
      </p>

      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  );
}
