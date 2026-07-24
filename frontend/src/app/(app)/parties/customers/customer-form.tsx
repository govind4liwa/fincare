"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useEntity } from "@/lib/entity-context";
import { listAccounts, type Account } from "@/lib/accounts";
import { getRecord, createRecord, updateRecord } from "@/lib/crud";
import { type Customer } from "@/lib/parties";
import { MasterForm, type FieldSpec, type FormValues } from "@/components/master-form";
import { Card, CardContent } from "@/components/ui/card";

const RESOURCE = "customers";
const TYPES = [
  ["b2b", "B2B"],
  ["b2c", "B2C"],
  ["corporate", "Corporate"],
  ["platform", "Platform"],
] as const;

const BLANK: FormValues = {
  code: "",
  name: "",
  customer_type: "b2b",
  trn: "",
  receivable_account: "",
  credit_days: "",
  credit_limit: "",
  email: "",
  phone: "",
  emirate: "",
  address: "",
  is_active: true,
};

export function CustomerForm({ id }: { id?: string }) {
  const router = useRouter();
  const { selectedId, selectedEntity } = useEntity();
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [initial, setInitial] = useState<FormValues | null>(id ? null : BLANK);
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    if (!selectedId) return;
    let active = true;
    listAccounts(selectedId)
      .then((rows) => {
        if (active) setAccounts(rows.filter((a) => a.account_type === "receivable" && a.is_active));
      })
      .catch(() => {
        if (active) setLoadError("Couldn't load receivable accounts.");
      });
    return () => {
      active = false;
    };
  }, [selectedId]);

  useEffect(() => {
    if (!id) return;
    let active = true;
    getRecord<Customer>(RESOURCE, id)
      .then((c) => {
        if (!active) return;
        setInitial({
          code: c.code,
          name: c.name,
          customer_type: c.customer_type,
          trn: c.trn,
          receivable_account: c.receivable_account,
          credit_days: c.credit_days?.toString() ?? "",
          credit_limit: c.credit_limit ?? "",
          email: c.email,
          phone: c.phone,
          emirate: c.emirate,
          address: c.address,
          is_active: c.is_active,
        });
      })
      .catch(() => {
        if (active) setLoadError("Couldn't load this customer.");
      });
    return () => {
      active = false;
    };
  }, [id]);

  const fields: FieldSpec[] = useMemo(
    () => [
      { name: "code", label: "Code", required: true, placeholder: "CUS-001" },
      { name: "name", label: "Name", required: true, colSpan: 2 },
      {
        name: "customer_type",
        label: "Type",
        type: "select",
        options: TYPES.map(([value, label]) => ({ value, label })),
      },
      { name: "trn", label: "TRN", placeholder: "15-digit tax reg. no." },
      {
        name: "receivable_account",
        label: "Receivable account",
        type: "select",
        required: true,
        options: accounts.map((a) => ({ value: a.id, label: `${a.code} · ${a.name}` })),
      },
      { name: "credit_days", label: "Credit days", type: "number" },
      { name: "credit_limit", label: "Credit limit", type: "number" },
      { name: "email", label: "Email" },
      { name: "phone", label: "Phone" },
      { name: "emirate", label: "Emirate" },
      { name: "address", label: "Address", colSpan: 3 },
      { name: "is_active", label: "Active", type: "checkbox" },
    ],
    [accounts],
  );

  async function onSubmit(values: FormValues) {
    const payload = {
      ...(id ? {} : { entity: selectedId }),
      code: values.code,
      name: values.name,
      customer_type: values.customer_type,
      trn: values.trn,
      receivable_account: values.receivable_account,
      credit_days: values.credit_days === "" ? null : Number(values.credit_days),
      credit_limit: values.credit_limit === "" ? null : values.credit_limit,
      email: values.email,
      phone: values.phone,
      emirate: values.emirate,
      address: values.address,
      is_active: values.is_active,
    };
    if (id) await updateRecord(RESOURCE, id, payload);
    else await createRecord(RESOURCE, payload);
    router.push("/parties");
  }

  if (!selectedId && !id) {
    return (
      <Card>
        <CardContent className="py-12 text-center text-sm text-muted-foreground">
          Pick an entity from the switcher above to add a customer.
        </CardContent>
      </Card>
    );
  }
  if (loadError) return <p className="text-sm text-destructive">{loadError}</p>;
  if (!initial) return <p className="text-sm text-muted-foreground">Loading…</p>;

  return (
    <MasterForm
      title={id ? "Edit Customer" : "New Customer"}
      subtitle={
        selectedEntity
          ? `${selectedEntity.numeric_code} · ${selectedEntity.trade_name || selectedEntity.legal_name}`
          : undefined
      }
      fields={fields}
      initial={initial}
      submitLabel={id ? "Save changes" : "Create customer"}
      cancelHref="/parties"
      onSubmit={onSubmit}
    />
  );
}
