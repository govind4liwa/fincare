# ERD — `fleet`, `drivers`, `bookings` & `platforms` (Operations & Profitability)

**Project:** FinCare · **Phase:** 1.B (operational) · **Status:** Draft for review
**Scope:** the transport/limousine operational layer — vehicles, drivers, trips,
ride-hailing platforms — and the per-vehicle / per-driver / per-platform
profitability that the group needs. These apps generate **source documents and
analytic dimensions**; all money still posts **through** the ledger engine
(`02-erd-ledger-vouchers.md`).
**Depends on:** `core`, `tenants`, `accounts`, `ledger`, `vouchers`, `ar`, `ap`.

Conventions (doc 01): UUID `id`; audit mixin; soft delete where noted;
money = `numeric(18,2)`; rate/qty = `numeric(18,6)`; every row carries
`entity_id`. Audit/soft-delete columns omitted from grids.

> These apply primarily to category band 1 (Transport) and band 7 (Car Rental),
> but the design is generic. The profitability dimensions (`vehicle_id`,
> `driver_id`, `platform_id`) are the same nullable FKs already on
> `ledger_journal_line` (doc 02) — that is where profitability is actually
> measured.

---

## App: `fleet` (vehicles)

### `fleet_vehicle`

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| entity_id | uuid | no | FK → tenants_entity | owning entity |
| code | varchar(24) | no | | internal fleet no; unique within entity |
| plate_no | varchar(16) | no | IX | RTA plate |
| emirate | varchar(32) | no | | registration emirate |
| make | varchar(64) | yes | | |
| model | varchar(64) | yes | | |
| model_year | smallint | yes | | |
| chassis_no | varchar(32) | yes | | VIN |
| ownership_type | varchar(12) | no | | owned / financed / leased / rented |
| purchase_date | date | yes | | |
| purchase_cost | numeric(18,2) | yes | | capitalised cost |
| asset_account_id | uuid | yes | FK → accounts_account | 100-150 Vehicle cost account |
| accum_dep_account_id | uuid | yes | FK → accounts_account | accumulated depreciation |
| dep_method | varchar(12) | yes | | straight_line / reducing_balance |
| dep_useful_life_months | smallint | yes | | |
| residual_value | numeric(18,2) | yes | | |
| current_driver_id | uuid | yes | FK → drivers_driver | active assignment |
| status | varchar(12) | no | IX | active / idle / maintenance / accident / sold |
| is_active | boolean | no | | |

> Unique: (`entity_id`, `code`) and (`entity_id`, `plate_no`).

### `fleet_vehicle_document`

Tracks Mulkiya, insurance, permits — with expiry for renewal alerts.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| vehicle_id | uuid | no | FK → fleet_vehicle | |
| doc_type | varchar(24) | no | | mulkiya / insurance / permit / salik_tag |
| number | varchar(64) | yes | | |
| issue_date | date | yes | | |
| expiry_date | date | yes | IX | drives renewal reminders |
| cost | numeric(18,2) | yes | | renewal cost (posts via expense voucher) |
| attachment_id | uuid | yes | FK → core_attachment | scan |

### `fleet_vehicle_loan`

Finance/EMI tracking for financed vehicles.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| vehicle_id | uuid | no | FK → fleet_vehicle | |
| lender | varchar(128) | no | | bank / finance co |
| principal | numeric(18,2) | no | | financed amount |
| down_payment | numeric(18,2) | yes | | |
| interest_rate | numeric(6,3) | yes | | flat/reducing %, config |
| tenor_months | smallint | no | | |
| emi_amount | numeric(18,2) | no | | monthly instalment |
| start_date | date | no | | |
| loan_account_id | uuid | no | FK → accounts_account | 200-220 Vehicle Loan Payable |
| interest_account_id | uuid | no | FK → accounts_account | 700-710 Loan Interest Expense |
| is_active | boolean | no | | |

> **EMI posting** (CLAUDE.md §4): DR Vehicle Loan Payable + DR Loan Interest
> Expense / CR Bank — generated as a payment voucher each period.

### `fleet_depreciation_run`

Periodic depreciation batch; posts DR Depreciation Expense / CR Accumulated
Depreciation per vehicle (with `vehicle_id` dim).

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| entity_id | uuid | no | FK → tenants_entity | |
| period_id | uuid | no | FK → ledger_accounting_period | |
| run_date | date | no | | |
| total_amount | numeric(18,2) | no | | sum across vehicles |
| journal_entry_id | uuid | yes | FK → ledger_journal_entry | the posted depreciation JE |
| status | varchar(12) | no | | draft / posted |

---

## App: `drivers`

### `drivers_driver`

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| entity_id | uuid | no | FK → tenants_entity | |
| code | varchar(24) | no | | unique within entity |
| name | varchar(255) | no | | |
| nationality | varchar(64) | yes | | |
| passport_no | varchar(32) | yes | | |
| emirates_id | varchar(32) | yes | | |
| eid_expiry | date | yes | IX | renewal alert |
| visa_expiry | date | yes | IX | renewal alert |
| license_no | varchar(32) | yes | | |
| license_expiry | date | yes | IX | |
| health_insurance_expiry | date | yes | | Daman / DHA |
| join_date | date | yes | | |
| pay_type | varchar(12) | no | | salary / commission / hybrid |
| basic_salary | numeric(18,2) | yes | | |
| commission_pct | numeric(6,3) | yes | | share of net trip revenue |
| payable_account_id | uuid | no | FK → accounts_account | driver payout liability |
| advance_account_id | uuid | yes | FK → accounts_account | advances receivable from driver |
| status | varchar(12) | no | IX | active / on_leave / left |
| is_active | boolean | no | | |

> Unique: (`entity_id`, `code`).

### `drivers_driver_document`

Same shape as `fleet_vehicle_document` (visa, EID, licence, contract, Daman).

### `drivers_advance`

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| entity_id | uuid | no | FK → tenants_entity | |
| driver_id | uuid | no | FK → drivers_driver | |
| advance_date | date | no | | |
| amount | numeric(18,2) | no | | |
| recovered_amount | numeric(18,2) | no | | recovered via settlements |
| balance | numeric(18,2) | no | | outstanding |
| voucher_id | uuid | yes | FK → vouchers_voucher | the payment voucher that paid it |
| status | varchar(12) | no | | open / recovering / cleared |

### `drivers_settlement`

Periodic driver payout: gross earnings − commission split − deductions
(advances, Salik recovery, fines) = net payable. Posts the payout JE.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| entity_id | uuid | no | FK → tenants_entity | |
| driver_id | uuid | no | FK → drivers_driver | |
| period_start | date | no | | |
| period_end | date | no | | |
| gross_earnings | numeric(18,2) | no | | from trips/platform earnings |
| commission_amount | numeric(18,2) | no | | driver's share (if commission) |
| salary_amount | numeric(18,2) | no | | if salaried |
| advance_recovery | numeric(18,2) | no | | applied to drivers_advance |
| salik_recovery | numeric(18,2) | no | | tolls recharged to driver |
| fine_recovery | numeric(18,2) | no | | traffic/RTA fines recovered |
| other_deductions | numeric(18,2) | no | | |
| net_payable | numeric(18,2) | no | | computed |
| journal_entry_id | uuid | yes | FK → ledger_journal_entry | posted settlement |
| status | varchar(12) | no | IX | draft / approved / posted / paid |

> Unique: (`entity_id`, `driver_id`, `period_start`, `period_end`).

---

## App: `platforms` (ride-hailing & aggregators)

### `platforms_platform`

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| entity_id | uuid | no | FK → tenants_entity | |
| name | varchar(64) | no | | Uber / Yango / Bolt / Careem / … |
| commission_pct | numeric(6,3) | yes | | platform's cut, config |
| settlement_cycle | varchar(12) | yes | | weekly / daily / monthly |
| revenue_account_id | uuid | no | FK → accounts_account | 400-410 platform earnings |
| commission_account_id | uuid | no | FK → accounts_account | 500-520 platform commission |
| clearing_account_id | uuid | no | FK → accounts_account | platform receivable / clearing |
| is_active | boolean | no | | |

### `platforms_settlement`

Reconciles a platform's statement (gross, commission, adjustments, net paid)
against the clearing account; surfaces variances.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| entity_id | uuid | no | FK → tenants_entity | |
| platform_id | uuid | no | FK → platforms_platform | |
| period_start | date | no | | |
| period_end | date | no | | |
| gross_earnings | numeric(18,2) | no | | per statement |
| commission | numeric(18,2) | no | | |
| adjustments | numeric(18,2) | no | | tips, incentives, fees |
| net_received | numeric(18,2) | no | | amount paid to bank |
| variance | numeric(18,2) | no | | statement vs. recorded trips |
| journal_entry_id | uuid | yes | FK → ledger_journal_entry | |
| status | varchar(12) | no | IX | draft / reconciled / posted |

> Unique: (`entity_id`, `platform_id`, `period_start`, `period_end`).

### `platforms_earning_import`

Raw imported statement lines (CSV/API) staged before reconciliation.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| settlement_id | uuid | yes | FK → platforms_settlement | once matched |
| platform_id | uuid | no | FK → platforms_platform | |
| trip_ref | varchar(64) | yes | | platform trip id |
| driver_ref | varchar(64) | yes | | platform driver id |
| earning_date | date | no | | |
| gross | numeric(18,2) | no | | |
| commission | numeric(18,2) | no | | |
| net | numeric(18,2) | no | | |
| matched | boolean | no | | reconciled to a trip? |

---

## App: `bookings` (trips & contracts)

### `bookings_trip`

The trip register — the operational grain that rolls up into revenue and
profitability.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| entity_id | uuid | no | FK → tenants_entity | |
| trip_date | date | no | IX | |
| trip_type | varchar(16) | no | | platform / personal / corporate / contract |
| vehicle_id | uuid | yes | FK → fleet_vehicle | |
| driver_id | uuid | yes | FK → drivers_driver | |
| platform_id | uuid | yes | FK → platforms_platform | null for personal/corporate |
| customer_id | uuid | yes | FK → ar_customer | corporate/contract trips |
| fare | numeric(18,2) | no | | gross fare |
| commission | numeric(18,2) | no | | platform commission on this trip |
| salik | numeric(18,2) | no | | tolls on the trip |
| tip | numeric(18,2) | no | | |
| distance_km | numeric(18,6) | yes | | |
| net_revenue | numeric(18,2) | no | | fare − commission |
| status | varchar(12) | no | IX | recorded / invoiced / settled |

> Platform trips are typically imported & aggregated; personal/corporate trips
> entered directly. Revenue is recognised by **periodic aggregate posting**
> (per platform/vehicle/driver), not one JE per trip — see flows below.

### `bookings_contract`

Monthly corporate/contract billing agreements.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| entity_id | uuid | no | FK → tenants_entity | |
| customer_id | uuid | no | FK → ar_customer | |
| vehicle_id | uuid | yes | FK → fleet_vehicle | assigned vehicle |
| driver_id | uuid | yes | FK → drivers_driver | assigned driver |
| contract_no | varchar(24) | no | | |
| start_date | date | no | | |
| end_date | date | yes | | |
| billing_cycle | varchar(12) | no | | monthly / weekly |
| monthly_amount | numeric(18,2) | no | | |
| tax_code_id | uuid | no | FK → accounts_tax_code | |
| status | varchar(12) | no | | active / suspended / ended |

> Contract billing generates an `ar_sales_invoice` each cycle (scheduled job).

---

## Key posting & reconciliation flows

```
TRIPS → REVENUE (periodic aggregate)
  group bookings_trip by platform/vehicle/driver for the period →
  JE: DR Platform Clearing (400-410 net)  CR Operating Revenue (per platform)
      DR Platform Commission (500-520)     (commission recognised)
  lines carry vehicle_id / driver_id / platform_id dims

PLATFORM SETTLEMENT
  platform pays net to bank → reconcile against clearing →
  JE: DR Bank  CR Platform Clearing ; variance → adjustment account

DRIVER SETTLEMENT
  gross − commission/salary − advances − salik − fines = net payable →
  JE: DR Driver Cost (500-530)  CR Driver Payable
      CR Driver Advance (recovery)  CR Salik/Fine Recovery (415 income)

VEHICLE EMI            DR Loan Payable + DR Interest  CR Bank
DEPRECIATION RUN       DR Depreciation Expense        CR Accumulated Depreciation
CORPORATE CONTRACT     scheduled ar_sales_invoice  →  DR AR / CR Revenue / CR Output VAT
```

---

## Profitability model (derived)

Per-vehicle / per-driver / per-platform / per-month profitability is **computed
from `ledger_journal_line`** filtered by the `vehicle_id` / `driver_id` /
`platform_id` dimensions — revenue (400) minus direct cost (500) minus allocated
overheads (600). No separate profitability ledger.

For dashboard performance, an **optional materialised snapshot**
(`reports_profit_snapshot`: entity, dim_type, dim_id, period, revenue, direct_cost,
overhead, net_profit) may be refreshed periodically — derived, never a source of
truth. This belongs to the `reports` app (next design doc).

```
profitability(dim) = Σ revenue lines(dim)  −  Σ direct-cost lines(dim)
                     −  Σ allocated overhead(dim)        [over period]
dim ∈ { vehicle, driver, platform, customer, branch, cost_center }
```

---

## Relationship summary

```
fleet_vehicle ──< fleet_vehicle_document
fleet_vehicle ──< fleet_vehicle_loan
fleet_vehicle ──< (current_driver) drivers_driver
fleet_depreciation_run ──(1:1)── ledger_journal_entry
drivers_driver ──< drivers_driver_document, drivers_advance, drivers_settlement
drivers_settlement ──(1:1)── ledger_journal_entry
platforms_platform ──< platforms_settlement ──< platforms_earning_import
platforms_settlement ──(1:1)── ledger_journal_entry
bookings_trip >── fleet_vehicle, drivers_driver, platforms_platform, ar_customer
bookings_contract >── ar_customer, fleet_vehicle, drivers_driver → ar_sales_invoice
ledger_journal_line >── (dims) fleet_vehicle, drivers_driver, platforms_platform
```

## Open decisions

1. **Trip granularity in GL:** periodic aggregate posting (shown, recommended —
   avoids millions of JEs) vs. one JE per trip. Default: aggregate; trips kept at
   detail in `bookings_trip` for analytics.
2. **Profit snapshot:** on-the-fly query (simple, always correct) vs. materialised
   `reports_profit_snapshot` (fast dashboards, needs refresh). Default: query
   first; add snapshot when volume demands.
3. **Driver commission base:** on gross fare vs. net of platform commission.
   Default: net of platform commission (confirm per driver contract).
4. **Overhead allocation to dims:** direct-only profitability vs. allocating 600
   overheads to vehicles/drivers by a driver. Default: direct contribution
   margin first; overhead allocation as a later reporting option.
