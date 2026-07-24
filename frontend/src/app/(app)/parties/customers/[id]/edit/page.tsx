"use client";

import { useParams } from "next/navigation";
import { CustomerForm } from "../../customer-form";

export default function EditCustomerPage() {
  const { id } = useParams<{ id: string }>();
  return <CustomerForm id={id} />;
}
