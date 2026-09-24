"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Lock, Unlock, XCircle } from "lucide-react";
import { useEntity } from "@/lib/entity-context";
import {
  closePeriod,
  createPeriod,
  listPeriods,
  lockPeriod,
  reopenPeriod,
  type Period,
} from "@/lib/reports";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const STATUS_STYLE: Record<Period["status"], string> = {
  open: "bg-primary/10 text-primary",
  closed: "bg-amber-500/10 text-amber-700 dark:text-amber-400",
  locked: "bg-destructive/10 text-destructive",
};

const MONTH_NAMES = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];

/** Derive a calendar-month period's fields from a "YYYY-MM" picker value —
 * covers the common case (fiscal year = calendar year, one period per
 * month); anything else still exists in the model, just not in this quick
 * form. */
function monthDefaults(monthStr: string) {
  const [year, month] = monthStr.split("-").map(Number);
  const start_date = `${monthStr}-01`;
  const lastDay = new Date(year, month, 0).getDate();
  const end_date = `${monthStr}-${String(lastDay).padStart(2, "0")}`;
  const name = `${MONTH_NAMES[month - 1]}-${year}`;
  return { fiscal_year: year, period_no: month, start_date, end_date, name };
}

export default function PeriodsPage() {
  const { selectedId, selectedEntity } = useEntity();
  const [periods, setPeriods] = useState<Period[]>([]);
  const [busyId, setBusyId] = useState("");
  const [error, setError] = useState("");
  const [loadError, setLoadError] = useState("");

  const [month, setMonth] = useState("");
  const [name, setName] = useState("");
  const [nameTouched, setNameTouched] = useState(false);
  const [creating, setCreating] = useState(false);

  const defaults = useMemo(() => (month ? monthDefaults(month) : null), [month]);

  function pickMonth(value: string) {
    setMonth(value);
    if (!nameTouched && value) setName(monthDefaults(value).name);
  }

  const reload = useCallback(async () => {
    if (!selectedId) return;
    const rows = await listPeriods(selectedId);
    setPeriods(rows);
  }, [selectedId]);

  useEffect(() => {
    if (!selectedId) return;
    let active = true;
    listPeriods(selectedId)
      .then((rows) => {
        if (active) setPeriods(rows);
      })
      .catch(() => {
        if (active) setLoadError("Couldn't load accounting periods.");
      });
    return () => {
      active = false;
    };
  }, [selectedId]);

  async function transition(id: string, fn: (id: string) => Promise<Period>) {
    setBusyId(id);
    setError("");
    try {
      await fn(id);
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setBusyId("");
    }
  }

  async function create() {
    if (!selectedId || !defaults) return setError("Pick a month first.");
    setCreating(true);
    setError("");
    try {
      await createPeriod({ entity: selectedId, ...defaults, name });
      await reload();
      setMonth("");
      setName("");
      setNameTouched(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setCreating(false);
    }
  }

  if (!selectedId) {
    return (
      <Card>
        <CardContent className="py-12 text-center text-sm text-muted-foreground">
          Pick an entity from the switcher above to manage its accounting periods.
        </CardContent>
      </Card>
    );
  }
  if (loadError) return <p className="text-sm text-destructive">{loadError}</p>;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">Accounting Periods</h1>
        <p className="text-sm text-muted-foreground">
          {selectedEntity?.numeric_code} ·{" "}
          {selectedEntity?.trade_name || selectedEntity?.legal_name}
        </p>
      </div>

      <Card className="max-w-xl">
        <CardContent className="flex flex-wrap items-end gap-3 py-5">
          <div className="flex flex-col gap-1.5">
            <Label>Month</Label>
            <Input type="month" value={month} onChange={(e) => pickMonth(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Name</Label>
            <Input
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                setNameTouched(true);
              }}
              className="w-32"
            />
          </div>
          <Button size="sm" onClick={create} disabled={creating || !month}>
            {creating ? "Creating…" : "New period"}
          </Button>
          {defaults && (
            <span className="text-xs text-muted-foreground">
              {defaults.start_date} – {defaults.end_date} · FY{defaults.fiscal_year} #
              {defaults.period_no}
            </span>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          <table className="w-full text-sm">
            <thead className="border-b border-border text-left text-xs text-muted-foreground">
              <tr>
                <th className="px-4 py-2 font-medium">Period</th>
                <th className="px-4 py-2 font-medium">Dates</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 font-medium">Closed</th>
                <th className="px-4 py-2 text-right font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {periods.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">
                    No accounting periods for this entity yet.
                  </td>
                </tr>
              ) : (
                periods.map((p) => {
                  const busy = busyId === p.id;
                  return (
                    <tr key={p.id} className="border-b border-border/60 last:border-0">
                      <td className="px-4 py-2 font-medium">{p.name}</td>
                      <td className="px-4 py-2 text-muted-foreground">
                        {p.start_date} – {p.end_date}
                      </td>
                      <td className="px-4 py-2">
                        <span
                          className={cn(
                            "rounded-full px-2 py-0.5 text-xs font-medium capitalize",
                            STATUS_STYLE[p.status],
                          )}
                        >
                          {p.status}
                        </span>
                      </td>
                      <td className="px-4 py-2 text-xs text-muted-foreground">
                        {p.closed_at ? `${p.closed_at.slice(0, 10)}${p.closed_by_email ? ` · ${p.closed_by_email}` : ""}` : "—"}
                      </td>
                      <td className="px-4 py-2">
                        <div className="flex items-center justify-end gap-2">
                          {p.status === "open" && (
                            <Button
                              variant="outline"
                              size="sm"
                              disabled={busy}
                              onClick={() => transition(p.id, closePeriod)}
                            >
                              <XCircle className="h-4 w-4" />
                              {busy ? "Closing…" : "Close"}
                            </Button>
                          )}
                          {p.status === "closed" && (
                            <>
                              <Button
                                variant="outline"
                                size="sm"
                                disabled={busy}
                                onClick={() => transition(p.id, reopenPeriod)}
                              >
                                <Unlock className="h-4 w-4" />
                                {busy ? "Reopening…" : "Reopen"}
                              </Button>
                              <Button
                                variant="outline"
                                size="sm"
                                disabled={busy}
                                onClick={() => transition(p.id, lockPeriod)}
                              >
                                <Lock className="h-4 w-4" />
                                {busy ? "Locking…" : "Lock"}
                              </Button>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </CardContent>
      </Card>

      <p className="text-xs text-muted-foreground">
        A new period opens directly — nothing can post into a date until its period exists.
        Closing blocks new postings into a period but can be reopened for a correction. Locking is
        one-way — a locked period never reopens. Creating and close/reopen need an accounting
        role; locking needs a manager or admin role.
      </p>

      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  );
}
