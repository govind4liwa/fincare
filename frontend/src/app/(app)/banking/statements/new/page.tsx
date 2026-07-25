"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Plus, Trash2 } from "lucide-react";
import { useEntity } from "@/lib/entity-context";
import { listBankAccounts, createStatement, type BankAccount } from "@/lib/banking";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

type Line = { txn_date: string; description: string; reference: string; deposit: string; withdrawal: string };

const emptyLine = (): Line => ({ txn_date: "", description: "", reference: "", deposit: "", withdrawal: "" });
const num = (v: string) => (Number.isFinite(Number(v)) ? Number(v) : 0);
const money = (n: number) =>
  n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function NewStatementPage() {
  const router = useRouter();
  const { selectedId, selectedEntity } = useEntity();
  const [banks, setBanks] = useState<BankAccount[]>([]);
  const [bankAccount, setBankAccount] = useState("");
  const [statementDate, setStatementDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [openingBalance, setOpeningBalance] = useState("");
  const [closingBalance, setClosingBalance] = useState("");
  const [lines, setLines] = useState<Line[]>([emptyLine()]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!selectedId) return;
    let active = true;
    listBankAccounts(selectedId)
      .then((rows) => {
        if (active) setBanks(rows.filter((b) => b.is_active));
      })
      .catch(() => {
        if (active) setError("Couldn't load bank accounts.");
      });
    return () => {
      active = false;
    };
  }, [selectedId]);

  const totals = useMemo(() => {
    const deposits = lines.reduce((s, l) => s + num(l.deposit), 0);
    const withdrawals = lines.reduce((s, l) => s + num(l.withdrawal), 0);
    return { deposits, withdrawals, net: deposits - withdrawals };
  }, [lines]);

  function updateLine(i: number, field: keyof Line, value: string) {
    setLines((prev) =>
      prev.map((l, idx) => {
        if (idx !== i) return l;
        const next = { ...l, [field]: value };
        if (field === "deposit" && value) next.withdrawal = "";
        if (field === "withdrawal" && value) next.deposit = "";
        return next;
      }),
    );
  }

  async function submit() {
    setError("");
    if (!bankAccount) return setError("Select a bank account.");
    const filled = lines.filter((l) => l.txn_date && (num(l.deposit) > 0 || num(l.withdrawal) > 0));
    if (filled.length === 0) return setError("Add at least one line with a date and an amount.");
    setSaving(true);
    try {
      await createStatement({
        entity: selectedId!,
        bank_account: bankAccount,
        statement_date: statementDate,
        opening_balance: openingBalance || "0",
        closing_balance: closingBalance || "0",
        lines: filled.map((l) => ({
          txn_date: l.txn_date,
          description: l.description,
          reference: l.reference,
          deposit: l.deposit || "0",
          withdrawal: l.withdrawal || "0",
        })),
      });
      router.push("/reconcile");
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
          Pick an entity from the switcher above to enter a statement.
        </CardContent>
      </Card>
    );
  }

  const fieldClass =
    "h-9 rounded-md border border-border bg-background px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40";

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">New Bank Statement</h1>
        <p className="text-sm text-muted-foreground">
          {selectedEntity?.numeric_code} · {selectedEntity?.trade_name || selectedEntity?.legal_name}
        </p>
      </div>

      <Card>
        <CardContent className="grid grid-cols-1 gap-4 py-5 sm:grid-cols-2 lg:grid-cols-4">
          <div className="flex flex-col gap-1.5">
            <Label>Bank account</Label>
            <select
              value={bankAccount}
              onChange={(e) => setBankAccount(e.target.value)}
              className={fieldClass}
            >
              <option value="">Select…</option>
              {banks.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.code} · {b.name}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Statement date</Label>
            <Input
              type="date"
              value={statementDate}
              onChange={(e) => setStatementDate(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Opening balance</Label>
            <Input
              type="number"
              inputMode="decimal"
              value={openingBalance}
              onChange={(e) => setOpeningBalance(e.target.value)}
              className="text-right tabular-nums"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Closing balance</Label>
            <Input
              type="number"
              inputMode="decimal"
              value={closingBalance}
              onChange={(e) => setClosingBalance(e.target.value)}
              className="text-right tabular-nums"
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-border text-left text-xs text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 font-medium">Date</th>
                  <th className="px-3 py-2 font-medium">Description</th>
                  <th className="px-3 py-2 font-medium">Reference</th>
                  <th className="px-3 py-2 text-right font-medium">Deposit</th>
                  <th className="px-3 py-2 text-right font-medium">Withdrawal</th>
                  <th className="w-10" />
                </tr>
              </thead>
              <tbody>
                {lines.map((l, i) => (
                  <tr key={i} className="border-b border-border/60">
                    <td className="px-3 py-1.5">
                      <Input
                        type="date"
                        value={l.txn_date}
                        onChange={(e) => updateLine(i, "txn_date", e.target.value)}
                        className="h-9 w-40"
                      />
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
                        value={l.reference}
                        onChange={(e) => updateLine(i, "reference", e.target.value)}
                        className="h-9 w-32"
                      />
                    </td>
                    <td className="px-3 py-1.5">
                      <Input
                        type="number"
                        inputMode="decimal"
                        value={l.deposit}
                        onChange={(e) => updateLine(i, "deposit", e.target.value)}
                        className="h-9 w-28 text-right tabular-nums"
                      />
                    </td>
                    <td className="px-3 py-1.5">
                      <Input
                        type="number"
                        inputMode="decimal"
                        value={l.withdrawal}
                        onChange={(e) => updateLine(i, "withdrawal", e.target.value)}
                        className="h-9 w-28 text-right tabular-nums"
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
                <tr className="border-t border-border font-medium">
                  <td className="px-3 py-2" colSpan={3}>
                    <button
                      type="button"
                      onClick={() => setLines((p) => [...p, emptyLine()])}
                      className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
                    >
                      <Plus className="h-4 w-4" /> Add line
                    </button>
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">{money(totals.deposits)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{money(totals.withdrawals)}</td>
                  <td />
                </tr>
              </tfoot>
            </table>
          </div>
        </CardContent>
      </Card>

      <div className="flex items-center justify-between gap-3">
        <span className="text-sm text-muted-foreground">
          Net movement: <span className="tabular-nums text-foreground">{money(totals.net)}</span>
        </span>
        <div className="flex items-center gap-2">
          <Link href="/reconcile">
            <Button variant="ghost" size="sm" type="button">
              Cancel
            </Button>
          </Link>
          <Button size="sm" onClick={submit} disabled={saving}>
            {saving ? "Saving…" : "Save statement"}
          </Button>
        </div>
      </div>

      {error && <p className={cn("text-sm text-destructive")}>{error}</p>}
    </div>
  );
}
