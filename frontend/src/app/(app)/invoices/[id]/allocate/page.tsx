"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { getRecord } from "@/lib/crud";
import {
  allocateInvoice,
  listInvoiceAllocations,
  listInvoiceSources,
  type Allocation,
  type AllocationSource,
  type SalesInvoice,
} from "@/lib/invoices";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";

const num = (v: string) => (Number.isFinite(Number(v)) ? Number(v) : 0);
const money = (v: string | number) =>
  Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const SOURCE_LABEL: Record<string, string> = {
  receipt_voucher: "Receipt",
  credit_note: "Credit note",
  advance: "Advance",
};

export default function AllocateInvoicePage() {
  const { id } = useParams<{ id: string }>();
  const [invoice, setInvoice] = useState<SalesInvoice | null>(null);
  const [sources, setSources] = useState<AllocationSource[]>([]);
  const [allocations, setAllocations] = useState<Allocation[]>([]);
  const [sourceId, setSourceId] = useState("");
  const [amount, setAmount] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [loadError, setLoadError] = useState("");

  const reload = useCallback(async () => {
    const inv = await getRecord<SalesInvoice>("invoices", id);
    setInvoice(inv);
    const [srcs, allocs] = await Promise.all([
      listInvoiceSources(inv.customer),
      listInvoiceAllocations(id),
    ]);
    setSources(srcs);
    setAllocations(allocs);
  }, [id]);

  useEffect(() => {
    let active = true;
    getRecord<SalesInvoice>("invoices", id)
      .then((inv) => {
        if (!active) return null;
        setInvoice(inv);
        return Promise.all([listInvoiceSources(inv.customer), listInvoiceAllocations(id)]);
      })
      .then((res) => {
        if (active && res) {
          setSources(res[0]);
          setAllocations(res[1]);
        }
      })
      .catch(() => {
        if (active) setLoadError("Couldn't load this invoice.");
      });
    return () => {
      active = false;
    };
  }, [id]);

  const selected = sources.find((s) => s.source_id === sourceId);
  const settleable =
    invoice && num(invoice.balance) > 0 && ["posted", "partially_paid"].includes(invoice.status);

  function pickSource(value: string) {
    setSourceId(value);
    const s = sources.find((x) => x.source_id === value);
    if (s && invoice) setAmount(Math.min(num(invoice.balance), num(s.available)).toFixed(2));
  }

  async function apply() {
    if (!selected) return setError("Select a source to allocate.");
    if (num(amount) <= 0) return setError("Enter an amount.");
    setSaving(true);
    setError("");
    try {
      await allocateInvoice(id, {
        source_type: selected.source_type,
        source_id: selected.source_id,
        amount,
      });
      setSourceId("");
      setAmount("");
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setSaving(false);
    }
  }

  if (loadError) return <p className="text-sm text-destructive">{loadError}</p>;
  if (!invoice) return <p className="text-sm text-muted-foreground">Loading…</p>;

  const fieldClass =
    "h-9 rounded-md border border-border bg-background px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40";

  return (
    <div className="flex max-w-3xl flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">Allocate Receipt</h1>
        <p className="text-sm text-muted-foreground">
          {invoice.invoice_no || "(draft)"} · {invoice.customer_code} {invoice.customer_name}
        </p>
      </div>

      <Card>
        <CardContent className="grid grid-cols-2 gap-4 py-4 text-sm sm:grid-cols-4">
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Total</p>
            <p className="font-medium tabular-nums">{money(invoice.total)}</p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Allocated</p>
            <p className="font-medium tabular-nums">
              {money(num(invoice.total) - num(invoice.balance))}
            </p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Balance due</p>
            <p className="font-semibold tabular-nums">{money(invoice.balance)}</p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Status</p>
            <p className="font-medium capitalize">{invoice.status.replace("_", " ")}</p>
          </div>
        </CardContent>
      </Card>

      {settleable ? (
        <Card>
          <CardContent className="flex flex-col gap-4 py-5">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <div className="flex flex-col gap-1.5 sm:col-span-2">
                <Label>Source (receipt or credit note)</Label>
                <select
                  value={sourceId}
                  onChange={(e) => pickSource(e.target.value)}
                  className={fieldClass}
                >
                  <option value="">Select a source…</option>
                  {sources.map((s) => (
                    <option key={s.source_id} value={s.source_id}>
                      {SOURCE_LABEL[s.source_type] ?? s.source_type} {s.label} · {money(s.available)}{" "}
                      available
                    </option>
                  ))}
                </select>
                {sources.length === 0 && (
                  <p className="text-xs text-muted-foreground">
                    No receipts or credit notes with a balance for this customer. Post a receipt
                    voucher (tagged to the customer) or a credit note first.
                  </p>
                )}
              </div>
              <div className="flex flex-col gap-1.5">
                <Label>Amount</Label>
                <Input
                  type="number"
                  inputMode="decimal"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  className="text-right tabular-nums"
                />
              </div>
            </div>
            <div className="flex items-center justify-between gap-3">
              <span className="text-xs text-muted-foreground">
                {selected
                  ? `Up to ${money(Math.min(num(invoice.balance), num(selected.available)))} can be applied.`
                  : ""}
              </span>
              <div className="flex items-center gap-2">
                <Link href="/invoices">
                  <Button variant="ghost" size="sm" type="button">
                    Done
                  </Button>
                </Link>
                <Button size="sm" onClick={apply} disabled={saving || !selected}>
                  {saving ? "Applying…" : "Apply allocation"}
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="py-8 text-center text-sm text-muted-foreground">
            {invoice.status === "paid"
              ? "This invoice is fully paid."
              : "This invoice can’t be allocated (it must be posted with an outstanding balance)."}{" "}
            <Link href="/invoices" className="text-primary hover:underline">
              Back to invoices
            </Link>
          </CardContent>
        </Card>
      )}

      {allocations.length > 0 && (
        <Card>
          <CardContent className="p-0">
            <table className="w-full text-sm">
              <thead className="border-b border-border text-left text-xs text-muted-foreground">
                <tr>
                  <th className="px-4 py-2 font-medium">Date</th>
                  <th className="px-4 py-2 font-medium">Source</th>
                  <th className="px-4 py-2 text-right font-medium">Amount</th>
                </tr>
              </thead>
              <tbody>
                {allocations.map((a, i) => (
                  <tr key={i} className="border-b border-border/60 last:border-0">
                    <td className="px-4 py-2">{a.date}</td>
                    <td className="px-4 py-2">{SOURCE_LABEL[a.source_type] ?? a.source_type}</td>
                    <td className="px-4 py-2 text-right tabular-nums">{money(a.amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}

      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  );
}
