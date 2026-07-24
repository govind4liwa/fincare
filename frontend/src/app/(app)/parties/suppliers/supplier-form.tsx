"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useEntity } from "@/lib/entity-context";
import { listAccounts, type Account } from "@/lib/accounts";
import { getRecord, createRecord, updateRecord } from "@/lib/crud";
import { type Supplier } from "@/lib/parties";
import { MasterForm, type FieldSpec, type FormValues } from "@/components/master-form";
import { Card, CardContent } from "@/components/ui/card";

const RESOURCE = "suppliers";

const BLANK: FormValues = {
  code: "",
  name: "",
  trn: "",
  payable_account: "",
  credit_days: "",
  email: "",
  phone: "",
  address: "",
  is_active: true,
};

export function SupplierForm({ id }: { id?: string }) {
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
        if (active) setAccounts(rows.filter((a) => a.account_type === "payable" && a.is_active));
      })
      .catch(() => {
        if (active) setLoadError("Couldn't load payable accounts.");
      });
    return () => {
      active = false;
    };
  }, [selectedId]);

  useEffect(() => {
    if (!id) return;
    let active = true;
    getRecord<Supplier>(RESOURCE, id)
      .then((s) => {
        if (!active) return;
        setInitial({
          code: s.code,
          name: s.name,
          trn: s.trn,
          payable_account: s.payable_account,
          credit_days: s.credit_days?.toString() ?? "",
          email: s.email,
          phone: s.phone,
          address: s.address,
          is_active: s.is_active,
        });
      })
      .catch(() => {
        if (active) setLoadError("Couldn't load this supplier.");
      });
    return () => {
      active = false;
    };
  }, [id]);

  const fields: FieldSpec[] = useMemo(
    () => [
      { name: "code", label: "Code", required: true, placeholder: "SUP-001" },
      { name: "name", label: "Name", required: true, colSpan: 2 },
      { name: "trn", label: "TRN", placeholder: "15-digit tax reg. no." },
      {
        name: "payable_account",
        label: "Payable account",
        type: "select",
        required: true,
        options: accounts.map((a) => ({ value: a.id, label: `${a.code} · ${a.name}` })),
      },
      { name: "credit_days", label: "Credit days", type: "number" },
      { name: "email", label: "Email" },
      { name: "phone", label: "Phone" },
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
      trn: values.trn,
      payable_account: values.payable_account,
      credit_days: values.credit_days === "" ? null : Number(values.credit_days),
      email: values.email,
      phone: values.phone,
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
          Pick an entity from the switcher above to add a supplier.
        </CardContent>
      </Card>
    );
  }
  if (loadError) return <p className="text-sm text-destructive">{loadError}</p>;
  if (!initial) return <p className="text-sm text-muted-foreground">Loading…</p>;

  return (
    <MasterForm
      title={id ? "Edit Supplier" : "New Supplier"}
      subtitle={
        selectedEntity
          ? `${selectedEntity.numeric_code} · ${selectedEntity.trade_name || selectedEntity.legal_name}`
          : undefined
      }
      fields={fields}
      initial={initial}
      submitLabel={id ? "Save changes" : "Create supplier"}
      cancelHref="/parties"
      onSubmit={onSubmit}
    />
  );
}
