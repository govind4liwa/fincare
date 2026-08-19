"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useEntity } from "@/lib/entity-context";
import { getRecord, createRecord, updateRecord } from "@/lib/crud";
import { listAccounts, type Account } from "@/lib/accounts";
import { listDrivers, type Driver } from "@/lib/fleet";
import { type Employee } from "@/lib/payroll";
import { MasterForm, type FieldSpec, type FormValues } from "@/components/master-form";
import { Card, CardContent } from "@/components/ui/card";

const RESOURCE = "employees";
const PAY_METHODS = [
  ["wps", "WPS"],
  ["bank", "Bank transfer"],
  ["cash", "Cash"],
] as const;
const STATUSES = [
  ["active", "Active"],
  ["on_leave", "On leave"],
  ["left", "Left"],
] as const;

const BLANK: FormValues = {
  code: "",
  name: "",
  driver: "",
  emirates_id: "",
  passport_no: "",
  nationality: "",
  join_date: "",
  designation: "",
  mol_personal_no: "",
  work_permit_no: "",
  pay_method: "wps",
  bank_routing_code: "",
  iban: "",
  payable_account: "",
  status: "active",
  left_date: "",
};

export function EmployeeForm({ id }: { id?: string }) {
  const router = useRouter();
  const { selectedId, selectedEntity } = useEntity();
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [drivers, setDrivers] = useState<Driver[]>([]);
  const [refsLoaded, setRefsLoaded] = useState(false);
  const [initial, setInitial] = useState<FormValues | null>(id ? null : BLANK);
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    if (!selectedId) return;
    let active = true;
    Promise.all([listAccounts(selectedId), listDrivers(selectedId)])
      .then(([a, d]) => {
        if (!active) return;
        setAccounts(a.filter((x) => x.is_active && x.is_postable));
        setDrivers(d);
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
    getRecord<Employee>(RESOURCE, id)
      .then((e) => {
        if (!active) return;
        setInitial({
          code: e.code,
          name: e.name,
          driver: e.driver ?? "",
          emirates_id: e.emirates_id,
          passport_no: e.passport_no,
          nationality: e.nationality,
          join_date: e.join_date,
          designation: e.designation,
          mol_personal_no: e.mol_personal_no,
          work_permit_no: e.work_permit_no,
          pay_method: e.pay_method,
          bank_routing_code: e.bank_routing_code,
          iban: e.iban,
          payable_account: e.payable_account,
          status: e.status,
          left_date: e.left_date ?? "",
        });
      })
      .catch(() => {
        if (active) setLoadError("Couldn't load this employee.");
      });
    return () => {
      active = false;
    };
  }, [id]);

  const FIELDS: FieldSpec[] = [
    { name: "code", label: "Employee code", required: true, placeholder: "E-001" },
    { name: "name", label: "Full name", required: true, colSpan: 2 },
    {
      name: "driver",
      label: "Linked driver (if a salaried driver)",
      type: "select",
      colSpan: 2,
      options: drivers.map((d) => ({ value: d.id, label: `${d.code} · ${d.name}` })),
    },
    { name: "nationality", label: "Nationality" },
    { name: "join_date", label: "Join date", type: "date", required: true },
    { name: "designation", label: "Designation" },
    { name: "emirates_id", label: "Emirates ID" },
    { name: "passport_no", label: "Passport no." },
    { name: "mol_personal_no", label: "MOL personal no. (WPS)" },
    { name: "work_permit_no", label: "Work permit no." },
    {
      name: "pay_method",
      label: "Pay method",
      type: "select",
      options: PAY_METHODS.map(([value, label]) => ({ value, label })),
    },
    { name: "bank_routing_code", label: "Bank routing code" },
    { name: "iban", label: "IBAN", colSpan: 2 },
    {
      name: "payable_account",
      label: "Payable account (Salaries Payable / WPS clearing)",
      type: "select",
      required: true,
      colSpan: 2,
      options: accounts.map((a) => ({ value: a.id, label: `${a.code} · ${a.name}` })),
    },
    {
      name: "status",
      label: "Status",
      type: "select",
      options: STATUSES.map(([value, label]) => ({ value, label })),
    },
    { name: "left_date", label: "Left date", type: "date" },
  ];

  async function onSubmit(values: FormValues) {
    const payload = {
      ...(id ? {} : { entity: selectedId }),
      code: values.code,
      name: values.name,
      driver: values.driver || null,
      emirates_id: values.emirates_id,
      passport_no: values.passport_no,
      nationality: values.nationality,
      join_date: values.join_date,
      designation: values.designation,
      mol_personal_no: values.mol_personal_no,
      work_permit_no: values.work_permit_no,
      pay_method: values.pay_method,
      bank_routing_code: values.bank_routing_code,
      iban: values.iban,
      payable_account: values.payable_account,
      status: values.status,
      left_date: values.left_date || null,
    };
    if (id) await updateRecord(RESOURCE, id, payload);
    else await createRecord(RESOURCE, payload);
    router.push("/employees");
  }

  if (!selectedId && !id) {
    return (
      <Card>
        <CardContent className="py-12 text-center text-sm text-muted-foreground">
          Pick an entity from the switcher above to add an employee.
        </CardContent>
      </Card>
    );
  }
  if (loadError) return <p className="text-sm text-destructive">{loadError}</p>;
  if (!initial || !refsLoaded) return <p className="text-sm text-muted-foreground">Loading…</p>;

  return (
    <MasterForm
      title={id ? "Edit Employee" : "New Employee"}
      subtitle={
        selectedEntity
          ? `${selectedEntity.numeric_code} · ${selectedEntity.trade_name || selectedEntity.legal_name}`
          : undefined
      }
      fields={FIELDS}
      initial={initial}
      submitLabel={id ? "Save changes" : "Create employee"}
      cancelHref="/employees"
      onSubmit={onSubmit}
    />
  );
}
