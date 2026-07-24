"use client";

import { useParams } from "next/navigation";
import { DriverForm } from "../../driver-form";

export default function EditDriverPage() {
  const { id } = useParams<{ id: string }>();
  return <DriverForm id={id} />;
}
