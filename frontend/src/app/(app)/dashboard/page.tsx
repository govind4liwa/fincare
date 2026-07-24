"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiFetch } from "@/lib/api";

type Health = { status?: string; service?: string; version?: string };

const KPIS = [
  { label: "Revenue (MTD)", value: "—", hint: "Awaiting reports API" },
  { label: "Expenses (MTD)", value: "—", hint: "Awaiting reports API" },
  { label: "Cash & Bank", value: "—", hint: "Awaiting ledger API" },
  { label: "VAT Payable", value: "—", hint: "Awaiting tax API" },
];

export default function DashboardPage() {
  const [backend, setBackend] = useState<"checking" | "ok" | "down">("checking");
  const [version, setVersion] = useState<string>("");

  useEffect(() => {
    // Prove the API wiring end-to-end via the core liveness endpoint.
    apiFetch("/core/liveness/")
      .then(async (res) => {
        if (!res.ok) throw new Error();
        const data = (await res.json()) as Health;
        setVersion(data.version ?? "");
        setBackend("ok");
      })
      .catch(() => setBackend("down"));
  }, []);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Dashboard</h1>
          <p className="text-sm text-muted-foreground">Overview of your workspace.</p>
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
        {KPIS.map((kpi) => (
          <Card key={kpi.label}>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {kpi.label}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-semibold">{kpi.value}</div>
              <p className="mt-1 text-xs text-muted-foreground">{kpi.hint}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Getting started</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          This is the Phase 1.6 shell. Master-data screens (Chart of Accounts, customers,
          suppliers, vehicles, drivers), voucher/invoice entry, and the reports viewer are the
          next deliverables — each wired to the DRF API under <code>/api/v1</code>.
        </CardContent>
      </Card>
    </div>
  );
}
