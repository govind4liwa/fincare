"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEntity } from "@/lib/entity-context";
import {
  NATURE_BY_FIRST_DIGIT,
  listAccountGroups,
  type AccountGroup,
} from "@/lib/accounts";
import { createRecord } from "@/lib/crud";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const fieldClass =
  "h-9 rounded-md border border-border bg-background px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40";

export default function NewAccountGroupPage() {
  const router = useRouter();
  const { selectedId, selectedEntity } = useEntity();
  const [mainGroups, setMainGroups] = useState<AccountGroup[]>([]);
  const [level, setLevel] = useState<1 | 2>(2);
  const [parentId, setParentId] = useState("");
  const [segment, setSegment] = useState("");
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!selectedId) return;
    let active = true;
    listAccountGroups(selectedId, 1)
      .then((rows) => {
        if (active) setMainGroups(rows);
      })
      .catch(() => {
        if (active) setError("Couldn't load Main groups.");
      });
    return () => {
      active = false;
    };
  }, [selectedId]);

  const parent = mainGroups.find((g) => g.id === parentId);
  const nature = level === 1 ? NATURE_BY_FIRST_DIGIT[segment[0] ?? ""] : parent?.nature;
  const composedCode = useMemo(() => {
    const seg = /^\d{1,3}$/.test(segment) ? segment.padStart(3, "0") : "___";
    if (level === 1) return selectedEntity ? `${selectedEntity.numeric_code}-${seg}` : "—";
    return parent ? `${parent.code}-${seg}` : "—";
  }, [level, parent, segment, selectedEntity]);

  async function submit() {
    setError("");
    if (!/^\d{3}$/.test(segment)) return setError("Segment must be exactly 3 digits (e.g. 150).");
    if (level === 2 && !parentId) return setError("Select the Main group this Sub group belongs to.");
    if (!name.trim()) return setError("Name is required.");

    setSaving(true);
    try {
      await createRecord("account-groups", {
        entity: selectedId,
        level,
        segment,
        name,
        parent: level === 2 ? parentId : null,
      });
      router.push("/accounts/new");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
      setSaving(false);
    }
  }

  if (!selectedId) {
    return (
      <Card>
        <CardContent className="py-12 text-center text-sm text-muted-foreground">
          Pick an entity from the switcher above to add a group.
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="flex max-w-2xl flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">New Account Group</h1>
        <p className="text-sm text-muted-foreground">
          {selectedEntity?.numeric_code} ·{" "}
          {selectedEntity?.trade_name || selectedEntity?.legal_name}
        </p>
      </div>

      <Card>
        <CardContent className="flex flex-wrap items-center justify-between gap-3 py-4">
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Group code</p>
            <p className="font-mono text-lg font-semibold">{composedCode}</p>
            {nature && <p className="text-xs text-muted-foreground capitalize">{nature}</p>}
          </div>
          <p className="max-w-sm text-xs text-muted-foreground">
            The code is composed from the entity + segment (Main) or parent + segment (Sub), and
            can’t be edited once the group exists (ADR-0004).
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="flex flex-col gap-4 py-5">
          <div className="flex flex-col gap-1.5">
            <Label>Tier</Label>
            <div className="flex items-center rounded-md border border-border p-0.5 text-sm w-fit">
              {(
                [
                  [1, "Main"],
                  [2, "Sub"],
                ] as const
              ).map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setLevel(value)}
                  className={cn(
                    "rounded px-3 py-1",
                    level === value ? "bg-primary/10 text-primary" : "text-muted-foreground",
                  )}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {level === 2 && (
            <div className="flex flex-col gap-1.5">
              <Label>
                Main group<span className="text-destructive"> *</span>
              </Label>
              <select
                value={parentId}
                onChange={(e) => setParentId(e.target.value)}
                className={fieldClass}
              >
                <option value="">Select Main group…</option>
                {mainGroups.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.code} · {g.name} ({g.nature})
                  </option>
                ))}
              </select>
              <p className="text-xs text-muted-foreground">
                The Sub group inherits this Main group&apos;s nature.
              </p>
            </div>
          )}

          <div className="flex flex-col gap-1.5">
            <Label>
              Segment<span className="text-destructive"> *</span>
            </Label>
            <Input
              value={segment}
              onChange={(e) => setSegment(e.target.value.replace(/\D/g, "").slice(0, 3))}
              placeholder={level === 1 ? "150" : "410"}
              inputMode="numeric"
              className="font-mono"
            />
            {level === 1 && (
              <p className="text-xs text-muted-foreground">
                First digit fixes the nature: 1 asset, 2 liability, 3 equity, 4 income, 5–7 expense.
              </p>
            )}
          </div>

          <div className="flex flex-col gap-1.5">
            <Label>
              Name<span className="text-destructive"> *</span>
            </Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} />
          </div>
        </CardContent>
      </Card>

      <div className="flex items-center justify-end gap-2">
        <Link href="/accounts/new">
          <Button variant="ghost" size="sm" type="button">
            Cancel
          </Button>
        </Link>
        <Button size="sm" onClick={submit} disabled={saving}>
          {saving ? "Saving…" : "Create group"}
        </Button>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  );
}
