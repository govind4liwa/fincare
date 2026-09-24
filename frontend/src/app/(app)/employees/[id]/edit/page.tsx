"use client";

import { useParams } from "next/navigation";
import { useEntity } from "@/lib/entity-context";
import { EmployeeForm } from "../../employee-form";
import { EmployeeSalaryStructure } from "../../employee-salary";

export default function EditEmployeePage() {
  const { id } = useParams<{ id: string }>();
  const { selectedId } = useEntity();
  return (
    <div className="flex flex-col gap-6">
      <EmployeeForm id={id} />
      {selectedId && <EmployeeSalaryStructure employeeId={id} entityId={selectedId} />}
    </div>
  );
}
