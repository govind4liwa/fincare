"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useEntity } from "@/lib/entity-context";
import { listAccounts, type Account } from "@/lib/accounts";
import { getRecord, createRecord, updateRecord } from "@/lib/crud";
import { type BankAccount } from "@/lib/banking";
import { MasterForm, type FieldSpec, type FormValues } from "@/components/master-form";
import { Card, CardContent } from "@/components/ui/card";

const RESOURCE = "bank-accounts";

const BLANK: FormValues = {
  code: "",
  name: "",
  gl_account: "",
  bank_name: "",
  account_number: "",
  iban: "",
  swift: "",
  branch_name: "",
  is_active: true,
};

export function BankAccountForm({ id }: { id?: string }) {
  const router = useRouter();
  const { selectedId, selectedEntity } = useEntity();
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [initial, setInitial] = useState<FormValues | null>(id ? null : BLANK);
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    if (!selectedId) return;
    let active = true;
    listAccounts(selectedId)
      .then((rows) => {
        if (active) setAccounts(rows.filter((a) => a.account_type === "bank" && a.is_active));
      })
      .catch(() => {
        if (active) setLoadError("Couldn't load bank GL accounts.");
      });
    return () => {
      active = false;
    };
  }, [selectedId]);

  useEffect(() => {
    if (!id) return;
    let active = true;
    getRecord<BankAccount>(RESOURCE, id)
      .then((b) => {
        if (!active) return;
        setInitial({
          code: b.code,
          name: b.name,
          gl_account: b.gl_account,
          bank_name: b.bank_name,
          account_number: b.account_number,
          iban: b.iban,
          swift: b.swift,
          branch_name: b.branch_name,
          is_active: b.is_active,
        });
      })
      .catch(() => {
        if (active) setLoadError("Couldn't load this bank account.");
      });
    return () => {
      active = false;
    };
  }, [id]);

  const fields: FieldSpec[] = useMemo(
    () => [
      { name: "code", label: "Code", required: true, placeholder: "ENBD" },
      { name: "name", label: "Name", required: true, colSpan: 2 },
      {
        name: "gl_account",
        label: "GL account (bank)",
        type: "select",
        required: true,
        options: accounts.map((a) => ({ value: a.id, label: `${a.code} · ${a.name}` })),
        help: "Only bank-type GL accounts are eligible.",
      },
      { name: "bank_name", label: "Bank name" },
      { name: "account_number", label: "Account number" },
      { name: "iban", label: "IBAN" },
      { name: "swift", label: "SWIFT" },
      { name: "branch_name", label: "Branch" },
      { name: "is_active", label: "Active", type: "checkbox" },
    ],
    [accounts],
  );

  async function onSubmit(values: FormValues) {
    const payload = {
      ...(id ? {} : { entity: selectedId }),
      code: values.code,
      name: values.name,
      gl_account: values.gl_account,
      bank_name: values.bank_name,
      account_number: values.account_number,
      iban: values.iban,
      swift: values.swift,
      branch_name: values.branch_name,
      is_active: values.is_active,
    };
    if (id) await updateRecord(RESOURCE, id, payload);
    else await createRecord(RESOURCE, payload);
    router.push("/banking");
  }

  if (!selectedId && !id) {
    return (
      <Card>
        <CardContent className="py-12 text-center text-sm text-muted-foreground">
          Pick an entity from the switcher above to add a bank account.
        </CardContent>
      </Card>
    );
  }
  if (loadError) return <p className="text-sm text-destructive">{loadError}</p>;
  if (!initial) return <p className="text-sm text-muted-foreground">Loading…</p>;

  return (
    <MasterForm
      title={id ? "Edit Bank Account" : "New Bank Account"}
      subtitle={
        selectedEntity
          ? `${selectedEntity.numeric_code} · ${selectedEntity.trade_name || selectedEntity.legal_name}`
          : undefined
      }
      fields={fields}
      initial={initial}
      submitLabel={id ? "Save changes" : "Create bank account"}
      cancelHref="/banking"
      onSubmit={onSubmit}
    />
  );
}
