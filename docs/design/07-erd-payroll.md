# ERD — `payroll` (HR Payroll, WPS, Gratuity)

**Project:** FinCare · **Phase:** 1.B (operational) · **Status:** Draft for review
**Scope:** monthly payroll for all employees (admin staff and salaried drivers) —
salary structures, payroll runs and payslips, UAE **WPS** (Wage Protection
System) SIF generation, end-of-service **gratuity** (EOSB), leave accrual & leave
salary, and salary advances. All money posts **through** the ledger engine
(ADR-0007).
**Depends on:** `core`, `tenants`, `accounts`, `ledger`, `vouchers`, `banking`,
and (optionally) `drivers`.

Conventions (doc 01): UUID `id`; audit mixin; soft delete where noted;
money = `numeric(18,2)`; every row carries `entity_id`. UAE statutory figures
(gratuity day-rates, WPS routing) are **configuration**, never hardcoded
(CLAUDE.md §4.8, §9). Audit/soft-delete columns omitted from grids.

> **Driver overlap:** a commission driver's payout runs through
> `drivers_settlement` (doc 04); a **salaried** employee (incl. a salaried driver)
> runs through payroll here. `payroll_employee.driver_id` links the two so a
> person is never paid twice — see §Driver/payroll boundary.

---

## App: `payroll`

### `payroll_employee`

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| entity_id | uuid | no | FK → tenants_entity | employing entity |
| code | varchar(24) | no | | unique within entity |
| name | varchar(255) | no | | |
| driver_id | uuid | yes | FK → drivers_driver | set if this employee is also a fleet driver |
| emirates_id | varchar(32) | yes | | |
| passport_no | varchar(32) | yes | | |
| nationality | varchar(64) | yes | | |
| join_date | date | no | | drives gratuity service period |
| designation | varchar(128) | yes | | |
| department_id | uuid | yes | FK → tenants_department | |
| branch_id | uuid | yes | FK → tenants_branch | |
| mol_personal_no | varchar(32) | yes | | MOHRE labour card / personal no (WPS) |
| work_permit_no | varchar(32) | yes | | |
| pay_method | varchar(12) | no | | wps / bank / cash |
| bank_routing_code | varchar(16) | yes | | WPS agent/bank routing |
| iban | varchar(34) | yes | | salary account |
| payable_account_id | uuid | no | FK → accounts_account | 240 Salaries Payable / WPS clearing |
| status | varchar(12) | no | IX | active / on_leave / left |
| left_date | date | yes | | for final settlement / gratuity |

> Unique: (`entity_id`, `code`).

### `payroll_salary_component`

Master of earning/deduction components (config).

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| entity_id | uuid | yes | FK → tenants_entity | null = group default |
| code | varchar(24) | no | | BASIC, HRA, TRANSPORT, OTHER, … |
| name | varchar(128) | no | | |
| component_type | varchar(12) | no | | earning / deduction |
| is_gratuity_base | boolean | no | | counts toward EOSB (typically only BASIC) |
| is_wps_fixed | boolean | no | | fixed (vs variable) for SIF split |
| expense_account_id | uuid | yes | FK → accounts_account | 530/610 salary expense for earnings |
| is_active | boolean | no | | |

> Unique: (`entity_id`, `code`).

### `payroll_employee_salary`

Effective-dated salary structure per employee (one row per component version).

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| employee_id | uuid | no | FK → payroll_employee | |
| component_id | uuid | no | FK → payroll_salary_component | |
| amount | numeric(18,2) | no | | monthly amount |
| effective_from | date | no | | |
| effective_to | date | yes | | null = current |

> Current structure = rows where `effective_to` is null / covers the run period.

### `payroll_run`

Monthly payroll batch per entity + period.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| entity_id | uuid | no | FK → tenants_entity | |
| period_id | uuid | no | FK → ledger_accounting_period | |
| salary_month | char(7) | no | | "2026-06" |
| run_date | date | no | | |
| gross_total | numeric(18,2) | no | | sum earnings |
| deduction_total | numeric(18,2) | no | | sum deductions |
| net_total | numeric(18,2) | no | | payable |
| status | varchar(12) | no | IX | draft / approved / posted / paid |
| journal_entry_id | uuid | yes | FK → ledger_journal_entry | salary accrual posting |
| approved_by | uuid | yes | FK → users_user | |

> Unique: (`entity_id`, `salary_month`).

### `payroll_payslip`

One per employee per run.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| run_id | uuid | no | FK → payroll_run | |
| employee_id | uuid | no | FK → payroll_employee | |
| working_days | numeric(6,2) | no | | days in period |
| lop_days | numeric(6,2) | no | | loss-of-pay / unpaid |
| gross_earnings | numeric(18,2) | no | | |
| total_deductions | numeric(18,2) | no | | incl. advance recovery |
| advance_recovery | numeric(18,2) | no | | applied to payroll_advance |
| net_pay | numeric(18,2) | no | | |
| status | varchar(12) | no | | draft / finalised / paid |

> Unique: (`run_id`, `employee_id`).

### `payroll_payslip_line`

Component breakdown of a payslip.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| payslip_id | uuid | no | FK → payroll_payslip | |
| component_id | uuid | no | FK → payroll_salary_component | |
| component_type | varchar(12) | no | | earning / deduction |
| amount | numeric(18,2) | no | | |

---

## WPS (Wage Protection System) — SIF generation

The SIF (Salary Information File) is generated per run for employees with
`pay_method = wps`. It is a Salary Control Record (employer header) plus one
Employee Detail Record per employee.

### `payroll_wps_batch` (Salary Control Record)

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| run_id | uuid | no | FK → payroll_run | |
| employer_eid | varchar(32) | no | | MOHRE establishment ID |
| employer_bank_routing | varchar(16) | no | | employer bank routing code |
| salary_month | char(7) | no | | |
| total_records | integer | no | | EDR count |
| total_salary | numeric(18,2) | no | | sum of fixed + variable |
| fixed_total | numeric(18,2) | no | | |
| variable_total | numeric(18,2) | no | | |
| sif_file_ref | varchar(512) | yes | | generated SIF file |
| status | varchar(12) | no | | generated / submitted |
| generated_at | timestamptz | yes | | |

### `payroll_wps_record` (Employee Detail Record)

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| batch_id | uuid | no | FK → payroll_wps_batch | |
| employee_id | uuid | no | FK → payroll_employee | |
| mol_personal_no | varchar(32) | no | | labour card / personal no |
| bank_routing_code | varchar(16) | no | | employee bank routing |
| iban | varchar(34) | no | | employee salary account |
| pay_start_date | date | no | | |
| pay_end_date | date | no | | |
| working_days | numeric(6,2) | no | | |
| fixed_amount | numeric(18,2) | no | | sum of WPS-fixed components |
| variable_amount | numeric(18,2) | no | | variable components |
| leave_days | numeric(6,2) | yes | | |
| notes | varchar(255) | yes | | |

> `total_salary` and `total_records` on the batch must reconcile to the sum of
> records; the SIF export validates this before producing the file.

---

## Gratuity (End-of-Service Benefit)

### `payroll_gratuity`

Accrual and final settlement of EOSB. Day-rate and caps are config (UAE Labour Law
defaults: ~21 days of basic per year for the first 5 years, ~30 days/year
thereafter, capped at 2 years' wage — held in `settings`, not hardcoded).

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| entity_id | uuid | no | FK → tenants_entity | |
| employee_id | uuid | no | FK → payroll_employee | |
| as_of_date | date | no | | accrual or settlement date |
| service_years | numeric(8,4) | no | | from join_date |
| basis_salary | numeric(18,2) | no | | gratuity-base (usually basic) |
| eligible_days | numeric(8,2) | no | | computed from rule/config |
| amount | numeric(18,2) | no | | accrued / payable |
| type | varchar(12) | no | | accrual / settlement |
| provision_account_id | uuid | no | FK → accounts_account | 240 Gratuity Provision |
| expense_account_id | uuid | no | FK → accounts_account | 610 Gratuity Expense |
| journal_entry_id | uuid | yes | FK → ledger_journal_entry | |
| status | varchar(12) | no | | draft / posted / settled |

> Periodic **accrual**: DR Gratuity Expense / CR Gratuity Provision. **Settlement**
> on leaving: DR Gratuity Provision / CR Bank (final settlement), with any
> shortfall to expense.

---

## Leave & leave salary

### `payroll_leave`

Leave balance and leave-salary accrual per employee.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| entity_id | uuid | no | FK → tenants_entity | |
| employee_id | uuid | no | FK → payroll_employee | |
| leave_type | varchar(16) | no | | annual / sick / unpaid |
| entitled_days | numeric(6,2) | no | | per period (e.g. 30/yr annual) |
| taken_days | numeric(6,2) | no | | |
| balance_days | numeric(6,2) | no | | |
| accrued_amount | numeric(18,2) | no | | leave-salary provision |
| provision_account_id | uuid | yes | FK → accounts_account | 240 Leave Provision |
| as_of_date | date | no | | |

> Leave-salary accrual: DR Leave Salary Expense / CR Leave Provision; payment on
> leave: DR Leave Provision / CR Bank.

---

## Salary advances / loans

### `payroll_advance`

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| entity_id | uuid | no | FK → tenants_entity | |
| employee_id | uuid | no | FK → payroll_employee | |
| advance_date | date | no | | |
| amount | numeric(18,2) | no | | |
| installments | smallint | yes | | recovery schedule |
| recovered_amount | numeric(18,2) | no | | recovered via payslips |
| balance | numeric(18,2) | no | | |
| advance_account_id | uuid | no | FK → accounts_account | Staff Advances (120) |
| voucher_id | uuid | yes | FK → vouchers_voucher | the payment voucher |
| status | varchar(12) | no | | open / recovering / cleared |

---

## Posting flows

```
PAYROLL RUN (accrual)      DR Salary Expense (per component → 530/610)
                           CR Staff Advance (advance recovery)
                           CR Other Deductions
                           CR Salaries Payable / WPS Clearing (net)
SALARY PAYMENT (WPS)       DR Salaries Payable / WPS Clearing   CR Bank
GRATUITY ACCRUAL           DR Gratuity Expense                  CR Gratuity Provision
GRATUITY SETTLEMENT        DR Gratuity Provision                CR Bank
LEAVE SALARY ACCRUAL       DR Leave Salary Expense              CR Leave Provision
SALARY ADVANCE PAID        DR Staff Advance                     CR Bank   (payment voucher)
```

All postings go through `ledger.services.posting.post_journal_entry` (ADR-0007);
the run produces one accrual entry, the WPS payment a separate payment entry.

---

## Driver / payroll boundary

- **Salaried driver:** salary via `payroll` (employee linked by `driver_id`);
  trip commission/recoveries via `drivers_settlement` for the operational view,
  but the *cash* salary is paid once, through payroll.
- **Pure commission driver:** paid only via `drivers_settlement`; not in a
  payroll run.
- The link prevents double-counting cost: salary hits `530 Driver Cost` once;
  settlement records commission/recoveries without re-paying basic salary.

> **Open decision (PR-1):** confirm whether salaried drivers' WPS salary is the
> single source of cash pay (recommended) and `drivers_settlement` is
> profitability-only for them. Default: yes.

---

## Relationship summary

```
payroll_employee ──< payroll_employee_salary >── payroll_salary_component
payroll_employee ──(optional)── drivers_driver
payroll_run ──< payroll_payslip ──< payroll_payslip_line >── payroll_salary_component
payroll_run ──< payroll_wps_batch ──< payroll_wps_record >── payroll_employee
payroll_employee ──< payroll_gratuity, payroll_leave, payroll_advance
payroll_run / payroll_gratuity / payroll_advance ──(1:1 at post)── ledger_journal_entry
payroll_advance ──(recovery)── payroll_payslip
```

## Open decisions

1. **PR-1 — Salaried-driver pay source:** WPS payroll is the single cash pay,
   settlement is profitability-only (recommended). Default: yes.
2. **Gratuity accrual cadence:** monthly accrual (smooths P&L, recommended) vs.
   recognise only on leaving. Default: monthly accrual.
3. **SIF format versioning:** store the SIF layout/version as config so MOHRE
   format changes don't need code edits. Default: config-driven layout.
4. **Leave salary:** accrue monthly (recommended) vs. expense when taken.
   Default: accrue monthly.
