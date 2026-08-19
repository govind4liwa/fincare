import { apiFetch } from "@/lib/api";

type Paginated<T> = { count: number; next: string | null; previous: string | null; results: T[] };

async function detail(res: Response, fallback: string): Promise<string> {
  const data = (await res.json().catch(() => ({}))) as { detail?: unknown };
  return typeof data.detail === "string" ? data.detail : fallback;
}

export type SalaryComponent = {
  id: string;
  entity: string | null;
  code: string;
  name: string;
  component_type: "earning" | "deduction";
  is_gratuity_base: boolean;
  is_wps_fixed: boolean;
  account: string | null;
  account_code: string;
  is_active: boolean;
};

export async function listSalaryComponents(entityId?: string | null): Promise<SalaryComponent[]> {
  const params = new URLSearchParams({ limit: "200", ordering: "code" });
  if (entityId) params.set("entity", entityId);
  const res = await apiFetch(`/salary-components/?${params.toString()}`);
  if (!res.ok) throw new Error(`Failed to load salary components (${res.status})`);
  return ((await res.json()) as Paginated<SalaryComponent>).results;
}

export async function createSalaryComponent(payload: {
  entity: string;
  code: string;
  name: string;
  component_type: string;
  is_gratuity_base: boolean;
  is_wps_fixed: boolean;
  account: string;
}): Promise<SalaryComponent> {
  const res = await apiFetch("/salary-components/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await detail(res, "Could not save this component."));
  return (await res.json()) as SalaryComponent;
}

export type EmployeeSalary = {
  id: string;
  employee: string;
  component: string;
  component_code: string;
  component_name: string;
  component_type: "earning" | "deduction";
  amount: string;
  effective_from: string;
  effective_to: string | null;
};

export async function listEmployeeSalaries(employeeId: string): Promise<EmployeeSalary[]> {
  const res = await apiFetch(`/employee-salaries/?employee=${employeeId}&limit=100`);
  if (!res.ok) throw new Error(`Failed to load salary structure (${res.status})`);
  return ((await res.json()) as Paginated<EmployeeSalary>).results;
}

export async function createEmployeeSalary(payload: {
  employee: string;
  component: string;
  amount: string;
  effective_from: string;
  effective_to: string | null;
}): Promise<EmployeeSalary> {
  const res = await apiFetch("/employee-salaries/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await detail(res, "Could not save this salary row."));
  return (await res.json()) as EmployeeSalary;
}

export type Employee = {
  id: string;
  entity: string;
  code: string;
  name: string;
  driver: string | null;
  driver_code: string;
  emirates_id: string;
  passport_no: string;
  nationality: string;
  join_date: string;
  designation: string;
  department: string | null;
  department_name: string;
  branch: string | null;
  mol_personal_no: string;
  work_permit_no: string;
  pay_method: "wps" | "bank" | "cash";
  bank_routing_code: string;
  iban: string;
  payable_account: string;
  payable_account_code: string;
  status: "active" | "on_leave" | "left";
  left_date: string | null;
  salary: EmployeeSalary[];
};

export async function listEmployees(entityId?: string | null): Promise<Employee[]> {
  const params = new URLSearchParams({ limit: "500", ordering: "code" });
  if (entityId) params.set("entity", entityId);
  const res = await apiFetch(`/employees/?${params.toString()}`);
  if (!res.ok) throw new Error(`Failed to load employees (${res.status})`);
  return ((await res.json()) as Paginated<Employee>).results;
}

export type PayslipLine = {
  id: string;
  component: string;
  component_code: string;
  component_type: "earning" | "deduction";
  amount: string;
};

export type Payslip = {
  id: string;
  run: string;
  employee: string;
  employee_code: string;
  employee_name: string;
  working_days: string;
  lop_days: string;
  gross_earnings: string;
  total_deductions: string;
  advance_recovery: string;
  net_pay: string;
  status: "draft" | "finalised" | "paid";
  lines: PayslipLine[];
};

export type Run = {
  id: string;
  entity: string;
  period: string | null;
  salary_month: string;
  run_date: string;
  gross_total: string;
  deduction_total: string;
  net_total: string;
  status: "draft" | "approved" | "posted" | "paid";
  journal_entry: string | null;
  payment_entry: string | null;
  approved_by: string | null;
  payslips: Payslip[];
};

export async function listRuns(entityId?: string | null): Promise<Run[]> {
  const params = new URLSearchParams({ limit: "100", ordering: "-salary_month" });
  if (entityId) params.set("entity", entityId);
  const res = await apiFetch(`/payroll-runs/?${params.toString()}`);
  if (!res.ok) throw new Error(`Failed to load payroll runs (${res.status})`);
  return ((await res.json()) as Paginated<Run>).results;
}

export async function createRun(payload: {
  entity: string;
  salary_month: string;
  run_date: string;
}): Promise<Run> {
  const res = await apiFetch("/payroll-runs/", { method: "POST", body: JSON.stringify(payload) });
  if (!res.ok) throw new Error(await detail(res, "Could not create this run."));
  return (await res.json()) as Run;
}

export async function buildRun(id: string): Promise<Run> {
  const res = await apiFetch(`/payroll-runs/${id}/build/`, {
    method: "POST",
    body: JSON.stringify({}),
  });
  if (!res.ok) throw new Error(await detail(res, "Could not build this run."));
  return (await res.json()) as Run;
}

export async function postRun(id: string): Promise<Run> {
  const res = await apiFetch(`/payroll-runs/${id}/post/`, {
    method: "POST",
    body: JSON.stringify({}),
  });
  if (!res.ok) throw new Error(await detail(res, "Could not post this run."));
  return (await res.json()) as Run;
}

export async function payRun(id: string, bankAccountId: string): Promise<Run> {
  const res = await apiFetch(`/payroll-runs/${id}/pay/`, {
    method: "POST",
    body: JSON.stringify({ bank_account: bankAccountId }),
  });
  if (!res.ok) throw new Error(await detail(res, "Could not pay this run."));
  return (await res.json()) as Run;
}

export type Advance = {
  id: string;
  entity: string;
  employee: string;
  employee_code: string;
  employee_name: string;
  advance_date: string;
  amount: string;
  installments: number;
  installment_amount: string;
  recovered_amount: string;
  balance: string;
  advance_account: string;
  bank_account: string | null;
  journal_entry: string | null;
  status: "open" | "recovering" | "cleared";
};

export async function listAdvances(entityId?: string | null): Promise<Advance[]> {
  const params = new URLSearchParams({ limit: "200", ordering: "-advance_date" });
  if (entityId) params.set("entity", entityId);
  const res = await apiFetch(`/payroll-advances/?${params.toString()}`);
  if (!res.ok) throw new Error(`Failed to load advances (${res.status})`);
  return ((await res.json()) as Paginated<Advance>).results;
}

export async function createAdvance(payload: {
  entity: string;
  employee: string;
  advance_date: string;
  amount: string;
  installments: number;
  installment_amount: string;
  advance_account: string;
  bank_account: string;
}): Promise<Advance> {
  const res = await apiFetch("/payroll-advances/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await detail(res, "Could not create this advance."));
  return (await res.json()) as Advance;
}

export async function payAdvance(id: string): Promise<Advance> {
  const res = await apiFetch(`/payroll-advances/${id}/pay/`, {
    method: "POST",
    body: JSON.stringify({}),
  });
  if (!res.ok) throw new Error(await detail(res, "Could not pay this advance."));
  return (await res.json()) as Advance;
}
