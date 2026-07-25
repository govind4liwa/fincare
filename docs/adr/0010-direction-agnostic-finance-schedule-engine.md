# ADR-0010 — Direction-Agnostic Finance Schedule Engine

**Status:** Proposed
**Date:** 2026-07-25
**Author:** Govind
**Supersedes:** —
**Superseded by:** —
**Related:** ADR-0007 (posting engine), ADR-0004 (CoA numbering),
`docs/design/04-erd-fleet-drivers-bookings-platforms.md`,
`docs/design/08-customer-vehicle-finance-receivable.md`,
`docs/supporting-source/Auto-Loan-Repayment-Schedule-Updated.xlsx`

---

## Context

The fleet EMI slice (PR #53) shipped a versioned, approval-locked amortization
schedule for **loans the company owes** (`fleet.VehicleLoan` → `LoanSchedule` →
`VehicleLoanInstallment`): generate as draft, validate exact reconciliation,
approve to lock, regenerate as a new version, never rewrite posted instalments.

The business also runs the **mirror transaction**: the company finances a
vehicle **to** a customer/driver (rent-to-own / hire-purchase — see the
Lexus ES300H / Muhammad Faisal workbook in `docs/supporting-source/`). That deal
needs the *same* schedule mechanics — versioning, approval, exact
reconciliation, rounding absorbed in the final instalment — plus a receivable
posting matrix, instalment receipt tracking, initial-expense recharge, and a
customer running account.

Building a second, parallel schedule stack for the receivable side would
duplicate the generation math, the version/approval state machine, the
reconciliation validator, and their tests — and the two would drift.

## Decision

Introduce **one direction-agnostic finance engine** in a new app,
`apps/financing`, and migrate the payable-side data into it while volume is
still trivial (one production loan).

1. **One agreement model, two directions.** `FinanceAgreement.direction`:
   - `LOAN_PAYABLE` — company borrows (counterparty = lender). Replaces
     `fleet.VehicleLoan`.
   - `FINANCE_RECEIVABLE` — company lends (counterparty = `ar.Customer`,
     optionally linked to `drivers.Driver`).
2. **Shared schedule stack.** `FinanceSchedule` / `FinanceInstallment` carry the
   existing version/approval/supersede state machine and the exact-reconciliation
   invariant unchanged. Amortization math moves to pure functions in
   `apps/financing/services/amortization.py`.
3. **Direction-specific posting only.** Generation, versioning, and approval are
   shared; only `services/post.py` branches by direction (payable: DR Loan
   Payable + DR Interest Expense / CR Bank — unchanged; receivable: per design
   doc 08 posting matrix). All postings go through the ledger engine (ADR-0007).
4. **A new amortization method**, `FLAT_QUOTED_EFFECTIVE`, reproducing the UAE
   auto-finance convention in the source workbook: EMI and total interest from
   the quoted flat rate; principal/interest split by the implied monthly IRR;
   final instalment absorbs rounding. (Verified to reproduce the workbook's 36
   rows exactly — see design doc 08 §4.3.)
5. **Fleet keeps the vehicle domain.** `fleet` retains Vehicle, documents, and
   depreciation. Loan endpoints under `/api/fleet/loans/` delegate to
   `financing` during a deprecation window, then move to `/api/financing/`.

## Alternatives Considered

| Option | Rejected Because |
|---|---|
| Second stack in `ar` (receivable-only models + copied services) | Duplicates the state machine, validator, and tests; guaranteed drift between the two schedules' behaviour |
| Generalize in place inside `apps/fleet` | Ties financing to vehicles forever; the same engine must later serve equipment finance, staff loans, and lender-provided imports; fleet is the wrong owner |
| Share only the math functions, keep separate models | The hard-won invariants (monotonic versions over soft delete, approval locking, posted-row protection) live in models + services, not in the math; sharing only math re-implements the risky part twice |
| Abstract base model with two concrete tables | Doubles migrations, admin, serializers, and query surfaces for near-identical schemas; direction is data, not structure |
| Defer the refactor until after the receivable slice | Data migration cost only grows; today it is one loan, two schedules, and a handful of instalments |

## Consequences

**Easier:** one tested engine for every schedule (bank loans, customer finance,
future equipment/staff finance); the receivable slice starts from working
version/approval code; `LENDER_PROVIDED` import lands once, for both directions.

**Harder:** a data migration for the just-shipped fleet loan tables (small
today, done in its own slice with count/checksum verification); a deprecation
window on `/api/fleet/loans/`; frontend loan pages repoint to the new endpoints.

## Migration Notes

Executed as Slice B of design doc 08 §16: create `apps/financing` (models +
copied services, parameterized by direction) → data-migrate `VehicleLoan`,
`LoanSchedule`, `VehicleLoanInstallment` rows preserving PKs, version numbers,
statuses, and `journal_entry` links → fleet API delegates → drop fleet loan
models in a later release once the frontend has repointed. Posted journal
entries are **never** touched by the migration (source_type strings are
remapped via a data migration on the source documents only, not on GL rows).
