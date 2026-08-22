"use client";

import { useEffect, useState } from "react";
import { useEntity } from "@/lib/entity-context";
import { listAccounts, type Account } from "@/lib/accounts";
import {
  createSalaryComponent,
  listSalaryComponents,
  updateSalaryComponent,
  type SalaryComponent,
} from "@/lib/payroll";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";

const fieldClass =
  "h-9 rounded-md border border-border bg-background px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40";

type EditValues = {
  code: string;
  name: string;
  component_type: string;
  is_gratuity_base: boolean;
  is_wps_fixed: boolean;
  account: string;
};

export default function SalaryComponentsPage() {
  const { selectedId, selectedEntity } = useEntity();
  const [components, setComponents] = useState<SalaryComponent[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [loadError, setLoadError] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const [form, setForm] = useState({
    code: "",
    name: "",
    component_type: "earning",
    is_gratuity_base: false,
    is_wps_fixed: true,
    account: "",
  });

  const [editingId, setEditingId] = useState("");
  const [editForm, setEditForm] = useState<EditValues | null>(null);
  const [savingEdit, setSavingEdit] = useState(false);

  useEffect(() => {
    if (!selectedId) return;
    let active = true;
    Promise.all([listSalaryComponents(selectedId), listAccounts(selectedId)])
      .then(([c, a]) => {
        if (!active) return;
        setComponents(c);
        setAccounts(a.filter((x) => x.is_active && x.is_postable));
      })
      .catch(() => {
        if (active) setLoadError("Couldn't load salary components.");
      });
    return () => {
      active = false;
    };
  }, [selectedId]);

  async function add() {
    if (!selectedId || !form.code || !form.name || !form.account) {
      return setError("Code, name, and account are required.");
    }
    setSaving(true);
    setError("");
    try {
      const created = await createSalaryComponent({ ...form, entity: selectedId });
      setComponents((prev) => [...prev, created]);
      setForm((p) => ({ ...p, code: "", name: "" }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setSaving(false);
    }
  }

  function startEdit(c: SalaryComponent) {
    setError("");
    setEditingId(c.id);
    setEditForm({
      code: c.code,
      name: c.name,
      component_type: c.component_type,
      is_gratuity_base: c.is_gratuity_base,
      is_wps_fixed: c.is_wps_fixed,
      account: c.account ?? "",
    });
  }

  function cancelEdit() {
    setEditingId("");
    setEditForm(null);
  }

  async function saveEdit(id: string) {
    if (!editForm) return;
    if (!editForm.code || !editForm.name || !editForm.account) {
      return setError("Code, name, and account are required.");
    }
    setSavingEdit(true);
    setError("");
    try {
      const updated = await updateSalaryComponent(id, editForm);
      setComponents((prev) => prev.map((c) => (c.id === id ? updated : c)));
      cancelEdit();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setSavingEdit(false);
    }
  }

  if (!selectedId) {
    return (
      <Card>
        <CardContent className="py-12 text-center text-sm text-muted-foreground">
          Pick an entity from the switcher above to manage salary components.
        </CardContent>
      </Card>
    );
  }
  if (loadError) return <p className="text-sm text-destructive">{loadError}</p>;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">Salary Components</h1>
        <p className="text-sm text-muted-foreground">
          {selectedEntity?.numeric_code} ·{" "}
          {selectedEntity?.trade_name || selectedEntity?.legal_name} — earning/deduction line
          types used to build employee salary structures and payslips.
        </p>
      </div>

      <Card>
        <CardContent className="flex flex-wrap items-end gap-3 py-5">
          <div className="flex flex-col gap-1.5">
            <Label>Code</Label>
            <Input
              value={form.code}
              onChange={(e) => setForm((p) => ({ ...p, code: e.target.value.toUpperCase() }))}
              placeholder="BASIC"
              className="w-28"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Name</Label>
            <Input
              value={form.name}
              onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Type</Label>
            <select
              value={form.component_type}
              onChange={(e) => setForm((p) => ({ ...p, component_type: e.target.value }))}
              className={fieldClass}
            >
              <option value="earning">Earning</option>
              <option value="deduction">Deduction</option>
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>GL account</Label>
            <select
              value={form.account}
              onChange={(e) => setForm((p) => ({ ...p, account: e.target.value }))}
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
          <label className="flex items-center gap-2 pb-2 text-sm">
            <input
              type="checkbox"
              checked={form.is_gratuity_base}
              onChange={(e) => setForm((p) => ({ ...p, is_gratuity_base: e.target.checked }))}
              className="h-4 w-4 rounded border-border"
            />
            Gratuity base
          </label>
          <label className="flex items-center gap-2 pb-2 text-sm">
            <input
              type="checkbox"
              checked={form.is_wps_fixed}
              onChange={(e) => setForm((p) => ({ ...p, is_wps_fixed: e.target.checked }))}
              className="h-4 w-4 rounded border-border"
            />
            WPS fixed
          </label>
          <Button size="sm" onClick={add} disabled={saving}>
            {saving ? "Adding…" : "Add component"}
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          <table className="w-full text-sm">
            <thead className="border-b border-border text-left text-xs text-muted-foreground">
              <tr>
                <th className="px-4 py-2 font-medium">Code</th>
                <th className="px-4 py-2 font-medium">Name</th>
                <th className="px-4 py-2 font-medium">Type</th>
                <th className="px-4 py-2 font-medium">Account</th>
                <th className="px-4 py-2 text-center font-medium">Gratuity base</th>
                <th className="px-4 py-2 text-center font-medium">WPS fixed</th>
                <th className="px-4 py-2 text-right font-medium" />
              </tr>
            </thead>
            <tbody>
              {components.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">
                    No salary components yet.
                  </td>
                </tr>
              ) : (
                components.map((c) => {
                  if (editingId === c.id && editForm) {
                    return (
                      <tr key={c.id} className="border-b border-border/60 bg-accent/20 last:border-0">
                        <td className="px-4 py-2">
                          <Input
                            value={editForm.code}
                            onChange={(e) =>
                              setEditForm((p) => p && { ...p, code: e.target.value.toUpperCase() })
                            }
                            className="w-24"
                          />
                        </td>
                        <td className="px-4 py-2">
                          <Input
                            value={editForm.name}
                            onChange={(e) => setEditForm((p) => p && { ...p, name: e.target.value })}
                          />
                        </td>
                        <td className="px-4 py-2">
                          <select
                            value={editForm.component_type}
                            onChange={(e) =>
                              setEditForm((p) => p && { ...p, component_type: e.target.value })
                            }
                            className={fieldClass}
                          >
                            <option value="earning">Earning</option>
                            <option value="deduction">Deduction</option>
                          </select>
                        </td>
                        <td className="px-4 py-2">
                          <select
                            value={editForm.account}
                            onChange={(e) =>
                              setEditForm((p) => p && { ...p, account: e.target.value })
                            }
                            className={fieldClass}
                          >
                            <option value="">Select…</option>
                            {accounts.map((a) => (
                              <option key={a.id} value={a.id}>
                                {a.code} · {a.name}
                              </option>
                            ))}
                          </select>
                        </td>
                        <td className="px-4 py-2 text-center">
                          <input
                            type="checkbox"
                            checked={editForm.is_gratuity_base}
                            onChange={(e) =>
                              setEditForm((p) => p && { ...p, is_gratuity_base: e.target.checked })
                            }
                            className="h-4 w-4 rounded border-border"
                          />
                        </td>
                        <td className="px-4 py-2 text-center">
                          <input
                            type="checkbox"
                            checked={editForm.is_wps_fixed}
                            onChange={(e) =>
                              setEditForm((p) => p && { ...p, is_wps_fixed: e.target.checked })
                            }
                            className="h-4 w-4 rounded border-border"
                          />
                        </td>
                        <td className="px-4 py-2 text-right whitespace-nowrap">
                          <Button size="sm" disabled={savingEdit} onClick={() => saveEdit(c.id)}>
                            {savingEdit ? "Saving…" : "Save"}
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="ml-2"
                            disabled={savingEdit}
                            onClick={cancelEdit}
                          >
                            Cancel
                          </Button>
                        </td>
                      </tr>
                    );
                  }
                  return (
                    <tr key={c.id} className="border-b border-border/60 last:border-0">
                      <td className="px-4 py-2 font-mono text-xs">{c.code}</td>
                      <td className="px-4 py-2">
                        {c.name}
                        {c.entity === null && (
                          <span className="ml-1 text-xs text-muted-foreground">(group-wide)</span>
                        )}
                      </td>
                      <td className="px-4 py-2 capitalize text-muted-foreground">
                        {c.component_type}
                      </td>
                      <td className="px-4 py-2 font-mono text-xs text-muted-foreground">
                        {c.account_code || "—"}
                      </td>
                      <td className="px-4 py-2 text-center">{c.is_gratuity_base ? "✓" : "—"}</td>
                      <td className="px-4 py-2 text-center">{c.is_wps_fixed ? "✓" : "—"}</td>
                      <td className="px-4 py-2 text-right">
                        <Button size="sm" variant="outline" onClick={() => startEdit(c)}>
                          Edit
                        </Button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </CardContent>
      </Card>

      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  );
}
