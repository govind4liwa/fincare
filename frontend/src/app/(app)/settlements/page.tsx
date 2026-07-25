"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Plus } from "lucide-react";
import { useEntity } from "@/lib/entity-context";
import { listSettlements, postSettlement, type Settlement } from "@/lib/settlements";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const money = (v: string) =>
  Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const STATUS_STYLE: Record<string, string> = {
  draft: "bg-muted text-muted-foreground",
  posted: "bg-primary/10 text-primary",
  reversed: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
  cancelled: "bg-red-500/10 text-red-600 dark:text-red-400",
};

export default function SettlementsPage() {
  const { selectedId, selectedEntity } = useEntity();
  const [rows, setRows] = useState<Settlement[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(
    () =>
      listSettlements(selectedId).then((data) => {
        setRows(data);
        setError("");
      }),
    [selectedId],
  );

  useEffect(() => {
    let active = true;
    listSettlements(selectedId)
      .then((data) => {
        if (active) setRows(data);
      })
      .catch(() => {
        if (active) setError("Couldn't load driver settlements.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [selectedId]);

  async function post(id: string) {
    setBusy(id);
    setError("");
    try {
      await postSettlement(id);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Driver Settlements</h1>
          <p className="text-sm text-muted-foreground">
            {selectedEntity
              ? `${selectedEntity.numeric_code} · ${selectedEntity.trade_name || selectedEntity.legal_name}`
              : "All accessible entities"}
          </p>
        </div>
        <Link href="/settlements/new">
          <Button size="sm">
            <Plus className="h-4 w-4" />
            New settlement
          </Button>
        </Link>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {loading ? (
        <p className="text-sm text-muted-foreground">Loading settlements…</p>
      ) : rows.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-sm text-muted-foreground">
            No settlements yet. A settlement nets a driver&apos;s earnings against deductions and
            pays the balance.
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b border-border text-left text-xs text-muted-foreground">
                  <tr>
                    <th className="px-4 py-2 font-medium">Date</th>
                    <th className="px-4 py-2 font-medium">No.</th>
                    <th className="px-4 py-2 font-medium">Driver</th>
                    <th className="px-4 py-2 font-medium">Period</th>
                    <th className="px-4 py-2 text-right font-medium">Gross</th>
                    <th className="px-4 py-2 text-right font-medium">Deductions</th>
                    <th className="px-4 py-2 text-right font-medium">Net</th>
                    <th className="px-4 py-2 text-center font-medium">Status</th>
                    <th className="w-10" />
                  </tr>
                </thead>
                <tbody>
                  {rows.map((s) => (
                    <tr key={s.id} className="border-b border-border/60 last:border-0">
                      <td className="whitespace-nowrap px-4 py-2">{s.settlement_date}</td>
                      <td className="whitespace-nowrap px-4 py-2 font-mono text-xs">
                        {s.settlement_no || <span className="text-muted-foreground">(draft)</span>}
                      </td>
                      <td className="max-w-xs truncate px-4 py-2">
                        <span className="font-mono text-xs text-muted-foreground">
                          {s.driver_code}
                        </span>{" "}
                        {s.driver_name}
                      </td>
                      <td className="whitespace-nowrap px-4 py-2 text-xs text-muted-foreground">
                        {s.period_start} → {s.period_end}
                      </td>
                      <td className="whitespace-nowrap px-4 py-2 text-right tabular-nums">
                        {money(s.gross_amount)}
                      </td>
                      <td className="whitespace-nowrap px-4 py-2 text-right tabular-nums text-muted-foreground">
                        {money(s.total_deductions)}
                      </td>
                      <td
                        className={cn(
                          "whitespace-nowrap px-4 py-2 text-right font-medium tabular-nums",
                          Number(s.net_amount) < 0 && "text-amber-600 dark:text-amber-400",
                        )}
                        title={
                          Number(s.net_amount) < 0
                            ? "Amount due from the driver — recorded as a receivable, not a bank receipt"
                            : "Net payout to the driver"
                        }
                      >
                        {money(s.net_amount)}
                      </td>
                      <td className="px-4 py-2 text-center">
                        <span
                          className={cn(
                            "rounded-full px-2 py-0.5 text-xs font-medium capitalize",
                            STATUS_STYLE[s.status],
                          )}
                        >
                          {s.status}
                        </span>
                      </td>
                      <td className="whitespace-nowrap px-3 py-2 text-right">
                        {s.status === "draft" && (
                          <button
                            type="button"
                            onClick={() => post(s.id)}
                            disabled={busy === s.id}
                            className="text-xs font-medium text-primary hover:underline disabled:opacity-40"
                          >
                            {busy === s.id ? "Posting…" : "Post"}
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
