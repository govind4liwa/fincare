"use client";

import { useEffect, useState } from "react";
import { useEntity } from "@/lib/entity-context";
import { listAuditLogs, type AuditAction, type AuditLog } from "@/lib/audit";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const fieldClass =
  "h-9 rounded-md border border-border bg-background px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40";

const ACTIONS: { value: AuditAction | ""; label: string }[] = [
  { value: "", label: "All actions" },
  { value: "create", label: "Create" },
  { value: "update", label: "Update" },
  { value: "delete", label: "Delete" },
  { value: "post", label: "Post" },
  { value: "reverse", label: "Reverse" },
  { value: "cancel", label: "Cancel" },
  { value: "login", label: "Login" },
];

const ACTION_STYLE: Record<AuditAction, string> = {
  create: "bg-primary/10 text-primary",
  update: "bg-amber-500/10 text-amber-700 dark:text-amber-400",
  delete: "bg-destructive/10 text-destructive",
  post: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
  reverse: "bg-amber-500/10 text-amber-700 dark:text-amber-400",
  cancel: "bg-destructive/10 text-destructive",
  login: "bg-muted text-muted-foreground",
};

export default function AuditLogPage() {
  const { selectedId, selectedEntity } = useEntity();
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [action, setAction] = useState("");
  const [loadError, setLoadError] = useState("");
  const [expanded, setExpanded] = useState("");

  useEffect(() => {
    if (!selectedId) return;
    let active = true;
    listAuditLogs({ entityId: selectedId, action: action || undefined })
      .then((rows) => {
        if (active) setLogs(rows);
      })
      .catch(() => {
        if (active)
          setLoadError(
            "Couldn't load the audit trail — this needs an accountant, manager, or admin role.",
          );
      });
    return () => {
      active = false;
    };
  }, [selectedId, action]);

  if (!selectedId) {
    return (
      <Card>
        <CardContent className="py-12 text-center text-sm text-muted-foreground">
          Pick an entity from the switcher above to view its audit trail.
        </CardContent>
      </Card>
    );
  }
  if (loadError) return <p className="text-sm text-destructive">{loadError}</p>;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">Audit Trail</h1>
        <p className="text-sm text-muted-foreground">
          {selectedEntity?.numeric_code} ·{" "}
          {selectedEntity?.trade_name || selectedEntity?.legal_name} — an append-only record of
          who did what, when.
        </p>
      </div>

      <div className="flex items-center gap-2">
        <select value={action} onChange={(e) => setAction(e.target.value)} className={fieldClass}>
          {ACTIONS.map((a) => (
            <option key={a.value} value={a.value}>
              {a.label}
            </option>
          ))}
        </select>
      </div>

      <Card>
        <CardContent className="p-0">
          <table className="w-full text-sm">
            <thead className="border-b border-border text-left text-xs text-muted-foreground">
              <tr>
                <th className="px-4 py-2 font-medium">When</th>
                <th className="px-4 py-2 font-medium">Who</th>
                <th className="px-4 py-2 font-medium">Action</th>
                <th className="px-4 py-2 font-medium">Record</th>
                <th className="px-4 py-2 font-medium">Message</th>
              </tr>
            </thead>
            <tbody>
              {logs.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">
                    No audit entries yet.
                  </td>
                </tr>
              ) : (
                logs.map((log) => (
                  <tr
                    key={log.id}
                    className={cn(
                      "cursor-pointer border-b border-border/60 last:border-0 hover:bg-accent/30",
                      Object.keys(log.changes).length === 0 && "cursor-default hover:bg-transparent",
                    )}
                    onClick={() =>
                      Object.keys(log.changes).length > 0 &&
                      setExpanded(expanded === log.id ? "" : log.id)
                    }
                  >
                    <td className="px-4 py-2 whitespace-nowrap text-muted-foreground">
                      {new Date(log.timestamp).toLocaleString()}
                    </td>
                    <td className="px-4 py-2">{log.actor_email || "system"}</td>
                    <td className="px-4 py-2">
                      <span
                        className={cn(
                          "rounded-full px-2 py-0.5 text-xs font-medium capitalize",
                          ACTION_STYLE[log.action],
                        )}
                      >
                        {log.action}
                      </span>
                    </td>
                    <td className="px-4 py-2">
                      <span className="text-muted-foreground">
                        {log.content_type_label || "—"}
                      </span>{" "}
                      {log.object_repr}
                    </td>
                    <td className="px-4 py-2 text-muted-foreground">
                      {log.message}
                      {expanded === log.id && (
                        <dl className="mt-2 flex flex-col gap-1 text-xs">
                          {Object.entries(log.changes).map(([field, [before, after]]) => (
                            <div key={field} className="flex gap-2">
                              <dt className="font-medium text-foreground">{field}:</dt>
                              <dd>
                                {String(before)} → {String(after)}
                              </dd>
                            </div>
                          ))}
                        </dl>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}
