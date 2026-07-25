"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Plus } from "lucide-react";
import { useEntity } from "@/lib/entity-context";
import { listAdvances, postAdvance, type Advance } from "@/lib/settlements";
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

export default function AdvancesPage() {
  const { selectedId, selectedEntity } = useEntity();
  const [rows, setRows] = useState<Advance[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(
    () =>
      listAdvances(selectedId).then((data) => {
        setRows(data);
        setError("");
      }),
    [selectedId],
  );

  useEffect(() => {
    let active = true;
    listAdvances(selectedId)
      .then((data) => {
        if (active) setRows(data);
      })
      .catch(() => {
        if (active) setError("Couldn't load driver advances.");
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
      await postAdvance(id);
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
          <h1 className="text-2xl font-semibold">Driver Advances</h1>
          <p className="text-sm text-muted-foreground">
            {selectedEntity
              ? `${selectedEntity.numeric_code} · ${selectedEntity.trade_name || selectedEntity.legal_name}`
              : "All accessible entities"}
          </p>
        </div>
        <Link href="/advances/new">
          <Button size="sm">
            <Plus className="h-4 w-4" />
            New advance
          </Button>
        </Link>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {loading ? (
        <p className="text-sm text-muted-foreground">Loading advances…</p>
      ) : rows.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-sm text-muted-foreground">
            No advances yet. A cash advance is recovered later through a driver settlement.
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
                    <th className="px-4 py-2 text-right font-medium">Amount</th>
                    <th className="px-4 py-2 text-right font-medium">Recovered</th>
                    <th className="px-4 py-2 text-right font-medium">Balance</th>
                    <th className="px-4 py-2 text-center font-medium">Status</th>
                    <th className="w-10" />
                  </tr>
                </thead>
                <tbody>
                  {rows.map((a) => (
                    <tr key={a.id} className="border-b border-border/60 last:border-0">
                      <td className="whitespace-nowrap px-4 py-2">{a.advance_date}</td>
                      <td className="whitespace-nowrap px-4 py-2 font-mono text-xs">
                        {a.advance_no || <span className="text-muted-foreground">(draft)</span>}
                      </td>
                      <td className="max-w-xs truncate px-4 py-2">
                        <span className="font-mono text-xs text-muted-foreground">
                          {a.driver_code}
                        </span>{" "}
                        {a.driver_name}
                      </td>
                      <td className="whitespace-nowrap px-4 py-2 text-right font-medium tabular-nums">
                        {money(a.amount)}
                      </td>
                      <td className="whitespace-nowrap px-4 py-2 text-right tabular-nums text-muted-foreground">
                        {money(a.recovered_amount)}
                      </td>
                      <td className="whitespace-nowrap px-4 py-2 text-right tabular-nums">
                        {money(a.balance)}
                      </td>
                      <td className="px-4 py-2 text-center">
                        <span
                          className={cn(
                            "rounded-full px-2 py-0.5 text-xs font-medium capitalize",
                            STATUS_STYLE[a.status],
                          )}
                        >
                          {a.status}
                        </span>
                      </td>
                      <td className="whitespace-nowrap px-3 py-2 text-right">
                        {a.status === "draft" && (
                          <button
                            type="button"
                            onClick={() => post(a.id)}
                            disabled={busy === a.id}
                            className="text-xs font-medium text-primary hover:underline disabled:opacity-40"
                          >
                            {busy === a.id ? "Posting…" : "Post"}
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
