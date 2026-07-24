"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Plus, Trash2 } from "lucide-react";
import { useEntity } from "@/lib/entity-context";
import { listAccounts, type Account } from "@/lib/accounts";
import { createVoucher, postVoucher, type VoucherLineInput } from "@/lib/vouchers";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const TYPES = [
  ["receipt", "Receipt"],
  ["payment", "Payment"],
  ["contra", "Contra"],
  ["expense", "Expense"],
  ["journal", "Journal"],
] as const;

type Line = { account: string; description: string; debit: string; credit: string };

const emptyLine = (): Line => ({ account: "", description: "", debit: "", credit: "" });
const num = (v: string) => (Number.isFinite(Number(v)) ? Number(v) : 0);

export default function NewVoucherPage() {
  const router = useRouter();
  const { selectedId, selectedEntity } = useEntity();
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [type, setType] = useState("receipt");
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [reference, setReference] = useState("");
  const [narration, setNarration] = useState("");
  const [lines, setLines] = useState<Line[]>([emptyLine(), emptyLine()]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!selectedId) return;
    let active = true;
    listAccounts(selectedId)
      .then((rows) => {
        if (active) setAccounts(rows.filter((a) => a.is_postable && a.is_active));
      })
      .catch(() => {
        if (active) setError("Couldn't load accounts.");
      });
    return () => {
      active = false;
    };
  }, [selectedId]);

  const totals = useMemo(() => {
    const debit = lines.reduce((s, l) => s + num(l.debit), 0);
    const credit = lines.reduce((s, l) => s + num(l.credit), 0);
    return { debit, credit, diff: debit - credit };
  }, [lines]);

  const balanced = totals.debit > 0 && Math.abs(totals.diff) < 0.005;

  function updateLine(i: number, field: keyof Line, value: string) {
    setLines((prev) =>
      prev.map((l, idx) => {
        if (idx !== i) return l;
        const next = { ...l, [field]: value };
        // a line is one-sided: entering a debit clears the credit and vice versa
        if (field === "debit" && value) next.credit = "";
        if (field === "credit" && value) next.debit = "";
        return next;
      }),
    );
  }

  async function submit(alsoPost: boolean) {
    setError("");
    const filled = lines.filter((l) => l.account && (num(l.debit) > 0 || num(l.credit) > 0));
    if (filled.length < 2) {
      setError("Add at least two lines with an account and an amount.");
      return;
    }
    if (alsoPost && !balanced) {
      setError("Debits and credits must balance before posting.");
      return;
    }
    setSaving(true);
    try {
      const payload = {
        entity: selectedId!,
        voucher_type: type,
        voucher_date: date,
        reference,
        narration,
        lines: filled.map<VoucherLineInput>((l) => ({
          account: l.account,
          description: l.description,
          debit: l.debit || "0",
          credit: l.credit || "0",
        })),
      };
      const { id } = await createVoucher(payload);
      if (alsoPost) await postVoucher(id);
      router.push("/vouchers");
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
          Pick an entity from the switcher above to create a voucher.
        </CardContent>
      </Card>
    );
  }

  const fieldClass =
    "h-9 rounded-md border border-border bg-background px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40";

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">New Voucher</h1>
        <p className="text-sm text-muted-foreground">
          {selectedEntity?.numeric_code} · {selectedEntity?.trade_name || selectedEntity?.legal_name}
        </p>
      </div>

      <Card>
        <CardContent className="grid grid-cols-1 gap-4 py-5 sm:grid-cols-2 lg:grid-cols-4">
          <div className="flex flex-col gap-1.5">
            <Label>Type</Label>
            <select value={type} onChange={(e) => setType(e.target.value)} className={fieldClass}>
              {TYPES.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Date</Label>
            <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Reference</Label>
            <Input value={reference} onChange={(e) => setReference(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
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
                  <th className="px-3 py-2 font-medium">Account</th>
                  <th className="px-3 py-2 font-medium">Description</th>
                  <th className="px-3 py-2 text-right font-medium">Debit</th>
                  <th className="px-3 py-2 text-right font-medium">Credit</th>
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
                      <Input
                        type="number"
                        inputMode="decimal"
                        value={l.debit}
                        onChange={(e) => updateLine(i, "debit", e.target.value)}
                        className="h-9 w-28 text-right tabular-nums"
                      />
                    </td>
                    <td className="px-3 py-1.5">
                      <Input
                        type="number"
                        inputMode="decimal"
                        value={l.credit}
                        onChange={(e) => updateLine(i, "credit", e.target.value)}
                        className="h-9 w-28 text-right tabular-nums"
                      />
                    </td>
                    <td className="px-2 text-center">
                      <button
                        type="button"
                        onClick={() => setLines((p) => p.filter((_, idx) => idx !== i))}
                        disabled={lines.length <= 2}
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
                <tr className="border-t border-border font-medium">
                  <td className="px-3 py-2" colSpan={2}>
                    <button
                      type="button"
                      onClick={() => setLines((p) => [...p, emptyLine()])}
                      className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
                    >
                      <Plus className="h-4 w-4" /> Add line
                    </button>
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">{totals.debit.toFixed(2)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{totals.credit.toFixed(2)}</td>
                  <td />
                </tr>
              </tfoot>
            </table>
          </div>
        </CardContent>
      </Card>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <span
          className={cn(
            "text-sm",
            balanced ? "text-primary" : totals.debit || totals.credit ? "text-amber-600" : "text-muted-foreground",
          )}
        >
          {balanced
            ? "Balanced"
            : `Out of balance by ${Math.abs(totals.diff).toFixed(2)}`}
        </span>
        <div className="flex items-center gap-2">
          <Link href="/vouchers">
            <Button variant="ghost" size="sm" type="button">
              Cancel
            </Button>
          </Link>
          <Button variant="outline" size="sm" onClick={() => submit(false)} disabled={saving}>
            Save draft
          </Button>
          <Button size="sm" onClick={() => submit(true)} disabled={saving || !balanced}>
            {saving ? "Saving…" : "Save & Post"}
          </Button>
        </div>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  );
}
