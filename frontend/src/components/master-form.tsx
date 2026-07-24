"use client";

import { useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export type FieldSpec = {
  name: string;
  label: string;
  type?: "text" | "number" | "date" | "checkbox" | "select";
  options?: { value: string; label: string }[];
  required?: boolean;
  placeholder?: string;
  colSpan?: 1 | 2 | 3;
  help?: string;
};

export type FormValues = Record<string, string | boolean>;

const FIELD_CLASS =
  "h-9 rounded-md border border-border bg-background px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40";

function spanClass(n?: number) {
  if (n === 3) return "sm:col-span-2 lg:col-span-3";
  if (n === 2) return "sm:col-span-2";
  return "";
}

/** Schema-driven create/edit form for flat master records. */
export function MasterForm({
  title,
  subtitle,
  fields,
  initial,
  submitLabel,
  cancelHref,
  onSubmit,
}: {
  title: string;
  subtitle?: string;
  fields: FieldSpec[];
  initial: FormValues;
  submitLabel: string;
  cancelHref: string;
  onSubmit: (values: FormValues) => Promise<void>;
}) {
  const [values, setValues] = useState<FormValues>(initial);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const set = (name: string, value: string | boolean) =>
    setValues((v) => ({ ...v, [name]: value }));

  async function handleSubmit() {
    setError("");
    const missing = fields.find(
      (f) => f.required && !String(values[f.name] ?? "").trim(),
    );
    if (missing) {
      setError(`${missing.label} is required.`);
      return;
    }
    setSaving(true);
    try {
      await onSubmit(values);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
      setSaving(false);
    }
  }

  return (
    <div className="flex max-w-4xl flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">{title}</h1>
        {subtitle && <p className="text-sm text-muted-foreground">{subtitle}</p>}
      </div>

      <Card>
        <CardContent className="grid grid-cols-1 gap-4 py-5 sm:grid-cols-2 lg:grid-cols-3">
          {fields.map((f) => {
            if (f.type === "checkbox") {
              return (
                <label
                  key={f.name}
                  className={cn(
                    "flex items-center gap-2 self-end pb-2 text-sm",
                    spanClass(f.colSpan),
                  )}
                >
                  <input
                    type="checkbox"
                    checked={Boolean(values[f.name])}
                    onChange={(e) => set(f.name, e.target.checked)}
                    className="h-4 w-4 rounded border-border"
                  />
                  {f.label}
                </label>
              );
            }
            return (
              <div key={f.name} className={cn("flex flex-col gap-1.5", spanClass(f.colSpan))}>
                <Label>
                  {f.label}
                  {f.required && <span className="text-destructive"> *</span>}
                </Label>
                {f.type === "select" ? (
                  <select
                    value={String(values[f.name] ?? "")}
                    onChange={(e) => set(f.name, e.target.value)}
                    className={FIELD_CLASS}
                  >
                    <option value="">Select…</option>
                    {(f.options ?? []).map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                ) : (
                  <Input
                    type={f.type === "number" ? "number" : f.type === "date" ? "date" : "text"}
                    inputMode={f.type === "number" ? "decimal" : undefined}
                    value={String(values[f.name] ?? "")}
                    onChange={(e) => set(f.name, e.target.value)}
                    placeholder={f.placeholder}
                  />
                )}
                {f.help && <p className="text-xs text-muted-foreground">{f.help}</p>}
              </div>
            );
          })}
        </CardContent>
      </Card>

      <div className="flex items-center justify-end gap-2">
        <Link href={cancelHref}>
          <Button variant="ghost" size="sm" type="button">
            Cancel
          </Button>
        </Link>
        <Button size="sm" onClick={handleSubmit} disabled={saving}>
          {saving ? "Saving…" : submitLabel}
        </Button>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  );
}
