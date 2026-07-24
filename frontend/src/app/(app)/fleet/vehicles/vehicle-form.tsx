"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useEntity } from "@/lib/entity-context";
import { getRecord, createRecord, updateRecord } from "@/lib/crud";
import { type Vehicle } from "@/lib/fleet";
import { MasterForm, type FieldSpec, type FormValues } from "@/components/master-form";
import { Card, CardContent } from "@/components/ui/card";

const RESOURCE = "vehicles";
const OWNERSHIP = [
  ["owned", "Owned"],
  ["leased", "Leased"],
  ["financed", "Financed"],
] as const;

const FIELDS: FieldSpec[] = [
  { name: "code", label: "Fleet code", required: true, placeholder: "V-001" },
  { name: "plate_no", label: "Plate no." },
  { name: "plate_emirate", label: "Plate emirate" },
  {
    name: "ownership",
    label: "Ownership",
    type: "select",
    options: OWNERSHIP.map(([value, label]) => ({ value, label })),
  },
  { name: "make", label: "Make" },
  { name: "model", label: "Model" },
  { name: "model_year", label: "Model year", type: "number" },
  { name: "vin", label: "VIN / chassis" },
  { name: "acquisition_date", label: "Acquisition date", type: "date" },
  { name: "acquisition_cost", label: "Acquisition cost", type: "number" },
  { name: "is_active", label: "Active", type: "checkbox" },
];

const BLANK: FormValues = {
  code: "",
  plate_no: "",
  plate_emirate: "",
  ownership: "owned",
  make: "",
  model: "",
  model_year: "",
  vin: "",
  acquisition_date: "",
  acquisition_cost: "",
  is_active: true,
};

export function VehicleForm({ id }: { id?: string }) {
  const router = useRouter();
  const { selectedId, selectedEntity } = useEntity();
  const [initial, setInitial] = useState<FormValues | null>(id ? null : BLANK);
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    if (!id) return;
    let active = true;
    getRecord<Vehicle>(RESOURCE, id)
      .then((v) => {
        if (!active) return;
        setInitial({
          code: v.code,
          plate_no: v.plate_no,
          plate_emirate: v.plate_emirate,
          ownership: v.ownership,
          make: v.make,
          model: v.model,
          model_year: v.model_year?.toString() ?? "",
          vin: v.vin,
          acquisition_date: v.acquisition_date ?? "",
          acquisition_cost: v.acquisition_cost ?? "",
          is_active: v.is_active,
        });
      })
      .catch(() => {
        if (active) setLoadError("Couldn't load this vehicle.");
      });
    return () => {
      active = false;
    };
  }, [id]);

  async function onSubmit(values: FormValues) {
    const payload = {
      ...(id ? {} : { entity: selectedId }),
      code: values.code,
      plate_no: values.plate_no,
      plate_emirate: values.plate_emirate,
      ownership: values.ownership,
      make: values.make,
      model: values.model,
      model_year: values.model_year === "" ? null : Number(values.model_year),
      vin: values.vin,
      acquisition_date: values.acquisition_date === "" ? null : values.acquisition_date,
      acquisition_cost: values.acquisition_cost === "" ? "0" : values.acquisition_cost,
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
          Pick an entity from the switcher above to add a vehicle.
        </CardContent>
      </Card>
    );
  }
  if (loadError) return <p className="text-sm text-destructive">{loadError}</p>;
  if (!initial) return <p className="text-sm text-muted-foreground">Loading…</p>;

  return (
    <MasterForm
      title={id ? "Edit Vehicle" : "New Vehicle"}
      subtitle={
        selectedEntity
          ? `${selectedEntity.numeric_code} · ${selectedEntity.trade_name || selectedEntity.legal_name}`
          : undefined
      }
      fields={FIELDS}
      initial={initial}
      submitLabel={id ? "Save changes" : "Create vehicle"}
      cancelHref="/fleet"
      onSubmit={onSubmit}
    />
  );
}
