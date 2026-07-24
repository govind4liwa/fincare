# ADR-0007 — Journal Posting Engine

**Status:** Accepted
**Date:** 2026-06-28
**Author:** Govind
**Supersedes:** —
**Superseded by:** —
**Related:** ADR-0004 (numbering), ADR-0006 (VAT grouping),
`docs/design/02-erd-ledger-vouchers.md`, `03-erd-ar-ap-tax.md`,
`04-erd-fleet-drivers-bookings-platforms.md`

---

## Context

FinCare has many source documents that move money — vouchers (receipt, payment,
contra, expense, journal), sales invoices, purchase bills, credit/debit notes,
driver settlements, platform settlements, depreciation runs, EMI payments,
opening balances. Every one of them must end up as a balanced double-entry in the
general ledger, with an audit trail, period control, and multi-entity isolation.

The integrity of the books depends on these rules never being bypassed
(CLAUDE.md §4): `total_debit == total_credit`, money is `Decimal`, posted rows are
immutable, deletions are forbidden. If each document type wrote GL rows its own
way — in a view, a serializer, an ORM signal — those rules would be enforced
inconsistently and eventually violated. We need **one** authoritative write-path.

---

## Decision

All general-ledger writes go through a **single posting engine** in
`apps/ledger/services/posting.py`. It is the *only* code permitted to create or
change `ledger_journal_entry` / `ledger_journal_line` rows.

### 1. One entry point

```python
def post_journal_entry(entry: JournalEntry, *, user) -> JournalEntry
def reverse_journal_entry(entry, *, user, date=None) -> JournalEntry
```

Source documents (vouchers, invoices, bills, settlements, depreciation, …) build
an unposted `JournalEntry` with `source_type` + `source_id`, then call
`post_journal_entry`. No source app writes GL rows directly. Views and
serializers call services; they never post.

### 2. Invariants enforced at post (each asserted by a unit test)

1. **Balanced:** `SUM(base_debit) == SUM(base_credit)` and total ≠ 0.
2. **One-sided lines:** each line has exactly one of debit/credit non-zero.
3. **Postable accounts:** `account.is_postable AND account.is_active`; control
   accounts (`allow_manual_posting = false`) reject manual lines.
4. **Party on control accounts:** AR/AP lines carry `party_type` + `party_id`.
5. **Open period:** `entry_date` falls in an `open` period (or `closed` with the
   adjustment permission); `locked` always rejects.
6. **Currency → base:** each line carries `fx_rate`; `base_* = amount × fx_rate`;
   the balance check is in **base currency**.

### 3. Lifecycle & immutability

`draft → validated → posted → (reversed | cancelled)`.

- `post` assigns `entry_no` (gap-safe via `core_number_sequence`, ADR-0004), sets
  `posted_at` / `posted_by`, and flips status to `posted`.
- A **posted entry is immutable**: no edit, no soft delete, no hard delete.
  Corrections are made by **reversal only** — `reverse_journal_entry` posts a
  mirror entry (debits/credits swapped), linking `reversal_of_id` /
  `reversed_by_id`.
- `cancel` is allowed only from `draft` / `validated`.

### 4. Atomicity & idempotency

- The whole post (header + all lines + `entry_no` allocation) runs inside one
  `transaction.atomic()`. A partial post cannot exist.
- Re-posting is rejected (status guard) so a retried request cannot double-post;
  source documents hold a 1:1 `journal_entry_id` once posted.

### 5. Rounding policy

When VAT/FX rounding leaves a sub-fil residual, the engine books the difference to
a configured **rounding account** so the entry is exactly balanced. The residual
tolerance and account are configuration, not literals.

### 6. Multi-entity safety

Every entry and line carries `entity_id`; the engine sets/honours the RLS tenant
context (per `tenants` design). Intercompany postings are two balanced entries
(one per entity), linked via the intercompany map — never a single cross-entity
entry.

---

## Alternatives Considered

| Option | Rejected Because |
|---|---|
| Post in views / serializers | Rules duplicated per endpoint; drift and bypass inevitable |
| Django ORM `post_save` signals | Implicit, hard to test/trace, fire on unrelated saves, ordering issues |
| Database triggers for balancing | Logic split between DB and app; hard to unit test; opaque to developers |
| Allow editing/deleting posted entries | Destroys audit trail and period integrity; fails UAE audit expectations |
| Full event-sourcing / ledger CQRS | Over-engineered for Phase 1; heavy operational burden; revisit only if needed |
| One model per voucher writing its own GL | N inconsistent posting paths; the exact problem this ADR removes |

---

## Consequences

**Easier:**
- A single, test-covered place guarantees `debit == credit` and immutability for
  every document type, present and future.
- New source documents are cheap: build a `JournalEntry`, call one function.
- Audit trail is uniform; reversal history is explicit and queryable.
- Period close and multi-entity isolation are enforced centrally.

**Harder:**
- All source apps must depend on `apps.ledger` and conform to the entry-builder
  contract — a deliberate coupling.
- Reversal-only correction is stricter for users than editing, by design;
  the UI must make reversal easy.
- The engine is a critical path: it needs strong tests and careful change control.

---

## Risks

- **Bypass via raw ORM/SQL** — mitigated by code review, the "services own
  posting" rule (CLAUDE.md §4.3), and `make lint`; optionally a guard that blocks
  direct writes to GL models outside the service.
- **Performance on high-volume sources** (e.g. trips) — mitigated by periodic
  **aggregate** posting rather than per-event entries (doc 04, decision 1).
- **Rounding misconfiguration** — mitigated by a default rounding account in the
  seed and a test asserting balanced entries under rounding.
- **Period/timezone edge cases** — mitigated by resolving `period_id` from
  `entry_date` in entity-local terms and testing boundary dates.

---

## Migration Notes

Initial structure — built in build step 4 (`apps.ledger`). The engine ships with
unit tests covering: balanced post succeeds; unbalanced post raises; one-sided
line rule; posting to a closed/locked period; posted entry immutable (edit/delete
blocked); reversal creates a balanced mirror; idempotent re-post rejected;
rounding residual booked to the rounding account. All later posting apps
(`vouchers`, `ar`, `ap`, `banking`, `payroll`, `fleet`, `drivers`, `platforms`)
must post exclusively through this engine.
