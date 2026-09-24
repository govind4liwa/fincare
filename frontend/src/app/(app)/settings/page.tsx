"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, Check } from "lucide-react";
import { useEntity } from "@/lib/entity-context";
import { listAccounts, type Account } from "@/lib/accounts";
import {
  GRATUITY_RULE_DEFAULT,
  SIF_LAYOUT_DEFAULT,
  canConfigureDriverAccounting,
  canConfigureEntitySettings,
  getDriverAccountingConfig,
  isEligibleReceivableAccount,
  listEntitySettings,
  saveDriverReceivableAccount,
  type DriverAccountingConfig,
  type EntitySetting,
} from "@/lib/settings";
import { ConfigOverrideCard } from "./config-override-card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

/**
 * Everything one entity's settings screen needs, tagged with the entity it came
 * from. Holding it as a single snapshot means switching entities invalidates the
 * whole thing at once — a stale account list can never be shown next to a fresh
 * configuration.
 */
type Snapshot =
  | {
      entity: string;
      status: "ok";
      accounts: Account[];
      config: DriverAccountingConfig | null;
      canWrite: boolean;
      entitySettings: EntitySetting[];
      canConfigureSettings: boolean;
    }
  | { entity: string; status: "error"; message: string };

export default function SettingsPage() {
  const { selectedId, selectedEntity } = useEntity();
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  // null means "follow whatever is configured"; a string is an unsaved choice.
  const [choice, setChoice] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState("");

  useEffect(() => {
    if (!selectedId) return;
    let active = true;
    Promise.all([
      listAccounts(selectedId),
      getDriverAccountingConfig(selectedId),
      canConfigureDriverAccounting(),
      listEntitySettings(selectedId),
      canConfigureEntitySettings(),
    ])
      .then(([accounts, config, canWrite, entitySettings, canConfigureSettings]) => {
        if (!active) return;
        setSnapshot({
          entity: selectedId,
          status: "ok",
          accounts,
          config,
          canWrite,
          entitySettings,
          canConfigureSettings,
        });
        setChoice(null);
      })
      .catch((e: unknown) => {
        if (!active) return;
        setSnapshot({
          entity: selectedId,
          status: "error",
          message: e instanceof Error ? e.message : "Couldn't load settings.",
        });
      });
    return () => {
      active = false;
    };
  }, [selectedId]);

  // Anything tagged with a different entity is stale, so it reads as loading.
  const current = snapshot?.entity === selectedId ? snapshot : null;
  const loaded = current?.status === "ok" ? current : null;
  const config = loaded?.config ?? null;

  // Only accounts the server would accept, so the picker cannot offer a choice
  // that fails validation.
  const eligible = useMemo(
    () => (loaded?.accounts ?? []).filter(isEligibleReceivableAccount),
    [loaded],
  );

  const selected = choice ?? config?.default_receivable_account ?? "";
  const dirty = selected !== "" && selected !== (config?.default_receivable_account ?? "");

  async function save() {
    if (!dirty || !selectedId || !loaded) return;
    setSaving(true);
    setSaveError("");
    setSaved(false);
    try {
      const next = await saveDriverReceivableAccount(selectedId, selected, config);
      setSnapshot({ ...loaded, config: next });
      setChoice(null);
      setSaved(true);
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setSaving(false);
    }
  }

  function onSettingSaved(next: EntitySetting) {
    if (!loaded) return;
    const others = loaded.entitySettings.filter((s) => s.key !== next.key);
    setSnapshot({ ...loaded, entitySettings: [...others, next] });
  }

  if (!selectedId) {
    return (
      <Card>
        <CardContent className="py-12 text-center text-sm text-muted-foreground">
          Pick an entity from the switcher above to view its settings.
        </CardContent>
      </Card>
    );
  }

  const fieldClass =
    "h-9 rounded-md border border-border bg-background px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40";

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">Settings</h1>
        <p className="text-sm text-muted-foreground">
          Accounting configuration for {selectedEntity?.legal_name ?? "this entity"}.
        </p>
      </div>

      <Card className="max-w-3xl">
        <CardHeader>
          <CardTitle>Driver Receivable account</CardTitle>
          <CardDescription>
            When a driver&rsquo;s deductions exceed their earnings, the shortfall is money the
            driver owes. Posting debits this account and leaves bank and cash untouched — no money
            has been received. A separate receipt clears it when the driver actually pays.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {!current ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : current.status === "error" ? (
            <p className="text-sm text-destructive">{current.message}</p>
          ) : (
            <>
              {config ? (
                <div className="flex flex-col gap-1">
                  <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    Currently configured
                  </span>
                  <span className="text-sm font-medium tabular-nums">
                    {config.account_code} · {config.account_name}
                  </span>
                </div>
              ) : (
                <div className="flex items-start gap-2 rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-700 dark:text-amber-400">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                  <span>
                    Not configured. Settlements where deductions exceed earnings cannot be posted
                    for this entity until an account is chosen here.
                  </span>
                </div>
              )}

              {current.canWrite ? (
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="receivable-account">
                    {config ? "Change to" : "Choose an account"}
                  </Label>
                  <div className="flex flex-wrap items-center gap-2">
                    <select
                      id="receivable-account"
                      value={selected}
                      onChange={(e) => {
                        setChoice(e.target.value);
                        setSaved(false);
                      }}
                      className={cn(fieldClass, "min-w-80")}
                    >
                      <option value="">Select…</option>
                      {eligible.map((a) => (
                        <option key={a.id} value={a.id}>
                          {a.code} · {a.name}
                        </option>
                      ))}
                    </select>
                    <Button size="sm" onClick={save} disabled={!dirty || saving}>
                      {saving ? "Saving…" : "Save"}
                    </Button>
                    {saved && !dirty && (
                      <span className="flex items-center gap-1 text-sm text-emerald-600 dark:text-emerald-400">
                        <Check className="h-4 w-4" />
                        Saved
                      </span>
                    )}
                  </div>
                  {eligible.length === 0 && (
                    <p className="text-xs text-destructive">
                      No account in this entity&rsquo;s chart of accounts is eligible. Create a
                      postable asset account first.
                    </p>
                  )}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">
                  Changing this needs a manager or admin role. Configuring the account is what
                  authorises driver receivable postings, so it is deliberately not an everyday
                  edit.
                </p>
              )}

              <p className="border-t border-border pt-3 text-xs text-muted-foreground">
                Eligible accounts are active, postable, manually postable, debit-normal asset
                accounts. Bank, cash and fixed-asset accounts are excluded, as are control accounts
                and anything in a customer or supplier subledger — settlement lines carry the driver
                as a dimension, not a party subledger.
              </p>

              {saveError && <p className="text-sm text-destructive">{saveError}</p>}
            </>
          )}
        </CardContent>
      </Card>

      {loaded && (
        <>
          <Card className="max-w-3xl">
            <ConfigOverrideCard
              key={`${selectedId}-gratuity_rule-${loaded.entitySettings.find((s) => s.key === "gratuity_rule")?.id ?? "new"}`}
              title="Gratuity Rule"
              description="UAE Labour Law end-of-service day-rates, read by payroll's gratuity accrual. Applies group-wide until overridden here."
              settingKey="gratuity_rule"
              defaults={GRATUITY_RULE_DEFAULT}
              fields={[
                { key: "days_per_year_first", label: "Days/year (first years)", type: "number" },
                { key: "days_per_year_after", label: "Days/year (after)", type: "number" },
                { key: "first_years", label: "First-years threshold", type: "number" },
                { key: "month_days", label: "Month days (day-rate base)", type: "number" },
                { key: "cap_years", label: "Cap (years' wage)", type: "number" },
              ]}
              entityId={selectedId}
              row={loaded.entitySettings.find((s) => s.key === "gratuity_rule") ?? null}
              canWrite={loaded.canConfigureSettings}
              onSaved={onSettingSaved}
            />
          </Card>

          <Card className="max-w-3xl">
            <ConfigOverrideCard
              key={`${selectedId}-sif_layout-${loaded.entitySettings.find((s) => s.key === "sif_layout")?.id ?? "new"}`}
              title="SIF Layout"
              description="WPS Salary Information File header tags, read when payroll exports a SIF batch."
              settingKey="sif_layout"
              defaults={SIF_LAYOUT_DEFAULT}
              fields={[
                { key: "version", label: "Version", type: "text" },
                { key: "delimiter", label: "Delimiter", type: "text" },
                { key: "scr_tag", label: "SCR tag", type: "text" },
                { key: "edr_tag", label: "EDR tag", type: "text" },
              ]}
              entityId={selectedId}
              row={loaded.entitySettings.find((s) => s.key === "sif_layout") ?? null}
              canWrite={loaded.canConfigureSettings}
              onSaved={onSettingSaved}
            />
          </Card>
        </>
      )}
    </div>
  );
}
