"use client";

import { useEffect, useMemo, useState } from "react";
import { Search } from "lucide-react";
import { useEntity } from "@/lib/entity-context";
import { listDrivers, listVehicles, type Driver, type Vehicle } from "@/lib/fleet";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

type Tab = "vehicles" | "drivers";

export default function FleetPage() {
  const { selectedId, selectedEntity } = useEntity();
  const [tab, setTab] = useState<Tab>("vehicles");
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [drivers, setDrivers] = useState<Driver[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [query, setQuery] = useState("");

  useEffect(() => {
    let active = true;
    Promise.all([listVehicles(selectedId), listDrivers(selectedId)])
      .then(([v, d]) => {
        if (active) {
          setVehicles(v);
          setDrivers(d);
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

  const term = query.trim().toLowerCase();
  const filteredVehicles = useMemo(
    () =>
      !term
        ? vehicles
        : vehicles.filter(
            (v) =>
              v.code.toLowerCase().includes(term) ||
              v.plate_no.toLowerCase().includes(term) ||
              `${v.make} ${v.model}`.toLowerCase().includes(term),
          ),
    [vehicles, term],
  );
  const filteredDrivers = useMemo(
    () =>
      !term
        ? drivers
        : drivers.filter(
            (d) =>
              d.code.toLowerCase().includes(term) ||
              d.name.toLowerCase().includes(term) ||
              d.nationality.toLowerCase().includes(term),
          ),
    [drivers, term],
  );

  const tabClass = (t: Tab) =>
    cn(
      "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
      tab === t ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-accent",
    );

  const empty = (label: string) => (
    <Card>
      <CardContent className="py-12 text-center text-sm text-muted-foreground">
        No {label}{term ? " match your search" : " yet"}.
      </CardContent>
    </Card>
  );

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Fleet &amp; Drivers</h1>
          <p className="text-sm text-muted-foreground">
            {selectedEntity
              ? `${selectedEntity.numeric_code} · ${selectedEntity.trade_name || selectedEntity.legal_name}`
              : "All accessible entities"}
          </p>
        </div>
        <div className="relative w-full max-w-xs">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="pl-8"
          />
        </div>
      </div>

      <div className="flex w-fit items-center gap-1 rounded-lg border border-border bg-card p-1">
        <button className={tabClass("vehicles")} onClick={() => setTab("vehicles")}>
          Vehicles <span className="text-xs opacity-70">({vehicles.length})</span>
        </button>
        <button className={tabClass("drivers")} onClick={() => setTab("drivers")}>
          Drivers <span className="text-xs opacity-70">({drivers.length})</span>
        </button>
      </div>

      {loading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : error ? (
        <p className="text-sm text-destructive">Couldn&apos;t load fleet &amp; drivers.</p>
      ) : tab === "vehicles" ? (
        filteredVehicles.length === 0 ? (
          empty("vehicles")
        ) : (
          <Card>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="border-b border-border text-left text-xs text-muted-foreground">
                    <tr>
                      <th className="px-4 py-2 font-medium">Code</th>
                      <th className="px-4 py-2 font-medium">Plate</th>
                      <th className="px-4 py-2 font-medium">Make / Model</th>
                      <th className="px-4 py-2 text-center font-medium">Year</th>
                      <th className="px-4 py-2 font-medium">Ownership</th>
                      <th className="px-4 py-2 text-center font-medium">Active</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredVehicles.map((v) => (
                      <tr key={v.id} className="border-b border-border/60 last:border-0">
                        <td className="whitespace-nowrap px-4 py-2 font-mono text-xs">{v.code}</td>
                        <td className="whitespace-nowrap px-4 py-2">
                          {v.plate_no ? `${v.plate_emirate} ${v.plate_no}`.trim() : "—"}
                        </td>
                        <td className="px-4 py-2">{`${v.make} ${v.model}`.trim() || "—"}</td>
                        <td className="px-4 py-2 text-center text-muted-foreground">
                          {v.model_year ?? "—"}
                        </td>
                        <td className="px-4 py-2 capitalize text-muted-foreground">{v.ownership}</td>
                        <td className="px-4 py-2 text-center">{v.is_active ? "✓" : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        )
      ) : filteredDrivers.length === 0 ? (
        empty("drivers")
      ) : (
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b border-border text-left text-xs text-muted-foreground">
                  <tr>
                    <th className="px-4 py-2 font-medium">Code</th>
                    <th className="px-4 py-2 font-medium">Name</th>
                    <th className="px-4 py-2 font-medium">Nationality</th>
                    <th className="px-4 py-2 font-medium">Licence</th>
                    <th className="px-4 py-2 font-medium">Phone</th>
                    <th className="px-4 py-2 text-center font-medium">Active</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredDrivers.map((d) => (
                    <tr key={d.id} className="border-b border-border/60 last:border-0">
                      <td className="whitespace-nowrap px-4 py-2 font-mono text-xs">{d.code}</td>
                      <td className="px-4 py-2">{d.name}</td>
                      <td className="px-4 py-2 text-muted-foreground">{d.nationality || "—"}</td>
                      <td className="whitespace-nowrap px-4 py-2 text-muted-foreground">
                        {d.licence_no || "—"}
                      </td>
                      <td className="whitespace-nowrap px-4 py-2 text-muted-foreground">
                        {d.phone || "—"}
                      </td>
                      <td className="px-4 py-2 text-center">{d.is_active ? "✓" : "—"}</td>
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
