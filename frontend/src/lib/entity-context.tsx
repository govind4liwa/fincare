"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { listEntities, type Entity } from "@/lib/entities";

const STORAGE_KEY = "fincare_entity";

type EntityState = {
  entities: Entity[];
  loading: boolean;
  /** `null` = "All entities". */
  selectedId: string | null;
  setSelectedId: (id: string | null) => void;
  selectedEntity: Entity | null;
};

const EntityContext = createContext<EntityState | null>(null);

export function EntityProvider({ children }: { children: ReactNode }) {
  const [entities, setEntities] = useState<Entity[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedIdState] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    listEntities()
      .then((list) => {
        if (!active) return;
        setEntities(list);
        const stored = localStorage.getItem(STORAGE_KEY);
        // Keep a stored selection only if it's still accessible.
        setSelectedIdState(stored && list.some((e) => e.id === stored) ? stored : null);
      })
      .catch(() => {
        /* leave list empty; the switcher just shows "All entities" */
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const setSelectedId = (id: string | null) => {
    setSelectedIdState(id);
    if (id) localStorage.setItem(STORAGE_KEY, id);
    else localStorage.removeItem(STORAGE_KEY);
  };

  const selectedEntity = entities.find((e) => e.id === selectedId) ?? null;

  return (
    <EntityContext.Provider
      value={{ entities, loading, selectedId, setSelectedId, selectedEntity }}
    >
      {children}
    </EntityContext.Provider>
  );
}

export function useEntity(): EntityState {
  const ctx = useContext(EntityContext);
  if (!ctx) throw new Error("useEntity must be used within an EntityProvider");
  return ctx;
}
