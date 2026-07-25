"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useEntity } from "@/lib/entity-context";
import { listAccounts, type Account } from "@/lib/accounts";
import { listBankAccounts, type BankAccount } from "@/lib/banking";
import { listDrivers, type Driver } from "@/lib/fleet";
import { createAdvance, postAdvance } from "@/lib/settlements";
import { MasterForm, type FieldSpec, type FormValues } from "@/components/master-form";
import { Card, CardContent } from "@/components/ui/card";

const BLANK: FormValues = {
  driver: "",
  advance_date: new Date().toISOString().slice(0, 10),
  amount: "",
  advance_account: "",
  bank_account: "",
  post_now: true,
};

export default function NewAdvancePage() {
  const router = useRouter();
  const { selectedId, selectedEntity } = useEntity();
  const [drivers, setDrivers] = useState<Driver[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [banks, setBanks] = useState<BankAccount[]>([]);
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    if (!selectedId) return;
    let active = true;
    Promise.all([listDrivers(selectedId), listAccounts(selectedId), listBankAccounts(selectedId)])
      .then(([drv, accts, bnk]) => {
        if (!active) return;
        setDrivers(drv.filter((d) => d.is_active));
        // Advances are a receivable from the driver — an asset account.
        setAccounts(accts.filter((a) => a.is_postable && a.is_active && a.nature === "asset"));
        setBanks(bnk.filter((b) => b.is_active));
      })
      .catch(() => {
        if (active) setLoadError("Couldn't load drivers, accounts, or bank accounts.");
      });
    return () => {
      active = false;
    };
  }, [selectedId]);

  const fields: FieldSpec[] = useMemo(
    () => [
      {
        name: "driver",
        label: "Driver",
        type: "select",
        required: true,
        options: drivers.map((d) => ({ value: d.id, label: `${d.code} · ${d.name}` })),
      },
      { name: "advance_date", label: "Date", type: "date", required: true },
      { name: "amount", label: "Amount", type: "number", required: true },
      {
        name: "advance_account",
        label: "Advance account",
        type: "select",
        required: true,
        options: accounts.map((a) => ({ value: a.id, label: `${a.code} · ${a.name}` })),
        help: "Asset account the advance sits in until recovered.",
      },
      {
        name: "bank_account",
        label: "Pay from",
        type: "select",
        required: true,
        options: banks.map((b) => ({ value: b.id, label: `${b.code} · ${b.name}` })),
      },
      {
        name: "post_now",
        label: "Post immediately (DR Advance / CR Bank)",
        type: "checkbox",
        colSpan: 2,
      },
    ],
    [drivers, accounts, banks],
  );

  async function onSubmit(values: FormValues) {
    const created = await createAdvance({
      entity: selectedId!,
      driver: String(values.driver),
      advance_date: String(values.advance_date),
      amount: String(values.amount),
      advance_account: String(values.advance_account),
      bank_account: String(values.bank_account),
    });
    if (values.post_now) await postAdvance(created.id);
    router.push("/advances");
  }

  if (!selectedId) {
    return (
      <Card>
        <CardContent className="py-12 text-center text-sm text-muted-foreground">
          Pick an entity from the switcher above to record an advance.
        </CardContent>
      </Card>
    );
  }
  if (loadError) return <p className="text-sm text-destructive">{loadError}</p>;

  return (
    <MasterForm
      title="New Driver Advance"
      subtitle={
        selectedEntity
          ? `${selectedEntity.numeric_code} · ${selectedEntity.trade_name || selectedEntity.legal_name}`
          : undefined
      }
      fields={fields}
      initial={BLANK}
      submitLabel="Save advance"
      cancelHref="/advances"
      onSubmit={onSubmit}
    />
  );
}
