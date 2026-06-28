# FinCare — App / Module Inventory

The complete set of Django apps for FinCare — **21 backend apps** plus the
**Next.js frontend** — grouped by layer, with each one's purpose, its design doc,
and the build phase from `BUILD_ROADMAP.md`.

Every monetary app writes to the books **only** through `apps.ledger`'s posting
engine (ADR-0007) — that is the architectural spine.

---

## Platform layer (foundation)

| # | App | Purpose | Design doc | Phase |
|---|---|---|---|---|
| 1 | `core` | Base models, audit mixins, soft delete, Currency, FX rates, gap-safe number sequences, attachments | 01 | 1 |
| 2 | `users` | User accounts, RBAC roles/permissions, JWT auth | — (CLAUDE §6/§11) | 2 |
| 3 | `tenants` | Entity, branch, cost center, department, **business category (band)**, **VAT group**, intercompany map, RLS | 01 | 3 |
| 4 | `settings` | Fiscal year, VAT config, numbering series, feature flags (per entity) | 01 | 3 |
| 5 | `audit` | Append-only audit log, change diffs, activity trail | — (CLAUDE §11) | 4 |

## Accounting engine

| # | App | Purpose | Design doc | Phase |
|---|---|---|---|---|
| 6 | `accounts` | Chart of Accounts (Main/Sub/Charge), code-composition service, tax codes, seed | 01 | 5 |
| 7 | `ledger` | Accounting periods, journal entry/line, **the posting engine** ★ | 02 | 6 |
| 8 | `vouchers` | Receipt / Payment / Contra / Expense / Journal vouchers | 02 | 7 |

## Subledgers & tax

| # | App | Purpose | Design doc | Phase |
|---|---|---|---|---|
| 9 | `ar` | Customers, sales invoices, credit notes, receipt allocations, aging | 03 | 8 |
| 10 | `ap` | Suppliers, purchase bills, debit notes, payment allocations, aging | 03 | 9 |
| 11 | `tax` | UAE VAT return (per VAT group), VAT 201 boxes, Corporate Tax, rate history | 03 | 10 |

## Cash & bank

| # | App | Purpose | Design doc | Phase |
|---|---|---|---|---|
| 12 | `banking` | Bank accounts, transfers/deposits, statement import, reconciliation, POS settlement | 06 | 11 |
| 13 | `cashbook` | Cash accounts, petty-cash imprest, replenishment, cash counts | 06 | 11 |

## Operations & profitability (transport / limousine / car rental)

| # | App | Purpose | Design doc | Phase |
|---|---|---|---|---|
| 14 | `fleet` | Vehicle master, documents, loan/EMI, depreciation | 04 | 12 |
| 15 | `drivers` | Driver master, documents, advances, settlements | 04 | 12 |
| 16 | `platforms` | Uber/Yango/Bolt/Careem masters, settlement reconciliation, earnings import | 04 | 13 |
| 17 | `bookings` | Trip register, corporate/monthly contracts | 04 | 13 |

## Payroll

| # | App | Purpose | Design doc | Phase |
|---|---|---|---|---|
| 18 | `payroll` | Employees, salary structure, payslips, **WPS/SIF**, gratuity, leave, advances | 07 | 14 |

## Reporting & integration

| # | App | Purpose | Design doc | Phase |
|---|---|---|---|---|
| 19 | `reports` | Balance engine, statement templates, TB/P&L/BS/CF, profitability, consolidation | 05 | 15 |
| 20 | `exports` | Excel (openpyxl) & PDF (WeasyPrint) generation | 05 | 15 |
| 21 | `integrations` | Bank statement & platform earnings file importers, webhooks | 04 / 06 | 16 |

## Frontend (separate, not a Django app)

| # | Component | Purpose | Phase |
|---|---|---|---|
| — | **Next.js app** | UI: auth, entity switcher, COA & masters, voucher/invoice entry, dashboards, report viewers | 17 (Phase 1.6) |

---

## Totals

**21 Django apps + 1 Next.js frontend.**

Monetary apps that post via the ledger engine (ADR-0007): `vouchers`, `ar`, `ap`,
`banking`, `cashbook`, `fleet`, `drivers`, `platforms`, `bookings`, `payroll`.

## Notes

- A separate `vehicles` app was considered but folded into `fleet` (matches the
  planned-apps list in `CLAUDE.md` §3). Split it out later only if vehicle data
  outgrows the fleet app.
- `INSTALLED_APPS` order should follow the dependency graph in
  `BUILD_ROADMAP.md`: `core → users → tenants → settings → audit → accounts →
  ledger → …`.
- New apps must be added to `LOCAL_APPS` in `fincare/settings/base.py` and
  referenced as `apps.<name>`.

## References

- Data model: `docs/design/01`–`07`
- Decisions: `docs/adr/0004`–`0007` (RLS = `0008`, to be written in Phase 3)
- Build order & test gates: `docs/BUILD_ROADMAP.md`
