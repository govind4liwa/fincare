"use client";

import { useEffect, useState } from "react";
import {
  createEmployeeSalary,
  listEmployeeSalaries,
  listSalaryComponents,
  type EmployeeSalary,
  type SalaryComponent,
} from "@/lib/payroll";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const fieldClass =
  "h-9 rounded-md border border-border bg-background px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40";

const money = (v: string) =>
  Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

type Props = { employeeId: string; entityId: string };

/** Effective-dated salary structure for one employee. Each change is a new
 * row (see backend docstring) — there is no edit, only versioning forward. */
export function EmployeeSalaryStructure({ employeeId, entityId }: Props) {
  const [rows, setRows] = useState<EmployeeSalary[]>([]);
  const [components, setComponents] = useState<SalaryComponent[]>([]);
  const [loadError, setLoadError] = useState("");
  const [componentId, setComponentId] = useState("");
  const [amount, setAmount] = useState("");
  const [effectiveFrom, setEffectiveFrom] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    Promise.all([listEmployeeSalaries(employeeId), listSalaryComponents(entityId)])
      .then(([s, c]) => {
        if (!active) return;
        setRows(s);
        setComponents(c.filter((x) => x.is_active));
      })
      .catch(() => {
        if (active) setLoadError("Couldn't load salary structure.");
      });
    return () => {
      active = false;
    };
  }, [employeeId, entityId]);

  async function add() {
    if (!componentId || !amount || !effectiveFrom) {
      return setError("Component, amount, and effective date are required.");
    }
    setSaving(true);
    setError("");
    try {
      await createEmployeeSalary({
        employee: employeeId,
        component: componentId,
        amount,
        effective_from: effectiveFrom,
        effective_to: null,
      });
      setRows(await listEmployeeSalaries(employeeId));
      setAmount("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card className="max-w-4xl">
      <CardHeader>
        <CardTitle>Salary Structure</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {loadError && <p className="text-sm text-destructive">{loadError}</p>}
        {rows.length > 0 && (
          <table className="w-full text-sm">
            <thead className="border-b border-border text-left text-xs text-muted-foreground">
              <tr>
                <th className="py-2 font-medium">Component</th>
                <th className="py-2 font-medium">Type</th>
                <th className="py-2 text-right font-medium">Amount</th>
                <th className="py-2 font-medium">Effective from</th>
                <th className="py-2 font-medium">Effective to</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="border-b border-border/60 last:border-0">
                  <td className="py-2">
                    {r.component_code} · {r.component_name}
                  </td>
                  <td className="py-2 capitalize text-muted-foreground">{r.component_type}</td>
                  <td className="py-2 text-right tabular-nums">{money(r.amount)}</td>
                  <td className="py-2 text-muted-foreground">{r.effective_from}</td>
                  <td className="py-2 text-muted-foreground">{r.effective_to || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div className="flex flex-col gap-1.5">
            <Label>Component</Label>
            <select
              value={componentId}
              onChange={(e) => setComponentId(e.target.value)}
              className={fieldClass}
            >
              <option value="">Select…</option>
              {components.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.code} · {c.name}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Amount</Label>
            <Input
              type="number"
              inputMode="decimal"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Effective from</Label>
            <Input
              type="date"
              value={effectiveFrom}
              onChange={(e) => setEffectiveFrom(e.target.value)}
            />
          </div>
        </div>
        <div>
          <Button size="sm" onClick={add} disabled={saving}>
            {saving ? "Adding…" : "Add to structure"}
          </Button>
        </div>

        {error && <p className="text-sm text-destructive">{error}</p>}
      </CardContent>
    </Card>
  );
}
