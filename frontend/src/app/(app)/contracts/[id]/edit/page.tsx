"use client";

import { useParams } from "next/navigation";
import { ContractForm } from "../../contract-form";

export default function EditContractPage() {
  const { id } = useParams<{ id: string }>();
  return <ContractForm id={id} />;
}
