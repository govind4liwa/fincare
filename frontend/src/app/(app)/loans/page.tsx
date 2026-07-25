"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Plus } from "lucide-react";
import { useEntity } from "@/lib/entity-context";
import { listLoans, type VehicleLoan } from "@/lib/loans";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

const money = (v: string) =>
  Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const METHOD_LABEL: Record<string, string> = {
  reducing_balance: "Reducing balance",
  flat_rate: "Flat rate",
  flat_quoted_effective: "Flat quoted / effective split",
};

export default function LoansPage() {
  const router = useRouter();
  const { selectedId, selectedEntity } = useEntity();
  const [loans, setLoans] = useState<VehicleLoan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let active = true;
    listLoans(selectedId)
      .then((rows) => {
        if (active) {
          setLoans(rows);
          setError(false);
        }
      })
      .catch(() => {
        if (active) setError(true);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [selectedId]);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Vehicle Loans</h1>
          <p className="text-sm text-muted-foreground">
            {selectedEntity
              ? `${selectedEntity.numeric_code} · ${selectedEntity.trade_name || selectedEntity.legal_name}`
              : "All accessible entities"}
          </p>
        </div>
        <Link href="/loans/new">
          <Button size="sm">
            <Plus className="h-4 w-4" />
            New loan
          </Button>
        </Link>
      </div>

      {loading ? (
        <p className="text-sm text-muted-foreground">Loading loans…</p>
      ) : error ? (
        <p className="text-sm text-destructive">Couldn&apos;t load vehicle loans.</p>
      ) : loans.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-sm text-muted-foreground">
            No vehicle loans yet. Add one, then generate its EMI schedule.
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b border-border text-left text-xs text-muted-foreground">
                  <tr>
                    <th className="px-4 py-2 font-medium">Vehicle</th>
                    <th className="px-4 py-2 font-medium">Lender</th>
                    <th className="px-4 py-2 text-right font-medium">Principal</th>
                    <th className="px-4 py-2 text-center font-medium">Term</th>
                    <th className="px-4 py-2 font-medium">Method</th>
                    <th className="px-4 py-2 text-center font-medium">Schedule</th>
                  </tr>
                </thead>
                <tbody>
                  {loans.map((l) => (
                    <tr
                      key={l.id}
                      onClick={() => router.push(`/loans/${l.id}`)}
                      className="cursor-pointer border-b border-border/60 last:border-0 hover:bg-accent/50"
                    >
                      <td className="whitespace-nowrap px-4 py-2 font-mono text-xs">
                        {l.vehicle_code}
                      </td>
                      <td className="px-4 py-2">{l.lender || "—"}</td>
                      <td className="whitespace-nowrap px-4 py-2 text-right font-medium tabular-nums">
                        {money(l.principal)}
                      </td>
                      <td className="px-4 py-2 text-center text-muted-foreground">
                        {l.term_months ?? "—"}
                      </td>
                      <td className="px-4 py-2 text-muted-foreground">
                        {METHOD_LABEL[l.amortization_method] ?? l.amortization_method}
                      </td>
                      <td className="px-4 py-2 text-center">
                        {l.approved_schedule_version ? (
                          <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                            v{l.approved_schedule_version} approved
                          </span>
                        ) : (
                          <span className="text-xs text-muted-foreground">none</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
