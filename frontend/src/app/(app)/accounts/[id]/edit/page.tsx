"use client";

import { useParams } from "next/navigation";
import { AccountForm } from "../../account-form";

export default function EditAccountPage() {
  const { id } = useParams<{ id: string }>();
  return <AccountForm id={id} />;
}
