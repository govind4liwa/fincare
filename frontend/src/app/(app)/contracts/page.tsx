"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Plus } from "lucide-react";
import { useEntity } from "@/lib/entity-context";
import { generateContractInvoice, listContracts, type Contract } from "@/lib/bookings";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const money = (v: string) =>
  Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const STATUS_STYLE: Record<Contract["status"], string> = {
  active: "bg-primary/10 text-primary",
  suspended: "bg-amber-500/10 text-amber-700 dark:text-amber-400",
  ended: "bg-muted text-muted-foreground",
};

export default function ContractsPage() {
  const router = useRouter();
  const { selectedId, selectedEntity } = useEntity();
  const [contracts, setContracts] = useState<Contract[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [dates, setDates] = useState<Record<string, string>>({});
  const [busyId, setBusyId] = useState("");
  const [error, setError] = useState("");
  const [lastInvoice, setLastInvoice] = useState("");

  useEffect(() => {
    let active = true;
    listContracts(selectedId)
      .then((rows) => {
        if (active) {
          setContracts(rows);
          setLoadError(false);
        }
      })
      .catch(() => {
        if (active) setLoadError(true);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [selectedId]);

  async function generate(contract: Contract) {
    const invoiceDate = dates[contract.id];
    if (!invoiceDate) return setError("Pick an invoice date first.");
    setBusyId(contract.id);
    setError("");
    setLastInvoice("");
    try {
      const res = await generateContractInvoice(contract.id, invoiceDate, "");
      setLastInvoice(`${res.invoice_no} generated for ${contract.contract_no}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setBusyId("");
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Contracts</h1>
          <p className="text-sm text-muted-foreground">
            {selectedEntity
              ? `${selectedEntity.numeric_code} · ${selectedEntity.trade_name || selectedEntity.legal_name}`
              : "All accessible entities"}
          </p>
        </div>
        <Link href="/contracts/new">
          <Button size="sm">
            <Plus className="h-4 w-4" />
            New contract
          </Button>
        </Link>
      </div>

      {loading ? (
        <p className="text-sm text-muted-foreground">Loading contracts…</p>
      ) : loadError ? (
        <p className="text-sm text-destructive">Couldn&apos;t load contracts.</p>
      ) : contracts.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-sm text-muted-foreground">
            No contracts yet. Add one with the{" "}
            <span className="font-medium text-foreground">New contract</span> button.
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b border-border text-left text-xs text-muted-foreground">
                  <tr>
                    <th className="px-4 py-2 font-medium">Contract</th>
                    <th className="px-4 py-2 font-medium">Customer</th>
                    <th className="px-4 py-2 font-medium">Cycle</th>
                    <th className="px-4 py-2 text-right font-medium">Amount</th>
                    <th className="px-4 py-2 font-medium">Status</th>
                    <th className="px-4 py-2 text-right font-medium">Generate invoice</th>
                  </tr>
                </thead>
                <tbody>
                  {contracts.map((c) => (
                    <tr key={c.id} className="border-b border-border/60 last:border-0">
                      <td
                        className="cursor-pointer px-4 py-2 font-mono text-xs hover:underline"
                        onClick={() => router.push(`/contracts/${c.id}/edit`)}
                      >
                        {c.contract_no}
                      </td>
                      <td className="px-4 py-2">{c.customer_name}</td>
                      <td className="px-4 py-2 capitalize text-muted-foreground">
                        {c.billing_cycle}
                      </td>
                      <td className="px-4 py-2 text-right tabular-nums">
                        {money(c.monthly_amount)}
                      </td>
                      <td className="px-4 py-2">
                        <span
                          className={cn(
                            "rounded-full px-2 py-0.5 text-xs font-medium capitalize",
                            STATUS_STYLE[c.status],
                          )}
                        >
                          {c.status}
                        </span>
                      </td>
                      <td className="px-4 py-2">
                        {c.status === "active" && (
                          <div className="flex items-center justify-end gap-2">
                            <Input
                              type="date"
                              className="h-8 w-36"
                              value={dates[c.id] ?? ""}
                              onChange={(e) =>
                                setDates((prev) => ({ ...prev, [c.id]: e.target.value }))
                              }
                            />
                            <Button
                              size="sm"
                              disabled={busyId === c.id}
                              onClick={() => generate(c)}
                            >
                              {busyId === c.id ? "Generating…" : "Generate"}
                            </Button>
                          </div>
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

      {lastInvoice && <p className="text-sm text-emerald-600 dark:text-emerald-400">{lastInvoice}</p>}
      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  );
}
