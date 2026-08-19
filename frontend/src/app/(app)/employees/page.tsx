"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Plus } from "lucide-react";
import { useEntity } from "@/lib/entity-context";
import { listEmployees, type Employee } from "@/lib/payroll";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const STATUS_STYLE: Record<Employee["status"], string> = {
  active: "bg-primary/10 text-primary",
  on_leave: "bg-amber-500/10 text-amber-700 dark:text-amber-400",
  left: "bg-muted text-muted-foreground",
};

export default function EmployeesPage() {
  const router = useRouter();
  const { selectedId, selectedEntity } = useEntity();
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let active = true;
    listEmployees(selectedId)
      .then((rows) => {
        if (active) {
          setEmployees(rows);
          setError(false);
        }
      })
      .catch(() => {
        if (active) setError(true);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [selectedId]);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Employees</h1>
          <p className="text-sm text-muted-foreground">
            {selectedEntity
              ? `${selectedEntity.numeric_code} · ${selectedEntity.trade_name || selectedEntity.legal_name}`
              : "All accessible entities"}
          </p>
        </div>
        <Link href="/employees/new">
          <Button size="sm">
            <Plus className="h-4 w-4" />
            New employee
          </Button>
        </Link>
      </div>

      {loading ? (
        <p className="text-sm text-muted-foreground">Loading employees…</p>
      ) : error ? (
        <p className="text-sm text-destructive">Couldn&apos;t load employees.</p>
      ) : employees.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-sm text-muted-foreground">
            No employees yet. Add one with the{" "}
            <span className="font-medium text-foreground">New employee</span> button.
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b border-border text-left text-xs text-muted-foreground">
                  <tr>
                    <th className="px-4 py-2 font-medium">Code</th>
                    <th className="px-4 py-2 font-medium">Name</th>
                    <th className="px-4 py-2 font-medium">Designation</th>
                    <th className="px-4 py-2 font-medium">Pay method</th>
                    <th className="px-4 py-2 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {employees.map((e) => (
                    <tr
                      key={e.id}
                      onClick={() => router.push(`/employees/${e.id}/edit`)}
                      className="cursor-pointer border-b border-border/60 last:border-0 hover:bg-accent/50"
                    >
                      <td className="whitespace-nowrap px-4 py-2 font-mono text-xs">{e.code}</td>
                      <td className="px-4 py-2">{e.name}</td>
                      <td className="px-4 py-2 text-muted-foreground">{e.designation || "—"}</td>
                      <td className="px-4 py-2 uppercase text-muted-foreground">{e.pay_method}</td>
                      <td className="px-4 py-2">
                        <span
                          className={cn(
                            "rounded-full px-2 py-0.5 text-xs font-medium capitalize",
                            STATUS_STYLE[e.status],
                          )}
                        >
                          {e.status.replace("_", " ")}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
