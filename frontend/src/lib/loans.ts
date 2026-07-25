import { apiFetch } from "@/lib/api";

export type AmortizationMethod =
  | "reducing_balance"
  | "flat_rate"
  | "flat_quoted_effective";
export type ScheduleStatus = "draft" | "approved" | "superseded";

export type VehicleLoan = {
  id: string;
  entity: string;
  vehicle: string;
  vehicle_code: string;
  lender: string;
  loan_account: string;
  loan_account_code: string;
  interest_account: string;
  interest_account_code: string;
  principal: string;
  down_payment: string;
  term_months: number | null;
  emi_amount: string;
  annual_interest_rate: string;
  amortization_method: AmortizationMethod;
  quoted_flat_rate: string | null;
  effective_annual_rate: string | null;
  start_date: string | null;
  first_payment_date: string | null;
  is_active: boolean;
  approved_schedule_version: number | null;
};

export type Installment = {
  id: string;
  installment_no: number;
  due_date: string;
  opening_balance: string;
  principal_component: string;
  interest_component: string;
  total_amount: string;
  closing_balance: string;
  bank_account: string | null;
  status: string;
  journal_entry: string | null;
};

export type LoanSchedule = {
  id: string;
  loan: string;
  version_no: number;
  method: AmortizationMethod;
  opening_principal: string;
  annual_interest_rate: string;
  term_months: number;
  first_payment_date: string;
  total_principal: string;
  total_interest: string;
  total_payments: string;
  status: ScheduleStatus;
  approved_at: string | null;
  note: string;
  posted_count: number;
  installments: Installment[];
};

type Paginated<T> = { count: number; next: string | null; previous: string | null; results: T[] };

async function detail(res: Response, fallback: string): Promise<string> {
  const data = (await res.json().catch(() => ({}))) as { detail?: unknown };
  return typeof data.detail === "string" ? data.detail : fallback;
}

export async function listLoans(entityId?: string | null): Promise<VehicleLoan[]> {
  const params = new URLSearchParams({ limit: "200" });
  if (entityId) params.set("entity", entityId);
  const res = await apiFetch(`/vehicle-loans/?${params.toString()}`);
  if (!res.ok) throw new Error(`Failed to load loans (${res.status})`);
  return ((await res.json()) as Paginated<VehicleLoan>).results;
}

export async function getLoan(id: string): Promise<VehicleLoan> {
  const res = await apiFetch(`/vehicle-loans/${id}/`);
  if (!res.ok) throw new Error(`Failed to load the loan (${res.status})`);
  return (await res.json()) as VehicleLoan;
}

export async function listSchedules(loanId: string): Promise<LoanSchedule[]> {
  const res = await apiFetch(`/vehicle-loans/${loanId}/schedules/`);
  if (!res.ok) throw new Error(`Failed to load schedules (${res.status})`);
  return ((await res.json()) as { schedules: LoanSchedule[] }).schedules;
}

export async function generateSchedule(
  loanId: string,
  body: { first_payment_date?: string; note?: string } = {},
): Promise<LoanSchedule> {
  const res = await apiFetch(`/vehicle-loans/${loanId}/generate-schedule/`, {
    method: "POST",
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await detail(res, "Could not generate the schedule."));
  return (await res.json()) as LoanSchedule;
}

export async function approveSchedule(scheduleId: string): Promise<LoanSchedule> {
  const res = await apiFetch(`/loan-schedules/${scheduleId}/approve/`, {
    method: "POST",
    body: JSON.stringify({}),
  });
  if (!res.ok) throw new Error(await detail(res, "Could not approve the schedule."));
  return (await res.json()) as LoanSchedule;
}

export async function discardSchedule(scheduleId: string): Promise<void> {
  const res = await apiFetch(`/loan-schedules/${scheduleId}/discard/`, {
    method: "POST",
    body: JSON.stringify({}),
  });
  if (!res.ok) throw new Error(await detail(res, "Could not discard the schedule."));
}

export async function postInstallment(
  installmentId: string,
  bankAccount: string,
): Promise<Installment> {
  const res = await apiFetch(`/loan-installments/${installmentId}/post/`, {
    method: "POST",
    body: JSON.stringify({ bank_account: bankAccount }),
  });
  if (!res.ok) throw new Error(await detail(res, "Could not post this instalment."));
  return (await res.json()) as Installment;
}
