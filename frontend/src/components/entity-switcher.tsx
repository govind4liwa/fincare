"use client";

import { ChevronDown } from "lucide-react";
import { useEntity } from "@/lib/entity-context";

export function EntitySwitcher() {
  const { entities, selectedId, setSelectedId, loading } = useEntity();

  return (
    <div className="relative flex items-center gap-2 text-sm">
      <span className="text-muted-foreground">Entity:</span>
      <div className="relative">
        <select
          value={selectedId ?? ""}
          onChange={(e) => setSelectedId(e.target.value || null)}
          disabled={loading}
          aria-label="Active entity"
          className="h-8 appearance-none rounded-md border border-border bg-background pl-2 pr-7 text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 disabled:opacity-50"
        >
          <option value="">All entities</option>
          {entities.map((e) => (
            <option key={e.id} value={e.id}>
              {e.numeric_code} · {e.trade_name || e.legal_name}
            </option>
          ))}
        </select>
        <ChevronDown className="pointer-events-none absolute right-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
      </div>
    </div>
  );
}
