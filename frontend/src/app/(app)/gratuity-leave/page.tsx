"use client";

import { useEffect, useState } from "react";
import { useEntity } from "@/lib/entity-context";
import { listAccounts, type Account } from "@/lib/accounts";
import { listBankAccounts, type BankAccount } from "@/lib/banking";
import {
  accrueGratuity,
  accrueLeave,
  listEmployees,
  listGratuities,
  listLeaves,
  settleGratuity,
  type Employee,
  type Gratuity,
  type Leave,
} from "@/lib/payroll";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const fieldClass =
  "h-9 rounded-md border border-border bg-background px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40";

const money = (v: string) =>
  Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const GRATUITY_STATUS_STYLE: Record<Gratuity["status"], string> = {
  draft: "bg-muted text-muted-foreground",
  posted: "bg-primary/10 text-primary",
  settled: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
};

export default function GratuityLeavePage() {
  const { selectedId, selectedEntity } = useEntity();
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [banks, setBanks] = useState<BankAccount[]>([]);
  const [gratuities, setGratuities] = useState<Gratuity[]>([]);
  const [leaves, setLeaves] = useState<Leave[]>([]);
  const [loadError, setLoadError] = useState("");
  const [error, setError] = useState("");

  const [gForm, setGForm] = useState({
    employee: "",
    as_of_date: "",
    provision_account: "",
    expense_account: "",
  });
  const [accruing, setAccruing] = useState(false);

  const [settleForm, setSettleForm] = useState({
    employee: "",
    as_of_date: "",
    amount: "",
    provision_account: "",
    expense_account: "",
    bank_account: "",
  });
  const [settling, setSettling] = useState(false);

  const [lForm, setLForm] = useState({
    employee: "",
    leave_type: "annual",
    accrued_amount: "",
    entitled_days: "",
    taken_days: "",
    provision_account: "",
    expense_account: "",
    as_of_date: "",
  });
  const [accruingLeave, setAccruingLeave] = useState(false);

  useEffect(() => {
    if (!selectedId) return;
    let active = true;
    Promise.all([
      listEmployees(selectedId),
      listAccounts(selectedId),
      listBankAccounts(selectedId),
      listGratuities(),
      listLeaves(),
    ])
      .then(([emp, acc, b, g, l]) => {
        if (!active) return;
        const empIds = new Set(emp.map((e) => e.id));
        setEmployees(emp.filter((e) => e.status === "active"));
        setAccounts(acc.filter((a) => a.is_active && a.is_postable));
        setBanks(b);
        setGratuities(g.filter((x) => empIds.has(x.employee)));
        setLeaves(l.filter((x) => empIds.has(x.employee)));
      })
      .catch(() => {
        if (active) setLoadError("Couldn't load gratuity/leave records.");
      });
    return () => {
      active = false;
    };
  }, [selectedId]);

  async function accrue() {
    if (!gForm.employee || !gForm.as_of_date || !gForm.provision_account || !gForm.expense_account) {
      return setError("Employee, date, provision account, and expense account are required.");
    }
    setAccruing(true);
    setError("");
    try {
      const gratuity = await accrueGratuity(gForm);
      setGratuities((prev) => [gratuity, ...prev]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setAccruing(false);
    }
  }

  async function settle() {
    if (
      !settleForm.employee ||
      !settleForm.as_of_date ||
      !settleForm.amount ||
      !settleForm.provision_account ||
      !settleForm.expense_account ||
      !settleForm.bank_account
    ) {
      return setError("All settlement fields are required.");
    }
    setSettling(true);
    setError("");
    try {
      const gratuity = await settleGratuity(settleForm);
      setGratuities((prev) => [gratuity, ...prev]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setSettling(false);
    }
  }

  async function accrueLeaveRow() {
    if (
      !lForm.employee ||
      !lForm.accrued_amount ||
      !lForm.provision_account ||
      !lForm.expense_account ||
      !lForm.as_of_date
    ) {
      return setError("Employee, accrued amount, accounts, and date are required.");
    }
    setAccruingLeave(true);
    setError("");
    try {
      const leave = await accrueLeave(lForm);
      setLeaves((prev) => [leave, ...prev]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setAccruingLeave(false);
    }
  }

  if (!selectedId) {
    return (
      <Card>
        <CardContent className="py-12 text-center text-sm text-muted-foreground">
          Pick an entity from the switcher above to manage gratuity and leave.
        </CardContent>
      </Card>
    );
  }
  if (loadError) return <p className="text-sm text-destructive">{loadError}</p>;

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-2xl font-semibold">Gratuity &amp; Leave</h1>
        <p className="text-sm text-muted-foreground">
          {selectedEntity?.numeric_code} ·{" "}
          {selectedEntity?.trade_name || selectedEntity?.legal_name}
        </p>
      </div>

      <section className="flex flex-col gap-4">
        <h2 className="text-lg font-medium">End-of-service gratuity</h2>

        <Card>
          <CardContent className="flex flex-col gap-4 py-5">
            <p className="text-xs font-medium text-muted-foreground">Accrue</p>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <div className="flex flex-col gap-1.5 sm:col-span-2">
                <Label>Employee</Label>
                <select
                  value={gForm.employee}
                  onChange={(e) => setGForm((p) => ({ ...p, employee: e.target.value }))}
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
                <Label>As of date</Label>
                <Input
                  type="date"
                  value={gForm.as_of_date}
                  onChange={(e) => setGForm((p) => ({ ...p, as_of_date: e.target.value }))}
                />
              </div>
              <div className="flex flex-col gap-1.5 sm:col-span-2">
                <Label>Provision account</Label>
                <select
                  value={gForm.provision_account}
                  onChange={(e) => setGForm((p) => ({ ...p, provision_account: e.target.value }))}
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
                <Label>Expense account</Label>
                <select
                  value={gForm.expense_account}
                  onChange={(e) => setGForm((p) => ({ ...p, expense_account: e.target.value }))}
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
            </div>
            <div>
              <Button size="sm" onClick={accrue} disabled={accruing}>
                {accruing ? "Accruing…" : "Accrue gratuity"}
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="flex flex-col gap-4 py-5">
            <p className="text-xs font-medium text-muted-foreground">Settle (final payment)</p>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <div className="flex flex-col gap-1.5 sm:col-span-2">
                <Label>Employee</Label>
                <select
                  value={settleForm.employee}
                  onChange={(e) => setSettleForm((p) => ({ ...p, employee: e.target.value }))}
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
                <Label>As of date</Label>
                <Input
                  type="date"
                  value={settleForm.as_of_date}
                  onChange={(e) => setSettleForm((p) => ({ ...p, as_of_date: e.target.value }))}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label>Amount</Label>
                <Input
                  type="number"
                  inputMode="decimal"
                  value={settleForm.amount}
                  onChange={(e) => setSettleForm((p) => ({ ...p, amount: e.target.value }))}
                />
              </div>
              <div className="flex flex-col gap-1.5 sm:col-span-2">
                <Label>Provision account</Label>
                <select
                  value={settleForm.provision_account}
                  onChange={(e) =>
                    setSettleForm((p) => ({ ...p, provision_account: e.target.value }))
                  }
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
                <Label>Expense account</Label>
                <select
                  value={settleForm.expense_account}
                  onChange={(e) =>
                    setSettleForm((p) => ({ ...p, expense_account: e.target.value }))
                  }
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
                  value={settleForm.bank_account}
                  onChange={(e) => setSettleForm((p) => ({ ...p, bank_account: e.target.value }))}
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
              <Button size="sm" onClick={settle} disabled={settling}>
                {settling ? "Settling…" : "Settle gratuity"}
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
                  <th className="px-4 py-2 font-medium">As of</th>
                  <th className="px-4 py-2 font-medium">Type</th>
                  <th className="px-4 py-2 text-right font-medium">Amount</th>
                  <th className="px-4 py-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {gratuities.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">
                      No gratuity records yet.
                    </td>
                  </tr>
                ) : (
                  gratuities.map((g) => (
                    <tr key={g.id} className="border-b border-border/60 last:border-0">
                      <td className="px-4 py-2">
                        {g.employee_code} · {g.employee_name}
                      </td>
                      <td className="px-4 py-2 text-muted-foreground">{g.as_of_date}</td>
                      <td className="px-4 py-2 capitalize">{g.type}</td>
                      <td className="px-4 py-2 text-right tabular-nums">{money(g.amount)}</td>
                      <td className="px-4 py-2">
                        <span
                          className={cn(
                            "rounded-full px-2 py-0.5 text-xs font-medium capitalize",
                            GRATUITY_STATUS_STYLE[g.status],
                          )}
                        >
                          {g.status}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </CardContent>
        </Card>
      </section>

      <section className="flex flex-col gap-4">
        <h2 className="text-lg font-medium">Leave salary accrual</h2>

        <Card>
          <CardContent className="flex flex-col gap-4 py-5">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <div className="flex flex-col gap-1.5 sm:col-span-2">
                <Label>Employee</Label>
                <select
                  value={lForm.employee}
                  onChange={(e) => setLForm((p) => ({ ...p, employee: e.target.value }))}
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
                <Label>Leave type</Label>
                <select
                  value={lForm.leave_type}
                  onChange={(e) => setLForm((p) => ({ ...p, leave_type: e.target.value }))}
                  className={fieldClass}
                >
                  <option value="annual">Annual</option>
                  <option value="sick">Sick</option>
                  <option value="unpaid">Unpaid</option>
                </select>
              </div>
              <div className="flex flex-col gap-1.5">
                <Label>As of date</Label>
                <Input
                  type="date"
                  value={lForm.as_of_date}
                  onChange={(e) => setLForm((p) => ({ ...p, as_of_date: e.target.value }))}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label>Accrued amount</Label>
                <Input
                  type="number"
                  inputMode="decimal"
                  value={lForm.accrued_amount}
                  onChange={(e) => setLForm((p) => ({ ...p, accrued_amount: e.target.value }))}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label>Entitled days</Label>
                <Input
                  type="number"
                  value={lForm.entitled_days}
                  onChange={(e) => setLForm((p) => ({ ...p, entitled_days: e.target.value }))}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label>Taken days</Label>
                <Input
                  type="number"
                  value={lForm.taken_days}
                  onChange={(e) => setLForm((p) => ({ ...p, taken_days: e.target.value }))}
                />
              </div>
              <div className="flex flex-col gap-1.5 sm:col-span-2">
                <Label>Provision account</Label>
                <select
                  value={lForm.provision_account}
                  onChange={(e) => setLForm((p) => ({ ...p, provision_account: e.target.value }))}
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
                <Label>Expense account</Label>
                <select
                  value={lForm.expense_account}
                  onChange={(e) => setLForm((p) => ({ ...p, expense_account: e.target.value }))}
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
            </div>
            <div>
              <Button size="sm" onClick={accrueLeaveRow} disabled={accruingLeave}>
                {accruingLeave ? "Accruing…" : "Accrue leave salary"}
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
                  <th className="px-4 py-2 font-medium">As of</th>
                  <th className="px-4 py-2 font-medium">Type</th>
                  <th className="px-4 py-2 text-right font-medium">Balance days</th>
                  <th className="px-4 py-2 text-right font-medium">Accrued</th>
                </tr>
              </thead>
              <tbody>
                {leaves.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">
                      No leave accrual records yet.
                    </td>
                  </tr>
                ) : (
                  leaves.map((l) => (
                    <tr key={l.id} className="border-b border-border/60 last:border-0">
                      <td className="px-4 py-2">
                        {l.employee_code} · {l.employee_name}
                      </td>
                      <td className="px-4 py-2 text-muted-foreground">{l.as_of_date}</td>
                      <td className="px-4 py-2 capitalize">{l.leave_type}</td>
                      <td className="px-4 py-2 text-right tabular-nums">{l.balance_days}</td>
                      <td className="px-4 py-2 text-right tabular-nums">
                        {money(l.accrued_amount)}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </CardContent>
        </Card>
      </section>

      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  );
}
