"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Plus, Search } from "lucide-react";
import { useEntity } from "@/lib/entity-context";
import { listAccounts, type Account, type Nature } from "@/lib/accounts";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const NATURE_ORDER: Nature[] = ["asset", "liability", "equity", "income", "expense"];
const NATURE_LABEL: Record<Nature, string> = {
  asset: "Assets",
  liability: "Liabilities",
  equity: "Equity",
  income: "Income",
  expense: "Expenses",
};

export default function AccountsPage() {
  const router = useRouter();
  const { selectedId, selectedEntity } = useEntity();
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [query, setQuery] = useState("");

  useEffect(() => {
    let active = true;
    listAccounts(selectedId)
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

  const filtered = useMemo(() => {
    const term = query.trim().toLowerCase();
    if (!term) return accounts;
    return accounts.filter(
      (a) => a.code.toLowerCase().includes(term) || a.name.toLowerCase().includes(term),
    );
  }, [accounts, query]);

  const byNature = useMemo(() => {
    const groups = new Map<Nature, Account[]>();
    for (const a of filtered) {
      const list = groups.get(a.nature) ?? [];
      list.push(a);
      groups.set(a.nature, list);
    }
    return groups;
  }, [filtered]);

  const scope = selectedEntity
    ? `${selectedEntity.numeric_code} · ${selectedEntity.trade_name || selectedEntity.legal_name}`
    : "All accessible entities";

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Chart of Accounts</h1>
          <p className="text-sm text-muted-foreground">{scope}</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative w-full max-w-xs">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search code or name…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="pl-8"
            />
          </div>
          <Link href="/accounts/new">
            <Button size="sm" className="whitespace-nowrap">
              <Plus className="h-4 w-4" />
              New account
            </Button>
          </Link>
        </div>
      </div>

      {loading ? (
        <p className="text-sm text-muted-foreground">Loading accounts…</p>
      ) : error ? (
        <p className="text-sm text-destructive">Couldn&apos;t load the chart of accounts.</p>
      ) : accounts.length === 0 ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            No accounts yet{selectedEntity ? ` for ${selectedEntity.legal_name}` : ""}. Seed a chart
            of accounts (e.g. <code>manage.py seed_coa</code>) to populate this view.
          </CardContent>
        </Card>
      ) : filtered.length === 0 ? (
        <p className="text-sm text-muted-foreground">No accounts match “{query}”.</p>
      ) : (
        <div className="flex flex-col gap-5">
          {NATURE_ORDER.filter((n) => byNature.has(n)).map((nature) => {
            const rows = byNature.get(nature)!;
            return (
              <Card key={nature}>
                <CardHeader className="flex-row items-center justify-between py-4">
                  <CardTitle className="text-base">{NATURE_LABEL[nature]}</CardTitle>
                  <span className="text-xs text-muted-foreground">{rows.length}</span>
                </CardHeader>
                <CardContent className="p-0">
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="border-y border-border text-left text-xs text-muted-foreground">
                        <tr>
                          <th className="px-4 py-2 font-medium">Code</th>
                          <th className="px-4 py-2 font-medium">Account</th>
                          <th className="px-4 py-2 font-medium">Group</th>
                          <th className="px-4 py-2 font-medium">Type</th>
                          <th className="px-4 py-2 text-center font-medium">Dr/Cr</th>
                        </tr>
                      </thead>
                      <tbody>
                        {rows.map((a) => (
                          <tr
                            key={a.id}
                            onClick={() => router.push(`/accounts/${a.id}/edit`)}
                            className={cn(
                              "cursor-pointer border-b border-border/60 last:border-0 hover:bg-accent/50",
                              !a.is_active && "opacity-50",
                            )}
                          >
                            <td className="whitespace-nowrap px-4 py-2 font-mono text-xs">{a.code}</td>
                            <td className="px-4 py-2">
                              <span>{a.name}</span>
                              {a.is_control_account && (
                                <span className="ml-2 rounded bg-accent px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-muted-foreground">
                                  control
                                </span>
                              )}
                              {a.is_bank_account && (
                                <span className="ml-2 rounded bg-accent px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-muted-foreground">
                                  bank
                                </span>
                              )}
                            </td>
                            <td className="px-4 py-2 text-muted-foreground">{a.sub_group_name}</td>
                            <td className="px-4 py-2 text-muted-foreground">{a.account_type_display}</td>
                            <td className="px-4 py-2 text-center font-medium">
                              {a.normal_balance === "D" ? "Dr" : "Cr"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
