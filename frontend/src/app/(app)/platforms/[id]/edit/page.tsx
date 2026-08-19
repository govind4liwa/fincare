"use client";

import { useParams } from "next/navigation";
import { PlatformForm } from "../../platform-form";

export default function EditPlatformPage() {
  const { id } = useParams<{ id: string }>();
  return <PlatformForm id={id} />;
}
