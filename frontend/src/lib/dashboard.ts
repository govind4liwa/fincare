import { apiFetch } from "@/lib/api";

export type DashboardSummary = {
  period: { name: string; start: string; end: string } | null;
  revenue: string;
  expenses: string;
  cash_bank: string;
  vat_payable: string;
};

export async function getDashboard(entityId?: string | null): Promise<DashboardSummary> {
  const query = entityId ? `?entity=${entityId}` : "";
  const res = await apiFetch(`/reports/dashboard/${query}`);
  if (!res.ok) throw new Error(`Failed to load dashboard (${res.status})`);
  return (await res.json()) as DashboardSummary;
}
