# Changelog

All notable changes to FinCare will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/govind4liwa/fincare/compare/v0.3.0...develop
[0.3.0]: https://github.com/govind4liwa/fincare/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/govind4liwa/fincare/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/govind4liwa/fincare/releases/tag/v0.1.0
