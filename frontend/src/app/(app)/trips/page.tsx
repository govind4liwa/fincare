"use client";

import { useEffect, useMemo, useState } from "react";
import { useEntity } from "@/lib/entity-context";
import { listVehicles, listDrivers, type Vehicle, type Driver } from "@/lib/fleet";
import { listPlatforms, type Platform } from "@/lib/platforms";
import { listCustomers, type Customer } from "@/lib/parties";
import { createTrip, listTrips, postTripRevenue, type Trip } from "@/lib/bookings";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const fieldClass =
  "h-9 rounded-md border border-border bg-background px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40";

const money = (v: string) =>
  Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const TRIP_TYPES = [
  ["platform", "Platform"],
  ["personal", "Personal"],
  ["corporate", "Corporate"],
  ["contract", "Contract"],
] as const;

const STATUS_STYLE: Record<Trip["status"], string> = {
  recorded: "bg-muted text-muted-foreground",
  invoiced: "bg-primary/10 text-primary",
  settled: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
};

export default function TripsPage() {
  const { selectedId, selectedEntity } = useEntity();
  const [platforms, setPlatforms] = useState<Platform[]>([]);
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [drivers, setDrivers] = useState<Driver[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [trips, setTrips] = useState<Trip[]>([]);
  const [platformFilter, setPlatformFilter] = useState("");
  const [loadError, setLoadError] = useState("");
  const [error, setError] = useState("");

  const [form, setForm] = useState({
    trip_date: "",
    trip_type: "platform",
    vehicle: "",
    driver: "",
    platform: "",
    customer: "",
    fare: "",
    commission: "",
    salik: "",
    tip: "",
  });
  const [saving, setSaving] = useState(false);

  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [postDate, setPostDate] = useState("");
  const [posting, setPosting] = useState(false);

  useEffect(() => {
    if (!selectedId) return;
    let active = true;
    Promise.all([
      listPlatforms(selectedId),
      listVehicles(selectedId),
      listDrivers(selectedId),
      listCustomers(selectedId),
    ])
      .then(([p, v, d, c]) => {
        if (!active) return;
        setPlatforms(p);
        setVehicles(v);
        setDrivers(d);
        setCustomers(c);
      })
      .catch(() => {
        if (active) setLoadError("Couldn't load fleet/platform data.");
      });
    return () => {
      active = false;
    };
  }, [selectedId]);

  useEffect(() => {
    if (!selectedId) return;
    let active = true;
    listTrips({ entityId: selectedId, platformId: platformFilter || undefined })
      .then((rows) => {
        if (active) setTrips(rows);
      })
      .catch(() => {
        if (active) setLoadError("Couldn't load trips.");
      });
    return () => {
      active = false;
    };
  }, [selectedId, platformFilter]);

  const recordedForBulk = useMemo(
    () => trips.filter((t) => t.status === "recorded" && t.platform === platformFilter),
    [trips, platformFilter],
  );

  async function addTrip() {
    if (!selectedId || !form.trip_date) return setError("Trip date is required.");
    setSaving(true);
    setError("");
    try {
      const trip = await createTrip({
        entity: selectedId,
        trip_date: form.trip_date,
        trip_type: form.trip_type,
        vehicle: form.vehicle || null,
        driver: form.driver || null,
        platform: form.platform || null,
        customer: form.customer || null,
        fare: form.fare || "0",
        commission: form.commission || "0",
        salik: form.salik || "0",
        tip: form.tip || "0",
      });
      setTrips((prev) => [trip, ...prev]);
      setForm((p) => ({ ...p, fare: "", commission: "", salik: "", tip: "" }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setSaving(false);
    }
  }

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function postRevenue() {
    if (!platformFilter) return setError("Filter by a platform to post revenue.");
    if (selected.size === 0) return setError("Select at least one trip.");
    if (!postDate) return setError("Pick a posting date.");
    setPosting(true);
    setError("");
    try {
      await postTripRevenue(platformFilter, Array.from(selected), postDate);
      setTrips(await listTrips({ entityId: selectedId, platformId: platformFilter }));
      setSelected(new Set());
      setPostDate("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setPosting(false);
    }
  }

  if (!selectedId) {
    return (
      <Card>
        <CardContent className="py-12 text-center text-sm text-muted-foreground">
          Pick an entity from the switcher above to manage the trip register.
        </CardContent>
      </Card>
    );
  }
  if (loadError) return <p className="text-sm text-destructive">{loadError}</p>;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">Trip Register</h1>
        <p className="text-sm text-muted-foreground">
          {selectedEntity?.numeric_code} ·{" "}
          {selectedEntity?.trade_name || selectedEntity?.legal_name}
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Add trip</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
            <div className="flex flex-col gap-1.5">
              <Label>Date</Label>
              <Input
                type="date"
                value={form.trip_date}
                onChange={(e) => setForm((p) => ({ ...p, trip_date: e.target.value }))}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Type</Label>
              <select
                value={form.trip_type}
                onChange={(e) => setForm((p) => ({ ...p, trip_type: e.target.value }))}
                className={fieldClass}
              >
                {TRIP_TYPES.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Platform</Label>
              <select
                value={form.platform}
                onChange={(e) => setForm((p) => ({ ...p, platform: e.target.value }))}
                className={fieldClass}
              >
                <option value="">None</option>
                {platforms.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Vehicle</Label>
              <select
                value={form.vehicle}
                onChange={(e) => setForm((p) => ({ ...p, vehicle: e.target.value }))}
                className={fieldClass}
              >
                <option value="">None</option>
                {vehicles.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.code}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Driver</Label>
              <select
                value={form.driver}
                onChange={(e) => setForm((p) => ({ ...p, driver: e.target.value }))}
                className={fieldClass}
              >
                <option value="">None</option>
                {drivers.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.code}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5 sm:col-span-2">
              <Label>Customer (corporate/contract)</Label>
              <select
                value={form.customer}
                onChange={(e) => setForm((p) => ({ ...p, customer: e.target.value }))}
                className={fieldClass}
              >
                <option value="">None</option>
                {customers.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.code} · {c.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Fare</Label>
              <Input
                type="number"
                inputMode="decimal"
                value={form.fare}
                onChange={(e) => setForm((p) => ({ ...p, fare: e.target.value }))}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Commission</Label>
              <Input
                type="number"
                inputMode="decimal"
                value={form.commission}
                onChange={(e) => setForm((p) => ({ ...p, commission: e.target.value }))}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Salik</Label>
              <Input
                type="number"
                inputMode="decimal"
                value={form.salik}
                onChange={(e) => setForm((p) => ({ ...p, salik: e.target.value }))}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Tip</Label>
              <Input
                type="number"
                inputMode="decimal"
                value={form.tip}
                onChange={(e) => setForm((p) => ({ ...p, tip: e.target.value }))}
              />
            </div>
          </div>
          <div>
            <Button size="sm" onClick={addTrip} disabled={saving}>
              {saving ? "Adding…" : "Add trip"}
            </Button>
          </div>
        </CardContent>
      </Card>

      <div className="flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1.5">
          <Label>Filter by platform (required to select &amp; post revenue)</Label>
          <select
            value={platformFilter}
            onChange={(e) => {
              setPlatformFilter(e.target.value);
              setSelected(new Set());
            }}
            className={cn(fieldClass, "min-w-56")}
          >
            <option value="">All trips</option>
            {platforms.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>
        {platformFilter && (
          <>
            <div className="flex flex-col gap-1.5">
              <Label>Posting date</Label>
              <Input type="date" value={postDate} onChange={(e) => setPostDate(e.target.value)} />
            </div>
            <Button size="sm" onClick={postRevenue} disabled={posting || selected.size === 0}>
              {posting ? "Posting…" : `Post revenue (${selected.size} selected)`}
            </Button>
            <span className="text-xs text-muted-foreground">
              {recordedForBulk.length} recorded trip{recordedForBulk.length === 1 ? "" : "s"}{" "}
              eligible
            </span>
          </>
        )}
      </div>

      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-border text-left text-xs text-muted-foreground">
                <tr>
                  {platformFilter && <th className="px-4 py-2" />}
                  <th className="px-4 py-2 font-medium">Date</th>
                  <th className="px-4 py-2 font-medium">Type</th>
                  <th className="px-4 py-2 font-medium">Vehicle/Driver</th>
                  <th className="px-4 py-2 font-medium">Platform/Customer</th>
                  <th className="px-4 py-2 text-right font-medium">Fare</th>
                  <th className="px-4 py-2 text-right font-medium">Commission</th>
                  <th className="px-4 py-2 text-right font-medium">Net</th>
                  <th className="px-4 py-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {trips.length === 0 ? (
                  <tr>
                    <td
                      colSpan={platformFilter ? 9 : 8}
                      className="px-4 py-8 text-center text-muted-foreground"
                    >
                      No trips yet.
                    </td>
                  </tr>
                ) : (
                  trips.map((t) => (
                    <tr key={t.id} className="border-b border-border/60 last:border-0">
                      {platformFilter && (
                        <td className="px-4 py-2">
                          {t.status === "recorded" && t.platform === platformFilter && (
                            <input
                              type="checkbox"
                              checked={selected.has(t.id)}
                              onChange={() => toggle(t.id)}
                              className="h-4 w-4 rounded border-border"
                            />
                          )}
                        </td>
                      )}
                      <td className="whitespace-nowrap px-4 py-2 text-muted-foreground">
                        {t.trip_date}
                      </td>
                      <td className="px-4 py-2 capitalize">{t.trip_type}</td>
                      <td className="px-4 py-2 text-muted-foreground">
                        {[t.vehicle_code, t.driver_code].filter(Boolean).join(" · ") || "—"}
                      </td>
                      <td className="px-4 py-2 text-muted-foreground">
                        {t.platform_name || t.customer_name || "—"}
                      </td>
                      <td className="px-4 py-2 text-right tabular-nums">{money(t.fare)}</td>
                      <td className="px-4 py-2 text-right tabular-nums">{money(t.commission)}</td>
                      <td className="px-4 py-2 text-right tabular-nums">{money(t.net_revenue)}</td>
                      <td className="px-4 py-2">
                        <span
                          className={cn(
                            "rounded-full px-2 py-0.5 text-xs font-medium capitalize",
                            STATUS_STYLE[t.status],
                          )}
                        >
                          {t.status}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  );
}
