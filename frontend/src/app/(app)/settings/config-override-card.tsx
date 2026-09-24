"use client";

import { useState } from "react";
import { saveEntitySetting, type EntitySetting } from "@/lib/settings";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

type Field = { key: string; label: string; type: "number" | "text" };

/** Merge the entity's override (if any) over the documented default. */
function merge(defaults: Record<string, unknown>, override: Record<string, unknown> | undefined) {
  return { ...defaults, ...(override ?? {}) };
}

function toFormValues(merged: Record<string, unknown>): Record<string, string> {
  return Object.fromEntries(Object.entries(merged).map(([k, v]) => [k, String(v)]));
}

/**
 * One `EntitySetting` key, edited as its documented fields rather than raw
 * JSON — the shape is fixed by the consuming service (payroll's
 * `gratuity_rule`/`sif_layout`), so a typed form can't produce malformed
 * config the way a free-text JSON box could.
 */
export function ConfigOverrideCard({
  title,
  description,
  settingKey,
  fields,
  defaults,
  entityId,
  row,
  canWrite,
  onSaved,
}: {
  title: string;
  description: string;
  settingKey: string;
  fields: Field[];
  defaults: Record<string, unknown>;
  entityId: string;
  row: EntitySetting | null;
  canWrite: boolean;
  onSaved: (row: EntitySetting) => void;
}) {
  // Lazy initial state only — the parent remounts this component (via a `key`
  // covering entityId/row) whenever the underlying row changes, so the form
  // never needs to sync to a prop change after mount.
  const [form, setForm] = useState<Record<string, string>>(() =>
    toFormValues(merge(defaults, row?.value)),
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const overridden = row !== null && Object.keys(row.value).length > 0;

  async function save(value: Record<string, unknown>) {
    setSaving(true);
    setError("");
    try {
      const next = await saveEntitySetting(entityId, settingKey, value, row);
      onSaved(next);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setSaving(false);
    }
  }

  function submit() {
    const value: Record<string, unknown> = {};
    for (const f of fields) {
      const raw = form[f.key] ?? "";
      value[f.key] = f.type === "number" ? Number(raw) : raw;
    }
    return save(value);
  }

  return (
    <>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          {title}
          {overridden && (
            <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
              Overridden
            </span>
          )}
        </CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
          {fields.map((f) => (
            <div key={f.key} className="flex flex-col gap-1.5">
              <Label htmlFor={`${settingKey}-${f.key}`}>{f.label}</Label>
              <Input
                id={`${settingKey}-${f.key}`}
                type={f.type === "number" ? "number" : "text"}
                value={form[f.key] ?? ""}
                disabled={!canWrite}
                onChange={(e) => setForm((prev) => ({ ...prev, [f.key]: e.target.value }))}
              />
            </div>
          ))}
        </div>
        {canWrite ? (
          <div className="flex items-center gap-2">
            <Button size="sm" onClick={submit} disabled={saving}>
              {saving ? "Saving…" : "Save override"}
            </Button>
            {overridden && (
              <Button
                variant="ghost"
                size="sm"
                disabled={saving}
                onClick={() => save({})}
              >
                Reset to default
              </Button>
            )}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">Changing this needs a manager or admin role.</p>
        )}
        {error && <p className="text-sm text-destructive">{error}</p>}
      </CardContent>
    </>
  );
}
