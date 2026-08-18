import { apiFetch } from "@/lib/api";

export type Period = {
  id: string;
  entity: string;
  name: string;
  fiscal_year: number;
  period_no: number;
  start_date: string;
  end_date: string;
  status: "open" | "closed" | "locked";
  closed_at: string | null;
  closed_by_email?: string;
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

async function periodDetail(res: Response, fallback: string): Promise<string> {
  const data = (await res.json().catch(() => ({}))) as { detail?: unknown };
  return typeof data.detail === "string" ? data.detail : fallback;
}

async function transitionPeriod(id: string, action: "close" | "reopen" | "lock"): Promise<Period> {
  const res = await apiFetch(`/periods/${id}/${action}/`, {
    method: "POST",
    body: JSON.stringify({}),
  });
  if (!res.ok) throw new Error(await periodDetail(res, `Could not ${action} this period.`));
  return (await res.json()) as Period;
}

export const closePeriod = (id: string) => transitionPeriod(id, "close");
export const reopenPeriod = (id: string) => transitionPeriod(id, "reopen");
export const lockPeriod = (id: string) => transitionPeriod(id, "lock");

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

/** Fetch a report export (auth-protected) as a blob and trigger a browser download. */
async function downloadReport(
  code: string,
  entityId: string,
  periodId: string,
  basis: string,
  exportFmt: "xlsx" | "pdf",
): Promise<void> {
  const res = await apiFetch(`/reports/${code}/?${reportQuery(entityId, periodId, basis, exportFmt)}`);
  if (!res.ok) throw new Error("Export failed");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${code}.${exportFmt}`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export function downloadReportXlsx(
  code: string,
  entityId: string,
  periodId: string,
  basis: string,
): Promise<void> {
  return downloadReport(code, entityId, periodId, basis, "xlsx");
}

export function downloadReportPdf(
  code: string,
  entityId: string,
  periodId: string,
  basis: string,
): Promise<void> {
  return downloadReport(code, entityId, periodId, basis, "pdf");
}
