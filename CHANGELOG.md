# Changelog

All notable changes to FinCare will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.5.0] - 2026-09-20

**Every app is now operable from the browser.** v0.4.0 shipped a backend whose
accounting engine was complete but largely unreachable: nine apps had fully
built, unit-tested service layers and *no API at all* — no serializer, no
ViewSet, no route, no screen. This release closes that gap end to end. Platform
settlements, trip revenue, VAT 201 and Corporate Tax filing, payroll and WPS,
the cashbook, the audit trail, and file imports all became things an operator
can actually do, rather than capabilities that only existed in tests.

Almost nothing here changes how the books work — the posting rules, the ledger
engine and the service layer are the ones v0.4.0 already shipped and tested.
What changed is reach.

### Added

- **Platforms** — platform masters, staged earning rows, and the settlement
  workflow: create a draft, `reconcile` to aggregate staged imports into
  gross/commission/variance, then `post` to book DR Bank / CR Platform Clearing
  with the adjustment either way. Screens for the master list and the
  settlement workflow.
- **Bookings** — the trip register and corporate contracts. Trips can be
  multi-selected and posted as one balanced aggregate revenue entry grouped by
  vehicle and driver; a contract generates its cycle's sales invoice.
- **UAE tax filing** — VAT 201 returns and Corporate Tax returns, each with
  `compute` and `file` actions and an expandable box-by-box breakdown.
  Corporate Tax gained a `file_corporate_tax_return` service so it has the same
  compute → file lifecycle as VAT rather than stopping at "computed". VAT
  return scoping is polymorphic: a return belongs either to a VAT group's
  member entities or to one standalone entity, and access is checked against
  the caller's accessible entities directly.
- **Payroll** (shipped as four reviewable slices) — employees and their
  effective-dated salary structures; the run lifecycle (`build` derives
  payslips from the current structure and recovers open advances, `post` books
  the accrual, `pay` books the payment separately); salary advances with
  recovery; WPS batch generation with a reconciled SIF file download; and
  gratuity and leave accrual with gratuity settlement.
- **Cashbook** — cash accounts and petty-cash floats, replenishments
  (DR Petty Cash / CR Bank), and physical cash counts with an editable
  denomination tally whose variance posts to a short/over account.
- **File imports** — import profiles describing a source's column layout (a
  profile with no entity is group-wide), plus multipart upload endpoints for
  bank statements (→ statement lines for reconciliation) and platform earnings
  (→ staged rows for settlement). Re-importing a file is idempotent. A failed
  run is recorded as an `ERROR` batch carrying the reason, so bad files are
  reported rather than silently dropped, while the HTTP response stays generic.
  Uploads are bounded by extension and by `INTEGRATIONS_MAX_UPLOAD_MB`.
- **Audit trail** — a read-only view of the existing append-only log, filterable
  by action and expandable to a field-level before/after diff. Unlike the other
  endpoints added here, reads are role-gated too: the trail covers other users'
  actions across the entity, not just the caller's own.
- **Accounting periods** — the full lifecycle. Periods can be created (rejecting
  overlapping date ranges, since posting resolves an entry's period from its
  date alone), closed, reopened, and locked. Closing is routine and reversible;
  locking is one-way, applying to the period the same immutability the system
  applies to posted entries.
- **Driver receivables can now be cleared** — a `DriverClearing` document with
  two kinds that differ only in what they debit: a receipt (DR Bank) or a
  write-off (DR Bad Debts). Both always credit the entity's *configured*
  receivable account — the same account the negative-net settlement debited —
  and both accounts are resolved at posting time and persisted, so a later
  configuration change cannot rewrite posted history.
- **Multi-invoice allocation** — apply one receipt, payment, credit note or
  debit note across several open documents in a single atomic action, and undo
  a previous allocation. Reversals are recorded (`reversed_at`/`reversed_by`),
  never deleted, so the subledger history stays auditable.
- **Chart of Accounts groups** — new Main and Sub groups can be created, with a
  Sub group inheriting its parent's nature so a branch stays one nature end to
  end. Codes remain immutable once created, as with accounts.
- **Fleet** — vehicle documents with expiry ageing (each renewal is a new row,
  so expired documents remain as renewal history) and depreciation runs that
  post one line per configured active vehicle.
- **Entity settings** — typed override cards for the gratuity rule and SIF
  layout, showing the merged effective value over the documented UAE defaults,
  with a reset back to default.
- **PDF report export** — the existing WeasyPrint renderer is now wired to the
  report endpoint alongside Excel.
- **Self-profile endpoint** (`/users/me/`) — identity, roles and accessible
  entities; the app header now shows who is signed in and with what roles.

### Changed

- **The sidebar was reorganised** into eight collapsible categories plus
  Dashboard, Reports and Settings as direct links — no route was added, removed
  or renamed in that change. The desktop accordion auto-expands to the active
  route on every navigation, and mobile drills into one category at a time.
  Both are keyboard-operable and respect `prefers-reduced-motion`.
- Salary components can be edited inline, not just created — the backend had
  always accepted `PATCH`, but the screen never offered it.
- `apiFetch` no longer forces `application/json` when the request body is
  `FormData`, so the browser can set its own multipart boundary.

### Fixed

- **Authenticated page reloads bounced to the login screen.** The app layout's
  auth guard redirected off the transient `false` that `useSyncExternalStore`
  reports on the first hydration render, so every refresh logged you out
  despite valid tokens. The redirect is now deferred a tick and cancelled if
  the value resolves true first.
- Trip revenue posting crashed on a date string from the request body, which
  needed parsing to a `date` before reaching the service.
- A non-UTF-8 CSV, an unopenable workbook, or a missing worksheet now surface
  as a clean import error instead of an unhandled decoder or openpyxl
  exception.

### Security

- **Row-Level Security now covers every transactional table.** The original RLS
  migration protected the ten tables that existed when it landed; every app
  built afterwards shipped tables carrying `entity_id` with no policy at all —
  53 of 62 were unprotected, so a query that forgot to filter could return
  another entity's rows. All of them now carry the isolation policy, and a test
  introspects the models (rather than a hand-maintained list) so a new table
  without a policy fails the build.
- **Fixed the "no tenant context" check**, which did not mean what it said. The
  policy tested the context variable for NULL, but a PostgreSQL custom setting
  reverts to the *empty string* once it has been set and the transaction ends.
  On a reused connection an unset context therefore matched **nothing instead of
  everything** — inverting the intended failure mode and silently breaking the
  superuser path, whose way of signalling "unrestricted" is to leave the context
  unset. Existing databases pick up the corrected policy on migrate.
- Still outstanding, and deliberately recorded rather than assumed done: child
  tables with no `entity_id` of their own (journal lines, invoice lines,
  statement lines, payslips) remain unprotected, since an `entity_id`-keyed
  policy cannot express them. See the ADR-0008 amendment.

Row-Level Security remains gated by `RLS_ENABLED` (default off), so none of this
changes behaviour until it is switched on.

### Documentation

- Design 08 (vehicle financing) was reviewed against the shipped code and
  twelve issues folded in, four substantive — including a raise-dues path that
  would have silently driven a non-control account negative, and a customer
  statement that double-counted every migrated opening balance. A review log
  was added so the resolved decisions are not relitigated.

### Internal

- **The frontend has test tooling** for the first time: Vitest and Testing
  Library, with 28 tests covering the new navigation's expand/collapse,
  active-route behaviour, keyboard operation and mobile drill-down.

## [0.4.0] - 2026-07-25

**Vehicle finance schedules and driver settlements.**

### Added
- **Vehicle-loan amortization schedules** — versioned, reconciled and lockable:
  - **Per-loan amortization method**: `REDUCING_BALANCE`, `FLAT_RATE`, and
    `FLAT_QUOTED_EFFECTIVE` — the UAE auto-finance convention where a contract is
    quoted flat but each instalment is split at the effective rate it implies. The
    split rate is the IRR of the contract, solved deterministically on `Decimal`
    (Newton with an analytic derivative, bisection fallback, no binary floats).
    `LENDER_PROVIDED` is documented as the extension point for importing a bank's
    own schedule.
  - **`LoanSchedule` versions** (draft → approved → superseded) snapshot the inputs
    and totals they were generated from. Rounding drift is absorbed by the *final*
    instalment, and a schedule is validated to reconcile exactly — principal,
    interest, payments and a balance closing to zero — before it is saved.
  - Approving a version locks it and supersedes the previous one; version numbers
    are monotonic and never reused. **EMIs can only be posted from an approved
    schedule.**
  - A `/loans` workspace to create loans, generate and compare versions, approve or
    discard drafts, and post instalments.
- **Driver advances and settlements**:
  - **Advances** — `DR Driver Advance / CR Bank`, with recovery tracked against the
    outstanding balance. Concurrent settlements recovering the same advance are
    serialised so they cannot jointly over-recover it.
  - **Settlements** — gross earnings less deductions (commission, salary, advance
    recovery, Salik, fines), posting the net to bank when the driver is owed money.
  - **Negative net** — when deductions exceed earnings the driver *owes* money, so
    posting debits a **Driver Receivable** account and leaves **bank and cash
    untouched**; a separate receipt clears it when the money is actually collected.
    A settlement must opt in via `allows_negative_net`.
  - `/advances` and `/settlements` screens with live gross → deductions → net
    totals and advance-recovery pickers.
- **Per-entity Driver Receivable configuration** — each entity nominates exactly one
  account that may hold a driver receivable, and configuring it *is* the approval.
  No account is reclassified: `Staff Advances` remains a general asset and the
  `RECEIVABLE` account type still means customer AR. Existing entities are
  configured automatically on upgrade, and new ones at provisioning time; an entity
  with no unambiguous match is left unconfigured rather than pointed at a guess.
  A `/settings` screen lets a manager or admin change it.

### Changed
- Loan rate columns widened from 3 to 6 decimal places — a monthly effective rate
  needs the extra precision, and at 3 dp a flat-quoted schedule drifts. Existing
  values are preserved exactly.

## [0.3.0] - 2026-07-25

**Bank reconciliation.**

### Added
- **Banking API** (previously unmounted): bank-account master, statement entry,
  and reconciliation endpoints, all entity-scoped with role-gated writes.
- **Bank accounts** — entity-scoped masters linked to a bank-type GL account
  (validated), with deactivate-not-delete.
- **Bank reconciliation** — a `/reconcile` workspace showing statement vs GL
  balance, the difference, and the matched/unmatched breakdown:
  - **Auto-match** imports statement lines to posted bank-GL journal lines
    (deposit ↔ GL debit, withdrawal ↔ GL credit) with date-window and
    amount-tolerance rules; rerun-safe (idempotent).
  - **Manual match / unmatch** for the exceptions — 1:1, with side and equal
    amount enforced, bypassing the auto date/reference rules.
  - **Completion & locking** — a reconciliation can be completed only when every
    statement line is matched and the statement/GL balances agree; completing
    locks it and marks the statement reconciled. A manager or admin can
    **reopen** a completed reconciliation. Every action is audited.

## [0.2.0] - 2026-07-25

Phase 1.6 — the **operator web UI**: a Next.js frontend for day-to-day
bookkeeping, plus the write APIs behind it.

### Added
- **Next.js 16 frontend** (monorepo `frontend/`, Dockerized on port 3005):
  JWT email login, an app shell with a live **entity switcher**, light/dark
  theme, and a Next→DRF API proxy.
- **Read screens**: Chart of Accounts, Customers & Suppliers, Fleet & Drivers,
  Reports viewer (Trial Balance / P&L / Balance Sheet / Cash Flow with Excel
  export), and a Dashboard with KPIs wired to real ledger figures.
- **Entry forms** (create → post, with live totals): Vouchers, Sales Invoices,
  Purchase Bills (reverse-charge + per-line recoverable VAT), Credit Notes,
  and Debit Notes.
- **Master create/edit forms**: Customers, Suppliers, Vehicles, Drivers, and
  Chart of Accounts (codes composed as `EEE-MMM-SSS-CCC` per ADR-0004 and
  immutable once created).
- **AP debit-note posting** (`post_debit_note`) — the mirror of a purchase bill.
- **Receipt/payment allocation** — settle open invoices and bills against
  receipts, payments, and credit/debit notes (subledger reconciliation, capped
  at each source's unallocated amount).
- Supporting **DRF APIs** for all of the above (entities, accounts / groups /
  tax-codes, customers, suppliers, invoices, bills, credit/debit notes, periods,
  vehicles, drivers, vouchers, reports/dashboard) — entity-scoped, with
  role-gated writes.

### Fixed
- Report **Excel export** returned 404 — the export param is `export=`, not
  `format=` (which DRF reserves for content negotiation).
- Next→DRF **API proxy** now reaches DRF correctly (trailing-slash handling +
  `ALLOWED_HOSTS`).
- Email-based **login**; a `.gitignore` rule that was hiding `frontend/src/lib/`.

### Changed
- Master-data endpoints share an `EntityScopedMasterViewSet` — reads open to
  members, writes require an accounting role, and deletion is disabled
  (deactivate via `is_active`, never hard-delete).

### Security
- DRF error responses no longer echo exception text (CodeQL
  `py/information-exposure`).

## [0.1.0] - 2026-07-24

First application release — the complete FinCare accounting backend.

### Added
- **Accounting backend** across 21 Django apps: `core`, `users`, `settings`,
  `audit`, `tenants`, `accounts`, `ledger`, `vouchers`, `ar`, `ap`, `banking`,
  `cashbook`, `tax`, `fleet`, `drivers`, `bookings`, `platforms`, `payroll`,
  `reports`, `exports`, `integrations`.
- Double-entry posting engine (`apps.ledger.services.posting`): atomic, balanced,
  period-gated, immutable with reversal-based corrections (ADR-0007).
- PostgreSQL Row-Level Security multi-tenancy with per-request entity scoping.
- Chart of Accounts with `EEE-MMM-SSS-CCC` account coding (ADR-0004/0005).
- UAE VAT (FTA VAT 201) and Corporate Tax modelling; VAT-group shared TRN (ADR-0006).
- Sub-ledgers: AR/AP with aging, banking with reconciliation, cashbook, vouchers.
- Fleet / driver / bookings / platforms modules with per-vehicle and per-driver
  profitability tagging.
- WPS-ready payroll (gratuity, leave, advances).
- Financial reporting (statements, trial balance, consolidation, profitability) with
  Excel (openpyxl) and PDF (WeasyPrint) exporters.
- JWT auth, role-based access control, OpenAPI schema (drf-spectacular).
- Repository scaffold: CI/security/CodeQL workflows, Docker baseline, GitFlow-Lite,
  Conventional Commits, pre-commit (ruff/black/isort/mypy/bandit/gitleaks), CODEOWNERS,
  and Architecture Decision Records.

### Changed
- Upgraded to **Django 6.0** (from 5.0), including the coupled `django-celery-beat` /
  `redis` bumps and the `CheckConstraint(check=...)` → `condition=` migration.
- Modernised the dev toolchain: pytest 9, black 26, ruff 0.15, isort 8, mypy.
- Updated CI actions: CodeQL v4, setup-python, setup-buildx, gitleaks, dependency-review.
- Corrected the Celery worker/beat Docker healthchecks (worker pings; beat opts out).

### Security
- Resolved all outstanding Dependabot advisories (**80 → 0**; 6 critical, 25 high),
  covering Django, WeasyPrint, and sentry-sdk on the production dependency set.

[Unreleased]: https://github.com/govind4liwa/fincare/compare/v0.4.0...develop
[0.4.0]: https://github.com/govind4liwa/fincare/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/govind4liwa/fincare/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/govind4liwa/fincare/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/govind4liwa/fincare/releases/tag/v0.1.0
