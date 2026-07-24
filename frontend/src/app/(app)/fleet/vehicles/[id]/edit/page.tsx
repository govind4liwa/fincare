"use client";

import { useParams } from "next/navigation";
import { VehicleForm } from "../../vehicle-form";

export default function EditVehiclePage() {
  const { id } = useParams<{ id: string }>();
  return <VehicleForm id={id} />;
}
