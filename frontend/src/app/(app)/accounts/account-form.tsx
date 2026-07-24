"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEntity } from "@/lib/entity-context";
import { listAccountGroups, type Account, type AccountGroup } from "@/lib/accounts";
import { getRecord, createRecord, updateRecord } from "@/lib/crud";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const RESOURCE = "accounts";

const ACCOUNT_TYPES = [
  ["general", "General"],
  ["bank", "Bank"],
  ["cash", "Cash"],
  ["receivable", "Receivable"],
  ["payable", "Payable"],
  ["vat_input", "Input VAT"],
  ["vat_output", "Output VAT"],
  ["fixed_asset", "Fixed Asset"],
  ["loan", "Loan"],
  ["revenue", "Revenue"],
  ["expense", "Expense"],
  ["equity", "Equity"],
] as const;

const fieldClass =
  "h-9 rounded-md border border-border bg-background px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40";

type State = {
  subGroup: string;
  chargeSegment: string;
  name: string;
  accountType: string;
  normalBalance: string;
  subledger: string;
  isPostable: boolean;
  isBankAccount: boolean;
  isControlAccount: boolean;
  allowManualPosting: boolean;
  isActive: boolean;
};

const BLANK: State = {
  subGroup: "",
  chargeSegment: "",
  name: "",
  accountType: "general",
  normalBalance: "",
  subledger: "",
  isPostable: true,
  isBankAccount: false,
  isControlAccount: false,
  allowManualPosting: true,
  isActive: true,
};

export function AccountForm({ id }: { id?: string }) {
  const router = useRouter();
  const { selectedId, selectedEntity } = useEntity();
  const [groups, setGroups] = useState<AccountGroup[]>([]);
  const [form, setForm] = useState<State | null>(id ? null : BLANK);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    if (!selectedId) return;
    let active = true;
    listAccountGroups(selectedId, 2)
      .then((rows) => {
        if (active) setGroups(rows);
      })
      .catch(() => {
        if (active) setLoadError("Couldn't load account groups.");
      });
    return () => {
      active = false;
    };
  }, [selectedId]);

  useEffect(() => {
    if (!id) return;
    let active = true;
    getRecord<Account>(RESOURCE, id)
      .then((a) => {
        if (!active) return;
        setForm({
          subGroup: a.sub_group,
          chargeSegment: a.charge_segment,
          name: a.name,
          accountType: a.account_type,
          normalBalance: a.normal_balance,
          subledger: a.subledger,
          isPostable: a.is_postable,
          isBankAccount: a.is_bank_account,
          isControlAccount: a.is_control_account,
          allowManualPosting: a.allow_manual_posting,
          isActive: a.is_active,
        });
      })
      .catch(() => {
        if (active) setLoadError("Couldn't load this account.");
      });
    return () => {
      active = false;
    };
  }, [id]);

  const set = <K extends keyof State>(key: K, value: State[K]) =>
    setForm((f) => (f ? { ...f, [key]: value } : f));

  const composedCode = useMemo(() => {
    if (!form) return "";
    const group = groups.find((g) => g.id === form.subGroup);
    const charge = /^\d{1,3}$/.test(form.chargeSegment)
      ? form.chargeSegment.padStart(3, "0")
      : "___";
    return group ? `${group.code}-${charge}` : "—";
  }, [form, groups]);

  async function submit() {
    if (!form) return;
    setError("");
    if (!id) {
      if (!form.subGroup) return setError("Select a sub-group.");
      if (!/^\d{3}$/.test(form.chargeSegment))
        return setError("Charge segment must be exactly 3 digits (e.g. 004).");
    }
    if (!form.name.trim()) return setError("Name is required.");

    setSaving(true);
    try {
      if (id) {
        await updateRecord(RESOURCE, id, {
          name: form.name,
          account_type: form.accountType,
          normal_balance: form.normalBalance,
          subledger: form.subledger,
          is_postable: form.isPostable,
          is_bank_account: form.isBankAccount,
          is_control_account: form.isControlAccount,
          allow_manual_posting: form.allowManualPosting,
          is_active: form.isActive,
        });
      } else {
        await createRecord(RESOURCE, {
          entity: selectedId,
          sub_group: form.subGroup,
          charge_segment: form.chargeSegment,
          name: form.name,
          account_type: form.accountType,
          normal_balance: form.normalBalance,
          subledger: form.subledger,
          is_postable: form.isPostable,
          is_bank_account: form.isBankAccount,
          is_control_account: form.isControlAccount,
          allow_manual_posting: form.allowManualPosting,
          is_active: form.isActive,
        });
      }
      router.push("/accounts");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
      setSaving(false);
    }
  }

  if (!selectedId && !id) {
    return (
      <Card>
        <CardContent className="py-12 text-center text-sm text-muted-foreground">
          Pick an entity from the switcher above to add an account.
        </CardContent>
      </Card>
    );
  }
  if (loadError) return <p className="text-sm text-destructive">{loadError}</p>;
  if (!form) return <p className="text-sm text-muted-foreground">Loading…</p>;

  const selectedGroup = groups.find((g) => g.id === form.subGroup);

  return (
    <div className="flex max-w-4xl flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">{id ? "Edit Account" : "New Account"}</h1>
        <p className="text-sm text-muted-foreground">
          {selectedEntity?.numeric_code} ·{" "}
          {selectedEntity?.trade_name || selectedEntity?.legal_name}
        </p>
      </div>

      <Card>
        <CardContent className="flex flex-wrap items-center justify-between gap-3 py-4">
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Account code</p>
            <p className="font-mono text-lg font-semibold">{composedCode}</p>
          </div>
          <p className="max-w-sm text-xs text-muted-foreground">
            The code is composed from the sub-group + charge segment (ADR-0004) and{" "}
            {id ? "cannot be changed after creation." : "can’t be edited once the account exists."}
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="grid grid-cols-1 gap-4 py-5 sm:grid-cols-2 lg:grid-cols-3">
          <div className="flex flex-col gap-1.5 sm:col-span-2">
            <Label>
              Sub-group<span className="text-destructive"> *</span>
            </Label>
            {id ? (
              <Input value={selectedGroup ? `${selectedGroup.code} · ${selectedGroup.name}` : ""} disabled />
            ) : (
              <select
                value={form.subGroup}
                onChange={(e) => set("subGroup", e.target.value)}
                className={fieldClass}
              >
                <option value="">Select sub-group…</option>
                {groups.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.code} · {g.name} ({g.nature})
                  </option>
                ))}
              </select>
            )}
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>
              Charge segment<span className="text-destructive"> *</span>
            </Label>
            <Input
              value={form.chargeSegment}
              onChange={(e) => set("chargeSegment", e.target.value.replace(/\D/g, "").slice(0, 3))}
              placeholder="004"
              disabled={Boolean(id)}
              inputMode="numeric"
              className="font-mono"
            />
          </div>

          <div className="flex flex-col gap-1.5 sm:col-span-2">
            <Label>
              Name<span className="text-destructive"> *</span>
            </Label>
            <Input value={form.name} onChange={(e) => set("name", e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Account type</Label>
            <select
              value={form.accountType}
              onChange={(e) => set("accountType", e.target.value)}
              className={fieldClass}
            >
              {ACCOUNT_TYPES.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Normal balance</Label>
            <select
              value={form.normalBalance}
              onChange={(e) => set("normalBalance", e.target.value)}
              className={fieldClass}
            >
              <option value="">Auto (from group nature)</option>
              <option value="D">Debit</option>
              <option value="C">Credit</option>
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Subledger</Label>
            <select
              value={form.subledger}
              onChange={(e) => set("subledger", e.target.value)}
              className={fieldClass}
            >
              <option value="">None</option>
              <option value="customer">Customer</option>
              <option value="supplier">Supplier</option>
            </select>
          </div>

          <label className="flex items-center gap-2 self-end pb-2 text-sm">
            <input
              type="checkbox"
              checked={form.isPostable}
              onChange={(e) => set("isPostable", e.target.checked)}
              className="h-4 w-4 rounded border-border"
            />
            Postable
          </label>
          <label className="flex items-center gap-2 self-end pb-2 text-sm">
            <input
              type="checkbox"
              checked={form.allowManualPosting}
              onChange={(e) => set("allowManualPosting", e.target.checked)}
              className="h-4 w-4 rounded border-border"
            />
            Allow manual posting
          </label>
          <label className="flex items-center gap-2 self-end pb-2 text-sm">
            <input
              type="checkbox"
              checked={form.isControlAccount}
              onChange={(e) => set("isControlAccount", e.target.checked)}
              className="h-4 w-4 rounded border-border"
            />
            Control account
          </label>
          <label className="flex items-center gap-2 self-end pb-2 text-sm">
            <input
              type="checkbox"
              checked={form.isBankAccount}
              onChange={(e) => set("isBankAccount", e.target.checked)}
              className="h-4 w-4 rounded border-border"
            />
            Bank account
          </label>
          <label className="flex items-center gap-2 self-end pb-2 text-sm">
            <input
              type="checkbox"
              checked={form.isActive}
              onChange={(e) => set("isActive", e.target.checked)}
              className="h-4 w-4 rounded border-border"
            />
            Active
          </label>
        </CardContent>
      </Card>

      <div className="flex items-center justify-end gap-2">
        <Link href="/accounts">
          <Button variant="ghost" size="sm" type="button">
            Cancel
          </Button>
        </Link>
        <Button size="sm" onClick={submit} disabled={saving}>
          {saving ? "Saving…" : id ? "Save changes" : "Create account"}
        </Button>
      </div>

      {error && <p className={cn("text-sm text-destructive")}>{error}</p>}
    </div>
  );
}
