"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Plus } from "lucide-react";
import { useEntity } from "@/lib/entity-context";
import { listVouchers, type Voucher, type VoucherStatus } from "@/lib/vouchers";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const TYPE_LABEL: Record<Voucher["voucher_type"], string> = {
  receipt: "Receipt",
  payment: "Payment",
  contra: "Contra",
  expense: "Expense",
  journal: "Journal",
};

const STATUS_STYLE: Record<VoucherStatus, string> = {
  draft: "bg-muted text-muted-foreground",
  posted: "bg-primary/10 text-primary",
  reversed: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
  cancelled: "bg-red-500/10 text-red-600 dark:text-red-400",
};

function money(value: string): string {
  const n = Number(value);
  return Number.isFinite(n)
    ? n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    : value;
}

export default function VouchersPage() {
  const { selectedId, selectedEntity } = useEntity();
  const [vouchers, setVouchers] = useState<Voucher[]>([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [type, setType] = useState("");
  const [status, setStatus] = useState("");

  useEffect(() => {
    let active = true;
    listVouchers({ entityId: selectedId, type, status })
      .then((data) => {
        if (active) {
          setVouchers(data.results);
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
  }, [selectedId, type, status]);

  const selectClass =
    "h-9 rounded-md border border-border bg-background px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40";

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Vouchers</h1>
          <p className="text-sm text-muted-foreground">
            {selectedEntity
              ? `${selectedEntity.numeric_code} · ${selectedEntity.trade_name || selectedEntity.legal_name}`
              : "All accessible entities"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select
            aria-label="Type"
            value={type}
            onChange={(e) => setType(e.target.value)}
            className={selectClass}
          >
            <option value="">All types</option>
            {Object.entries(TYPE_LABEL).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
          <select
            aria-label="Status"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className={selectClass}
          >
            <option value="">All statuses</option>
            <option value="draft">Draft</option>
            <option value="posted">Posted</option>
            <option value="reversed">Reversed</option>
            <option value="cancelled">Cancelled</option>
          </select>
          <Link href="/vouchers/new">
            <Button size="sm">
              <Plus className="h-4 w-4" />
              New voucher
            </Button>
          </Link>
        </div>
      </div>

      {loading ? (
        <p className="text-sm text-muted-foreground">Loading vouchers…</p>
      ) : error ? (
        <p className="text-sm text-destructive">Couldn&apos;t load vouchers.</p>
      ) : vouchers.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-sm text-muted-foreground">
            No vouchers{type || status ? " match these filters" : " yet"}. Voucher entry (with the
            double-entry posting flow) is the next slice — the API already supports it.
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
                    <th className="px-4 py-2 font-medium">Type</th>
                    <th className="px-4 py-2 font-medium">Reference</th>
                    <th className="px-4 py-2 text-right font-medium">Amount</th>
                    <th className="px-4 py-2 text-center font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {vouchers.map((v) => (
                    <tr key={v.id} className="border-b border-border/60 last:border-0">
                      <td className="whitespace-nowrap px-4 py-2">{v.voucher_date}</td>
                      <td className="whitespace-nowrap px-4 py-2 font-mono text-xs">
                        {v.voucher_no || <span className="text-muted-foreground">(draft)</span>}
                      </td>
                      <td className="px-4 py-2">{TYPE_LABEL[v.voucher_type]}</td>
                      <td className="max-w-xs truncate px-4 py-2 text-muted-foreground">
                        {v.reference || v.narration || "—"}
                      </td>
                      <td className="whitespace-nowrap px-4 py-2 text-right font-medium">
                        {money(v.amount)}
                      </td>
                      <td className="px-4 py-2 text-center">
                        <span
                          className={cn(
                            "rounded-full px-2 py-0.5 text-xs font-medium capitalize",
                            STATUS_STYLE[v.status],
                          )}
                        >
                          {v.status}
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

      {!loading && !error && vouchers.length > 0 && (
        <p className="text-xs text-muted-foreground">
          {vouchers.length} of {count} voucher{count === 1 ? "" : "s"}
        </p>
      )}
    </div>
  );
}
