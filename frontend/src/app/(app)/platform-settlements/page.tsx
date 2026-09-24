"use client";

import { useEffect, useMemo, useState } from "react";
import { useEntity } from "@/lib/entity-context";
import { listAccounts, type Account } from "@/lib/accounts";
import { listBankAccounts, type BankAccount } from "@/lib/banking";
import {
  createEarningImport,
  createPlatformSettlement,
  listEarningImports,
  listPlatformSettlements,
  listPlatforms,
  postSettlement,
  reconcileSettlement,
  type EarningImport,
  type Platform,
  type PlatformSettlement,
} from "@/lib/platforms";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const fieldClass =
  "h-9 rounded-md border border-border bg-background px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40";

const money = (v: string) =>
  Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const STATUS_STYLE: Record<PlatformSettlement["status"], string> = {
  draft: "bg-muted text-muted-foreground",
  reconciled: "bg-amber-500/10 text-amber-700 dark:text-amber-400",
  posted: "bg-primary/10 text-primary",
  reversed: "bg-destructive/10 text-destructive",
};

export default function PlatformSettlementsPage() {
  const { selectedId, selectedEntity } = useEntity();
  const [platforms, setPlatforms] = useState<Platform[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [banks, setBanks] = useState<BankAccount[]>([]);
  const [settlements, setSettlements] = useState<PlatformSettlement[]>([]);
  const [platformId, setPlatformId] = useState("");
  const [imports, setImports] = useState<EarningImport[]>([]);
  const [loadError, setLoadError] = useState("");
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState("");

  const [earning, setEarning] = useState({
    trip_ref: "",
    driver_ref: "",
    earning_date: "",
    gross: "",
    commission: "",
    net: "",
  });
  const [savingEarning, setSavingEarning] = useState(false);

  const [draft, setDraft] = useState({
    period_start: "",
    period_end: "",
    settlement_date: "",
    net_received: "",
    bank_account: "",
    adjustment_account: "",
    adjustments: "",
  });
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    if (!selectedId) return;
    let active = true;
    Promise.all([listPlatforms(selectedId), listAccounts(selectedId), listBankAccounts(selectedId)])
      .then(([p, a, b]) => {
        if (!active) return;
        setPlatforms(p);
        setAccounts(a.filter((x) => x.is_active && x.is_postable));
        setBanks(b);
        setPlatformId((prev) => prev || p[0]?.id || "");
      })
      .catch(() => {
        if (active) setLoadError("Couldn't load platforms.");
      });
    return () => {
      active = false;
    };
  }, [selectedId]);

  useEffect(() => {
    if (!selectedId) return;
    let active = true;
    listPlatformSettlements(selectedId)
      .then((rows) => {
        if (active) setSettlements(rows);
      })
      .catch(() => {
        if (active) setLoadError("Couldn't load settlements.");
      });
    return () => {
      active = false;
    };
  }, [selectedId]);

  useEffect(() => {
    if (!platformId) return;
    let active = true;
    listEarningImports({ entityId: selectedId, platformId })
      .then((rows) => {
        if (active) setImports(rows);
      })
      .catch(() => {
        if (active) setLoadError("Couldn't load earning imports.");
      });
    return () => {
      active = false;
    };
  }, [platformId, selectedId]);

  const platform = platforms.find((p) => p.id === platformId);
  const platformSettlements = useMemo(
    () => settlements.filter((s) => s.platform === platformId),
    [settlements, platformId],
  );
  const unmatchedCount = imports.filter((i) => !i.matched).length;

  async function addEarning() {
    if (!selectedId || !platformId) return;
    setSavingEarning(true);
    setError("");
    try {
      const row = await createEarningImport({
        entity: selectedId,
        platform: platformId,
        trip_ref: earning.trip_ref,
        driver_ref: earning.driver_ref,
        earning_date: earning.earning_date,
        gross: earning.gross || "0",
        commission: earning.commission || "0",
        net: earning.net || "0",
      });
      setImports((prev) => [row, ...prev]);
      setEarning({ trip_ref: "", driver_ref: "", earning_date: "", gross: "", commission: "", net: "" });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setSavingEarning(false);
    }
  }

  async function createDraft() {
    if (!selectedId || !platformId) return;
    setCreating(true);
    setError("");
    try {
      const settlement = await createPlatformSettlement({
        entity: selectedId,
        platform: platformId,
        period_start: draft.period_start,
        period_end: draft.period_end,
        settlement_date: draft.settlement_date,
        net_received: draft.net_received || "0",
        bank_account: draft.bank_account,
        adjustment_account: draft.adjustment_account,
        adjustments: draft.adjustments || "0",
      });
      setSettlements((prev) => [settlement, ...prev]);
      setDraft({
        period_start: "",
        period_end: "",
        settlement_date: "",
        net_received: "",
        bank_account: "",
        adjustment_account: "",
        adjustments: "",
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setCreating(false);
    }
  }

  async function reconcile(id: string) {
    setBusyId(id);
    setError("");
    try {
      const updated = await reconcileSettlement(id);
      setSettlements((prev) => prev.map((s) => (s.id === id ? updated : s)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setBusyId("");
    }
  }

  async function post(id: string) {
    setBusyId(id);
    setError("");
    try {
      const updated = await postSettlement(id);
      setSettlements((prev) => prev.map((s) => (s.id === id ? updated : s)));
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
          Pick an entity from the switcher above to manage platform settlements.
        </CardContent>
      </Card>
    );
  }
  if (loadError) return <p className="text-sm text-destructive">{loadError}</p>;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">Platform Settlements</h1>
        <p className="text-sm text-muted-foreground">
          {selectedEntity?.numeric_code} ·{" "}
          {selectedEntity?.trade_name || selectedEntity?.legal_name}
        </p>
      </div>

      <div className="flex flex-col gap-1.5">
        <Label>Platform</Label>
        <select
          value={platformId}
          onChange={(e) => setPlatformId(e.target.value)}
          className={cn(fieldClass, "max-w-xs")}
        >
          {platforms.length === 0 && <option value="">No platforms yet</option>}
          {platforms.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
      </div>

      {platform && (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Staged earnings</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <p className="text-xs text-muted-foreground">
                {unmatchedCount} unmatched of {imports.length} imported — matched rows are claimed by
                a reconciled settlement.
              </p>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-6">
                <div className="flex flex-col gap-1.5">
                  <Label>Trip ref</Label>
                  <Input
                    value={earning.trip_ref}
                    onChange={(e) => setEarning((p) => ({ ...p, trip_ref: e.target.value }))}
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label>Driver ref</Label>
                  <Input
                    value={earning.driver_ref}
                    onChange={(e) => setEarning((p) => ({ ...p, driver_ref: e.target.value }))}
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label>Date</Label>
                  <Input
                    type="date"
                    value={earning.earning_date}
                    onChange={(e) => setEarning((p) => ({ ...p, earning_date: e.target.value }))}
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label>Gross</Label>
                  <Input
                    type="number"
                    inputMode="decimal"
                    value={earning.gross}
                    onChange={(e) => setEarning((p) => ({ ...p, gross: e.target.value }))}
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label>Commission</Label>
                  <Input
                    type="number"
                    inputMode="decimal"
                    value={earning.commission}
                    onChange={(e) => setEarning((p) => ({ ...p, commission: e.target.value }))}
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label>Net</Label>
                  <Input
                    type="number"
                    inputMode="decimal"
                    value={earning.net}
                    onChange={(e) => setEarning((p) => ({ ...p, net: e.target.value }))}
                  />
                </div>
              </div>
              <div>
                <Button size="sm" onClick={addEarning} disabled={savingEarning}>
                  {savingEarning ? "Adding…" : "Add earning row"}
                </Button>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>New settlement</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <div className="flex flex-col gap-1.5">
                  <Label>Period start</Label>
                  <Input
                    type="date"
                    value={draft.period_start}
                    onChange={(e) => setDraft((p) => ({ ...p, period_start: e.target.value }))}
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label>Period end</Label>
                  <Input
                    type="date"
                    value={draft.period_end}
                    onChange={(e) => setDraft((p) => ({ ...p, period_end: e.target.value }))}
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label>Settlement date</Label>
                  <Input
                    type="date"
                    value={draft.settlement_date}
                    onChange={(e) => setDraft((p) => ({ ...p, settlement_date: e.target.value }))}
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label>Net received (bank)</Label>
                  <Input
                    type="number"
                    inputMode="decimal"
                    value={draft.net_received}
                    onChange={(e) => setDraft((p) => ({ ...p, net_received: e.target.value }))}
                  />
                </div>
                <div className="flex flex-col gap-1.5 sm:col-span-2">
                  <Label>Bank account</Label>
                  <select
                    value={draft.bank_account}
                    onChange={(e) => setDraft((p) => ({ ...p, bank_account: e.target.value }))}
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
                <div className="flex flex-col gap-1.5 sm:col-span-2">
                  <Label>Adjustment account (if variance)</Label>
                  <select
                    value={draft.adjustment_account}
                    onChange={(e) => setDraft((p) => ({ ...p, adjustment_account: e.target.value }))}
                    className={fieldClass}
                  >
                    <option value="">None</option>
                    {accounts.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.code} · {a.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div>
                <Button size="sm" onClick={createDraft} disabled={creating}>
                  {creating ? "Creating…" : "Create draft settlement"}
                </Button>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-0">
              <table className="w-full text-sm">
                <thead className="border-b border-border text-left text-xs text-muted-foreground">
                  <tr>
                    <th className="px-4 py-2 font-medium">Settlement</th>
                    <th className="px-4 py-2 font-medium">Period</th>
                    <th className="px-4 py-2 text-right font-medium">Gross</th>
                    <th className="px-4 py-2 text-right font-medium">Commission</th>
                    <th className="px-4 py-2 text-right font-medium">Net received</th>
                    <th className="px-4 py-2 text-right font-medium">Variance</th>
                    <th className="px-4 py-2 font-medium">Status</th>
                    <th className="px-4 py-2 text-right font-medium" />
                  </tr>
                </thead>
                <tbody>
                  {platformSettlements.length === 0 ? (
                    <tr>
                      <td colSpan={8} className="px-4 py-8 text-center text-muted-foreground">
                        No settlements for this platform yet.
                      </td>
                    </tr>
                  ) : (
                    platformSettlements.map((s) => (
                      <tr key={s.id} className="border-b border-border/60 last:border-0">
                        <td className="px-4 py-2 font-mono text-xs">{s.settlement_no || "(draft)"}</td>
                        <td className="px-4 py-2 text-muted-foreground">
                          {s.period_start} – {s.period_end}
                        </td>
                        <td className="px-4 py-2 text-right tabular-nums">{money(s.gross_earnings)}</td>
                        <td className="px-4 py-2 text-right tabular-nums">{money(s.commission)}</td>
                        <td className="px-4 py-2 text-right tabular-nums">{money(s.net_received)}</td>
                        <td className="px-4 py-2 text-right tabular-nums">{money(s.variance)}</td>
                        <td className="px-4 py-2">
                          <span
                            className={cn(
                              "rounded-full px-2 py-0.5 text-xs font-medium capitalize",
                              STATUS_STYLE[s.status],
                            )}
                          >
                            {s.status}
                          </span>
                        </td>
                        <td className="px-4 py-2 text-right">
                          {s.status === "draft" && (
                            <Button
                              size="sm"
                              variant="outline"
                              disabled={busyId === s.id}
                              onClick={() => reconcile(s.id)}
                            >
                              {busyId === s.id ? "Reconciling…" : "Reconcile"}
                            </Button>
                          )}
                          {s.status === "reconciled" && (
                            <Button size="sm" disabled={busyId === s.id} onClick={() => post(s.id)}>
                              {busyId === s.id ? "Posting…" : "Post"}
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
        </>
      )}

      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  );
}
