"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AlertTriangle } from "lucide-react";
import { useEntity } from "@/lib/entity-context";
import { listBankAccounts, type BankAccount } from "@/lib/banking";
import { listDrivers, type Driver } from "@/lib/fleet";
import {
  CLEARING_KINDS,
  createClearing,
  listOutstandingSettlements,
  postClearing,
  type ClearingKind,
  type Settlement,
} from "@/lib/settlements";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const num = (v: string) => (Number.isFinite(Number(v)) ? Number(v) : 0);
const money = (n: number) =>
  n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const today = () => new Date().toISOString().slice(0, 10);

export default function NewDriverClearingPage() {
  const router = useRouter();
  const { selectedId, selectedEntity } = useEntity();
  const [drivers, setDrivers] = useState<Driver[]>([]);
  const [banks, setBanks] = useState<BankAccount[]>([]);

  const [driver, setDriver] = useState("");
  const [kind, setKind] = useState<ClearingKind>("receipt");
  const [clearingDate, setClearingDate] = useState(today);
  const [bankAccount, setBankAccount] = useState("");
  const [reference, setReference] = useState("");
  const [narration, setNarration] = useState("");
  // Tagged with the driver it was fetched for, so a stale list can never be shown
  // against a newly picked driver.
  const [fetched, setFetched] = useState<{ driver: string; rows: Settlement[] } | null>(null);
  const [applied, setApplied] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!selectedId) return;
    let active = true;
    Promise.all([listDrivers(selectedId), listBankAccounts(selectedId)])
      .then(([drv, bnk]) => {
        if (!active) return;
        setDrivers(drv.filter((d) => d.is_active));
        setBanks(bnk.filter((b) => b.is_active));
      })
      .catch(() => {
        if (active) setError("Couldn't load drivers or bank accounts.");
      });
    return () => {
      active = false;
    };
  }, [selectedId]);

  // What this driver still owes follows the driver picker.
  useEffect(() => {
    if (!driver) return;
    let active = true;
    listOutstandingSettlements(driver)
      .then((rows) => {
        if (!active) return;
        setFetched({ driver, rows });
        setApplied({});
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [driver]);

  // Anything fetched for a different driver is stale, so it reads as empty.
  // Memoised so the empty case is a stable reference for the totals below.
  const outstanding = useMemo(
    () => (fetched?.driver === driver ? fetched.rows : []),
    [fetched, driver],
  );

  const lines = useMemo(
    () =>
      outstanding
        .map((s) => ({ settlement: s.id, amount: applied[s.id] ?? "" }))
        .filter((l) => num(l.amount) > 0),
    [outstanding, applied],
  );
  const total = useMemo(() => lines.reduce((sum, l) => sum + num(l.amount), 0), [lines]);
  const overApplied = outstanding.some(
    (s) => num(applied[s.id] ?? "") > Number(s.receivable_balance),
  );

  function applyAll() {
    setApplied(Object.fromEntries(outstanding.map((s) => [s.id, s.receivable_balance])));
  }

  async function submit(alsoPost: boolean) {
    setError("");
    if (!driver) return setError("Select a driver.");
    if (kind === "receipt" && !bankAccount) {
      return setError("Select the bank account the money was paid into.");
    }
    if (lines.length === 0) return setError("Apply the clearing to at least one settlement.");
    if (overApplied) return setError("An applied amount exceeds what that settlement still owes.");

    setSaving(true);
    try {
      const created = await createClearing({
        entity: selectedId!,
        driver,
        kind,
        clearing_date: clearingDate,
        amount: total.toFixed(2),
        // A write-off moves no money, so it must not name a bank account.
        bank_account: kind === "receipt" ? bankAccount : null,
        reference,
        narration,
        lines: lines.map((l) => ({ settlement: l.settlement, amount: num(l.amount).toFixed(2) })),
      });
      if (alsoPost) await postClearing(created.id);
      router.push("/driver-clearings");
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
          Pick an entity from the switcher above to record a clearing.
        </CardContent>
      </Card>
    );
  }

  const fieldClass =
    "h-9 rounded-md border border-border bg-background px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40";
  const kindHelp = CLEARING_KINDS.find((k) => k.value === kind)?.help;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">New Driver Clearing</h1>
        <p className="text-sm text-muted-foreground">
          Settle what a driver owes — {selectedEntity?.legal_name ?? "this entity"}.
        </p>
      </div>

      <Card>
        <CardContent className="grid gap-4 p-6 md:grid-cols-2 lg:grid-cols-3">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="driver">
              Driver<span className="text-destructive"> *</span>
            </Label>
            <select
              id="driver"
              value={driver}
              onChange={(e) => setDriver(e.target.value)}
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
            <Label htmlFor="kind">How is it being settled?</Label>
            <select
              id="kind"
              value={kind}
              onChange={(e) => setKind(e.target.value as ClearingKind)}
              className={fieldClass}
            >
              {CLEARING_KINDS.map((k) => (
                <option key={k.value} value={k.value}>
                  {k.label}
                </option>
              ))}
            </select>
            <p className="text-xs text-muted-foreground">{kindHelp}</p>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="date">Date</Label>
            <Input
              id="date"
              type="date"
              value={clearingDate}
              onChange={(e) => setClearingDate(e.target.value)}
            />
          </div>

          {kind === "receipt" ? (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="bank">
                Paid into<span className="text-destructive"> *</span>
              </Label>
              <select
                id="bank"
                value={bankAccount}
                onChange={(e) => setBankAccount(e.target.value)}
                className={fieldClass}
              >
                <option value="">Select bank account…</option>
                {banks.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.code} · {b.name}
                  </option>
                ))}
              </select>
            </div>
          ) : (
            <div className="flex flex-col gap-1.5">
              <Label>Expensed to</Label>
              <div
                className={cn(fieldClass, "flex items-center bg-muted/50 text-muted-foreground")}
              >
                The entity&rsquo;s configured bad-debt account
              </div>
              <p className="text-xs text-muted-foreground">
                No money moves, so no bank account is involved.
              </p>
            </div>
          )}

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="reference">Reference</Label>
            <Input
              id="reference"
              value={reference}
              onChange={(e) => setReference(e.target.value)}
              placeholder="Cheque no., transfer ref…"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="narration">Narration</Label>
            <Input
              id="narration"
              value={narration}
              onChange={(e) => setNarration(e.target.value)}
              placeholder="Optional"
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          <div className="flex items-center justify-between border-b border-border px-4 py-3">
            <h2 className="text-sm font-medium">Outstanding settlements</h2>
            {outstanding.length > 0 && (
              <Button variant="outline" size="sm" type="button" onClick={applyAll}>
                Apply full balance
              </Button>
            )}
          </div>
          {!driver ? (
            <p className="px-4 py-6 text-sm text-muted-foreground">
              Select a driver to see what they owe.
            </p>
          ) : outstanding.length === 0 ? (
            <p className="px-4 py-6 text-sm text-muted-foreground">
              This driver owes nothing. A receivable only arises when a settlement&rsquo;s
              deductions exceed their earnings.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b border-border text-left text-muted-foreground">
                  <tr>
                    <th className="px-4 py-2 font-medium">Settlement</th>
                    <th className="px-4 py-2 font-medium">Period</th>
                    <th className="px-4 py-2 text-right font-medium">Shortfall</th>
                    <th className="px-4 py-2 text-right font-medium">Already cleared</th>
                    <th className="px-4 py-2 text-right font-medium">Outstanding</th>
                    <th className="px-4 py-2 text-right font-medium">Apply</th>
                  </tr>
                </thead>
                <tbody>
                  {outstanding.map((s) => {
                    const value = applied[s.id] ?? "";
                    const over = num(value) > Number(s.receivable_balance);
                    return (
                      <tr key={s.id} className="border-b border-border last:border-0">
                        <td className="px-4 py-2 tabular-nums">{s.settlement_no}</td>
                        <td className="px-4 py-2 text-muted-foreground">
                          {s.period_start} → {s.period_end}
                        </td>
                        <td className="px-4 py-2 text-right tabular-nums">
                          {money(Math.abs(Number(s.net_amount)))}
                        </td>
                        <td className="px-4 py-2 text-right tabular-nums text-muted-foreground">
                          {money(Number(s.cleared_amount))}
                        </td>
                        <td className="px-4 py-2 text-right font-medium tabular-nums">
                          {money(Number(s.receivable_balance))}
                        </td>
                        <td className="px-4 py-2 text-right">
                          <Input
                            type="number"
                            step="0.01"
                            min="0"
                            value={value}
                            onChange={(e) =>
                              setApplied((prev) => ({ ...prev, [s.id]: e.target.value }))
                            }
                            className={cn(
                              "ml-auto w-32 text-right tabular-nums",
                              over && "border-destructive",
                            )}
                          />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <Card className="md:w-72">
          <CardContent className="flex flex-col gap-1 p-4 text-sm">
            <div className="flex justify-between gap-8 border-b border-border pb-1 font-semibold">
              <span>{kind === "write_off" ? "Total written off" : "Total received"}</span>
              <span className="tabular-nums">{money(total)}</span>
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              {kind === "write_off"
                ? "Posting expenses this to bad debts and clears the receivable."
                : "Posting debits the bank and clears the receivable."}
            </p>
          </CardContent>
        </Card>

        <div className="flex flex-col items-end gap-3">
          {overApplied && (
            <p className="flex items-center gap-1.5 text-sm text-destructive">
              <AlertTriangle className="h-4 w-4" />
              An applied amount exceeds what that settlement still owes.
            </p>
          )}
          <div className="flex items-center gap-2">
            <Link href="/driver-clearings">
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
              disabled={saving || total <= 0 || overApplied || (kind === "receipt" && !bankAccount)}
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
