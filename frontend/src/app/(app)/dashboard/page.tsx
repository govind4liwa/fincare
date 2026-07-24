"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiFetch } from "@/lib/api";
import { useEntity } from "@/lib/entity-context";
import { getDashboard, type DashboardSummary } from "@/lib/dashboard";

type Health = { status?: string; service?: string; version?: string };

function money(value: string | undefined): string {
  if (value === undefined) return "—";
  const n = Number(value);
  return Number.isFinite(n)
    ? n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    : value;
}

export default function DashboardPage() {
  const { selectedId, selectedEntity } = useEntity();
  const [backend, setBackend] = useState<"checking" | "ok" | "down">("checking");
  const [version, setVersion] = useState<string>("");
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [kpiError, setKpiError] = useState(false);

  useEffect(() => {
    apiFetch("/core/liveness/")
      .then(async (res) => {
        if (!res.ok) throw new Error();
        const data = (await res.json()) as Health;
        setVersion(data.version ?? "");
        setBackend("ok");
      })
      .catch(() => setBackend("down"));
  }, []);

  useEffect(() => {
    let active = true;
    getDashboard(selectedId)
      .then((data) => {
        if (active) {
          setSummary(data);
          setKpiError(false);
        }
      })
      .catch(() => {
        if (active) setKpiError(true);
      });
    return () => {
      active = false;
    };
  }, [selectedId]);

  const kpis = [
    { label: "Revenue (period)", value: summary?.revenue, hint: "Income posted this period" },
    { label: "Expenses (period)", value: summary?.expenses, hint: "Expenses posted this period" },
    { label: "Cash & Bank", value: summary?.cash_bank, hint: "Closing balance" },
    { label: "VAT Payable", value: summary?.vat_payable, hint: "Output − recoverable input" },
  ];

  const subtitle = summary?.period
    ? `Overview · ${summary.period.name}`
    : "Overview of your workspace.";

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Dashboard</h1>
          <p className="text-sm text-muted-foreground">{subtitle}</p>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <span
            className={
              backend === "ok"
                ? "h-2 w-2 rounded-full bg-primary"
                : backend === "down"
                  ? "h-2 w-2 rounded-full bg-destructive"
                  : "h-2 w-2 rounded-full bg-muted-foreground animate-pulse"
            }
          />
          <span className="text-muted-foreground">
            API{" "}
            {backend === "ok"
              ? `connected${version ? ` · v${version}` : ""}`
              : backend === "down"
                ? "unreachable"
                : "checking…"}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {kpis.map((kpi) => (
          <Card key={kpi.label}>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {kpi.label}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-baseline gap-1">
                <span className="text-xs text-muted-foreground">AED</span>
                <span className="text-2xl font-semibold tabular-nums">{money(kpi.value)}</span>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                {kpiError ? "Couldn't load" : kpi.hint}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Getting started</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          {selectedEntity
            ? `Showing figures for ${selectedEntity.trade_name || selectedEntity.legal_name}. `
            : "Showing figures across all accessible entities. "}
          Browse the Chart of Accounts, Vouchers, and Customers &amp; Suppliers from the sidebar.
          Voucher/invoice entry forms and the full reports viewer are the next deliverables.
        </CardContent>
      </Card>
    </div>
  );
}
