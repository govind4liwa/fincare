"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Plus, Scale } from "lucide-react";
import { useEntity } from "@/lib/entity-context";
import { listBankAccounts, type BankAccount } from "@/lib/banking";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

export default function BankingPage() {
  const router = useRouter();
  const { selectedId, selectedEntity } = useEntity();
  const [accounts, setAccounts] = useState<BankAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let active = true;
    listBankAccounts(selectedId)
      .then((rows) => {
        if (active) {
          setAccounts(rows);
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
          <h1 className="text-2xl font-semibold">Bank Accounts</h1>
          <p className="text-sm text-muted-foreground">
            {selectedEntity
              ? `${selectedEntity.numeric_code} · ${selectedEntity.trade_name || selectedEntity.legal_name}`
              : "All accessible entities"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link href="/reconcile">
            <Button variant="outline" size="sm">
              <Scale className="h-4 w-4" />
              Reconcile
            </Button>
          </Link>
          <Link href="/banking/new">
            <Button size="sm">
              <Plus className="h-4 w-4" />
              New bank account
            </Button>
          </Link>
        </div>
      </div>

      {loading ? (
        <p className="text-sm text-muted-foreground">Loading bank accounts…</p>
      ) : error ? (
        <p className="text-sm text-destructive">Couldn&apos;t load bank accounts.</p>
      ) : accounts.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-sm text-muted-foreground">
            No bank accounts yet. Add one (linked to a bank-type GL account) with the{" "}
            <span className="font-medium text-foreground">New bank account</span> button.
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b border-border text-left text-xs text-muted-foreground">
                  <tr>
                    <th className="px-4 py-2 font-medium">Code</th>
                    <th className="px-4 py-2 font-medium">Name</th>
                    <th className="px-4 py-2 font-medium">GL account</th>
                    <th className="px-4 py-2 font-medium">Bank</th>
                    <th className="px-4 py-2 text-center font-medium">Active</th>
                  </tr>
                </thead>
                <tbody>
                  {accounts.map((a) => (
                    <tr
                      key={a.id}
                      onClick={() => router.push(`/banking/${a.id}/edit`)}
                      className="cursor-pointer border-b border-border/60 last:border-0 hover:bg-accent/50"
                    >
                      <td className="whitespace-nowrap px-4 py-2 font-mono text-xs">{a.code}</td>
                      <td className="px-4 py-2">{a.name}</td>
                      <td className="whitespace-nowrap px-4 py-2 font-mono text-xs text-muted-foreground">
                        {a.gl_account_code}
                      </td>
                      <td className="px-4 py-2 text-muted-foreground">{a.bank_name || "—"}</td>
                      <td className="px-4 py-2 text-center">{a.is_active ? "✓" : "—"}</td>
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
