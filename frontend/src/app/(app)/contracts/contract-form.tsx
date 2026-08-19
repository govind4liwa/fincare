"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useEntity } from "@/lib/entity-context";
import { getRecord, createRecord, updateRecord } from "@/lib/crud";
import { listAccounts, type Account } from "@/lib/accounts";
import { listCustomers, type Customer } from "@/lib/parties";
import { listVehicles, listDrivers, type Vehicle, type Driver } from "@/lib/fleet";
import { listTaxCodes, type TaxCode } from "@/lib/taxes";
import { type Contract } from "@/lib/bookings";
import { MasterForm, type FieldSpec, type FormValues } from "@/components/master-form";
import { Card, CardContent } from "@/components/ui/card";

const RESOURCE = "contracts";
const CYCLES = [
  ["monthly", "Monthly"],
  ["weekly", "Weekly"],
] as const;
const STATUSES = [
  ["active", "Active"],
  ["suspended", "Suspended"],
  ["ended", "Ended"],
] as const;

const BLANK: FormValues = {
  customer: "",
  vehicle: "",
  driver: "",
  contract_no: "",
  start_date: "",
  end_date: "",
  billing_cycle: "monthly",
  monthly_amount: "",
  revenue_account: "",
  tax_code: "",
  status: "active",
};

export function ContractForm({ id }: { id?: string }) {
  const router = useRouter();
  const { selectedId, selectedEntity } = useEntity();
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [drivers, setDrivers] = useState<Driver[]>([]);
  const [taxCodes, setTaxCodes] = useState<TaxCode[]>([]);
  const [refsLoaded, setRefsLoaded] = useState(false);
  const [initial, setInitial] = useState<FormValues | null>(id ? null : BLANK);
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    if (!selectedId) return;
    let active = true;
    Promise.all([
      listAccounts(selectedId),
      listCustomers(selectedId),
      listVehicles(selectedId),
      listDrivers(selectedId),
      listTaxCodes(selectedId, "output"),
    ])
      .then(([a, c, v, d, t]) => {
        if (!active) return;
        setAccounts(a.filter((x) => x.is_active && x.is_postable));
        setCustomers(c);
        setVehicles(v);
        setDrivers(d);
        setTaxCodes(t);
        setRefsLoaded(true);
      })
      .catch(() => {
        if (active) setLoadError("Couldn't load reference data.");
      });
    return () => {
      active = false;
    };
  }, [selectedId]);

  useEffect(() => {
    if (!id) return;
    let active = true;
    getRecord<Contract>(RESOURCE, id)
      .then((c) => {
        if (!active) return;
        setInitial({
          customer: c.customer,
          vehicle: c.vehicle ?? "",
          driver: c.driver ?? "",
          contract_no: c.contract_no,
          start_date: c.start_date,
          end_date: c.end_date ?? "",
          billing_cycle: c.billing_cycle,
          monthly_amount: c.monthly_amount,
          revenue_account: c.revenue_account,
          tax_code: c.tax_code,
          status: c.status,
        });
      })
      .catch(() => {
        if (active) setLoadError("Couldn't load this contract.");
      });
    return () => {
      active = false;
    };
  }, [id]);

  const FIELDS: FieldSpec[] = [
    { name: "contract_no", label: "Contract no.", required: true, placeholder: "CTR-001" },
    {
      name: "customer",
      label: "Customer",
      type: "select",
      required: true,
      colSpan: 2,
      options: customers.map((c) => ({ value: c.id, label: `${c.code} · ${c.name}` })),
    },
    {
      name: "vehicle",
      label: "Vehicle",
      type: "select",
      options: vehicles.map((v) => ({ value: v.id, label: v.code })),
    },
    {
      name: "driver",
      label: "Driver",
      type: "select",
      options: drivers.map((d) => ({ value: d.id, label: d.code })),
    },
    { name: "start_date", label: "Start date", type: "date", required: true },
    { name: "end_date", label: "End date", type: "date" },
    {
      name: "billing_cycle",
      label: "Billing cycle",
      type: "select",
      options: CYCLES.map(([value, label]) => ({ value, label })),
    },
    { name: "monthly_amount", label: "Amount per cycle", type: "number", required: true },
    {
      name: "revenue_account",
      label: "Revenue account",
      type: "select",
      required: true,
      colSpan: 2,
      options: accounts.map((a) => ({ value: a.id, label: `${a.code} · ${a.name}` })),
    },
    {
      name: "tax_code",
      label: "Tax code",
      type: "select",
      required: true,
      options: taxCodes.map((t) => ({ value: t.id, label: `${t.code} (${t.rate}%)` })),
    },
    {
      name: "status",
      label: "Status",
      type: "select",
      options: STATUSES.map(([value, label]) => ({ value, label })),
    },
  ];

  async function onSubmit(values: FormValues) {
    const payload = {
      ...(id ? {} : { entity: selectedId }),
      customer: values.customer,
      vehicle: values.vehicle || null,
      driver: values.driver || null,
      contract_no: values.contract_no,
      start_date: values.start_date,
      end_date: values.end_date || null,
      billing_cycle: values.billing_cycle,
      monthly_amount: values.monthly_amount,
      revenue_account: values.revenue_account,
      tax_code: values.tax_code,
      status: values.status,
    };
    if (id) await updateRecord(RESOURCE, id, payload);
    else await createRecord(RESOURCE, payload);
    router.push("/contracts");
  }

  if (!selectedId && !id) {
    return (
      <Card>
        <CardContent className="py-12 text-center text-sm text-muted-foreground">
          Pick an entity from the switcher above to add a contract.
        </CardContent>
      </Card>
    );
  }
  if (loadError) return <p className="text-sm text-destructive">{loadError}</p>;
  if (!initial || !refsLoaded) return <p className="text-sm text-muted-foreground">Loading…</p>;

  return (
    <MasterForm
      title={id ? "Edit Contract" : "New Contract"}
      subtitle={
        selectedEntity
          ? `${selectedEntity.numeric_code} · ${selectedEntity.trade_name || selectedEntity.legal_name}`
          : undefined
      }
      fields={FIELDS}
      initial={initial}
      submitLabel={id ? "Save changes" : "Create contract"}
      cancelHref="/contracts"
      onSubmit={onSubmit}
    />
  );
}
