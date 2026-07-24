# FinCare — Phase 1 Build Roadmap

**Purpose:** an execution plan that maps the design library (ADRs 0004–0007,
design docs 01–07) to **ordered Claude Code sessions**, each with a clear scope,
the design references to load, a ready-to-paste prompt, and a Definition-of-Done
test gate. Build strictly in dependency order — earlier phases are imported by
later ones.

**How to use:** one phase ≈ one or more Claude Code sessions on its own feature
branch. Start each session in the repo so `CLAUDE.md` loads, paste the phase
prompt, review the diff, run `make lint && make test`, then open a PR. Do not mark
a phase done until its test gate passes (CLAUDE.md §7).

---

## Guiding principles (apply to every phase)

1. **Architecture is fixed; code follows the docs.** Each phase implements the
   models exactly as specified in its design doc; deviations need an ADR.
2. **Everything posts through the engine.** No app writes GL rows except via
   `apps/ledger/services/posting.py` (ADR-0007).
3. **Money = `Decimal`, AED default; UAE values are config, not literals.**
4. **Test gate is mandatory.** Every posting path ships a unit test proving
   `debit == credit`. `make lint && make test` green before PR.
5. **Small diffs.** One app (or one concern) per session; models → services →
   API → tests, in that order.

---

## Dependency graph

```
core
 ├─ users ─────────────┐
 ├─ settings           │
 ├─ audit ◄── users     │
 └─ tenants ◄── users ──┘         (band/category, VAT group, RLS)
        └─ accounts                (COA, coding service, tax codes, seed)
              └─ ledger  ★          (periods + posting engine)
                   ├─ vouchers
                   ├─ ar ── tax ◄── ap
                   ├─ ap
                   ├─ banking ── cashbook
                   ├─ fleet, drivers ── bookings ◄── platforms
                   └─ payroll
                         └─ reports ── exports
                               └─ integrations
                                     └─ frontend (Next.js, Phase 1.6)
```

★ `ledger` is the keystone — everything monetary depends on it.

---

## Phase 0 — Bootstrap & CI verification

**Goal:** confirm the already-scaffolded repo runs and CI is green before adding
domain code.

**Builds:** nothing new — verify `docker compose up`, Postgres/Redis, `make lint`,
`make test`, drf-spectacular schema endpoint, settings split.

**Design refs:** ADR-0003 (settings split), README, DEVELOPMENT.md.

**Prompt:**
```
Verify the FinCare scaffold runs end-to-end: docker compose up brings up Postgres,
Redis and web; make lint and make test pass; the /api/schema/ endpoint serves.
Fix any setup breakage. Do not add domain models yet.
```

**Test gate:** `docker compose ps` healthy · `make lint` clean · `make test`
green · Swagger loads.

---

## Phase 1 — `apps.core`

**Goal:** shared primitives every app depends on.

**Builds:** `BaseModel` (UUID pk, audit fields, soft-delete manager), `Currency`,
`ExchangeRate`, `NumberSequence` (gap-safe, entity+series), `Attachment`.

**Design refs:** doc 01 §core.

**Prompt:**
```
Implement apps.core per docs/design/01-erd-core-tenants-accounts.md (core section):
BaseModel abstract (UUID pk, created_at/updated_at/created_by/updated_by, soft
delete + manager excluding deleted), Currency, ExchangeRate, NumberSequence
(gap-safe allocation under SELECT … FOR UPDATE), Attachment (generic FK). Add
unit tests for the soft-delete manager and concurrent-safe sequence allocation.
Register in LOCAL_APPS. Run make lint && make test.
```

**Test gate:** soft-delete manager hides deleted rows · sequence never duplicates
under concurrency · migrations apply clean.

---

## Phase 2 — `apps.users` (auth, RBAC, JWT)

**Goal:** authentication and role-based permissions used by every endpoint.

**Builds:** custom `User`, roles/permissions (RBAC), JWT (SimpleJWT) login/refresh,
permission base classes, `created_by`/`updated_by` wiring.

**Design refs:** CLAUDE.md §6 (permissions), §11 (security).

**Prompt:**
```
Implement apps.users: custom User model, role-based permission groups, JWT auth
(djangorestframework-simplejwt) with login/refresh endpoints, and reusable DRF
permission classes (view/add/post/approve per resource). Wire created_by/updated_by
population. Tests for auth flow and a permission-denied path. make lint && make test.
```

**Test gate:** JWT login/refresh works · unauthorised request blocked · role
without `post` permission cannot post.

---

## Phase 3 — `apps.tenants` (+ RLS) & `apps.settings`

**Goal:** the multi-entity backbone, category/band, VAT group, and per-entity
configuration; PostgreSQL Row-Level Security.

**Builds:** `BusinessCategory` (with `band`), `VatGroup`, `Entity` (numeric_code,
category_id, vat_group_id, corporate_tax_trn), `Branch`, `CostCenter`,
`Department`, `IntercompanyMap`; RLS policies + per-request tenant context
middleware; `settings` (fiscal year, VAT config, numbering series, feature flags).

**Design refs:** doc 01 §tenants, ADR-0004 (band), ADR-0005 (category), ADR-0006
(VAT group). **Write an ADR for the RLS approach.**

**Prompt:**
```
Implement apps.tenants per docs/design/01 (tenants section) and ADR-0004/0005/0006:
BusinessCategory(band), VatGroup(trn), Entity(numeric_code 3-digit, category_id,
vat_group_id, corporate_tax_trn), Branch, CostCenter, Department, IntercompanyMap.
Add PostgreSQL RLS: a per-request tenant-context middleware setting a session GUC
and a migration enabling RLS policies on tenant-scoped tables. Implement apps.settings
(fiscal year, VAT config, numbering series, feature flags). Write docs/adr/0008-rls-tenant-isolation.md.
Tests proving cross-entity rows are invisible without the right context. make lint && make test.
```

**Test gate:** entity in category sets band correctly · cross-entity read blocked
by RLS without context · VAT TRN resolves from group · CT number per entity ·
RLS ADR committed.

---

## Phase 4 — `apps.audit`

**Goal:** tamper-evident audit logging before any accounting posting exists.

**Builds:** `AuditLog` (actor, action, model, object_id, before/after, timestamp,
entity), activity log, hooks/mixins to record create/update/post/reverse.

**Design refs:** CLAUDE.md §11, doc 05 (audit-trail report consumes this).

**Prompt:**
```
Implement apps.audit: an append-only AuditLog (actor, action, content_type,
object_id, change diff as jsonb, entity_id, timestamp) and a mixin/service to
record create/update/post/reverse without coupling domain apps. No deletes of
audit rows. Tests for log capture on a sample model. make lint && make test.
```

**Test gate:** create/update/post events logged with diff · audit rows immutable ·
logs scoped by entity.

---

## Phase 5 — `apps.accounts` (Chart of Accounts)

**Goal:** the COA structure, the code-composition service, tax codes, and the
seed.

**Builds:** `AccountGroup` (Main/Sub levels), `Account` (charge leaf, char(15)
code), `TaxCode`; `services/coding.py` (compose + validate `EEE-MMM-SSS-CCC`);
`services/seed.py` (category-template seeding); management command + fixtures
from `FinCare_Chart_of_Accounts.xlsx`.

**Design refs:** doc 01 §accounts, ADR-0004, ADR-0005, the seed workbook.

**Prompt:**
```
Implement apps.accounts per docs/design/01 (accounts section), ADR-0004 and ADR-0005.
AccountGroup holds Main(level1)/Sub(level2) segments; Account is the charge leaf with
char(15) code. Build services/coding.py to compose & validate codes
(regex ^\d{3}-\d{3}-\d{3}-\d{3}$, entity segment from numeric_code, band from category,
charge code via core NumberSequence; DB CHECK + serializer validator). Build a
category-template seed service + management command that reproduces the worked COA in
FinCare_Chart_of_Accounts.xlsx for a given entity. TaxCode model + rate. Tests:
code composition, entity-segment guard, seed idempotency. make lint && make test.
```

**Test gate:** every generated code matches the regex · entity-segment mismatch
rejected · seeding entity 101 reproduces the transport COA · re-seed is additive
(idempotent) · control accounts block manual posting flag.

---

## Phase 6 — `apps.ledger` (posting engine) ★ KEYSTONE

**Goal:** the double-entry core. Highest-stakes phase — use a verification
subagent.

**Builds:** `AccountingPeriod`, `JournalEntry`, `JournalLine`;
`services/posting.py` (`post_journal_entry`, `reverse_journal_entry`); lifecycle
state machine; period gating; rounding policy.

**Design refs:** doc 02 (ledger), ADR-0007.

**Prompt:**
```
Implement apps.ledger per docs/design/02 and ADR-0007. AccountingPeriod
(open/closed/locked), JournalEntry (lifecycle draft→validated→posted→reversed/cancelled,
reversal links, source_type/source_id, base totals), JournalLine (one-sided debit/credit,
fx→base, dims: cost_center/party/vehicle/driver/platform/tax_code). Build
services/posting.py: post_journal_entry (atomic; asserts balanced in base currency,
one-sided lines, postable+active accounts, party on control accounts, open period;
allocates entry_no; sets posted_at/by; immutable thereafter) and reverse_journal_entry
(mirror entry). Rounding residual to a configured rounding account. Tests: balanced
post ok; unbalanced raises; closed/locked period blocked; posted entry edit/delete
blocked; reversal balanced; idempotent re-post rejected; rounding booked. make lint && make test.
```

**Test gate (run a verification subagent over the diff):** all eight ADR-0007
tests pass · cannot edit/delete a posted entry by any path · reversal nets to zero
· concurrency-safe `entry_no`.

---

## Phase 7 — `apps.vouchers`

**Goal:** first source documents posting through the engine.

**Builds:** `Voucher` (receipt/payment/contra/expense/journal) + `VoucherLine`;
`services/post.py` building a JE and calling the ledger engine; DRF ViewSets with
a dedicated `/post/` action + RBAC.

**Design refs:** doc 02 (vouchers), CLAUDE.md §4 mappings.

**Prompt:**
```
Implement apps.vouchers per docs/design/02 (vouchers): Voucher + VoucherLine,
services/post.py that maps lines to a JournalEntry (source_type="voucher") and posts
via ledger.services.posting — never writing GL directly. DRF ViewSets with a /post/
action and RBAC; reversing a voucher reverses its entry. Tests for each voucher type's
debit/credit mapping (receipt, payment, contra, expense, journal). make lint && make test.
```

**Test gate:** each voucher type posts the correct Dr/Cr · voucher↔entry 1:1 ·
reverse cascades · only authorised role can post.

---

## Phase 8 — `apps.ar` (Accounts Receivable)

**Builds:** `Customer`, `SalesInvoice` + lines, `CreditNote` + lines,
`ReceiptAllocation`; aging query; invoice posting (DR AR / CR Revenue / CR Output
VAT).

**Design refs:** doc 03 §ar.

**Prompt:**
```
Implement apps.ar per docs/design/03 (ar section): Customer, SalesInvoice + lines
(place_of_supply, tax snapshot, profitability dims), CreditNote + lines,
ReceiptAllocation (links receipt vouchers/credit notes/advances to invoices). Invoice
posts via the ledger engine with Output VAT from accounts.TaxCode (no hardcoded rate).
Aging query (current/30/60/90/120+). Tests for the standard invoice posting and an
allocation reducing balance. make lint && make test.
```

**Test gate:** invoice posts DR AR/CR Revenue/CR Output VAT · allocation updates
balance & status · aging buckets correct · VAT from tax code, not literal.

---

## Phase 9 — `apps.ap` (Accounts Payable)

**Builds:** `Supplier`, `PurchaseBill` + lines (reverse-charge flag, recoverable
input VAT), `DebitNote` + lines, `PaymentAllocation`; supplier aging.

**Design refs:** doc 03 §ap.

**Prompt:**
```
Implement apps.ap per docs/design/03 (ap section): Supplier, PurchaseBill + lines
(is_reverse_charge, recoverable flag, per-vehicle/driver cost dims), DebitNote + lines,
PaymentAllocation. Bill posts DR Expense/Asset + DR Input VAT / CR AP via the engine;
reverse-charge raises both input and output VAT. Supplier aging. Tests for bill posting
and reverse-charge. make lint && make test.
```

**Test gate:** bill posts correctly · input VAT only when recoverable ·
reverse-charge raises both sides · aging correct.

---

## Phase 10 — `apps.tax` (UAE VAT & Corporate Tax)

**Builds:** `TaxCodeRateHistory`, `TaxReturn` (per VAT group), `TaxReturnBox` (VAT
201 incl. emirate split), `CorporateTaxReturn` (per entity); VAT computation
service aggregating member entities.

**Design refs:** doc 03 §tax, ADR-0006.

**Prompt:**
```
Implement apps.tax per docs/design/03 (tax) and ADR-0006: TaxCodeRateHistory
(effective-dated), TaxReturn per VAT group aggregating all member entities' posted
tax lines, TaxReturnBox (VAT 201 boxes incl. 1a–1g emirate split), CorporateTaxReturn
per entity. VAT computation service classifying output/input by tax_code + account
direction; box structure data-driven. Tests: a multi-entity VAT group return sums
members; emirate split correct. make lint && make test.
```

**Test gate:** return aggregates across VAT-group members under one TRN · boxes
reconcile to ledger tax lines · CT return is per entity · rates effective-dated.

---

## Phase 11 — `apps.banking` & `apps.cashbook`

**Builds:** bank account metadata, transfers/deposits, statement import +
reconciliation + items, POS settlement; cash accounts, petty-cash imprest,
replenishment, cash count + denominations.

**Design refs:** doc 06.

**Prompt:**
```
Implement apps.banking and apps.cashbook per docs/design/06. Banking: BankAccount,
BankTransfer (contra posting + charges), BankStatement + StatementLine (import),
Reconciliation + ReconciliationItem (rule-based match: amount+date window+reference),
PosSettlement (DR Bank+Fee / CR POS Clearing). Cashbook: CashAccount, PettyCashFloat,
Replenishment (DR Petty Cash/CR Bank), CashCount + Denomination (variance to short/over).
All post via the engine. Tests for transfer, POS settlement, reconciliation match,
cash variance. make lint && make test.
```

**Test gate:** transfer/deposit balanced · reconciliation finalises at zero
difference · POS fee split correct · cash variance posts to short/over.

---

## Phase 12 — `apps.fleet` & `apps.drivers`

**Builds:** vehicle master + documents + loan/EMI + depreciation run; driver
master + documents + advances + settlement.

**Design refs:** doc 04 §fleet, §drivers.

**Prompt:**
```
Implement apps.fleet and apps.drivers per docs/design/04. Fleet: Vehicle,
VehicleDocument (expiry alerts), VehicleLoan (EMI posting DR Loan+Interest/CR Bank),
DepreciationRun (DR Depreciation/CR Accum Dep, per-vehicle dim). Drivers: Driver,
DriverDocument, Advance (recovery), Settlement (gross − commission/salary − advances
− salik − fines = net, posts payout). All via the engine with profitability dims.
Tests for EMI, depreciation, and a driver settlement. make lint && make test.
```

**Test gate:** EMI splits principal/interest · depreciation per vehicle dim ·
settlement nets correctly and posts · expiry alerts queryable.

---

## Phase 13 — `apps.platforms` & `apps.bookings`

**Builds:** platform master + settlement + earning import; trip register +
corporate contracts (scheduled invoicing).

**Design refs:** doc 04 §platforms, §bookings.

**Prompt:**
```
Implement apps.platforms and apps.bookings per docs/design/04. Platforms: Platform
(revenue/commission/clearing accounts), Settlement (reconcile statement vs clearing,
variance), EarningImport staging. Bookings: Trip (dims vehicle/driver/platform/customer)
with periodic aggregate revenue posting, Contract (scheduled ar.SalesInvoice each cycle).
Tests: aggregate trip revenue posting; platform settlement reconciliation; contract
invoice generation. make lint && make test.
```

**Test gate:** aggregate trip posting carries dims · settlement clears clearing
account, variance flagged · contract generates invoices on cycle.

---

## Phase 14 — `apps.payroll` (+ WPS)

**Builds:** employee master + salary components/structure, run + payslip + lines,
WPS SIF batch + records, gratuity, leave, advances.

**Design refs:** doc 07.

**Prompt:**
```
Implement apps.payroll per docs/design/07. Employee (driver_id link, WPS fields),
SalaryComponent, EmployeeSalary (effective-dated), Run → Payslip → PayslipLine, WpsBatch
(SCR) + WpsRecord (EDR) with SIF export (config-driven layout), Gratuity (accrual +
settlement, day-rate from settings), Leave (accrual), Advance (payslip recovery). Run
posts accrual; payment posts separately; all via the engine. Honour the driver/payroll
boundary (no double pay). Tests: payroll run accrual balanced; SIF totals reconcile;
gratuity accrual. make lint && make test.
```

**Test gate:** run accrual balanced & posts · SIF batch totals reconcile to records
· gratuity/leave config-driven · salaried driver not double-paid.

---

## Phase 15 — `apps.reports` & `apps.exports`

**Builds:** balance engine, statement templates + lines, optional snapshots,
report run/schedule; the 16-report catalog; Excel/PDF export.

**Design refs:** doc 05.

**Prompt:**
```
Implement apps.reports and apps.exports per docs/design/05. Balance engine
(account_balances, trial_balance, ledger_detail; basis cash/accrual; dim filters;
multi-entity for consolidation). StatementTemplate + StatementLine (COA range mapping)
seeded for TB/PNL/BS/CF. Report catalog endpoints (TB, GL, P&L, BS, Cash Flow indirect,
VAT summary, AR/AP aging, profitability by dim, management pack, entity & consolidated
with intercompany elimination, audit trail). Exports to Excel (openpyxl) and PDF
(WeasyPrint); ReportRun log + ReportSchedule (Celery). Tests: TB nets to zero; P&L/BS
tie; consolidation eliminates intercompany. make lint && make test.
```

**Test gate:** TB debits = credits · BS balances · P&L ties to retained movement ·
consolidation eliminates intercompany · Excel & PDF render without error.

---

## Phase 16 — `apps.integrations`

**Builds:** bank statement file import (per-bank mappers), platform earnings
import (Uber/Yango/Bolt/Careem), POS import, webhooks.

**Design refs:** doc 06 (statement import), doc 04 (platform import).

**Prompt:**
```
Implement apps.integrations: file importers (CSV/XLSX) for bank statements (per-bank
column mapping → banking.StatementLine) and platform earnings (→ platforms.EarningImport),
with validation and idempotent re-import. Tests with sample files. make lint && make test.
```

**Test gate:** sample bank/platform files import to staging · re-import idempotent
· bad rows reported, not silently dropped.

---

## Phase 17 — Frontend (Next.js) — Phase 1.6

**Builds:** Next.js app, auth (JWT), entity switcher, COA & masters screens,
voucher/invoice/bill entry, dashboards, report viewers/exports.

**Design refs:** all API endpoints from phases 1–16; CLAUDE.md stack.

**Prompt:**
```
Scaffold the Next.js 16 + Tailwind + shadcn/ui frontend: JWT auth, entity switcher
honouring tenant context, and screens for COA, customers/suppliers, voucher/invoice/bill
entry (draft→post), dashboards (KPIs, profitability), and report viewers with Excel/PDF
download. Build screen-by-screen against the live API; one module per PR.
```

**Test gate:** login + entity switch works · a sales invoice can be entered and
posted via UI · a report renders and exports.

---

## Phase 18 — Hardening & UAT

**Builds:** security review (bandit/CodeQL triage), RLS/permission audit,
audit-trail completeness check, performance pass on reports, seed of the full
~25-entity register, UAT with real sample data.

**Prompt:**
```
Run a hardening pass: security-review the pending changes, verify RLS blocks
cross-entity access on every transactional endpoint, confirm posted transactions are
immutable across all apps, profile the heaviest reports, and seed the full entity
register. Produce a UAT checklist and fix findings.
```

**Test gate:** no high/critical security findings · RLS enforced everywhere ·
immutability holds on all posting apps · reports within performance budget.

---

## Milestones

| Milestone | Phases | Outcome |
|---|---|---|
| **M1 — Accounting core** | 0–6 | Platform + COA + posting engine; a balanced JE can be posted & reversed |
| **M2 — Documents & subledgers** | 7–9 | Vouchers, invoices, bills, allocations, aging |
| **M3 — Tax & treasury** | 10–11 | VAT 201 per group, CT per entity, bank/cash + reconciliation |
| **M4 — Operations & profitability** | 12–13 | Vehicle/driver/platform tracking; per-dim profitability |
| **M5 — Payroll** | 14 | WPS payroll, SIF, gratuity, leave |
| **M6 — Reporting** | 15–16 | Full statement & MIS suite, Excel/PDF, imports |
| **M7 — Product** | 17–18 | Next.js MVP, hardened, UAT-ready |

---

## Per-phase Definition of Done (CLAUDE.md §7)

Every phase PR must satisfy **all**:

- [ ] Models match the design doc; any change has an ADR
- [ ] Service layer owns posting; views thin; everything monetary via the engine
- [ ] Serializer + permission on every new endpoint
- [ ] Unit test proving `debit == credit` for each new posting path
- [ ] `make lint` (ruff/black/isort/mypy) and `make test` (pytest) green
- [ ] No floats for money; no deletion of posted rows
- [ ] UAE values config-driven (no hardcoded TRN/VAT rate/gratuity rate)
- [ ] Migration-safe; RLS respected on new transactional tables
- [ ] Audit log captures create/update/post/reverse

> For the keystone (Phase 6) and hardening (Phase 18), run a **verification
> subagent** over the diff in addition to the test gate.
