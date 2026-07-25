"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useEntity } from "@/lib/entity-context";
import { listAccounts, type Account } from "@/lib/accounts";
import { listVehicles, type Vehicle } from "@/lib/fleet";
import { createRecord } from "@/lib/crud";
import { MasterForm, type FieldSpec, type FormValues } from "@/components/master-form";
import { Card, CardContent } from "@/components/ui/card";

const RESOURCE = "vehicle-loans";

// No pre-selected method: the amortization basis must be chosen deliberately,
// because it decides how much interest each period carries.
const BLANK: FormValues = {
  vehicle: "",
  lender: "",
  loan_account: "",
  interest_account: "",
  principal: "",
  down_payment: "",
  term_months: "",
  annual_interest_rate: "",
  amortization_method: "",
  quoted_flat_rate: "",
  effective_annual_rate: "",
  start_date: "",
  first_payment_date: "",
  is_active: true,
};

export default function NewLoanPage() {
  const router = useRouter();
  const { selectedId, selectedEntity } = useEntity();
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    if (!selectedId) return;
    let active = true;
    Promise.all([listVehicles(selectedId), listAccounts(selectedId)])
      .then(([veh, accts]) => {
        if (!active) return;
        setVehicles(veh.filter((v) => v.is_active));
        setAccounts(accts.filter((a) => a.is_postable && a.is_active));
      })
      .catch(() => {
        if (active) setLoadError("Couldn't load vehicles or accounts.");
      });
    return () => {
      active = false;
    };
  }, [selectedId]);

  const fields: FieldSpec[] = useMemo(() => {
    const liabilities = accounts.filter((a) => a.nature === "liability");
    const expenses = accounts.filter((a) => a.nature === "expense");
    return [
      {
        name: "vehicle",
        label: "Vehicle",
        type: "select",
        required: true,
        options: vehicles.map((v) => ({
          value: v.id,
          label: `${v.code}${v.plate_no ? ` · ${v.plate_no}` : ""}`,
        })),
      },
      { name: "lender", label: "Lender", colSpan: 2 },
      {
        name: "amortization_method",
        label: "Amortization method",
        type: "select",
        required: true,
        options: [
          { value: "reducing_balance", label: "Reducing balance" },
          { value: "flat_rate", label: "Flat rate" },
        ],
        help: "Must match the lender's schedule — it decides the interest split.",
      },
      {
        name: "loan_account",
        label: "Loan payable account",
        type: "select",
        required: true,
        options: liabilities.map((a) => ({ value: a.id, label: `${a.code} · ${a.name}` })),
      },
      {
        name: "interest_account",
        label: "Interest expense account",
        type: "select",
        required: true,
        options: expenses.map((a) => ({ value: a.id, label: `${a.code} · ${a.name}` })),
      },
      { name: "principal", label: "Principal", type: "number", required: true },
      { name: "down_payment", label: "Down payment", type: "number" },
      { name: "term_months", label: "Term (months)", type: "number", required: true },
      {
        name: "annual_interest_rate",
        label: "Rate applied % p.a.",
        type: "number",
        help: "The rate the schedule is computed from.",
      },
      { name: "quoted_flat_rate", label: "Quoted flat rate %", type: "number" },
      { name: "effective_annual_rate", label: "Effective annual rate %", type: "number" },
      { name: "start_date", label: "Start date", type: "date" },
      {
        name: "first_payment_date",
        label: "First payment date",
        type: "date",
        required: true,
        help: "Subsequent EMIs fall on the same day each month.",
      },
      { name: "is_active", label: "Active", type: "checkbox" },
    ];
  }, [vehicles, accounts]);

  async function onSubmit(values: FormValues) {
    const optional = (v: string | boolean) => (v === "" ? null : v);
    const created = await createRecord<{ id: string }>(RESOURCE, {
      entity: selectedId,
      vehicle: values.vehicle,
      lender: values.lender,
      loan_account: values.loan_account,
      interest_account: values.interest_account,
      amortization_method: values.amortization_method,
      principal: values.principal || "0",
      down_payment: values.down_payment || "0",
      term_months: Number(values.term_months),
      annual_interest_rate: values.annual_interest_rate || "0",
      quoted_flat_rate: optional(values.quoted_flat_rate),
      effective_annual_rate: optional(values.effective_annual_rate),
      start_date: optional(values.start_date),
      first_payment_date: optional(values.first_payment_date),
      is_active: values.is_active,
    });
    router.push(`/loans/${created.id}`);
  }

  if (!selectedId) {
    return (
      <Card>
        <CardContent className="py-12 text-center text-sm text-muted-foreground">
          Pick an entity from the switcher above to add a loan.
        </CardContent>
      </Card>
    );
  }
  if (loadError) return <p className="text-sm text-destructive">{loadError}</p>;

  return (
    <MasterForm
      title="New Vehicle Loan"
      subtitle={
        selectedEntity
          ? `${selectedEntity.numeric_code} · ${selectedEntity.trade_name || selectedEntity.legal_name}`
          : undefined
      }
      fields={fields}
      initial={BLANK}
      submitLabel="Create loan"
      cancelHref="/loans"
      onSubmit={onSubmit}
    />
  );
}
