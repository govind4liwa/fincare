"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Plus, Undo2 } from "lucide-react";
import { useEntity } from "@/lib/entity-context";
import {
  listClearings,
  reverseClearing,
  type DriverClearing,
} from "@/lib/settlements";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const money = (v: string) =>
  Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const STATUS_STYLE: Record<string, string> = {
  draft: "bg-muted text-muted-foreground",
  posted: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
  reversed: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
  cancelled: "bg-muted text-muted-foreground",
};

export default function DriverClearingsPage() {
  const { selectedId, selectedEntity } = useEntity();
  const [rows, setRows] = useState<DriverClearing[]>([]);
  const [loaded, setLoaded] = useState<string | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(
    (entityId: string) =>
      listClearings(entityId)
        .then((data) => {
          setRows(data);
          setLoaded(entityId);
        })
        .catch(() => setError("Couldn't load driver clearings.")),
    [],
  );

  useEffect(() => {
    if (!selectedId) return;
    let active = true;
    listClearings(selectedId)
      .then((data) => {
        if (!active) return;
        setRows(data);
        setLoaded(selectedId);
      })
      .catch(() => {
        if (active) setError("Couldn't load driver clearings.");
      });
    return () => {
      active = false;
    };
  }, [selectedId]);

  async function reverse(row: DriverClearing) {
    setError("");
    setBusy(row.id);
    try {
      await reverseClearing(row.id);
      if (selectedId) await load(selectedId);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not reverse this clearing.");
    } finally {
      setBusy("");
    }
  }

  if (!selectedId) {
    return (
      <Card>
        <CardContent className="py-12 text-center text-sm text-muted-foreground">
          Pick an entity from the switcher above to see driver clearings.
        </CardContent>
      </Card>
    );
  }

  const loading = loaded !== selectedId && !error;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Driver Clearings</h1>
          <p className="text-sm text-muted-foreground">
            Settling what drivers owe — {selectedEntity?.legal_name ?? "this entity"}.
          </p>
        </div>
        <Link href="/driver-clearings/new">
          <Button size="sm">
            <Plus className="mr-1.5 h-4 w-4" />
            New clearing
          </Button>
        </Link>
      </div>

      <Card>
        <CardContent className="p-0">
          {loading ? (
            <p className="p-6 text-sm text-muted-foreground">Loading…</p>
          ) : rows.length === 0 ? (
            <p className="p-6 text-sm text-muted-foreground">
              No clearings yet. When a settlement&rsquo;s deductions exceed the driver&rsquo;s
              earnings, the shortfall stays outstanding until it is collected or written off here.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b border-border text-left text-muted-foreground">
                  <tr>
                    <th className="px-4 py-2 font-medium">Date</th>
                    <th className="px-4 py-2 font-medium">No.</th>
                    <th className="px-4 py-2 font-medium">Driver</th>
                    <th className="px-4 py-2 font-medium">Kind</th>
                    <th className="px-4 py-2 text-right font-medium">Amount</th>
                    <th className="px-4 py-2 font-medium">Applied to</th>
                    <th className="px-4 py-2 font-medium">Status</th>
                    <th className="px-4 py-2" />
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.id} className="border-b border-border last:border-0">
                      <td className="px-4 py-2 tabular-nums">{row.clearing_date}</td>
                      <td className="px-4 py-2 tabular-nums">
                        {row.clearing_no || <span className="text-muted-foreground">(draft)</span>}
                      </td>
                      <td className="px-4 py-2">
                        {row.driver_code} {row.driver_name}
                      </td>
                      <td className="px-4 py-2">{row.kind_display}</td>
                      <td className="px-4 py-2 text-right tabular-nums">{money(row.amount)}</td>
                      <td className="px-4 py-2 text-muted-foreground">
                        {row.lines.map((l) => l.settlement_no).filter(Boolean).join(", ") || "—"}
                      </td>
                      <td className="px-4 py-2">
                        <span
                          className={cn(
                            "rounded-full px-2 py-0.5 text-xs font-medium capitalize",
                            STATUS_STYLE[row.status] ?? STATUS_STYLE.draft,
                          )}
                        >
                          {row.status}
                        </span>
                      </td>
                      <td className="px-4 py-2 text-right">
                        {row.status === "posted" && (
                          <Button
                            variant="ghost"
                            size="sm"
                            disabled={busy === row.id}
                            onClick={() => reverse(row)}
                            title="Reverse this clearing and put the receivable back"
                          >
                            <Undo2 className="mr-1.5 h-3.5 w-3.5" />
                            {busy === row.id ? "Reversing…" : "Reverse"}
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  );
}
