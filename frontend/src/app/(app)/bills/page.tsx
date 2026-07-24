"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Plus } from "lucide-react";
import { useEntity } from "@/lib/entity-context";
import { listBills, type PurchaseBill, type BillStatus } from "@/lib/bills";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const STATUS_STYLE: Record<BillStatus, string> = {
  draft: "bg-muted text-muted-foreground",
  posted: "bg-primary/10 text-primary",
  partially_paid: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
  paid: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
  cancelled: "bg-red-500/10 text-red-600 dark:text-red-400",
};

const STATUS_LABEL: Record<BillStatus, string> = {
  draft: "Draft",
  posted: "Posted",
  partially_paid: "Part-paid",
  paid: "Paid",
  cancelled: "Cancelled",
};

function money(value: string): string {
  const n = Number(value);
  return Number.isFinite(n)
    ? n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    : value;
}

export default function BillsPage() {
  const { selectedId, selectedEntity } = useEntity();
  const [bills, setBills] = useState<PurchaseBill[]>([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [status, setStatus] = useState("");

  useEffect(() => {
    let active = true;
    listBills({ entityId: selectedId, status })
      .then((data) => {
        if (active) {
          setBills(data.results);
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
  }, [selectedId, status]);

  const selectClass =
    "h-9 rounded-md border border-border bg-background px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40";

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Purchase Bills</h1>
          <p className="text-sm text-muted-foreground">
            {selectedEntity
              ? `${selectedEntity.numeric_code} · ${selectedEntity.trade_name || selectedEntity.legal_name}`
              : "All accessible entities"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select
            aria-label="Status"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className={selectClass}
          >
            <option value="">All statuses</option>
            {Object.entries(STATUS_LABEL).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
          <Link href="/bills/new">
            <Button size="sm">
              <Plus className="h-4 w-4" />
              New bill
            </Button>
          </Link>
        </div>
      </div>

      {loading ? (
        <p className="text-sm text-muted-foreground">Loading bills…</p>
      ) : error ? (
        <p className="text-sm text-destructive">Couldn&apos;t load bills.</p>
      ) : bills.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-sm text-muted-foreground">
            No bills{status ? " match this filter" : " yet"}. Record your first supplier bill with the{" "}
            <span className="font-medium text-foreground">New bill</span> button.
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
                    <th className="px-4 py-2 font-medium">Supplier</th>
                    <th className="px-4 py-2 font-medium">Supplier inv.</th>
                    <th className="px-4 py-2 text-right font-medium">Total</th>
                    <th className="px-4 py-2 text-right font-medium">Balance</th>
                    <th className="px-4 py-2 text-center font-medium">Status</th>
                    <th className="w-10" />
                  </tr>
                </thead>
                <tbody>
                  {bills.map((b) => (
                    <tr key={b.id} className="border-b border-border/60 last:border-0">
                      <td className="whitespace-nowrap px-4 py-2">{b.bill_date}</td>
                      <td className="whitespace-nowrap px-4 py-2 font-mono text-xs">
                        {b.bill_no || <span className="text-muted-foreground">(draft)</span>}
                      </td>
                      <td className="max-w-xs truncate px-4 py-2">
                        <span className="font-mono text-xs text-muted-foreground">
                          {b.supplier_code}
                        </span>{" "}
                        {b.supplier_name}
                        {b.is_reverse_charge && (
                          <span className="ml-1 rounded bg-amber-500/10 px-1 text-[10px] font-medium text-amber-600 dark:text-amber-400">
                            RCM
                          </span>
                        )}
                      </td>
                      <td className="max-w-[10rem] truncate px-4 py-2 font-mono text-xs text-muted-foreground">
                        {b.supplier_invoice_no || "—"}
                      </td>
                      <td className="whitespace-nowrap px-4 py-2 text-right font-medium">
                        {money(b.total)}
                      </td>
                      <td className="whitespace-nowrap px-4 py-2 text-right tabular-nums text-muted-foreground">
                        {money(b.balance)}
                      </td>
                      <td className="px-4 py-2 text-center">
                        <span
                          className={cn(
                            "rounded-full px-2 py-0.5 text-xs font-medium",
                            STATUS_STYLE[b.status],
                          )}
                        >
                          {STATUS_LABEL[b.status]}
                        </span>
                      </td>
                      <td className="whitespace-nowrap px-3 py-2 text-right">
                        {Number(b.balance) > 0 &&
                        ["posted", "partially_paid"].includes(b.status) ? (
                          <Link
                            href={`/bills/${b.id}/allocate`}
                            className="text-xs font-medium text-primary hover:underline"
                          >
                            Allocate
                          </Link>
                        ) : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {!loading && !error && bills.length > 0 && (
        <p className="text-xs text-muted-foreground">
          {bills.length} of {count} bill{count === 1 ? "" : "s"}
        </p>
      )}
    </div>
  );
}
