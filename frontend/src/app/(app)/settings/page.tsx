"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, Check } from "lucide-react";
import { useEntity } from "@/lib/entity-context";
import { listAccounts, type Account } from "@/lib/accounts";
import {
  canConfigureDriverAccounting,
  getDriverAccountingConfig,
  isEligibleReceivableAccount,
  saveDriverReceivableAccount,
  type DriverAccountingConfig,
} from "@/lib/settings";
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
    ])
      .then(([accounts, config, canWrite]) => {
        if (!active) return;
        setSnapshot({ entity: selectedId, status: "ok", accounts, config, canWrite });
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
    </div>
  );
}
