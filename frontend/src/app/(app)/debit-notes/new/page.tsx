"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Plus, Trash2 } from "lucide-react";
import { useEntity } from "@/lib/entity-context";
import { listAccounts, type Account } from "@/lib/accounts";
import { listSuppliers, type Supplier } from "@/lib/parties";
import { listTaxCodes, type TaxCode } from "@/lib/taxes";
import { listBills, type PurchaseBill } from "@/lib/bills";
import { createDebitNote, postDebitNote, type DebitNoteLineInput } from "@/lib/debit-notes";
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

export default function NewDebitNotePage() {
  const router = useRouter();
  const { selectedId, selectedEntity } = useEntity();
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [taxCodes, setTaxCodes] = useState<TaxCode[]>([]);
  const [bills, setBills] = useState<PurchaseBill[]>([]);
  const [supplier, setSupplier] = useState("");
  const [noteDate, setNoteDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [originalBill, setOriginalBill] = useState("");
  const [reason, setReason] = useState("");
  const [lines, setLines] = useState<Line[]>([emptyLine()]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!selectedId) return;
    let active = true;
    Promise.all([
      listSuppliers(selectedId),
      listAccounts(selectedId),
      listTaxCodes(selectedId, "input"),
      listBills({ entityId: selectedId }),
    ])
      .then(([sup, accts, taxes, bl]) => {
        if (!active) return;
        setSuppliers(sup.filter((s) => s.is_active));
        setAccounts(
          accts.filter(
            (a) => a.is_postable && a.is_active && (a.nature === "expense" || a.nature === "asset"),
          ),
        );
        setTaxCodes(taxes);
        setBills(bl.results);
      })
      .catch(() => {
        if (active) setError("Couldn't load suppliers, accounts, or tax codes.");
      });
    return () => {
      active = false;
    };
  }, [selectedId]);

  const rateOf = useMemo(() => {
    const map = new Map(taxCodes.map((t) => [t.id, num(t.rate)]));
    return (id: string) => map.get(id) ?? 0;
  }, [taxCodes]);

  const supplierBills = useMemo(
    () => bills.filter((b) => b.supplier === supplier && b.status !== "draft"),
    [bills, supplier],
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
    if (!supplier) {
      setError("Select a supplier.");
      return;
    }
    const filled = lines.filter((l) => l.account && num(l.amount) > 0);
    if (filled.length === 0) {
      setError("Add at least one line with an account and an amount.");
      return;
    }
    setSaving(true);
    try {
      const { id } = await createDebitNote({
        entity: selectedId!,
        supplier,
        debit_note_date: noteDate,
        original_bill: originalBill || null,
        reason,
        lines: filled.map<DebitNoteLineInput>((l) => ({
          account: l.account,
          description: l.description,
          line_amount: l.amount || "0",
          tax_code: l.taxCode || null,
        })),
      });
      if (alsoPost) await postDebitNote(id);
      router.push("/debit-notes");
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
          Pick an entity from the switcher above to create a debit note.
        </CardContent>
      </Card>
    );
  }

  const fieldClass =
    "h-9 rounded-md border border-border bg-background px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40";

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">New Debit Note</h1>
        <p className="text-sm text-muted-foreground">
          {selectedEntity?.numeric_code} · {selectedEntity?.trade_name || selectedEntity?.legal_name}
        </p>
      </div>

      <Card>
        <CardContent className="grid grid-cols-1 gap-4 py-5 sm:grid-cols-2 lg:grid-cols-4">
          <div className="flex flex-col gap-1.5">
            <Label>Supplier</Label>
            <select
              value={supplier}
              onChange={(e) => {
                setSupplier(e.target.value);
                setOriginalBill("");
              }}
              className={fieldClass}
            >
              <option value="">Select supplier…</option>
              {suppliers.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.code} · {s.name}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Date</Label>
            <Input type="date" value={noteDate} onChange={(e) => setNoteDate(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Against bill</Label>
            <select
              value={originalBill}
              onChange={(e) => setOriginalBill(e.target.value)}
              className={fieldClass}
              disabled={!supplier}
            >
              <option value="">None</option>
              {supplierBills.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.bill_no || "(draft)"} · {money(Number(b.total))}
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
                  <th className="px-3 py-2 font-medium">Account</th>
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
          <Link href="/debit-notes">
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
