"use client";

import { useParams } from "next/navigation";
import { VehicleForm } from "../../vehicle-form";
import { VehicleDocuments } from "../../vehicle-documents";

export default function EditVehiclePage() {
  const { id } = useParams<{ id: string }>();
  return (
    <div className="flex flex-col gap-6">
      <VehicleForm id={id} />
      <VehicleDocuments vehicleId={id} />
    </div>
  );
}
