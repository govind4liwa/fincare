"use client";

import { useEffect, useState } from "react";
import { Download } from "lucide-react";
import { useEntity } from "@/lib/entity-context";
import {
  REPORTS,
  downloadReportXlsx,
  fetchReport,
  listPeriods,
  type Period,
  type ReportTable,
} from "@/lib/reports";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const MONEY = /^-?[\d,]+\.\d{2}$/;

export default function ReportsPage() {
  const { selectedId, selectedEntity } = useEntity();
  const [periods, setPeriods] = useState<Period[]>([]);
  const [periodId, setPeriodId] = useState("");
  const [code, setCode] = useState("TB");
  const [basis, setBasis] = useState("accrual");
  const [table, setTable] = useState<ReportTable | null>(null);
  const [error, setError] = useState(false);
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    if (!selectedId) return;
    let active = true;
    listPeriods(selectedId)
      .then((ps) => {
        if (!active) return;
        setPeriods(ps);
        setPeriodId(ps[0]?.id ?? "");
      })
      .catch(() => {
        if (active) setError(true);
      });
    return () => {
      active = false;
    };
  }, [selectedId]);

  useEffect(() => {
    if (!selectedId || !periodId) return;
    let active = true;
    fetchReport(code, selectedId, periodId, basis)
      .then((t) => {
        if (active) {
          setTable(t);
          setError(false);
        }
      })
      .catch(() => {
        if (active) setError(true);
      });
    return () => {
      active = false;
    };
  }, [selectedId, periodId, code, basis]);

  async function onExport() {
    if (!selectedId || !periodId) return;
    setExporting(true);
    try {
      await downloadReportXlsx(code, selectedId, periodId, basis);
    } catch {
      setError(true);
    } finally {
      setExporting(false);
    }
  }

  const selectClass =
    "h-9 rounded-md border border-border bg-background px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40";

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">Reports</h1>
        <p className="text-sm text-muted-foreground">
          {selectedEntity
            ? `${selectedEntity.numeric_code} · ${selectedEntity.trade_name || selectedEntity.legal_name}`
            : "Select an entity"}
        </p>
      </div>

      {!selectedId ? (
        <Card>
          <CardContent className="py-12 text-center text-sm text-muted-foreground">
            Reports are per-entity. Pick an entity from the switcher above to run one.
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <select
              aria-label="Report"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              className={selectClass}
            >
              {REPORTS.map((r) => (
                <option key={r.code} value={r.code}>
                  {r.title}
                </option>
              ))}
            </select>
            <select
              aria-label="Period"
              value={periodId}
              onChange={(e) => setPeriodId(e.target.value)}
              className={selectClass}
              disabled={periods.length === 0}
            >
              {periods.length === 0 ? (
                <option value="">No periods</option>
              ) : (
                periods.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))
              )}
            </select>
            <div className="flex items-center rounded-md border border-border p-0.5 text-sm">
              {["accrual", "cash"].map((b) => (
                <button
                  key={b}
                  onClick={() => setBasis(b)}
                  className={cn(
                    "rounded px-2 py-1 capitalize",
                    basis === b ? "bg-primary/10 text-primary" : "text-muted-foreground",
                  )}
                >
                  {b}
                </button>
              ))}
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={onExport}
              disabled={exporting || !periodId}
            >
              <Download className="h-4 w-4" />
              {exporting ? "Exporting…" : "Excel"}
            </Button>
          </div>

          {error ? (
            <p className="text-sm text-destructive">Couldn&apos;t build the report.</p>
          ) : periods.length === 0 ? (
            <Card>
              <CardContent className="py-12 text-center text-sm text-muted-foreground">
                No accounting periods for this entity yet.
              </CardContent>
            </Card>
          ) : !table ? (
            <p className="text-sm text-muted-foreground">Running report…</p>
          ) : (
            <Card>
              <CardContent className="p-0">
                <div className="flex items-center justify-between border-b border-border px-4 py-3">
                  <h2 className="font-semibold">{table.title}</h2>
                  {"balanced" in table.meta && (
                    <span
                      className={cn(
                        "rounded-full px-2 py-0.5 text-xs font-medium",
                        table.meta.balanced
                          ? "bg-primary/10 text-primary"
                          : "bg-destructive/10 text-destructive",
                      )}
                    >
                      {table.meta.balanced ? "Balanced" : "Unbalanced"}
                    </span>
                  )}
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="border-b border-border text-xs text-muted-foreground">
                      <tr>
                        {table.columns.map((c, i) => (
                          <th
                            key={c}
                            className={cn("px-4 py-2 font-medium", i === 0 ? "text-left" : "text-right")}
                          >
                            {c}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {table.rows.map((row, ri) => {
                        const isTotal = row.some((c) => /total|net profit/i.test(c));
                        return (
                          <tr
                            key={ri}
                            className={cn(
                              "border-b border-border/60 last:border-0",
                              isTotal && "font-semibold",
                            )}
                          >
                            {row.map((cell, ci) => (
                              <td
                                key={ci}
                                className={cn(
                                  "px-4 py-2",
                                  MONEY.test(cell)
                                    ? "text-right font-mono tabular-nums"
                                    : "text-left",
                                )}
                              >
                                {cell}
                              </td>
                            ))}
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
