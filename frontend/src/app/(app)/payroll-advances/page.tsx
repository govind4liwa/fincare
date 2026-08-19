"use client";

import { useEffect, useState } from "react";
import { useEntity } from "@/lib/entity-context";
import { listAccounts, type Account } from "@/lib/accounts";
import { listBankAccounts, type BankAccount } from "@/lib/banking";
import { listEmployees, type Employee } from "@/lib/payroll";
import { createAdvance, listAdvances, payAdvance, type Advance } from "@/lib/payroll";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const fieldClass =
  "h-9 rounded-md border border-border bg-background px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40";

const money = (v: string) =>
  Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const STATUS_STYLE: Record<Advance["status"], string> = {
  open: "bg-muted text-muted-foreground",
  recovering: "bg-amber-500/10 text-amber-700 dark:text-amber-400",
  cleared: "bg-primary/10 text-primary",
};

export default function PayrollAdvancesPage() {
  const { selectedId, selectedEntity } = useEntity();
  const [advances, setAdvances] = useState<Advance[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [banks, setBanks] = useState<BankAccount[]>([]);
  const [loadError, setLoadError] = useState("");
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState("");

  const [form, setForm] = useState({
    employee: "",
    advance_date: "",
    amount: "",
    installments: "1",
    installment_amount: "",
    advance_account: "",
    bank_account: "",
  });
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    if (!selectedId) return;
    let active = true;
    Promise.all([
      listAdvances(selectedId),
      listEmployees(selectedId),
      listAccounts(selectedId),
      listBankAccounts(selectedId),
    ])
      .then(([a, e, acc, b]) => {
        if (!active) return;
        setAdvances(a);
        setEmployees(e.filter((x) => x.status === "active"));
        setAccounts(acc.filter((x) => x.is_active && x.is_postable));
        setBanks(b);
      })
      .catch(() => {
        if (active) setLoadError("Couldn't load advances.");
      });
    return () => {
      active = false;
    };
  }, [selectedId]);

  async function create() {
    if (!selectedId) return;
    if (!form.employee || !form.advance_date || !form.amount || !form.advance_account || !form.bank_account) {
      return setError("Employee, date, amount, advance account, and bank account are required.");
    }
    setCreating(true);
    setError("");
    try {
      const advance = await createAdvance({
        entity: selectedId,
        employee: form.employee,
        advance_date: form.advance_date,
        amount: form.amount,
        installments: Number(form.installments) || 1,
        installment_amount: form.installment_amount || "0",
        advance_account: form.advance_account,
        bank_account: form.bank_account,
      });
      setAdvances((prev) => [advance, ...prev]);
      setForm((p) => ({ ...p, amount: "", installment_amount: "" }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setCreating(false);
    }
  }

  async function pay(id: string) {
    setBusyId(id);
    setError("");
    try {
      const updated = await payAdvance(id);
      setAdvances((prev) => prev.map((a) => (a.id === id ? updated : a)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setBusyId("");
    }
  }

  if (!selectedId) {
    return (
      <Card>
        <CardContent className="py-12 text-center text-sm text-muted-foreground">
          Pick an entity from the switcher above to manage salary advances.
        </CardContent>
      </Card>
    );
  }
  if (loadError) return <p className="text-sm text-destructive">{loadError}</p>;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">Salary Advances</h1>
        <p className="text-sm text-muted-foreground">
          {selectedEntity?.numeric_code} ·{" "}
          {selectedEntity?.trade_name || selectedEntity?.legal_name} — paid now, recovered
          automatically from future payroll runs.
        </p>
      </div>

      <Card>
        <CardContent className="flex flex-col gap-4 py-5">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div className="flex flex-col gap-1.5 sm:col-span-2">
              <Label>Employee</Label>
              <select
                value={form.employee}
                onChange={(e) => setForm((p) => ({ ...p, employee: e.target.value }))}
                className={fieldClass}
              >
                <option value="">Select…</option>
                {employees.map((emp) => (
                  <option key={emp.id} value={emp.id}>
                    {emp.code} · {emp.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Date</Label>
              <Input
                type="date"
                value={form.advance_date}
                onChange={(e) => setForm((p) => ({ ...p, advance_date: e.target.value }))}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Amount</Label>
              <Input
                type="number"
                inputMode="decimal"
                value={form.amount}
                onChange={(e) => setForm((p) => ({ ...p, amount: e.target.value }))}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Installments</Label>
              <Input
                type="number"
                value={form.installments}
                onChange={(e) => setForm((p) => ({ ...p, installments: e.target.value }))}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Installment amount (optional)</Label>
              <Input
                type="number"
                inputMode="decimal"
                placeholder="Even split if left blank"
                value={form.installment_amount}
                onChange={(e) => setForm((p) => ({ ...p, installment_amount: e.target.value }))}
              />
            </div>
            <div className="flex flex-col gap-1.5 sm:col-span-2">
              <Label>Advance account (Staff Advances)</Label>
              <select
                value={form.advance_account}
                onChange={(e) => setForm((p) => ({ ...p, advance_account: e.target.value }))}
                className={fieldClass}
              >
                <option value="">Select…</option>
                {accounts.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.code} · {a.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5 sm:col-span-2">
              <Label>Pay from</Label>
              <select
                value={form.bank_account}
                onChange={(e) => setForm((p) => ({ ...p, bank_account: e.target.value }))}
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
          </div>
          <div>
            <Button size="sm" onClick={create} disabled={creating}>
              {creating ? "Creating…" : "New advance"}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          <table className="w-full text-sm">
            <thead className="border-b border-border text-left text-xs text-muted-foreground">
              <tr>
                <th className="px-4 py-2 font-medium">Employee</th>
                <th className="px-4 py-2 font-medium">Date</th>
                <th className="px-4 py-2 text-right font-medium">Amount</th>
                <th className="px-4 py-2 text-right font-medium">Recovered</th>
                <th className="px-4 py-2 text-right font-medium">Balance</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 text-right font-medium" />
              </tr>
            </thead>
            <tbody>
              {advances.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">
                    No salary advances yet.
                  </td>
                </tr>
              ) : (
                advances.map((a) => (
                  <tr key={a.id} className="border-b border-border/60 last:border-0">
                    <td className="px-4 py-2">
                      {a.employee_code} · {a.employee_name}
                    </td>
                    <td className="px-4 py-2 text-muted-foreground">{a.advance_date}</td>
                    <td className="px-4 py-2 text-right tabular-nums">{money(a.amount)}</td>
                    <td className="px-4 py-2 text-right tabular-nums">
                      {money(a.recovered_amount)}
                    </td>
                    <td className="px-4 py-2 text-right tabular-nums">{money(a.balance)}</td>
                    <td className="px-4 py-2">
                      <span
                        className={cn(
                          "rounded-full px-2 py-0.5 text-xs font-medium capitalize",
                          STATUS_STYLE[a.status],
                        )}
                      >
                        {a.status}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-right">
                      {a.status === "open" && !a.journal_entry && (
                        <Button size="sm" disabled={busyId === a.id} onClick={() => pay(a.id)}>
                          {busyId === a.id ? "Paying…" : "Pay"}
                        </Button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </CardContent>
      </Card>

      <p className="text-xs text-muted-foreground">
        Pay books DR Staff Advances / CR Bank. Recovery then happens automatically — each payroll
        run&apos;s Build step deducts one installment per open advance until it&apos;s cleared.
      </p>

      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  );
}
