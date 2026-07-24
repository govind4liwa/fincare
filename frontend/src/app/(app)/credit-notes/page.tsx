"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Plus } from "lucide-react";
import { useEntity } from "@/lib/entity-context";
import { listCreditNotes, type CreditNote, type NoteStatus } from "@/lib/credit-notes";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const STATUS_STYLE: Record<NoteStatus, string> = {
  draft: "bg-muted text-muted-foreground",
  posted: "bg-primary/10 text-primary",
  partially_paid: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
  paid: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
  cancelled: "bg-red-500/10 text-red-600 dark:text-red-400",
};

function money(value: string): string {
  const n = Number(value);
  return Number.isFinite(n)
    ? n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    : value;
}

export default function CreditNotesPage() {
  const { selectedId, selectedEntity } = useEntity();
  const [notes, setNotes] = useState<CreditNote[]>([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let active = true;
    listCreditNotes({ entityId: selectedId })
      .then((data) => {
        if (active) {
          setNotes(data.results);
          setCount(data.count);
          setError(false);
        }
      })
      .catch(() => {
        if (active) setError(true);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [selectedId]);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Credit Notes</h1>
          <p className="text-sm text-muted-foreground">
            {selectedEntity
              ? `${selectedEntity.numeric_code} · ${selectedEntity.trade_name || selectedEntity.legal_name}`
              : "All accessible entities"}
          </p>
        </div>
        <Link href="/credit-notes/new">
          <Button size="sm">
            <Plus className="h-4 w-4" />
            New credit note
          </Button>
        </Link>
      </div>

      {loading ? (
        <p className="text-sm text-muted-foreground">Loading credit notes…</p>
      ) : error ? (
        <p className="text-sm text-destructive">Couldn&apos;t load credit notes.</p>
      ) : notes.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-sm text-muted-foreground">
            No credit notes yet. A credit note reduces what a customer owes (returns, corrections) —
            create one with <span className="font-medium text-foreground">New credit note</span>.
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
                    <th className="px-4 py-2 font-medium">Customer</th>
                    <th className="px-4 py-2 font-medium">Reason</th>
                    <th className="px-4 py-2 text-right font-medium">Total</th>
                    <th className="px-4 py-2 text-center font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {notes.map((n) => (
                    <tr key={n.id} className="border-b border-border/60 last:border-0">
                      <td className="whitespace-nowrap px-4 py-2">{n.credit_note_date}</td>
                      <td className="whitespace-nowrap px-4 py-2 font-mono text-xs">
                        {n.credit_note_no || <span className="text-muted-foreground">(draft)</span>}
                      </td>
                      <td className="max-w-xs truncate px-4 py-2">
                        <span className="font-mono text-xs text-muted-foreground">
                          {n.customer_code}
                        </span>{" "}
                        {n.customer_name}
                      </td>
                      <td className="max-w-xs truncate px-4 py-2 text-muted-foreground">
                        {n.reason || "—"}
                      </td>
                      <td className="whitespace-nowrap px-4 py-2 text-right font-medium">
                        {money(n.total)}
                      </td>
                      <td className="px-4 py-2 text-center">
                        <span
                          className={cn(
                            "rounded-full px-2 py-0.5 text-xs font-medium capitalize",
                            STATUS_STYLE[n.status],
                          )}
                        >
                          {n.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {!loading && !error && notes.length > 0 && (
        <p className="text-xs text-muted-foreground">
          {notes.length} of {count} credit note{count === 1 ? "" : "s"}
        </p>
      )}
    </div>
  );
}
