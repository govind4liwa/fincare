import { apiFetch } from "@/lib/api";

export type Period = {
  id: string;
  name: string;
  fiscal_year: number;
  period_no: number;
  start_date: string;
  end_date: string;
  status: string;
};

export type ReportTable = {
  code: string;
  title: string;
  columns: string[];
  rows: string[][];
  meta: Record<string, unknown>;
};

type Paginated<T> = { count: number; results: T[] };

export const REPORTS = [
  { code: "TB", title: "Trial Balance" },
  { code: "PNL", title: "Profit & Loss" },
  { code: "BS", title: "Balance Sheet" },
  { code: "CF", title: "Cash Flow" },
];

export async function listPeriods(entityId?: string | null): Promise<Period[]> {
  const params = new URLSearchParams({ limit: "100", ordering: "-start_date" });
  if (entityId) params.set("entity", entityId);
  const res = await apiFetch(`/periods/?${params.toString()}`);
  if (!res.ok) throw new Error(`Failed to load periods (${res.status})`);
  return ((await res.json()) as Paginated<Period>).results;
}

function reportQuery(entityId: string, periodId: string, basis: string, exportFmt: string) {
  // Use `export=` (not `format=`) — DRF reserves `format` for content negotiation.
  return new URLSearchParams({
    entity_id: entityId,
    period_id: periodId,
    basis,
    export: exportFmt,
  }).toString();
}

export async function fetchReport(
  code: string,
  entityId: string,
  periodId: string,
  basis: string,
): Promise<ReportTable> {
  const res = await apiFetch(`/reports/${code}/?${reportQuery(entityId, periodId, basis, "json")}`);
  if (!res.ok) throw new Error(`Failed to build report (${res.status})`);
  return ((await res.json()) as { report: ReportTable }).report;
}

/** Fetch the xlsx (auth-protected) as a blob and trigger a browser download. */
export async function downloadReportXlsx(
  code: string,
  entityId: string,
  periodId: string,
  basis: string,
): Promise<void> {
  const res = await apiFetch(`/reports/${code}/?${reportQuery(entityId, periodId, basis, "xlsx")}`);
  if (!res.ok) throw new Error("Export failed");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${code}.xlsx`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
