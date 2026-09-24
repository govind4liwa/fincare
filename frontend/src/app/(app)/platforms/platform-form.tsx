"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useEntity } from "@/lib/entity-context";
import { getRecord, createRecord, updateRecord } from "@/lib/crud";
import { listAccounts, type Account } from "@/lib/accounts";
import { type Platform } from "@/lib/platforms";
import { MasterForm, type FieldSpec, type FormValues } from "@/components/master-form";
import { Card, CardContent } from "@/components/ui/card";

const RESOURCE = "platforms";
const CYCLES = [
  ["daily", "Daily"],
  ["weekly", "Weekly"],
  ["monthly", "Monthly"],
] as const;

const BLANK: FormValues = {
  name: "",
  commission_pct: "0",
  settlement_cycle: "weekly",
  revenue_account: "",
  commission_account: "",
  clearing_account: "",
  is_active: true,
};

export function PlatformForm({ id }: { id?: string }) {
  const router = useRouter();
  const { selectedId, selectedEntity } = useEntity();
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [accountsLoaded, setAccountsLoaded] = useState(false);
  const [initial, setInitial] = useState<FormValues | null>(id ? null : BLANK);
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    if (!selectedId) return;
    let active = true;
    listAccounts(selectedId)
      .then((rows) => {
        if (!active) return;
        setAccounts(rows.filter((a) => a.is_active && a.is_postable));
        setAccountsLoaded(true);
      })
      .catch(() => {
        if (active) setLoadError("Couldn't load accounts.");
      });
    return () => {
      active = false;
    };
  }, [selectedId]);

  useEffect(() => {
    if (!id) return;
    let active = true;
    getRecord<Platform>(RESOURCE, id)
      .then((p) => {
        if (!active) return;
        setInitial({
          name: p.name,
          commission_pct: p.commission_pct,
          settlement_cycle: p.settlement_cycle,
          revenue_account: p.revenue_account,
          commission_account: p.commission_account,
          clearing_account: p.clearing_account,
          is_active: p.is_active,
        });
      })
      .catch(() => {
        if (active) setLoadError("Couldn't load this platform.");
      });
    return () => {
      active = false;
    };
  }, [id]);

  const accountOptions = accounts.map((a) => ({ value: a.id, label: `${a.code} · ${a.name}` }));
  const FIELDS: FieldSpec[] = [
    { name: "name", label: "Name", required: true, placeholder: "Uber" },
    { name: "commission_pct", label: "Commission %", type: "number" },
    {
      name: "settlement_cycle",
      label: "Settlement cycle",
      type: "select",
      options: CYCLES.map(([value, label]) => ({ value, label })),
    },
    {
      name: "revenue_account",
      label: "Revenue account",
      type: "select",
      options: accountOptions,
      required: true,
      colSpan: 2,
    },
    {
      name: "commission_account",
      label: "Commission account",
      type: "select",
      options: accountOptions,
      required: true,
      colSpan: 2,
    },
    {
      name: "clearing_account",
      label: "Clearing account (receivable)",
      type: "select",
      options: accountOptions,
      required: true,
      colSpan: 2,
    },
    { name: "is_active", label: "Active", type: "checkbox" },
  ];

  async function onSubmit(values: FormValues) {
    const payload = {
      ...(id ? {} : { entity: selectedId }),
      name: values.name,
      commission_pct: values.commission_pct === "" ? "0" : values.commission_pct,
      settlement_cycle: values.settlement_cycle,
      revenue_account: values.revenue_account,
      commission_account: values.commission_account,
      clearing_account: values.clearing_account,
      is_active: values.is_active,
    };
    if (id) await updateRecord(RESOURCE, id, payload);
    else await createRecord(RESOURCE, payload);
    router.push("/platforms");
  }

  if (!selectedId && !id) {
    return (
      <Card>
        <CardContent className="py-12 text-center text-sm text-muted-foreground">
          Pick an entity from the switcher above to add a platform.
        </CardContent>
      </Card>
    );
  }
  if (loadError) return <p className="text-sm text-destructive">{loadError}</p>;
  if (!initial || !accountsLoaded) return <p className="text-sm text-muted-foreground">Loading…</p>;

  return (
    <MasterForm
      title={id ? "Edit Platform" : "New Platform"}
      subtitle={
        selectedEntity
          ? `${selectedEntity.numeric_code} · ${selectedEntity.trade_name || selectedEntity.legal_name}`
          : undefined
      }
      fields={FIELDS}
      initial={initial}
      submitLabel={id ? "Save changes" : "Create platform"}
      cancelHref="/platforms"
      onSubmit={onSubmit}
    />
  );
}
