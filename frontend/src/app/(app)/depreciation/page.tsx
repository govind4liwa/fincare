"use client";

import { useEffect, useState } from "react";
import { useEntity } from "@/lib/entity-context";
import {
  createDepreciationRun,
  listDepreciationRuns,
  postDepreciationRun,
  type DepreciationRun,
} from "@/lib/fleet";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const money = (v: string) =>
  Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const STATUS_STYLE: Record<DepreciationRun["status"], string> = {
  draft: "bg-muted text-muted-foreground",
  posted: "bg-primary/10 text-primary",
  reversed: "bg-destructive/10 text-destructive",
  cancelled: "bg-destructive/10 text-destructive",
};

export default function DepreciationPage() {
  const { selectedId, selectedEntity } = useEntity();
  const [runs, setRuns] = useState<DepreciationRun[]>([]);
  const [loadError, setLoadError] = useState("");
  const [runDate, setRunDate] = useState("");
  const [periodLabel, setPeriodLabel] = useState("");
  const [creating, setCreating] = useState(false);
  const [postingId, setPostingId] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!selectedId) return;
    let active = true;
    listDepreciationRuns(selectedId)
      .then((rows) => {
        if (active) setRuns(rows);
      })
      .catch(() => {
        if (active) setLoadError("Couldn't load depreciation runs.");
      });
    return () => {
      active = false;
    };
  }, [selectedId]);

  async function create() {
    if (!selectedId || !runDate) return setError("Pick a run date.");
    setCreating(true);
    setError("");
    try {
      const run = await createDepreciationRun({
        entity: selectedId,
        run_date: runDate,
        period_label: periodLabel,
      });
      setRuns((prev) => [run, ...prev]);
      setRunDate("");
      setPeriodLabel("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setCreating(false);
    }
  }

  async function post(id: string) {
    setPostingId(id);
    setError("");
    try {
      const updated = await postDepreciationRun(id);
      setRuns((prev) => prev.map((r) => (r.id === id ? updated : r)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setPostingId("");
    }
  }

  if (!selectedId) {
    return (
      <Card>
        <CardContent className="py-12 text-center text-sm text-muted-foreground">
          Pick an entity from the switcher above to run vehicle depreciation.
        </CardContent>
      </Card>
    );
  }
  if (loadError) return <p className="text-sm text-destructive">{loadError}</p>;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">Vehicle Depreciation</h1>
        <p className="text-sm text-muted-foreground">
          {selectedEntity?.numeric_code} ·{" "}
          {selectedEntity?.trade_name || selectedEntity?.legal_name}
        </p>
      </div>

      <Card className="max-w-2xl">
        <CardContent className="flex flex-wrap items-end gap-3 py-5">
          <div className="flex flex-col gap-1.5">
            <Label>Run date</Label>
            <Input type="date" value={runDate} onChange={(e) => setRunDate(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Period label</Label>
            <Input
              placeholder="Jun-2026"
              value={periodLabel}
              onChange={(e) => setPeriodLabel(e.target.value)}
            />
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
                <th className="px-4 py-2 font-medium">Run</th>
                <th className="px-4 py-2 font-medium">Date</th>
                <th className="px-4 py-2 font-medium">Period</th>
                <th className="px-4 py-2 text-right font-medium">Vehicles</th>
                <th className="px-4 py-2 text-right font-medium">Total</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 text-right font-medium" />
              </tr>
            </thead>
            <tbody>
              {runs.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">
                    No depreciation runs for this entity yet.
                  </td>
                </tr>
              ) : (
                runs.map((r) => (
                  <tr key={r.id} className="border-b border-border/60 last:border-0">
                    <td className="px-4 py-2 font-mono text-xs">{r.run_no || "(draft)"}</td>
                    <td className="px-4 py-2 text-muted-foreground">{r.run_date}</td>
                    <td className="px-4 py-2">{r.period_label || "—"}</td>
                    <td className="px-4 py-2 text-right tabular-nums">{r.lines.length}</td>
                    <td className="px-4 py-2 text-right tabular-nums">{money(r.total_amount)}</td>
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
                        <Button
                          size="sm"
                          disabled={postingId === r.id}
                          onClick={() => post(r.id)}
                        >
                          {postingId === r.id ? "Posting…" : "Post"}
                        </Button>
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
        Posting builds one line per active vehicle with depreciation configured (straight-line,
        acquisition cost less residual over its useful life) and posts a single balanced entry —
        DR Depreciation Expense / CR Accumulated Depreciation, carrying the vehicle dimension.
      </p>

      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  );
}
