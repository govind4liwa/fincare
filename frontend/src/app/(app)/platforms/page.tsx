"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { HandCoins, Plus } from "lucide-react";
import { useEntity } from "@/lib/entity-context";
import { listPlatforms, type Platform } from "@/lib/platforms";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

export default function PlatformsPage() {
  const router = useRouter();
  const { selectedId, selectedEntity } = useEntity();
  const [platforms, setPlatforms] = useState<Platform[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let active = true;
    listPlatforms(selectedId)
      .then((rows) => {
        if (active) {
          setPlatforms(rows);
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
          <h1 className="text-2xl font-semibold">Platforms</h1>
          <p className="text-sm text-muted-foreground">
            {selectedEntity
              ? `${selectedEntity.numeric_code} · ${selectedEntity.trade_name || selectedEntity.legal_name}`
              : "All accessible entities"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link href="/platform-settlements">
            <Button variant="outline" size="sm">
              <HandCoins className="h-4 w-4" />
              Settlements
            </Button>
          </Link>
          <Link href="/platforms/new">
            <Button size="sm">
              <Plus className="h-4 w-4" />
              New platform
            </Button>
          </Link>
        </div>
      </div>

      {loading ? (
        <p className="text-sm text-muted-foreground">Loading platforms…</p>
      ) : error ? (
        <p className="text-sm text-destructive">Couldn&apos;t load platforms.</p>
      ) : platforms.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-sm text-muted-foreground">
            No platforms yet. Add one (Uber, Yango, Bolt, Careem…) with the{" "}
            <span className="font-medium text-foreground">New platform</span> button.
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b border-border text-left text-xs text-muted-foreground">
                  <tr>
                    <th className="px-4 py-2 font-medium">Name</th>
                    <th className="px-4 py-2 text-right font-medium">Commission %</th>
                    <th className="px-4 py-2 font-medium">Cycle</th>
                    <th className="px-4 py-2 font-medium">Clearing account</th>
                    <th className="px-4 py-2 text-center font-medium">Active</th>
                  </tr>
                </thead>
                <tbody>
                  {platforms.map((p) => (
                    <tr
                      key={p.id}
                      onClick={() => router.push(`/platforms/${p.id}/edit`)}
                      className="cursor-pointer border-b border-border/60 last:border-0 hover:bg-accent/50"
                    >
                      <td className="px-4 py-2 font-medium">{p.name}</td>
                      <td className="px-4 py-2 text-right tabular-nums">{p.commission_pct}</td>
                      <td className="px-4 py-2 capitalize text-muted-foreground">
                        {p.settlement_cycle || "—"}
                      </td>
                      <td className="whitespace-nowrap px-4 py-2 font-mono text-xs text-muted-foreground">
                        {p.clearing_account_code}
                      </td>
                      <td className="px-4 py-2 text-center">{p.is_active ? "✓" : "—"}</td>
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
