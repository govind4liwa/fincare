"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Plus, Trash2 } from "lucide-react";
import { useEntity } from "@/lib/entity-context";
import { listAccounts, type Account } from "@/lib/accounts";
import { listCustomers, type Customer } from "@/lib/parties";
import { listTaxCodes, type TaxCode } from "@/lib/taxes";
import { listInvoices, type SalesInvoice } from "@/lib/invoices";
import { createCreditNote, postCreditNote, type CreditNoteLineInput } from "@/lib/credit-notes";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

type Line = { account: string; description: string; amount: string; taxCode: string };

const emptyLine = (): Line => ({ account: "", description: "", amount: "", taxCode: "" });
const num = (v: string) => (Number.isFinite(Number(v)) ? Number(v) : 0);
const money = (n: number) =>
  n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function NewCreditNotePage() {
  const router = useRouter();
  const { selectedId, selectedEntity } = useEntity();
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [taxCodes, setTaxCodes] = useState<TaxCode[]>([]);
  const [invoices, setInvoices] = useState<SalesInvoice[]>([]);
  const [customer, setCustomer] = useState("");
  const [noteDate, setNoteDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [originalInvoice, setOriginalInvoice] = useState("");
  const [reason, setReason] = useState("");
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
      listInvoices({ entityId: selectedId }),
    ])
      .then(([cust, accts, taxes, inv]) => {
        if (!active) return;
        setCustomers(cust.filter((c) => c.is_active));
        setAccounts(accts.filter((a) => a.is_postable && a.is_active && a.nature === "income"));
        setTaxCodes(taxes);
        setInvoices(inv.results);
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

  const customerInvoices = useMemo(
    () => invoices.filter((i) => i.customer === customer && i.status !== "draft"),
    [invoices, customer],
  );

  const totals = useMemo(() => {
    let subtotal = 0;
    let tax = 0;
    for (const l of lines) {
      subtotal += num(l.amount);
      tax += (num(l.amount) * rateOf(l.taxCode)) / 100;
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
    const filled = lines.filter((l) => l.account && num(l.amount) > 0);
    if (filled.length === 0) {
      setError("Add at least one line with a revenue account and an amount.");
      return;
    }
    setSaving(true);
    try {
      const { id } = await createCreditNote({
        entity: selectedId!,
        customer,
        credit_note_date: noteDate,
        original_invoice: originalInvoice || null,
        reason,
        lines: filled.map<CreditNoteLineInput>((l) => ({
          revenue_account: l.account,
          description: l.description,
          line_amount: l.amount || "0",
          tax_code: l.taxCode || null,
        })),
      });
      if (alsoPost) await postCreditNote(id);
      router.push("/credit-notes");
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
          Pick an entity from the switcher above to create a credit note.
        </CardContent>
      </Card>
    );
  }

  const fieldClass =
    "h-9 rounded-md border border-border bg-background px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40";

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">New Credit Note</h1>
        <p className="text-sm text-muted-foreground">
          {selectedEntity?.numeric_code} · {selectedEntity?.trade_name || selectedEntity?.legal_name}
        </p>
      </div>

      <Card>
        <CardContent className="grid grid-cols-1 gap-4 py-5 sm:grid-cols-2 lg:grid-cols-4">
          <div className="flex flex-col gap-1.5">
            <Label>Customer</Label>
            <select
              value={customer}
              onChange={(e) => {
                setCustomer(e.target.value);
                setOriginalInvoice("");
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
            <Label>Date</Label>
            <Input type="date" value={noteDate} onChange={(e) => setNoteDate(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Against invoice</Label>
            <select
              value={originalInvoice}
              onChange={(e) => setOriginalInvoice(e.target.value)}
              className={fieldClass}
              disabled={!customer}
            >
              <option value="">None</option>
              {customerInvoices.map((i) => (
                <option key={i.id} value={i.id}>
                  {i.invoice_no || "(draft)"} · {money(Number(i.total))}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Reason</Label>
            <Input value={reason} onChange={(e) => setReason(e.target.value)} />
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
                  <th className="px-3 py-2 font-medium">VAT</th>
                  <th className="px-3 py-2 text-right font-medium">Amount</th>
                  <th className="w-10" />
                </tr>
              </thead>
              <tbody>
                {lines.map((l, i) => (
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
                    <td className="px-3 py-1.5">
                      <Input
                        type="number"
                        inputMode="decimal"
                        value={l.amount}
                        onChange={(e) => updateLine(i, "amount", e.target.value)}
                        className="h-9 w-32 text-right tabular-nums"
                      />
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
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <td className="px-3 py-2" colSpan={5}>
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
          <Link href="/credit-notes">
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
