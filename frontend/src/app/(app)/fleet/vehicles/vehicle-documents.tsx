"use client";

import { useEffect, useState } from "react";
import {
  createVehicleDocument,
  listVehicleDocuments,
  type VehicleDocument,
} from "@/lib/fleet";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const DOC_TYPES = [
  ["registration", "Registration / Mulkiya"],
  ["insurance", "Insurance"],
  ["salik_tag", "Salik Tag"],
  ["permit", "Permit"],
  ["other", "Other"],
] as const;

const fieldClass =
  "h-9 rounded-md border border-border bg-background px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40";

function expiryTone(days: number | null) {
  if (days === null) return "";
  if (days < 0) return "text-destructive font-medium";
  if (days <= 30) return "text-amber-600 dark:text-amber-400 font-medium";
  return "text-muted-foreground";
}

type Props = { vehicleId: string };

/** Documents for one vehicle. Each renewal is a new row (see backend docstring) —
 * there is no edit, only adding the next period's document. */
export function VehicleDocuments({ vehicleId }: Props) {
  const [docs, setDocs] = useState<VehicleDocument[]>([]);
  const [loadError, setLoadError] = useState("");
  const [docType, setDocType] = useState<string>(DOC_TYPES[0][0]);
  const [docNo, setDocNo] = useState("");
  const [issueDate, setIssueDate] = useState("");
  const [expiryDate, setExpiryDate] = useState("");
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    listVehicleDocuments(vehicleId)
      .then((rows) => {
        if (active) setDocs(rows);
      })
      .catch(() => {
        if (active) setLoadError("Couldn't load documents.");
      });
    return () => {
      active = false;
    };
  }, [vehicleId]);

  async function add() {
    setSaving(true);
    setError("");
    try {
      await createVehicleDocument({
        vehicle: vehicleId,
        doc_type: docType,
        doc_no: docNo,
        issue_date: issueDate || null,
        expiry_date: expiryDate || null,
        note,
      });
      setDocs(await listVehicleDocuments(vehicleId));
      setDocNo("");
      setIssueDate("");
      setExpiryDate("");
      setNote("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card className="max-w-4xl">
      <CardHeader>
        <CardTitle>Documents</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {loadError && <p className="text-sm text-destructive">{loadError}</p>}
        {docs.length > 0 && (
          <table className="w-full text-sm">
            <thead className="border-b border-border text-left text-xs text-muted-foreground">
              <tr>
                <th className="py-2 font-medium">Type</th>
                <th className="py-2 font-medium">Doc no.</th>
                <th className="py-2 font-medium">Issued</th>
                <th className="py-2 font-medium">Expires</th>
                <th className="py-2 text-right font-medium">Days left</th>
              </tr>
            </thead>
            <tbody>
              {docs.map((d) => (
                <tr key={d.id} className="border-b border-border/60 last:border-0">
                  <td className="py-2 capitalize">{d.doc_type.replace("_", " ")}</td>
                  <td className="py-2">{d.doc_no || "—"}</td>
                  <td className="py-2 text-muted-foreground">{d.issue_date || "—"}</td>
                  <td className="py-2 text-muted-foreground">{d.expiry_date || "—"}</td>
                  <td className={cn("py-2 text-right tabular-nums", expiryTone(d.days_to_expiry))}>
                    {d.days_to_expiry ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
          <div className="flex flex-col gap-1.5">
            <Label>Type</Label>
            <select value={docType} onChange={(e) => setDocType(e.target.value)} className={fieldClass}>
              {DOC_TYPES.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Doc no.</Label>
            <Input value={docNo} onChange={(e) => setDocNo(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Issued</Label>
            <Input type="date" value={issueDate} onChange={(e) => setIssueDate(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Expires</Label>
            <Input type="date" value={expiryDate} onChange={(e) => setExpiryDate(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Note</Label>
            <Input value={note} onChange={(e) => setNote(e.target.value)} />
          </div>
        </div>
        <div>
          <Button size="sm" onClick={add} disabled={saving}>
            {saving ? "Adding…" : "Add document"}
          </Button>
        </div>

        {error && <p className="text-sm text-destructive">{error}</p>}
      </CardContent>
    </Card>
  );
}
