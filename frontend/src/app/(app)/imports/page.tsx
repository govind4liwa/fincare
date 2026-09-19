"use client";

import { useEffect, useState } from "react";
import { useEntity } from "@/lib/entity-context";
import { listBankAccounts, type BankAccount } from "@/lib/banking";
import { listPlatforms, type Platform } from "@/lib/platforms";
import {
  BANK_FIELDS,
  PLATFORM_FIELDS,
  REQUIRED_FIELDS,
  createProfile,
  listBatches,
  listProfiles,
  updateProfile,
  uploadBankStatement,
  uploadPlatformEarnings,
  type ImportBatch,
  type ImportKind,
  type ImportProfile,
} from "@/lib/integrations";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const fieldClass =
  "h-9 rounded-md border border-border bg-background px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40";

const ACCEPT = ".csv,.txt,.xlsx,.xlsm";

const KIND_LABEL: Record<ImportKind, string> = {
  bank_statement: "Bank statement",
  platform_earning: "Platform earnings",
};

/** Human labels for the canonical mapping fields. */
const FIELD_LABEL: Record<string, string> = {
  txn_date: "Transaction date",
  description: "Description",
  reference: "Reference",
  deposit: "Deposit",
  withdrawal: "Withdrawal",
  running_balance: "Running balance",
  earning_date: "Earning date",
  trip_ref: "Trip reference",
  driver_ref: "Driver reference",
  gross: "Gross",
  commission: "Commission",
  net: "Net",
};

type ProfileForm = {
  kind: ImportKind;
  name: string;
  source_key: string;
  date_format: string;
  skip_rows: string;
  sheet: string;
  scope: "entity" | "global";
  map: Record<string, string>;
};

const emptyProfileForm = (kind: ImportKind = "bank_statement"): ProfileForm => ({
  kind,
  name: "",
  source_key: "",
  date_format: "",
  skip_rows: "0",
  sheet: "",
  scope: "entity",
  map: {},
});

export default function ImportsPage() {
  const { selectedId, selectedEntity } = useEntity();
  const [bankAccounts, setBankAccounts] = useState<BankAccount[]>([]);
  const [platforms, setPlatforms] = useState<Platform[]>([]);
  const [profiles, setProfiles] = useState<ImportProfile[]>([]);
  const [batches, setBatches] = useState<ImportBatch[]>([]);
  const [loadError, setLoadError] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const [bankForm, setBankForm] = useState({ bank_account: "", profile: "", statement_no: "" });
  const [bankFile, setBankFile] = useState<File | null>(null);
  const [platformForm, setPlatformForm] = useState({ platform: "", profile: "" });
  const [platformFile, setPlatformFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState("");
  const [fileInputEpoch, setFileInputEpoch] = useState(0);

  const [profileForm, setProfileForm] = useState<ProfileForm>(emptyProfileForm());
  const [editingId, setEditingId] = useState("");
  const [savingProfile, setSavingProfile] = useState(false);
  const [busyProfileId, setBusyProfileId] = useState("");

  useEffect(() => {
    if (!selectedId) return;
    let active = true;
    Promise.all([
      listBankAccounts(selectedId),
      listPlatforms(selectedId),
      listProfiles(),
      listBatches(selectedId),
    ])
      .then(([accounts, plats, profs, hist]) => {
        if (!active) return;
        // Only active sources can be imported into — the API rejects the rest.
        setBankAccounts(accounts.filter((a) => a.is_active));
        setPlatforms(plats.filter((p) => p.is_active));
        setProfiles(profs);
        setBatches(hist);
      })
      .catch(() => {
        if (active) setLoadError("Couldn't load the imports workspace.");
      });
    return () => {
      active = false;
    };
  }, [selectedId]);

  const bankProfiles = profiles.filter((p) => p.kind === "bank_statement" && p.is_active);
  const platformProfiles = profiles.filter((p) => p.kind === "platform_earning" && p.is_active);
  const mappableFields = profileForm.kind === "bank_statement" ? BANK_FIELDS : PLATFORM_FIELDS;

  async function refreshBatches() {
    if (!selectedId) return;
    try {
      setBatches(await listBatches(selectedId));
    } catch {
      // keep the stale list; the next successful action refreshes it
    }
  }

  async function importBank() {
    if (!bankFile || !bankForm.bank_account || !bankForm.profile) {
      return setError("Bank account, profile, and a file are required.");
    }
    setUploading("bank");
    setError("");
    setNotice("");
    try {
      const batch = await uploadBankStatement({
        file: bankFile,
        bank_account: bankForm.bank_account,
        profile: bankForm.profile,
        statement_no: bankForm.statement_no || undefined,
      });
      setBatches((prev) => [batch, ...prev]);
      setNotice(
        `${batch.filename}: ${batch.created_count} line(s) imported, ` +
          `${batch.skipped_count} duplicate(s) skipped.`,
      );
      setBankFile(null);
      setFileInputEpoch((n) => n + 1);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
      await refreshBatches(); // a failed run is recorded on the batch log
    } finally {
      setUploading("");
    }
  }

  async function importPlatform() {
    if (!platformFile || !platformForm.platform || !platformForm.profile) {
      return setError("Platform, profile, and a file are required.");
    }
    setUploading("platform");
    setError("");
    setNotice("");
    try {
      const batch = await uploadPlatformEarnings({
        file: platformFile,
        platform: platformForm.platform,
        profile: platformForm.profile,
      });
      setBatches((prev) => [batch, ...prev]);
      setNotice(
        `${batch.filename}: ${batch.created_count} earning(s) staged, ` +
          `${batch.skipped_count} duplicate(s) skipped.`,
      );
      setPlatformFile(null);
      setFileInputEpoch((n) => n + 1);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
      await refreshBatches();
    } finally {
      setUploading("");
    }
  }

  function startEdit(profile: ImportProfile) {
    setEditingId(profile.id);
    setProfileForm({
      kind: profile.kind,
      name: profile.name,
      source_key: profile.source_key,
      date_format: profile.date_format,
      skip_rows: String(profile.skip_rows),
      sheet: profile.sheet,
      scope: profile.entity ? "entity" : "global",
      map: { ...profile.column_map },
    });
  }

  function cancelEdit() {
    setEditingId("");
    setProfileForm(emptyProfileForm(profileForm.kind));
  }

  async function saveProfile() {
    if (!selectedId || !profileForm.name || !profileForm.source_key) {
      return setError("Profile name and source key are required.");
    }
    const columnMap = Object.fromEntries(
      Object.entries(profileForm.map).filter(([, v]) => v.trim() !== ""),
    );
    const missing = REQUIRED_FIELDS[profileForm.kind].filter((f) => !columnMap[f]);
    if (missing.length) {
      return setError(
        `Map the required column(s): ${missing.map((f) => FIELD_LABEL[f] ?? f).join(", ")}.`,
      );
    }
    setSavingProfile(true);
    setError("");
    setNotice("");
    const payload = {
      entity: profileForm.scope === "global" ? null : selectedId,
      kind: profileForm.kind,
      name: profileForm.name,
      source_key: profileForm.source_key,
      column_map: columnMap,
      date_format: profileForm.date_format,
      skip_rows: Number(profileForm.skip_rows) || 0,
      sheet: profileForm.sheet,
    };
    try {
      if (editingId) {
        const updated = await updateProfile(editingId, payload);
        setProfiles((prev) => prev.map((p) => (p.id === editingId ? updated : p)));
      } else {
        const created = await createProfile(payload);
        setProfiles((prev) => [...prev, created]);
      }
      cancelEdit();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setSavingProfile(false);
    }
  }

  async function toggleProfile(profile: ImportProfile) {
    setBusyProfileId(profile.id);
    setError("");
    try {
      const updated = await updateProfile(profile.id, { is_active: !profile.is_active });
      setProfiles((prev) => prev.map((p) => (p.id === profile.id ? updated : p)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setBusyProfileId("");
    }
  }

  if (!selectedId) {
    return (
      <Card>
        <CardContent className="py-12 text-center text-sm text-muted-foreground">
          Pick an entity from the switcher above to import files.
        </CardContent>
      </Card>
    );
  }
  if (loadError) return <p className="text-sm text-destructive">{loadError}</p>;

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-2xl font-semibold">File Imports</h1>
        <p className="text-sm text-muted-foreground">
          {selectedEntity?.numeric_code} ·{" "}
          {selectedEntity?.trade_name || selectedEntity?.legal_name} — import bank statements
          and platform earnings from CSV/XLSX files. Re-importing a file is safe: rows already
          staged are skipped.
        </p>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}
      {notice && <p className="text-sm text-emerald-600 dark:text-emerald-400">{notice}</p>}

      <section className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardContent className="flex flex-col gap-3 py-5">
            <p className="text-xs font-medium text-muted-foreground">
              Import a bank statement → statement lines for reconciliation
            </p>
            <div className="grid grid-cols-2 gap-2">
              <select
                value={bankForm.bank_account}
                onChange={(e) => setBankForm((p) => ({ ...p, bank_account: e.target.value }))}
                className={cn(fieldClass, "col-span-2")}
              >
                <option value="">Bank account…</option>
                {bankAccounts.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.code} · {a.name}
                  </option>
                ))}
              </select>
              <select
                value={bankForm.profile}
                onChange={(e) => setBankForm((p) => ({ ...p, profile: e.target.value }))}
                className={fieldClass}
              >
                <option value="">Profile…</option>
                {bankProfiles.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
              <Input
                placeholder="Statement no. (optional)"
                value={bankForm.statement_no}
                onChange={(e) => setBankForm((p) => ({ ...p, statement_no: e.target.value }))}
              />
              <input
                key={`bank-${fileInputEpoch}`}
                type="file"
                accept={ACCEPT}
                onChange={(e) => setBankFile(e.target.files?.[0] ?? null)}
                className={cn(fieldClass, "col-span-2 py-1.5 file:mr-2 file:border-0 file:bg-transparent file:text-sm file:font-medium")}
              />
            </div>
            <div>
              <Button size="sm" onClick={importBank} disabled={uploading === "bank"}>
                {uploading === "bank" ? "Importing…" : "Import statement"}
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="flex flex-col gap-3 py-5">
            <p className="text-xs font-medium text-muted-foreground">
              Import platform earnings → staged rows for settlement reconciliation
            </p>
            <div className="grid grid-cols-2 gap-2">
              <select
                value={platformForm.platform}
                onChange={(e) => setPlatformForm((p) => ({ ...p, platform: e.target.value }))}
                className={fieldClass}
              >
                <option value="">Platform…</option>
                {platforms.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
              <select
                value={platformForm.profile}
                onChange={(e) => setPlatformForm((p) => ({ ...p, profile: e.target.value }))}
                className={fieldClass}
              >
                <option value="">Profile…</option>
                {platformProfiles.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
              <input
                key={`platform-${fileInputEpoch}`}
                type="file"
                accept={ACCEPT}
                onChange={(e) => setPlatformFile(e.target.files?.[0] ?? null)}
                className={cn(fieldClass, "col-span-2 py-1.5 file:mr-2 file:border-0 file:bg-transparent file:text-sm file:font-medium")}
              />
            </div>
            <div>
              <Button size="sm" onClick={importPlatform} disabled={uploading === "platform"}>
                {uploading === "platform" ? "Importing…" : "Import earnings"}
              </Button>
            </div>
          </CardContent>
        </Card>
      </section>

      <section className="flex flex-col gap-4">
        <h2 className="text-lg font-medium">Import history</h2>
        <Card>
          <CardContent className="overflow-x-auto py-4">
            {batches.length === 0 ? (
              <p className="text-sm text-muted-foreground">No imports yet.</p>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-xs text-muted-foreground">
                    <th className="py-2 pr-3 font-medium">When</th>
                    <th className="py-2 pr-3 font-medium">Kind</th>
                    <th className="py-2 pr-3 font-medium">File</th>
                    <th className="py-2 pr-3 font-medium">Source</th>
                    <th className="py-2 pr-3 font-medium">Profile</th>
                    <th className="py-2 pr-3 text-right font-medium">Created</th>
                    <th className="py-2 pr-3 text-right font-medium">Skipped</th>
                    <th className="py-2 pr-3 font-medium">Status</th>
                    <th className="py-2 font-medium">Message</th>
                  </tr>
                </thead>
                <tbody>
                  {batches.map((b) => (
                    <tr key={b.id} className="border-b last:border-0">
                      <td className="py-2 pr-3 whitespace-nowrap">
                        {b.imported_at ? new Date(b.imported_at).toLocaleString() : "—"}
                      </td>
                      <td className="py-2 pr-3 whitespace-nowrap">{KIND_LABEL[b.kind]}</td>
                      <td className="py-2 pr-3">{b.filename}</td>
                      <td className="py-2 pr-3">{b.bank_account_code || b.platform_name || "—"}</td>
                      <td className="py-2 pr-3">{b.profile_name || "—"}</td>
                      <td className="py-2 pr-3 text-right">{b.created_count}</td>
                      <td className="py-2 pr-3 text-right">{b.skipped_count}</td>
                      <td className="py-2 pr-3">
                        <span
                          className={cn(
                            "rounded px-1.5 py-0.5 text-xs",
                            b.status === "done"
                              ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                              : "bg-destructive/10 text-destructive",
                          )}
                        >
                          {b.status}
                        </span>
                      </td>
                      <td className="py-2 text-xs text-muted-foreground">{b.message}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </CardContent>
        </Card>
      </section>

      <section className="flex flex-col gap-4">
        <h2 className="text-lg font-medium">Import profiles</h2>
        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardContent className="flex flex-col gap-3 py-5">
              <p className="text-xs font-medium text-muted-foreground">
                {editingId ? "Edit profile" : "New profile"} — map your file&apos;s column
                headers to FinCare&apos;s fields
              </p>
              <div className="grid grid-cols-2 gap-2">
                <select
                  value={profileForm.kind}
                  onChange={(e) =>
                    setProfileForm((p) => ({
                      ...emptyProfileForm(e.target.value as ImportKind),
                      name: p.name,
                      source_key: p.source_key,
                    }))
                  }
                  className={fieldClass}
                  disabled={!!editingId}
                >
                  <option value="bank_statement">Bank statement</option>
                  <option value="platform_earning">Platform earnings</option>
                </select>
                <select
                  value={profileForm.scope}
                  onChange={(e) =>
                    setProfileForm((p) => ({ ...p, scope: e.target.value as "entity" | "global" }))
                  }
                  className={fieldClass}
                >
                  <option value="entity">This entity only</option>
                  <option value="global">Group-wide</option>
                </select>
                <Input
                  placeholder="Name (e.g. ENBD CSV)"
                  value={profileForm.name}
                  onChange={(e) => setProfileForm((p) => ({ ...p, name: e.target.value }))}
                />
                <Input
                  placeholder="Source key (e.g. ENBD, Uber)"
                  value={profileForm.source_key}
                  onChange={(e) => setProfileForm((p) => ({ ...p, source_key: e.target.value }))}
                />
                <Input
                  placeholder="Date format (blank = auto)"
                  value={profileForm.date_format}
                  onChange={(e) => setProfileForm((p) => ({ ...p, date_format: e.target.value }))}
                />
                <Input
                  type="number"
                  min="0"
                  placeholder="Rows to skip"
                  value={profileForm.skip_rows}
                  onChange={(e) => setProfileForm((p) => ({ ...p, skip_rows: e.target.value }))}
                />
                <Input
                  placeholder="XLSX sheet (blank = first)"
                  className="col-span-2"
                  value={profileForm.sheet}
                  onChange={(e) => setProfileForm((p) => ({ ...p, sheet: e.target.value }))}
                />
              </div>
              <div className="grid grid-cols-2 gap-2">
                {mappableFields.map((field) => (
                  <label key={field} className="flex flex-col gap-1 text-xs text-muted-foreground">
                    {FIELD_LABEL[field]}
                    {REQUIRED_FIELDS[profileForm.kind].includes(field) ? " *" : ""}
                    <Input
                      placeholder="Column header in the file"
                      value={profileForm.map[field] ?? ""}
                      onChange={(e) =>
                        setProfileForm((p) => ({
                          ...p,
                          map: { ...p.map, [field]: e.target.value },
                        }))
                      }
                    />
                  </label>
                ))}
              </div>
              <div className="flex gap-2">
                <Button size="sm" onClick={saveProfile} disabled={savingProfile}>
                  {savingProfile ? "Saving…" : editingId ? "Save changes" : "Add profile"}
                </Button>
                {editingId && (
                  <Button size="sm" variant="outline" onClick={cancelEdit}>
                    Cancel
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="overflow-x-auto py-4">
              {profiles.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No profiles yet — create one to describe your bank&apos;s or platform&apos;s
                  file layout.
                </p>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-xs text-muted-foreground">
                      <th className="py-2 pr-3 font-medium">Name</th>
                      <th className="py-2 pr-3 font-medium">Kind</th>
                      <th className="py-2 pr-3 font-medium">Source</th>
                      <th className="py-2 pr-3 font-medium">Scope</th>
                      <th className="py-2 pr-3 font-medium">Active</th>
                      <th className="py-2 font-medium" />
                    </tr>
                  </thead>
                  <tbody>
                    {profiles.map((p) => (
                      <tr key={p.id} className="border-b last:border-0">
                        <td className="py-2 pr-3">{p.name}</td>
                        <td className="py-2 pr-3 whitespace-nowrap">{KIND_LABEL[p.kind]}</td>
                        <td className="py-2 pr-3">{p.source_key}</td>
                        <td className="py-2 pr-3">{p.entity ? "Entity" : "Group-wide"}</td>
                        <td className="py-2 pr-3">{p.is_active ? "Yes" : "No"}</td>
                        <td className="py-2 whitespace-nowrap text-right">
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => startEdit(p)}
                            disabled={busyProfileId === p.id}
                          >
                            Edit
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => toggleProfile(p)}
                            disabled={busyProfileId === p.id}
                          >
                            {p.is_active ? "Deactivate" : "Activate"}
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </CardContent>
          </Card>
        </div>
      </section>
    </div>
  );
}
