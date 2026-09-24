"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { getRecord } from "@/lib/crud";
import {
  allocateInvoiceBulk,
  listInvoiceAllocations,
  listInvoiceSources,
  listInvoices,
  unallocateInvoice,
  type Allocation,
  type AllocationSource,
  type SalesInvoice,
} from "@/lib/invoices";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

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
  const [otherInvoices, setOtherInvoices] = useState<SalesInvoice[]>([]);
  const [sources, setSources] = useState<AllocationSource[]>([]);
  const [allocations, setAllocations] = useState<Allocation[]>([]);
  const [sourceId, setSourceId] = useState("");
  const [amounts, setAmounts] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [undoing, setUndoing] = useState("");
  const [error, setError] = useState("");
  const [loadError, setLoadError] = useState("");

  const reload = useCallback(async () => {
    const inv = await getRecord<SalesInvoice>("invoices", id);
    const [srcs, allocs, others] = await Promise.all([
      listInvoiceSources(inv.customer),
      listInvoiceAllocations(id),
      listInvoices({ customerId: inv.customer }),
    ]);
    setInvoice(inv);
    setSources(srcs);
    setAllocations(allocs);
    setOtherInvoices(
      others.results.filter(
        (o) =>
          o.id !== inv.id && num(o.balance) > 0 && ["posted", "partially_paid"].includes(o.status),
      ),
    );
  }, [id]);

  useEffect(() => {
    let active = true;
    getRecord<SalesInvoice>("invoices", id)
      .then((inv) =>
        Promise.all([
          listInvoiceSources(inv.customer),
          listInvoiceAllocations(id),
          listInvoices({ customerId: inv.customer }),
        ]).then(([srcs, allocs, others]) => {
          if (!active) return;
          setInvoice(inv);
          setSources(srcs);
          setAllocations(allocs);
          setOtherInvoices(
            others.results.filter(
              (o) =>
                o.id !== inv.id &&
                num(o.balance) > 0 &&
                ["posted", "partially_paid"].includes(o.status),
            ),
          );
        }),
      )
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
  const rows = invoice ? [invoice, ...otherInvoices] : [];
  const totalEntered = rows.reduce((sum, r) => sum + num(amounts[r.id] ?? ""), 0);
  const remaining = selected ? num(selected.available) - totalEntered : 0;

  function pickSource(value: string) {
    setSourceId(value);
    const s = sources.find((x) => x.source_id === value);
    setAmounts(
      s && invoice ? { [invoice.id]: Math.min(num(invoice.balance), num(s.available)).toFixed(2) } : {},
    );
  }

  function setRowAmount(invoiceId: string, value: string) {
    setAmounts((prev) => ({ ...prev, [invoiceId]: value }));
  }

  async function apply() {
    if (!selected || !invoice) return setError("Select a source to allocate.");
    const lines = rows
      .map((r) => ({ invoice_id: r.id, amount: amounts[r.id] ?? "" }))
      .filter((l) => num(l.amount) > 0);
    if (lines.length === 0) return setError("Enter an amount against at least one invoice.");
    setSaving(true);
    setError("");
    try {
      await allocateInvoiceBulk({
        customer: invoice.customer,
        source_type: selected.source_type,
        source_id: selected.source_id,
        lines,
      });
      setSourceId("");
      setAmounts({});
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setSaving(false);
    }
  }

  async function undo(allocationId: string) {
    setUndoing(allocationId);
    setError("");
    try {
      await unallocateInvoice(id, allocationId);
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setUndoing("");
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
            <div className="flex flex-col gap-1.5">
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

            {selected && (
              <div className="flex flex-col gap-2">
                <p className="text-xs text-muted-foreground">
                  Spread {money(selected.available)} across this customer&apos;s open invoices — this
                  one is pre-filled; add amounts to others to settle several in one action.
                </p>
                <table className="w-full text-sm">
                  <thead className="border-b border-border text-left text-xs text-muted-foreground">
                    <tr>
                      <th className="py-2 font-medium">Invoice</th>
                      <th className="py-2 text-right font-medium">Balance</th>
                      <th className="py-2 text-right font-medium">Amount to apply</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r) => (
                      <tr key={r.id} className="border-b border-border/60 last:border-0">
                        <td className="py-2">
                          {r.invoice_no || "(draft)"}
                          {r.id === invoice.id && (
                            <span className="ml-1 text-xs text-muted-foreground">(this invoice)</span>
                          )}
                        </td>
                        <td className="py-2 text-right tabular-nums">{money(r.balance)}</td>
                        <td className="py-2 text-right">
                          <Input
                            type="number"
                            inputMode="decimal"
                            value={amounts[r.id] ?? ""}
                            onChange={(e) => setRowAmount(r.id, e.target.value)}
                            className="text-right tabular-nums"
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <p className="text-right text-xs text-muted-foreground">
                  {remaining < 0
                    ? `${money(Math.abs(remaining))} over the source's available balance.`
                    : `${money(remaining)} of the source left unapplied.`}
                </p>
              </div>
            )}

            <div className="flex items-center justify-end gap-2">
              <Link href="/invoices">
                <Button variant="ghost" size="sm" type="button">
                  Done
                </Button>
              </Link>
              <Button size="sm" onClick={apply} disabled={saving || !selected}>
                {saving ? "Applying…" : "Apply allocation"}
              </Button>
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
                  <th className="px-4 py-2 text-right font-medium" />
                </tr>
              </thead>
              <tbody>
                {allocations.map((a) => (
                  <tr
                    key={a.id}
                    className={cn(
                      "border-b border-border/60 last:border-0",
                      a.reversed && "text-muted-foreground line-through",
                    )}
                  >
                    <td className="px-4 py-2">{a.date}</td>
                    <td className="px-4 py-2">{SOURCE_LABEL[a.source_type] ?? a.source_type}</td>
                    <td className="px-4 py-2 text-right tabular-nums">{money(a.amount)}</td>
                    <td className="px-4 py-2 text-right">
                      {!a.reversed && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => undo(a.id)}
                          disabled={undoing === a.id}
                        >
                          {undoing === a.id ? "Undoing…" : "Undo"}
                        </Button>
                      )}
                    </td>
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
