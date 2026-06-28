# Reporting Foundation — `reports`

**Project:** FinCare · **Phase:** 1 (foundation) · **Status:** Draft for review
**Scope:** the financial and management reporting layer — trial balance, the
three statements, cash flow, VAT summary, aging, profitability, management and
consolidated group reports, the audit-trail report, and Excel/PDF export.
**Depends on:** `core`, `tenants`, `accounts`, `ledger`, `ar`, `ap`, `tax`,
`fleet`, `drivers`, `platforms`, `audit`.

Conventions (doc 01): UUID `id`; audit mixin; money = `numeric(18,2)`; every
config/log row carries `entity_id` (nullable where group-scoped). Audit/soft-delete
columns omitted from grids.

---

## Design approach

**Reports are derived from the ledger, not stored as balances.** The general
ledger (`ledger_journal_line`) is the single source of truth; every statement is
a query over posted lines for an entity (or group) and period. On top of that:

1. A **balance engine** computes account balances and movements (the primitive
   every statement builds on).
2. **Statement templates** (config, data-driven) map the COA onto the layout of
   each statement, so presentation can change without code.
3. **Optional snapshots** (`balance_snapshot`, `profit_snapshot`) materialise
   period-end figures for fast dashboards — derived, never a source of truth.
4. **Report run / schedule** tables log generated outputs and drive scheduled MIS.

This keeps the books authoritative, supports both cash and accrual views
(doc 02 §Cash vs accrual), and makes new report variants cheap.

---

## Balance engine (`apps/reports/services/balances.py`)

```python
def account_balances(*, entity_ids, period, basis="accrual",
                     dims=None, as_of=None) -> list[AccountBalance]:
    """Opening, period movement, and closing per account, from posted lines.
       - entity_ids: one entity, or many for consolidation
       - basis: accrual (all lines) | cash (cash/bank-touching lines)
       - dims: optional filter (vehicle/driver/platform/cost_center/branch)
    """

def trial_balance(*, entity_ids, period, basis="accrual") -> TrialBalance
def ledger_detail(*, entity_id, account_id, date_from, date_to) -> list[Line]
```

`AccountBalance = (account, opening_debit, opening_credit, period_debit,
period_credit, closing_debit, closing_credit)`. Every statement is assembled from
these primitives + a statement template.

---

## Supporting tables

### `reports_statement_template`

Defines a statement's structure (P&L, Balance Sheet, Cash Flow, TB layout). Can be
group-shared (`entity_id` null) or entity-specific.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| entity_id | uuid | yes | FK → tenants_entity | null = group default template |
| code | varchar(16) | no | | PNL / BS / CF / TB |
| name | varchar(128) | no | | |
| is_active | boolean | no | | |

> Unique: (`entity_id`, `code`).

### `reports_statement_line`

The ordered, hierarchical lines of a template, mapped to COA segment ranges.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| template_id | uuid | no | FK → reports_statement_template | |
| line_no | smallint | no | | order |
| parent_id | uuid | yes | FK → reports_statement_line (self) | grouping tree |
| label | varchar(128) | no | | "Revenue", "Cost of Sales", … |
| line_type | varchar(16) | no | | header / range / subtotal / total / formula |
| main_from | char(3) | yes | | COA Main range start (e.g. "400") |
| main_to | char(3) | yes | | COA Main range end (e.g. "499") |
| sub_from | char(3) | yes | | optional finer Sub range |
| sub_to | char(3) | yes | | |
| sign | smallint | no | | +1 / −1 for presentation |
| formula | varchar(255) | yes | | for line_type=formula (refs other line_no) |
| indent | smallint | no | | display indent |
| is_bold | boolean | no | | |

> Because the COA is banded by nature (ADR-0004: 1xx asset … 7xx finance/tax),
> statement mapping is range-based and stable across entities/categories.

### `reports_balance_snapshot` (optional, performance)

Period-end balances per account; refreshed after close. Derived.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| entity_id | uuid | no | FK → tenants_entity | |
| period_id | uuid | no | FK → ledger_accounting_period | |
| account_id | uuid | no | FK → accounts_account | |
| opening_debit | numeric(18,2) | no | | |
| opening_credit | numeric(18,2) | no | | |
| period_debit | numeric(18,2) | no | | |
| period_credit | numeric(18,2) | no | | |
| closing_balance | numeric(18,2) | no | | signed by normal balance |

> Unique: (`entity_id`, `period_id`, `account_id`).

### `reports_profit_snapshot` (optional, from doc 04)

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| entity_id | uuid | no | FK → tenants_entity | |
| dim_type | varchar(16) | no | | vehicle / driver / platform / customer / branch / cost_center |
| dim_id | uuid | no | IX | the dimension row id |
| period_id | uuid | no | FK → ledger_accounting_period | |
| revenue | numeric(18,2) | no | | |
| direct_cost | numeric(18,2) | no | | |
| overhead | numeric(18,2) | no | | allocated (optional) |
| net_profit | numeric(18,2) | no | | |

> Unique: (`entity_id`, `dim_type`, `dim_id`, `period_id`).

### `reports_report_run`

Audit log of every generated report (who/what/when, and the produced file).

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| entity_scope | varchar(8) | no | | entity / group |
| entity_id | uuid | yes | FK → tenants_entity | null when group/consolidated |
| report_code | varchar(24) | no | IX | TB / GL / PNL / BS / CF / VAT / AR_AGE / … |
| params | jsonb | no | | period, basis, dims, filters |
| format | varchar(8) | no | | xlsx / pdf / json |
| file_ref | varchar(512) | yes | | storage key of output |
| status | varchar(12) | no | | queued / done / error |
| generated_at | timestamptz | yes | | |
| generated_by | uuid | yes | FK → users_user | |

### `reports_report_schedule`

Drives recurring MIS (e.g. monthly management pack) via Celery.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| name | varchar(128) | no | | |
| report_code | varchar(24) | no | | |
| entity_scope | varchar(8) | no | | entity / group |
| entity_id | uuid | yes | FK → tenants_entity | |
| params | jsonb | no | | |
| cron | varchar(32) | no | | schedule |
| format | varchar(8) | no | | |
| recipients | jsonb | yes | | emails |
| is_active | boolean | no | | |

---

## Report catalog

| Report | Code | Source | Key params | Notes |
|---|---|---|---|---|
| Trial Balance | TB | balance engine | entity(s), period, basis | opening/movement/closing; must net to zero |
| General Ledger | GL | ledger_journal_line | entity, account, date range | drill-down to entries |
| Profit & Loss | PNL | balances + PNL template | entity(s), period, basis, compare | period vs prior / budget |
| Balance Sheet | BS | balances + BS template | entity(s), as-of date | assets = liabilities + equity |
| Cash Flow | CF | balances + CF template | entity(s), period | indirect method (see below) |
| VAT Summary / 201 | VAT | tax_return + boxes | VAT group, period | per VAT group (ADR-0006) |
| Customer Aging | AR_AGE | ar open items | entity, as-of, buckets | current/30/60/90/120+ |
| Supplier Aging | AP_AGE | ap open items | entity, as-of, buckets | |
| Bank Reconciliation | BANK_REC | banking (later) | entity, bank account, date | book vs statement |
| Vehicle Profitability | PROF_VEH | profit by dim | entity, period | revenue − direct − overhead |
| Driver Profitability | PROF_DRV | profit by dim | entity, period | incl. settlements |
| Platform Earnings | PLAT_EARN | platforms + ledger | entity, platform, period | gross/commission/net |
| Monthly Management | MGMT | composite pack | entity(s), period | KPIs + statements bundle |
| Entity-wise Report | ENT | per-entity statements | period | one entity |
| Consolidated Group | GROUP | multi-entity + elimination | group, period | see consolidation |
| Audit Trail | AUDIT | audit app log | entity, user, date, object | who changed/posted what |

All tabular reports export to **Excel (openpyxl)** and **PDF (WeasyPrint)**
(stack §Reporting). Dashboards are served via the API and the Next.js frontend.

---

## Consolidation & intercompany elimination

- **Entity scope** runs a report for one entity. **Group scope** runs across the
  `parent_entity_id` consolidation tree (doc 01) by passing multiple `entity_ids`
  to the balance engine.
- **Intercompany elimination:** accounts flagged as intercompany (the due-to /
  due-from accounts in `tenants_intercompany_map`) are netted out on
  consolidation so group figures exclude internal trading. Same-VAT-group
  intra-group supplies are already out-of-scope for VAT (ADR-0006).
- Currency: all entities default to AED; if a future entity reports in another
  currency, consolidation translates closing balances at the period rate
  (`core_exchange_rate`).

---

## Cash flow method

Indirect method, derived: start from net profit (PNL), adjust for non-cash items
(depreciation, provisions) and movements in working capital (AR, AP, inventory,
tax), then split into Operating / Investing / Financing using a CF statement
template whose lines map COA ranges to activity buckets. A direct-method variant
can be added later from cash/bank line analysis.

---

## Performance notes

- Default: compute live from posted lines (always correct). Indexes on
  (`entity_id`, `entry_date`) and (`account_id`) on `ledger_journal_line` support
  this.
- For large datasets / dashboards: refresh `balance_snapshot` and
  `profit_snapshot` after period close; reports prefer snapshots when present and
  the period is closed, else compute live.
- Heavy/scheduled exports run as Celery jobs and land in `reports_report_run`.

---

## Relationship summary

```
ledger_journal_line ──(query)──► balance engine ──► statements (TB/PNL/BS/CF)
reports_statement_template ──< reports_statement_line  (COA range mapping)
reports_balance_snapshot  >── tenants_entity, ledger_accounting_period, accounts_account
reports_profit_snapshot   >── tenants_entity, ledger_accounting_period (dim_type/dim_id)
tax_return ──► VAT summary ;  ar/ap open items ──► aging
reports_report_run / reports_report_schedule  ──► xlsx / pdf outputs
tenants_intercompany_map ──► consolidation elimination
```

## Open decisions

1. **Snapshots now or later:** ship live-compute only for Phase 1 (simplest) and
   add snapshots when volume demands. Default: live first, snapshot tables defined
   but populated later.
2. **Cash flow method:** indirect (shown, recommended) vs. direct. Default:
   indirect; direct as a later add-on.
3. **Statement templates seeded vs. user-editable:** seed standard P&L/BS/CF/TB
   templates; allow admin editing later. Default: seed first.
4. **Budget data:** PNL "vs budget" needs a budget store (`reports_budget`),
   deferred to a later phase unless required now.
