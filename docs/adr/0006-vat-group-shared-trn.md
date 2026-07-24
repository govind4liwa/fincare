# ADR-0006 — VAT Group (Shared TRN) and Per-Entity Corporate Tax

**Status:** Accepted
**Date:** 2026-06-28
**Author:** Govind
**Supersedes:** —
**Superseded by:** —
**Related:** ADR-0005 (category COA), ADR-0004 (numbering)

---

## Context

Within the group, several legal entities are registered together under a **single
UAE VAT group** and therefore share **one TRN**, while other entities register
for VAT individually. UAE Corporate Tax works differently: each entity has its
**own** Corporate Tax registration regardless of VAT grouping (CT grouping, where
elected, is a separate determination and is not assumed here).

The earlier model put `trn` directly on `tenants_entity`, which cannot represent
"seven entities, one shared TRN" and would force the TRN to be duplicated and
kept in sync across rows.

Implications of VAT grouping that the system must respect:

- VAT is reported **once per VAT group**, not per member entity — the VAT return
  consolidates output/input VAT across all members under the shared TRN.
- **Intra-group supplies** between members of the same VAT group are generally
  outside the scope of VAT (no output VAT) — distinct from intercompany
  transactions between entities that are *not* in the same group.
- Each member still keeps its **own books** and its **own Corporate Tax** position.

---

## Decision

Separate the two tax registrations into distinct concepts.

1. Introduce `tenants_vat_group` holding the shared `trn` and a representative
   member. Entities link via `tenants_entity.vat_group_id` (nullable).
2. An entity's effective VAT TRN is **resolved from its VAT group**, never stored
   on the entity. An entity registering individually is modelled as a VAT group
   with a single member (or `vat_group_id = NULL` if not VAT-registered at all).
3. `corporate_tax_trn` stays **on the entity** and is always per-entity.
4. VAT reporting (in `apps.tax`) aggregates by `vat_group_id`: the VAT return
   summary sums output/input VAT across all member entities for the period under
   the one TRN.
5. Transactions between two entities **in the same VAT group** are flagged and
   default to an out-of-scope VAT treatment; transactions between entities **not**
   in the same group follow normal VAT rules (and the intercompany map of
   ADR-0004/§tenants).
6. TRN and CT numbers remain **configuration**, never hardcoded (CLAUDE.md §4.8).

---

## Alternatives Considered

| Option | Rejected Because |
|---|---|
| `trn` directly on each entity | Cannot represent a shared TRN; duplication drifts out of sync |
| Single TRN for the whole group | Wrong — only *some* entities share a group; others register individually |
| Merge VAT group and CT grouping into one "tax group" | Conflates two different regimes with different membership; VAT-group ≠ CT-group |
| Derive grouping implicitly from `parent_entity_id` | Consolidation tree ≠ VAT group membership; they differ |

---

## Consequences

**Easier:**
- One TRN stored once; all members resolve to it.
- VAT return is naturally a per-group aggregation.
- Intra-group out-of-scope treatment is detectable from group membership.
- Corporate Tax stays cleanly per entity.

**Harder:**
- VAT reporting must always group by `vat_group_id`, not by entity — reports and
  the FTA return file must respect this.
- Membership changes (an entity joins/leaves a VAT group) need an effective-date
  policy so historical returns stay correct.

---

## Risks

- **Mis-scoped intra-group transactions** (charging VAT within a group) —
  mitigated by flagging same-group counterparties and defaulting to out-of-scope.
- **Membership change mid-period** — mitigated by recording effective dates on
  group membership (to be added in `apps.tax` when VAT returns are built).
- **Assuming VAT grouping implies CT grouping** — explicitly avoided; CT stays
  per entity unless a separate CT-group decision is recorded in a future ADR.

> Compliance note (CLAUDE.md §9): this records **system logic** for representing
> VAT groups and CT registrations. Whether specific entities may form a VAT group
> or CT group is a tax-advisory determination, not decided here.

---

## Migration Notes

Initial structure. `trn` is modelled on `tenants_vat_group`, not on
`tenants_entity`. The sample VAT group `VG-01` and member assignments in
`FinCare_Chart_of_Accounts.xlsx` (VAT Groups sheet) are **placeholders** — the
real TRN and the actual membership of each of the 24 entities must be confirmed
before VAT return logic is built in `apps.tax`.
