"use client";

import { useParams } from "next/navigation";
import { BankAccountForm } from "../../account-form";

export default function EditBankAccountPage() {
  const { id } = useParams<{ id: string }>();
  return <BankAccountForm id={id} />;
}
