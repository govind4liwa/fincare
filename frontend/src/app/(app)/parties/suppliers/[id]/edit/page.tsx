"use client";

import { useParams } from "next/navigation";
import { SupplierForm } from "../../supplier-form";

export default function EditSupplierPage() {
  const { id } = useParams<{ id: string }>();
  return <SupplierForm id={id} />;
}
