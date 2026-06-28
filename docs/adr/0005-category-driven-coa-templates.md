# ADR-0005 — Category-Driven COA Templates & Entity Instantiation

**Status:** Accepted
**Date:** 2026-06-28
**Author:** Govind
**Supersedes:** —
**Superseded by:** —
**Related:** ADR-0004 (account numbering), ADR-0006 (VAT grouping)

---

## Context

The group operates ~24 legal entities spread across a small number of **business
categories** (transport, cafeteria, baqala, salon, tour & travel, restaurant,
car-rental, typing, pharmacy, and auto-workshop). Entities in the same category
share an almost identical Chart of Accounts — only the trading income (Main 400)
and direct-cost (Main 500) blocks differ between categories; the asset,
liability, equity, overhead and finance/tax backbone is common to all.

For the initial build the group wants **one representative entity per category**,
and later the ability to:

- add more entities under an existing category, and
- add entirely new categories,

both **without code changes or schema migrations**.

Defining a separate hand-built COA per entity would be 24 near-duplicate charts
to maintain — error-prone and impossible to keep consistent.

---

## Decision

Model the COA as **category templates** that entities are **instantiated** from.

1. `tenants_business_category` holds each category and points to a
   `coa_template_key`.
2. A COA template = the **shared backbone** + the category's **income/direct-cost
   sections**. Templates are data (seed definitions), not code branches.
3. Each `tenants_entity` has `category_id`. On entity creation, an idempotent
   service `apps/accounts/services/seed.py::seed_entity_coa(entity)` walks the
   category template and creates `accounts_account_group` (Main/Sub) and
   `accounts_account` (Charge) rows, composing codes via
   `apps/accounts/services/coding.py` with the entity's 2-digit prefix
   (ADR-0004).
4. **Adding an entity** to an existing category = create the entity + run the
   seed. **Adding a category** = add a `business_category` row and a template
   definition; no migration.
5. Templates are versioned. Re-seeding never overwrites or deletes existing
   posted-to accounts; it only **adds** missing ones (additive, idempotent).
6. Per-entity deviations (an extra account a single entity needs) are allowed by
   adding accounts directly to that entity after seeding — the template is the
   baseline, not a lock.

### Entity numbering

The entity segment is a **3-digit banded** code (ADR-0004): category band
(1 digit) + entity sequence within the category (2 digits). Transport entities
are `101, 102, …`; cafeterias `201, 202, …`; etc. The band is derived from the
entity's category, so category is readable from the code. `numeric_code` is
immutable once any account exists for the entity.

### Category → template coverage (initial)

| Category | Distinct 400/500 blocks | Live entities (target) |
|---|---|---|
| transport | ride-hailing revenue, recoveries, vehicle running, platform commission, driver cost | 7 |
| cafeteria | counter/delivery revenue, COGS, delivery commission | 4 |
| baqala | retail/commission revenue, goods COGS | 4 |
| salon | service/retail revenue, consumables, stylist cost | 3 |
| tour & travel | commission/package revenue, travel service cost | 2 |
| restaurant | dine-in/delivery revenue, food COGS | 1 |
| car-rental | rental/lease revenue, recoveries, fleet running | 1 |
| typing | service/PRO revenue, govt disbursement cost | 1 |
| pharmacy | medicine (zero-rated) & general revenue, medicine COGS | 1 |
| auto-workshop | labour/parts revenue, parts & body COGS, technician cost | 1 |

> Auto-workshop is confirmed as a live category (band 0), bringing the group to
> 10 categories. With workshop counted, the live entity total is 25
> (24-entity breakdown + 1 workshop).

---

## Alternatives Considered

| Option | Rejected Because |
|---|---|
| One hand-built COA per entity | 24 near-duplicates; drifts out of sync; unmaintainable |
| Single global COA shared by all entities | Entity segment is in the code; categories need different 400/500 blocks |
| Category logic hardcoded in Python `if` branches | Adding a category would require a code change + deploy, defeating the goal |
| Inheritance via parent/child COA at runtime | Adds query complexity; posted accounts must be concrete rows for the ledger |

---

## Consequences

**Easier:**
- New entity in an existing category is a one-call seed; codes are correct by
  construction.
- New category is a data change (category row + template definition).
- Consistency across same-category entities is guaranteed by the shared template.
- The seed workbook (`FinCare_Chart_of_Accounts.xlsx`) doubles as the human-
  readable template source.

**Harder:**
- Template changes must define a clear policy for already-seeded entities
  (additive re-seed only; never destructive).
- Per-entity customisations live outside the template, so a template diff does
  not fully describe a given entity's chart.

---

## Risks

- **Template drift vs. seeded entities** — mitigated by additive, idempotent
  re-seed and by treating the workbook/template as the single source.
- **Accidental destructive re-seed** — mitigated by the rule that seeding never
  deletes or edits accounts that already carry postings.
- **Category explosion** — low risk; categories are few and stable.

---

## Migration Notes

Initial structure. The seed service and template definitions are built in build
step 3 (`apps.accounts`). The representative dev entities (banded codes
101, 201, 301, 401, 501, 601, 701, 801, 901, and 001 for workshop) and their
templates are captured in `FinCare_Chart_of_Accounts.xlsx`. When the full
24-entity register is confirmed, add the remaining entities (next sequence in
each band, e.g. 102–107 for transport) and run the seed; no schema migration is
required to add entities or categories.
