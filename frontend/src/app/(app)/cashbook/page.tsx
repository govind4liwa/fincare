"use client";

import { useEffect, useState } from "react";
import { useEntity } from "@/lib/entity-context";
import { listAccounts, type Account } from "@/lib/accounts";
import { listBankAccounts, type BankAccount } from "@/lib/banking";
import {
  createCashAccount,
  createCashCount,
  createPettyCashFloat,
  createReplenishment,
  listCashAccounts,
  listCashCounts,
  listPettyCashFloats,
  listReplenishments,
  postCashCount,
  postReplenishment,
  type CashAccount,
  type CashCount,
  type PettyCashFloat,
  type Replenishment,
} from "@/lib/cashbook";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const fieldClass =
  "h-9 rounded-md border border-border bg-background px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40";

const money = (v: string) =>
  Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const STATUS_STYLE: Record<string, string> = {
  draft: "bg-muted text-muted-foreground",
  posted: "bg-primary/10 text-primary",
  reversed: "bg-destructive/10 text-destructive",
  cancelled: "bg-destructive/10 text-destructive",
};

export default function CashbookPage() {
  const { selectedId, selectedEntity } = useEntity();
  const [cashAccounts, setCashAccounts] = useState<CashAccount[]>([]);
  const [floats, setFloats] = useState<PettyCashFloat[]>([]);
  const [banks, setBanks] = useState<BankAccount[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [replenishments, setReplenishments] = useState<Replenishment[]>([]);
  const [counts, setCounts] = useState<CashCount[]>([]);
  const [loadError, setLoadError] = useState("");
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState("");

  const [accountForm, setAccountForm] = useState({ code: "", name: "", gl_account: "" });
  const [floatForm, setFloatForm] = useState({
    cash_account: "",
    code: "",
    float_amount: "",
    custodian: "",
  });
  const [repForm, setRepForm] = useState({
    petty_cash_float: "",
    bank_account: "",
    replenish_date: "",
    amount: "",
    reference: "",
  });
  const [countForm, setCountForm] = useState({
    cash_account: "",
    count_date: "",
    counted_by: "",
    expected_amount: "",
    variance_account: "",
  });
  const [denomRows, setDenomRows] = useState([{ denomination_value: "", quantity: "" }]);
  const [creating, setCreating] = useState("");

  useEffect(() => {
    if (!selectedId) return;
    let active = true;
    Promise.all([
      listCashAccounts(selectedId),
      listPettyCashFloats(selectedId),
      listBankAccounts(selectedId),
      listAccounts(selectedId),
      listReplenishments(selectedId),
      listCashCounts(selectedId),
    ])
      .then(([ca, pf, b, acc, rep, cnt]) => {
        if (!active) return;
        setCashAccounts(ca);
        setFloats(pf);
        setBanks(b);
        setAccounts(acc.filter((a) => a.is_active && a.is_postable));
        setReplenishments(rep);
        setCounts(cnt);
      })
      .catch(() => {
        if (active) setLoadError("Couldn't load cashbook data.");
      });
    return () => {
      active = false;
    };
  }, [selectedId]);

  async function createAccount() {
    if (!selectedId || !accountForm.code || !accountForm.name || !accountForm.gl_account) {
      return setError("Code, name, and GL account are required.");
    }
    setCreating("account");
    setError("");
    try {
      const acc = await createCashAccount({ entity: selectedId, ...accountForm });
      setCashAccounts((prev) => [...prev, acc]);
      setAccountForm({ code: "", name: "", gl_account: "" });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setCreating("");
    }
  }

  async function createFloat() {
    if (!selectedId || !floatForm.cash_account || !floatForm.code) {
      return setError("Cash account and code are required.");
    }
    setCreating("float");
    setError("");
    try {
      const created = await createPettyCashFloat({
        entity: selectedId,
        cash_account: floatForm.cash_account,
        code: floatForm.code,
        float_amount: floatForm.float_amount || "0",
        custodian: floatForm.custodian,
      });
      setFloats((prev) => [...prev, created]);
      setFloatForm({ cash_account: "", code: "", float_amount: "", custodian: "" });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setCreating("");
    }
  }

  async function createRep() {
    if (!selectedId || !repForm.petty_cash_float || !repForm.bank_account || !repForm.replenish_date || !repForm.amount) {
      return setError("Float, bank account, date, and amount are required.");
    }
    setCreating("rep");
    setError("");
    try {
      const rep = await createReplenishment({ entity: selectedId, ...repForm });
      setReplenishments((prev) => [rep, ...prev]);
      setRepForm({ petty_cash_float: "", bank_account: "", replenish_date: "", amount: "", reference: "" });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setCreating("");
    }
  }

  async function payRep(id: string) {
    setBusyId(id);
    setError("");
    try {
      const updated = await postReplenishment(id);
      setReplenishments((prev) => prev.map((r) => (r.id === id ? updated : r)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setBusyId("");
    }
  }

  const denomTotal = denomRows.reduce(
    (sum, r) => sum + (Number(r.denomination_value) || 0) * (Number(r.quantity) || 0),
    0,
  );

  async function createCount() {
    const rows = denomRows
      .filter((r) => r.denomination_value && r.quantity)
      .map((r) => ({ denomination_value: r.denomination_value, quantity: Number(r.quantity) }));
    if (!selectedId || !countForm.cash_account || !countForm.count_date || rows.length === 0) {
      return setError("Cash account, date, and at least one denomination line are required.");
    }
    setCreating("count");
    setError("");
    try {
      const count = await createCashCount({
        entity: selectedId,
        cash_account: countForm.cash_account,
        count_date: countForm.count_date,
        counted_by: countForm.counted_by,
        expected_amount: countForm.expected_amount || "0",
        variance_account: countForm.variance_account || undefined,
        denominations: rows,
      });
      setCounts((prev) => [count, ...prev]);
      setCountForm({ cash_account: "", count_date: "", counted_by: "", expected_amount: "", variance_account: "" });
      setDenomRows([{ denomination_value: "", quantity: "" }]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setCreating("");
    }
  }

  async function finalizeCount(id: string) {
    setBusyId(id);
    setError("");
    try {
      const updated = await postCashCount(id);
      setCounts((prev) => prev.map((c) => (c.id === id ? updated : c)));
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
          Pick an entity from the switcher above to manage the cashbook.
        </CardContent>
      </Card>
    );
  }
  if (loadError) return <p className="text-sm text-destructive">{loadError}</p>;

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-2xl font-semibold">Cashbook</h1>
        <p className="text-sm text-muted-foreground">
          {selectedEntity?.numeric_code} ·{" "}
          {selectedEntity?.trade_name || selectedEntity?.legal_name} — petty-cash floats,
          replenishments, and physical cash counts.
        </p>
      </div>

      <section className="flex flex-col gap-4">
        <h2 className="text-lg font-medium">Cash accounts &amp; floats</h2>
        <div className="grid gap-4 md:grid-cols-2">
          <Card>
            <CardContent className="flex flex-col gap-3 py-5">
              <p className="text-xs font-medium text-muted-foreground">New cash account</p>
              <div className="grid grid-cols-2 gap-2">
                <Input
                  placeholder="Code"
                  value={accountForm.code}
                  onChange={(e) => setAccountForm((p) => ({ ...p, code: e.target.value }))}
                />
                <Input
                  placeholder="Name"
                  value={accountForm.name}
                  onChange={(e) => setAccountForm((p) => ({ ...p, name: e.target.value }))}
                />
                <select
                  value={accountForm.gl_account}
                  onChange={(e) => setAccountForm((p) => ({ ...p, gl_account: e.target.value }))}
                  className={cn(fieldClass, "col-span-2")}
                >
                  <option value="">GL account…</option>
                  {accounts.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.code} · {a.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <Button size="sm" onClick={createAccount} disabled={creating === "account"}>
                  {creating === "account" ? "Saving…" : "Add cash account"}
                </Button>
              </div>
              <ul className="flex flex-col gap-1 text-xs text-muted-foreground">
                {cashAccounts.map((a) => (
                  <li key={a.id}>
                    {a.code} · {a.name} ({a.gl_account_code})
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="flex flex-col gap-3 py-5">
              <p className="text-xs font-medium text-muted-foreground">New petty-cash float</p>
              <div className="grid grid-cols-2 gap-2">
                <select
                  value={floatForm.cash_account}
                  onChange={(e) => setFloatForm((p) => ({ ...p, cash_account: e.target.value }))}
                  className={cn(fieldClass, "col-span-2")}
                >
                  <option value="">Cash account…</option>
                  {cashAccounts.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.code} · {a.name}
                    </option>
                  ))}
                </select>
                <Input
                  placeholder="Code"
                  value={floatForm.code}
                  onChange={(e) => setFloatForm((p) => ({ ...p, code: e.target.value }))}
                />
                <Input
                  type="number"
                  inputMode="decimal"
                  placeholder="Float amount"
                  value={floatForm.float_amount}
                  onChange={(e) => setFloatForm((p) => ({ ...p, float_amount: e.target.value }))}
                />
                <Input
                  placeholder="Custodian"
                  className="col-span-2"
                  value={floatForm.custodian}
                  onChange={(e) => setFloatForm((p) => ({ ...p, custodian: e.target.value }))}
                />
              </div>
              <div>
                <Button size="sm" onClick={createFloat} disabled={creating === "float"}>
                  {creating === "float" ? "Saving…" : "Add float"}
                </Button>
              </div>
              <ul className="flex flex-col gap-1 text-xs text-muted-foreground">
                {floats.map((f) => (
                  <li key={f.id}>
                    {f.code} · {f.cash_account_code} · {money(f.float_amount)} ({f.custodian})
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        </div>
      </section>

      <section className="flex flex-col gap-4">
        <h2 className="text-lg font-medium">Replenishments</h2>
        <Card>
          <CardContent className="flex flex-col gap-3 py-5">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
              <select
                value={repForm.petty_cash_float}
                onChange={(e) => setRepForm((p) => ({ ...p, petty_cash_float: e.target.value }))}
                className={cn(fieldClass, "sm:col-span-2")}
              >
                <option value="">Float…</option>
                {floats.map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.code} · {f.cash_account_code}
                  </option>
                ))}
              </select>
              <select
                value={repForm.bank_account}
                onChange={(e) => setRepForm((p) => ({ ...p, bank_account: e.target.value }))}
                className={fieldClass}
              >
                <option value="">Bank…</option>
                {banks.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.code}
                  </option>
                ))}
              </select>
              <Input
                type="date"
                value={repForm.replenish_date}
                onChange={(e) => setRepForm((p) => ({ ...p, replenish_date: e.target.value }))}
              />
              <Input
                type="number"
                inputMode="decimal"
                placeholder="Amount"
                value={repForm.amount}
                onChange={(e) => setRepForm((p) => ({ ...p, amount: e.target.value }))}
              />
            </div>
            <div>
              <Button size="sm" onClick={createRep} disabled={creating === "rep"}>
                {creating === "rep" ? "Creating…" : "New replenishment"}
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-0">
            <table className="w-full text-sm">
              <thead className="border-b border-border text-left text-xs text-muted-foreground">
                <tr>
                  <th className="px-4 py-2 font-medium">No.</th>
                  <th className="px-4 py-2 font-medium">Date</th>
                  <th className="px-4 py-2 font-medium">Float</th>
                  <th className="px-4 py-2 text-right font-medium">Amount</th>
                  <th className="px-4 py-2 font-medium">Status</th>
                  <th className="px-4 py-2 text-right font-medium" />
                </tr>
              </thead>
              <tbody>
                {replenishments.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">
                      No replenishments yet.
                    </td>
                  </tr>
                ) : (
                  replenishments.map((r) => (
                    <tr key={r.id} className="border-b border-border/60 last:border-0">
                      <td className="px-4 py-2 text-muted-foreground">{r.replenish_no || "—"}</td>
                      <td className="px-4 py-2 text-muted-foreground">{r.replenish_date}</td>
                      <td className="px-4 py-2">{r.cash_account_code}</td>
                      <td className="px-4 py-2 text-right tabular-nums">{money(r.amount)}</td>
                      <td className="px-4 py-2">
                        <span
                          className={cn(
                            "rounded-full px-2 py-0.5 text-xs font-medium capitalize",
                            STATUS_STYLE[r.status],
                          )}
                        >
                          {r.status}
                        </span>
                      </td>
                      <td className="px-4 py-2 text-right">
                        {r.status === "draft" && (
                          <Button size="sm" disabled={busyId === r.id} onClick={() => payRep(r.id)}>
                            {busyId === r.id ? "Posting…" : "Post"}
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
      </section>

      <section className="flex flex-col gap-4">
        <h2 className="text-lg font-medium">Cash counts</h2>
        <Card>
          <CardContent className="flex flex-col gap-4 py-5">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <select
                value={countForm.cash_account}
                onChange={(e) => setCountForm((p) => ({ ...p, cash_account: e.target.value }))}
                className={fieldClass}
              >
                <option value="">Cash account…</option>
                {cashAccounts.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.code} · {a.name}
                  </option>
                ))}
              </select>
              <Input
                type="date"
                value={countForm.count_date}
                onChange={(e) => setCountForm((p) => ({ ...p, count_date: e.target.value }))}
              />
              <Input
                placeholder="Counted by"
                value={countForm.counted_by}
                onChange={(e) => setCountForm((p) => ({ ...p, counted_by: e.target.value }))}
              />
              <Input
                type="number"
                inputMode="decimal"
                placeholder="Expected amount"
                value={countForm.expected_amount}
                onChange={(e) => setCountForm((p) => ({ ...p, expected_amount: e.target.value }))}
              />
              <select
                value={countForm.variance_account}
                onChange={(e) => setCountForm((p) => ({ ...p, variance_account: e.target.value }))}
                className={cn(fieldClass, "sm:col-span-2")}
              >
                <option value="">Variance account (if short/over)…</option>
                {accounts.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.code} · {a.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex flex-col gap-2">
              <Label>Denomination tally</Label>
              {denomRows.map((row, i) => (
                <div key={i} className="flex items-center gap-2">
                  <Input
                    type="number"
                    inputMode="decimal"
                    placeholder="Value (e.g. 100)"
                    value={row.denomination_value}
                    onChange={(e) =>
                      setDenomRows((prev) =>
                        prev.map((r, idx) => (idx === i ? { ...r, denomination_value: e.target.value } : r)),
                      )
                    }
                    className="w-40"
                  />
                  <Input
                    type="number"
                    placeholder="Qty"
                    value={row.quantity}
                    onChange={(e) =>
                      setDenomRows((prev) =>
                        prev.map((r, idx) => (idx === i ? { ...r, quantity: e.target.value } : r)),
                      )
                    }
                    className="w-24"
                  />
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => setDenomRows((prev) => prev.filter((_, idx) => idx !== i))}
                    disabled={denomRows.length === 1}
                  >
                    Remove
                  </Button>
                </div>
              ))}
              <div className="flex items-center gap-3">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() =>
                    setDenomRows((prev) => [...prev, { denomination_value: "", quantity: "" }])
                  }
                >
                  Add line
                </Button>
                <span className="text-xs text-muted-foreground">
                  Counted total: {money(String(denomTotal))}
                </span>
              </div>
            </div>

            <div>
              <Button size="sm" onClick={createCount} disabled={creating === "count"}>
                {creating === "count" ? "Creating…" : "New cash count"}
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-0">
            <table className="w-full text-sm">
              <thead className="border-b border-border text-left text-xs text-muted-foreground">
                <tr>
                  <th className="px-4 py-2 font-medium">No.</th>
                  <th className="px-4 py-2 font-medium">Date</th>
                  <th className="px-4 py-2 text-right font-medium">Expected</th>
                  <th className="px-4 py-2 text-right font-medium">Counted</th>
                  <th className="px-4 py-2 text-right font-medium">Variance</th>
                  <th className="px-4 py-2 font-medium">Status</th>
                  <th className="px-4 py-2 text-right font-medium" />
                </tr>
              </thead>
              <tbody>
                {counts.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">
                      No cash counts yet.
                    </td>
                  </tr>
                ) : (
                  counts.map((c) => (
                    <tr key={c.id} className="border-b border-border/60 last:border-0">
                      <td className="px-4 py-2 text-muted-foreground">{c.count_no || "—"}</td>
                      <td className="px-4 py-2 text-muted-foreground">{c.count_date}</td>
                      <td className="px-4 py-2 text-right tabular-nums">
                        {money(c.expected_amount)}
                      </td>
                      <td className="px-4 py-2 text-right tabular-nums">
                        {c.status === "draft" ? "—" : money(c.counted_amount)}
                      </td>
                      <td className="px-4 py-2 text-right tabular-nums">
                        {c.status === "draft" ? "—" : money(c.variance)}
                      </td>
                      <td className="px-4 py-2">
                        <span
                          className={cn(
                            "rounded-full px-2 py-0.5 text-xs font-medium capitalize",
                            STATUS_STYLE[c.status],
                          )}
                        >
                          {c.status}
                        </span>
                      </td>
                      <td className="px-4 py-2 text-right">
                        {c.status === "draft" && (
                          <Button
                            size="sm"
                            disabled={busyId === c.id}
                            onClick={() => finalizeCount(c.id)}
                          >
                            {busyId === c.id ? "Posting…" : "Post"}
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
      </section>

      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  );
}
