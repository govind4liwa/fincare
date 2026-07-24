"use client";

import { useEffect, useMemo, useState } from "react";
import { Search } from "lucide-react";
import { useEntity } from "@/lib/entity-context";
import {
  listCustomers,
  listSuppliers,
  type Customer,
  type Supplier,
} from "@/lib/parties";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

type Tab = "customers" | "suppliers";

export default function PartiesPage() {
  const { selectedId, selectedEntity } = useEntity();
  const [tab, setTab] = useState<Tab>("customers");
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [query, setQuery] = useState("");

  useEffect(() => {
    let active = true;
    Promise.all([listCustomers(selectedId), listSuppliers(selectedId)])
      .then(([c, s]) => {
        if (active) {
          setCustomers(c);
          setSuppliers(s);
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

  const rows = tab === "customers" ? customers : suppliers;

  const filtered = useMemo(() => {
    const term = query.trim().toLowerCase();
    if (!term) return rows;
    return rows.filter(
      (r) =>
        r.code.toLowerCase().includes(term) ||
        r.name.toLowerCase().includes(term) ||
        r.trn.toLowerCase().includes(term),
    );
  }, [rows, query]);

  const tabClass = (t: Tab) =>
    cn(
      "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
      tab === t ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-accent",
    );

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Customers &amp; Suppliers</h1>
          <p className="text-sm text-muted-foreground">
            {selectedEntity
              ? `${selectedEntity.numeric_code} · ${selectedEntity.trade_name || selectedEntity.legal_name}`
              : "All accessible entities"}
          </p>
        </div>
        <div className="relative w-full max-w-xs">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search code, name or TRN…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="pl-8"
          />
        </div>
      </div>

      <div className="flex items-center gap-1 rounded-lg border border-border bg-card p-1 w-fit">
        <button className={tabClass("customers")} onClick={() => setTab("customers")}>
          Customers <span className="text-xs opacity-70">({customers.length})</span>
        </button>
        <button className={tabClass("suppliers")} onClick={() => setTab("suppliers")}>
          Suppliers <span className="text-xs opacity-70">({suppliers.length})</span>
        </button>
      </div>

      {loading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : error ? (
        <p className="text-sm text-destructive">Couldn&apos;t load customers &amp; suppliers.</p>
      ) : filtered.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-sm text-muted-foreground">
            {rows.length === 0
              ? `No ${tab} yet. Create/edit forms are an upcoming slice.`
              : `No ${tab} match “${query}”.`}
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
                    <th className="px-4 py-2 font-medium">TRN</th>
                    <th className="px-4 py-2 font-medium">Contact</th>
                    <th className="px-4 py-2 text-center font-medium">Credit days</th>
                    <th className="px-4 py-2 text-center font-medium">Active</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((r) => (
                    <tr key={r.id} className="border-b border-border/60 last:border-0">
                      <td className="whitespace-nowrap px-4 py-2 font-mono text-xs">{r.code}</td>
                      <td className="px-4 py-2">{r.name}</td>
                      <td className="whitespace-nowrap px-4 py-2 text-muted-foreground">
                        {r.trn || "—"}
                      </td>
                      <td className="px-4 py-2 text-muted-foreground">
                        {r.email || r.phone || "—"}
                      </td>
                      <td className="px-4 py-2 text-center text-muted-foreground">
                        {r.credit_days ?? "—"}
                      </td>
                      <td className="px-4 py-2 text-center">{r.is_active ? "✓" : "—"}</td>
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
