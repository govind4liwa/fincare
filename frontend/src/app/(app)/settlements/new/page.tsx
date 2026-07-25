"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Plus, Trash2 } from "lucide-react";
import { useEntity } from "@/lib/entity-context";
import { listAccounts, type Account } from "@/lib/accounts";
import { listBankAccounts, type BankAccount } from "@/lib/banking";
import { listDrivers, listVehicles, type Driver, type Vehicle } from "@/lib/fleet";
import {
  DEDUCTION_KINDS,
  createSettlement,
  listOutstandingAdvances,
  postSettlement,
  type Advance,
  type DeductionKind,
} from "@/lib/settlements";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

type Line = {
  kind: DeductionKind;
  account: string;
  amount: string;
  advance: string;
  description: string;
};

const emptyLine = (): Line => ({
  kind: "commission",
  account: "",
  amount: "",
  advance: "",
  description: "",
});
const num = (v: string) => (Number.isFinite(Number(v)) ? Number(v) : 0);
const money = (n: number) =>
  n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const today = () => new Date().toISOString().slice(0, 10);

export default function NewSettlementPage() {
  const router = useRouter();
  const { selectedId, selectedEntity } = useEntity();
  const [drivers, setDrivers] = useState<Driver[]>([]);
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [banks, setBanks] = useState<BankAccount[]>([]);
  const [advances, setAdvances] = useState<Advance[]>([]);

  const [driver, setDriver] = useState("");
  const [vehicle, setVehicle] = useState("");
  const [periodStart, setPeriodStart] = useState(today);
  const [periodEnd, setPeriodEnd] = useState(today);
  const [settlementDate, setSettlementDate] = useState(today);
  const [gross, setGross] = useState("");
  const [grossAccount, setGrossAccount] = useState("");
  const [payAccount, setPayAccount] = useState("");
  const [receivableAccount, setReceivableAccount] = useState("");
  const [allowNegative, setAllowNegative] = useState(false);
  const [lines, setLines] = useState<Line[]>([emptyLine()]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!selectedId) return;
    let active = true;
    Promise.all([
      listDrivers(selectedId),
      listVehicles(selectedId),
      listAccounts(selectedId),
      listBankAccounts(selectedId),
    ])
      .then(([drv, veh, accts, bnk]) => {
        if (!active) return;
        setDrivers(drv.filter((d) => d.is_active));
        setVehicles(veh.filter((v) => v.is_active));
        setAccounts(accts.filter((a) => a.is_postable && a.is_active));
        setBanks(bnk.filter((b) => b.is_active));
      })
      .catch(() => {
        if (active) setError("Couldn't load drivers, accounts, or bank accounts.");
      });
    return () => {
      active = false;
    };
  }, [selectedId]);

  // Recoverable advances follow the chosen driver.
  useEffect(() => {
    if (!driver) return;
    let active = true;
    listOutstandingAdvances(driver)
      .then((rows) => {
        if (active) setAdvances(rows);
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [driver]);

  const totals = useMemo(() => {
    const deductions = lines.reduce((s, l) => s + num(l.amount), 0);
    const grossValue = num(gross);
    return { gross: grossValue, deductions, net: grossValue - deductions };
  }, [lines, gross]);

  const advanceById = useMemo(
    () => new Map(advances.map((a) => [a.id, a])),
    [advances],
  );

  function updateLine(i: number, field: keyof Line, value: string) {
    setLines((prev) =>
      prev.map((l, idx) => {
        if (idx !== i) return l;
        const next = { ...l, [field]: value } as Line;
        // Picking an advance implies the kind and the account it credits back.
        if (field === "advance" && value) {
          const adv = advanceById.get(value);
          next.kind = "advance";
          if (adv) next.account = adv.advance_account;
        }
        if (field === "kind" && value !== "advance") next.advance = "";
        return next;
      }),
    );
  }

  const overRecovered = lines.some((l) => {
    if (!l.advance) return false;
    const adv = advanceById.get(l.advance);
    return adv ? num(l.amount) > Number(adv.balance) : false;
  });

  async function submit(alsoPost: boolean) {
    setError("");
    if (!driver) return setError("Select a driver.");
    if (!grossAccount) return setError("Select the gross earnings account.");
    if (!payAccount) return setError("Select the bank account to pay from.");
    if (totals.gross <= 0) return setError("Gross earnings must be positive.");
    const filled = lines.filter((l) => l.account && num(l.amount) > 0);
    if (totals.net < 0 && !allowNegative) {
      return setError(
        "Deductions exceed gross earnings. Tick “Allow an amount due from the driver” to " +
          "record the shortfall as a receivable.",
      );
    }
    if (totals.net < 0 && !receivableAccount) {
      return setError("Select the driver receivable account to hold the amount due.");
    }
    if (overRecovered) return setError("A recovery exceeds its advance's outstanding balance.");

    setSaving(true);
    try {
      const created = await createSettlement({
        entity: selectedId!,
        driver,
        vehicle: vehicle || null,
        period_start: periodStart,
        period_end: periodEnd,
        settlement_date: settlementDate,
        gross_amount: gross,
        gross_account: grossAccount,
        pay_account: payAccount,
        driver_receivable_account: totals.net < 0 ? receivableAccount : null,
        allows_negative_net: allowNegative,
        deductions: filled.map((l) => ({
          kind: l.kind,
          account: l.account,
          amount: l.amount,
          advance: l.advance || null,
          description: l.description,
        })),
      });
      if (alsoPost) await postSettlement(created.id);
      router.push("/settlements");
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
          Pick an entity from the switcher above to create a settlement.
        </CardContent>
      </Card>
    );
  }

  const fieldClass =
    "h-9 rounded-md border border-border bg-background px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40";

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">New Driver Settlement</h1>
        <p className="text-sm text-muted-foreground">
          {selectedEntity?.numeric_code} · {selectedEntity?.trade_name || selectedEntity?.legal_name}
        </p>
      </div>

      <Card>
        <CardContent className="grid grid-cols-1 gap-4 py-5 sm:grid-cols-2 lg:grid-cols-4">
          <div className="flex flex-col gap-1.5">
            <Label>Driver</Label>
            <select
              value={driver}
              onChange={(e) => {
                setDriver(e.target.value);
                setAdvances([]);
              }}
              className={fieldClass}
            >
              <option value="">Select driver…</option>
              {drivers.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.code} · {d.name}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Vehicle (optional)</Label>
            <select
              value={vehicle}
              onChange={(e) => setVehicle(e.target.value)}
              className={fieldClass}
            >
              <option value="">None</option>
              {vehicles.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.code}
                  {v.plate_no ? ` · ${v.plate_no}` : ""}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Period start</Label>
            <Input type="date" value={periodStart} onChange={(e) => setPeriodStart(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Period end</Label>
            <Input type="date" value={periodEnd} onChange={(e) => setPeriodEnd(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Settlement date</Label>
            <Input
              type="date"
              value={settlementDate}
              onChange={(e) => setSettlementDate(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Gross earnings</Label>
            <Input
              type="number"
              inputMode="decimal"
              value={gross}
              onChange={(e) => setGross(e.target.value)}
              className="text-right tabular-nums"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Gross account</Label>
            <select
              value={grossAccount}
              onChange={(e) => setGrossAccount(e.target.value)}
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
          <div className="flex flex-col gap-1.5">
            <Label>Pay from</Label>
            <select
              value={payAccount}
              onChange={(e) => setPayAccount(e.target.value)}
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
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-border text-left text-xs text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 font-medium">Kind</th>
                  <th className="px-3 py-2 font-medium">Against advance</th>
                  <th className="px-3 py-2 font-medium">Account</th>
                  <th className="px-3 py-2 font-medium">Description</th>
                  <th className="px-3 py-2 text-right font-medium">Amount</th>
                  <th className="w-10" />
                </tr>
              </thead>
              <tbody>
                {lines.map((l, i) => {
                  const adv = l.advance ? advanceById.get(l.advance) : undefined;
                  const over = adv ? num(l.amount) > Number(adv.balance) : false;
                  return (
                    <tr key={i} className="border-b border-border/60">
                      <td className="px-3 py-1.5">
                        <select
                          value={l.kind}
                          onChange={(e) => updateLine(i, "kind", e.target.value)}
                          className={cn(fieldClass, "min-w-36")}
                        >
                          {DEDUCTION_KINDS.map((k) => (
                            <option key={k.value} value={k.value}>
                              {k.label}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="px-3 py-1.5">
                        <select
                          value={l.advance}
                          onChange={(e) => updateLine(i, "advance", e.target.value)}
                          className={cn(fieldClass, "min-w-44")}
                          disabled={!driver || advances.length === 0}
                        >
                          <option value="">—</option>
                          {advances.map((a) => (
                            <option key={a.id} value={a.id}>
                              {a.advance_no} · {money(Number(a.balance))} left
                            </option>
                          ))}
                        </select>
                      </td>
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
                          className="h-9 min-w-36"
                        />
                      </td>
                      <td className="px-3 py-1.5">
                        <Input
                          type="number"
                          inputMode="decimal"
                          value={l.amount}
                          onChange={(e) => updateLine(i, "amount", e.target.value)}
                          className={cn(
                            "h-9 w-28 text-right tabular-nums",
                            over && "border-destructive",
                          )}
                          title={over ? "Exceeds the advance's outstanding balance" : ""}
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
                  );
                })}
              </tbody>
              <tfoot>
                <tr>
                  <td className="px-3 py-2" colSpan={6}>
                    <button
                      type="button"
                      onClick={() => setLines((p) => [...p, emptyLine()])}
                      className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
                    >
                      <Plus className="h-4 w-4" /> Add deduction
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
              <span className="text-muted-foreground">Gross</span>
              <span className="tabular-nums">{money(totals.gross)}</span>
            </div>
            <div className="flex justify-between gap-8">
              <span className="text-muted-foreground">Deductions</span>
              <span className="tabular-nums">{money(totals.deductions)}</span>
            </div>
            <div className="flex justify-between gap-8 border-t border-border pt-1 font-semibold">
              <span>{totals.net < 0 ? "Amount due from driver" : "Net payout"}</span>
              <span
                className={cn(
                  "tabular-nums",
                  totals.net < 0 && "text-amber-600 dark:text-amber-400",
                )}
              >
                {money(Math.abs(totals.net))}
              </span>
            </div>
            {totals.net < 0 && (
              <p className="mt-1 border-t border-border pt-2 text-xs text-muted-foreground">
                Posting records this as a <span className="font-medium">receivable</span> from the
                driver. No bank or cash entry is made — record the money separately as a receipt
                when it is actually collected.
              </p>
            )}
          </CardContent>
        </Card>
        <div className="flex flex-col items-end gap-3">
          {totals.net < 0 && (
            <div className="flex flex-col gap-1.5">
              <Label>
                Driver receivable account<span className="text-destructive"> *</span>
              </Label>
              <select
                value={receivableAccount}
                onChange={(e) => setReceivableAccount(e.target.value)}
                className={cn(fieldClass, "min-w-72")}
              >
                <option value="">Select…</option>
                {accounts
                  .filter((a) => a.nature === "asset")
                  .map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.code} · {a.name}
                    </option>
                  ))}
              </select>
            </div>
          )}
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={allowNegative}
              onChange={(e) => setAllowNegative(e.target.checked)}
              className="h-4 w-4 rounded border-border"
            />
            Allow an amount due from the driver (creates a receivable)
          </label>
          <div className="flex items-center gap-2">
            <Link href="/settlements">
              <Button variant="ghost" size="sm" type="button">
                Cancel
              </Button>
            </Link>
            <Button variant="outline" size="sm" onClick={() => submit(false)} disabled={saving}>
              Save draft
            </Button>
            <Button
              size="sm"
              onClick={() => submit(true)}
              disabled={
                saving ||
                totals.gross <= 0 ||
                overRecovered ||
                (totals.net < 0 && (!allowNegative || !receivableAccount))
              }
            >
              {saving ? "Saving…" : "Save & Post"}
            </Button>
          </div>
        </div>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  );
}
