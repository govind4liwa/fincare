"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Plus, Trash2 } from "lucide-react";
import { useEntity } from "@/lib/entity-context";
import { listAccounts, type Account } from "@/lib/accounts";
import { listCustomers, type Customer } from "@/lib/parties";
import { listTaxCodes, type TaxCode } from "@/lib/taxes";
import { createInvoice, postInvoice, type InvoiceLineInput } from "@/lib/invoices";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

type Line = {
  account: string;
  description: string;
  qty: string;
  unitPrice: string;
  taxCode: string;
};

const emptyLine = (): Line => ({ account: "", description: "", qty: "1", unitPrice: "", taxCode: "" });
const num = (v: string) => (Number.isFinite(Number(v)) ? Number(v) : 0);
const money = (n: number) => n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function NewInvoicePage() {
  const router = useRouter();
  const { selectedId, selectedEntity } = useEntity();
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [taxCodes, setTaxCodes] = useState<TaxCode[]>([]);
  const [customer, setCustomer] = useState("");
  const [invoiceDate, setInvoiceDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [dueDate, setDueDate] = useState("");
  const [placeOfSupply, setPlaceOfSupply] = useState("");
  const [narration, setNarration] = useState("");
  const [lines, setLines] = useState<Line[]>([emptyLine()]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!selectedId) return;
    let active = true;
    Promise.all([
      listCustomers(selectedId),
      listAccounts(selectedId),
      listTaxCodes(selectedId, "output"),
    ])
      .then(([cust, accts, taxes]) => {
        if (!active) return;
        setCustomers(cust.filter((c) => c.is_active));
        setAccounts(accts.filter((a) => a.is_postable && a.is_active && a.nature === "income"));
        setTaxCodes(taxes);
      })
      .catch(() => {
        if (active) setError("Couldn't load customers, accounts, or tax codes.");
      });
    return () => {
      active = false;
    };
  }, [selectedId]);

  const rateOf = useMemo(() => {
    const map = new Map(taxCodes.map((t) => [t.id, num(t.rate)]));
    return (id: string) => map.get(id) ?? 0;
  }, [taxCodes]);

  const totals = useMemo(() => {
    let subtotal = 0;
    let tax = 0;
    for (const l of lines) {
      const amount = num(l.qty) * num(l.unitPrice);
      subtotal += amount;
      tax += (amount * rateOf(l.taxCode)) / 100;
    }
    return { subtotal, tax, total: subtotal + tax };
  }, [lines, rateOf]);

  function updateLine(i: number, field: keyof Line, value: string) {
    setLines((prev) => prev.map((l, idx) => (idx === i ? { ...l, [field]: value } : l)));
  }

  async function submit(alsoPost: boolean) {
    setError("");
    if (!customer) {
      setError("Select a customer.");
      return;
    }
    const filled = lines.filter((l) => l.account && num(l.unitPrice) > 0);
    if (filled.length === 0) {
      setError("Add at least one line with a revenue account and an amount.");
      return;
    }
    setSaving(true);
    try {
      const payload = {
        entity: selectedId!,
        customer,
        invoice_date: invoiceDate,
        due_date: dueDate || null,
        place_of_supply: placeOfSupply,
        narration,
        lines: filled.map<InvoiceLineInput>((l) => ({
          revenue_account: l.account,
          description: l.description,
          quantity: l.qty || "1",
          unit_price: l.unitPrice || "0",
          tax_code: l.taxCode || null,
        })),
      };
      const { id } = await createInvoice(payload);
      if (alsoPost) await postInvoice(id);
      router.push("/invoices");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setSaving(false);
    }
  }

  if (!selectedId) {
    return (
      <Card>
        <CardContent className="py-12 text-center text-sm text-muted-foreground">
          Pick an entity from the switcher above to create an invoice.
        </CardContent>
      </Card>
    );
  }

  const fieldClass =
    "h-9 rounded-md border border-border bg-background px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40";

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">New Sales Invoice</h1>
        <p className="text-sm text-muted-foreground">
          {selectedEntity?.numeric_code} · {selectedEntity?.trade_name || selectedEntity?.legal_name}
        </p>
      </div>

      <Card>
        <CardContent className="grid grid-cols-1 gap-4 py-5 sm:grid-cols-2 lg:grid-cols-3">
          <div className="flex flex-col gap-1.5">
            <Label>Customer</Label>
            <select
              value={customer}
              onChange={(e) => {
                setCustomer(e.target.value);
                const c = customers.find((x) => x.id === e.target.value);
                if (c && !placeOfSupply) setPlaceOfSupply(c.emirate || "");
              }}
              className={fieldClass}
            >
              <option value="">Select customer…</option>
              {customers.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.code} · {c.name}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Invoice date</Label>
            <Input type="date" value={invoiceDate} onChange={(e) => setInvoiceDate(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Due date</Label>
            <Input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Place of supply</Label>
            <Input
              value={placeOfSupply}
              onChange={(e) => setPlaceOfSupply(e.target.value)}
              placeholder="Emirate"
            />
          </div>
          <div className="flex flex-col gap-1.5 sm:col-span-2">
            <Label>Narration</Label>
            <Input value={narration} onChange={(e) => setNarration(e.target.value)} />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-border text-left text-xs text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 font-medium">Revenue account</th>
                  <th className="px-3 py-2 font-medium">Description</th>
                  <th className="px-3 py-2 text-right font-medium">Qty</th>
                  <th className="px-3 py-2 text-right font-medium">Unit price</th>
                  <th className="px-3 py-2 font-medium">VAT</th>
                  <th className="px-3 py-2 text-right font-medium">Amount</th>
                  <th className="w-10" />
                </tr>
              </thead>
              <tbody>
                {lines.map((l, i) => {
                  const amount = num(l.qty) * num(l.unitPrice);
                  return (
                    <tr key={i} className="border-b border-border/60">
                      <td className="px-3 py-1.5">
                        <select
                          value={l.account}
                          onChange={(e) => updateLine(i, "account", e.target.value)}
                          className={cn(fieldClass, "w-full min-w-52")}
                        >
                          <option value="">Select account…</option>
                          {accounts.map((a) => (
                            <option key={a.id} value={a.id}>
                              {a.code} · {a.name}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="px-3 py-1.5">
                        <Input
                          value={l.description}
                          onChange={(e) => updateLine(i, "description", e.target.value)}
                          className="h-9 min-w-40"
                        />
                      </td>
                      <td className="px-3 py-1.5">
                        <Input
                          type="number"
                          inputMode="decimal"
                          value={l.qty}
                          onChange={(e) => updateLine(i, "qty", e.target.value)}
                          className="h-9 w-20 text-right tabular-nums"
                        />
                      </td>
                      <td className="px-3 py-1.5">
                        <Input
                          type="number"
                          inputMode="decimal"
                          value={l.unitPrice}
                          onChange={(e) => updateLine(i, "unitPrice", e.target.value)}
                          className="h-9 w-28 text-right tabular-nums"
                        />
                      </td>
                      <td className="px-3 py-1.5">
                        <select
                          value={l.taxCode}
                          onChange={(e) => updateLine(i, "taxCode", e.target.value)}
                          className={cn(fieldClass, "min-w-24")}
                        >
                          <option value="">None</option>
                          {taxCodes.map((t) => (
                            <option key={t.id} value={t.id}>
                              {t.code} ({num(t.rate)}%)
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="px-3 py-1.5 text-right tabular-nums text-muted-foreground">
                        {money(amount)}
                      </td>
                      <td className="px-2 text-center">
                        <button
                          type="button"
                          onClick={() => setLines((p) => p.filter((_, idx) => idx !== i))}
                          disabled={lines.length <= 1}
                          className="text-muted-foreground hover:text-destructive disabled:opacity-30"
                          aria-label="Remove line"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
              <tfoot>
                <tr>
                  <td className="px-3 py-2" colSpan={7}>
                    <button
                      type="button"
                      onClick={() => setLines((p) => [...p, emptyLine()])}
                      className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
                    >
                      <Plus className="h-4 w-4" /> Add line
                    </button>
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        </CardContent>
      </Card>

      <div className="flex flex-wrap items-start justify-between gap-4">
        <Card className="min-w-56">
          <CardContent className="flex flex-col gap-1 py-4 text-sm">
            <div className="flex justify-between gap-8">
              <span className="text-muted-foreground">Subtotal</span>
              <span className="tabular-nums">{money(totals.subtotal)}</span>
            </div>
            <div className="flex justify-between gap-8">
              <span className="text-muted-foreground">VAT</span>
              <span className="tabular-nums">{money(totals.tax)}</span>
            </div>
            <div className="flex justify-between gap-8 border-t border-border pt-1 font-semibold">
              <span>Total</span>
              <span className="tabular-nums">{money(totals.total)}</span>
            </div>
          </CardContent>
        </Card>
        <div className="flex items-center gap-2">
          <Link href="/invoices">
            <Button variant="ghost" size="sm" type="button">
              Cancel
            </Button>
          </Link>
          <Button variant="outline" size="sm" onClick={() => submit(false)} disabled={saving}>
            Save draft
          </Button>
          <Button size="sm" onClick={() => submit(true)} disabled={saving || totals.total <= 0}>
            {saving ? "Saving…" : "Save & Post"}
          </Button>
        </div>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  );
}
