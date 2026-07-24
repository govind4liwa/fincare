"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useEntity } from "@/lib/entity-context";
import { getRecord, createRecord, updateRecord } from "@/lib/crud";
import { type Driver } from "@/lib/fleet";
import { MasterForm, type FieldSpec, type FormValues } from "@/components/master-form";
import { Card, CardContent } from "@/components/ui/card";

const RESOURCE = "drivers";

const FIELDS: FieldSpec[] = [
  { name: "code", label: "Code", required: true, placeholder: "D-001" },
  { name: "name", label: "Name", required: true, colSpan: 2 },
  { name: "nationality", label: "Nationality" },
  { name: "licence_no", label: "Licence no." },
  { name: "emirates_id", label: "Emirates ID" },
  { name: "phone", label: "Phone" },
  { name: "basic_salary", label: "Basic salary", type: "number" },
  { name: "commission_rate", label: "Commission rate %", type: "number" },
  { name: "is_active", label: "Active", type: "checkbox" },
];

const BLANK: FormValues = {
  code: "",
  name: "",
  nationality: "",
  licence_no: "",
  emirates_id: "",
  phone: "",
  basic_salary: "",
  commission_rate: "",
  is_active: true,
};

export function DriverForm({ id }: { id?: string }) {
  const router = useRouter();
  const { selectedId, selectedEntity } = useEntity();
  const [initial, setInitial] = useState<FormValues | null>(id ? null : BLANK);
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    if (!id) return;
    let active = true;
    getRecord<Driver>(RESOURCE, id)
      .then((d) => {
        if (!active) return;
        setInitial({
          code: d.code,
          name: d.name,
          nationality: d.nationality,
          licence_no: d.licence_no,
          emirates_id: d.emirates_id,
          phone: d.phone,
          basic_salary: d.basic_salary ?? "",
          commission_rate: d.commission_rate ?? "",
          is_active: d.is_active,
        });
      })
      .catch(() => {
        if (active) setLoadError("Couldn't load this driver.");
      });
    return () => {
      active = false;
    };
  }, [id]);

  async function onSubmit(values: FormValues) {
    const payload = {
      ...(id ? {} : { entity: selectedId }),
      code: values.code,
      name: values.name,
      nationality: values.nationality,
      licence_no: values.licence_no,
      emirates_id: values.emirates_id,
      phone: values.phone,
      basic_salary: values.basic_salary === "" ? "0" : values.basic_salary,
      commission_rate: values.commission_rate === "" ? "0" : values.commission_rate,
      is_active: values.is_active,
    };
    if (id) await updateRecord(RESOURCE, id, payload);
    else await createRecord(RESOURCE, payload);
    router.push("/fleet");
  }

  if (!selectedId && !id) {
    return (
      <Card>
        <CardContent className="py-12 text-center text-sm text-muted-foreground">
          Pick an entity from the switcher above to add a driver.
        </CardContent>
      </Card>
    );
  }
  if (loadError) return <p className="text-sm text-destructive">{loadError}</p>;
  if (!initial) return <p className="text-sm text-muted-foreground">Loading…</p>;

  return (
    <MasterForm
      title={id ? "Edit Driver" : "New Driver"}
      subtitle={
        selectedEntity
          ? `${selectedEntity.numeric_code} · ${selectedEntity.trade_name || selectedEntity.legal_name}`
          : undefined
      }
      fields={FIELDS}
      initial={initial}
      submitLabel={id ? "Save changes" : "Create driver"}
      cancelHref="/fleet"
      onSubmit={onSubmit}
    />
  );
}
