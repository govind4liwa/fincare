# ADR-0004 — Chart of Accounts Numbering Scheme

**Status:** Accepted
**Date:** 2026-06-28 (rev. 2026-06-28 — widened entity segment to 3 digits, banded)
**Author:** Govind
**Supersedes:** —
**Superseded by:** —
**Related:** ADR-0005 (category COA templates), ADR-0006 (VAT grouping)

---

## Context

FinCare maintains a per-entity Chart of Accounts across a multi-entity group
(~24 entities) operating mixed business categories (transport, cafeteria, baqala,
salon, tour & travel, restaurant, car-rental, typing, pharmacy, auto-workshop).
Account codes must:

- Identify the owning **entity** and its **business category** on the face of the
  code, for consolidation and cross-company reporting.
- Encode a stable Main → Sub → Charge hierarchy so reports roll up by segment
  without joins or string parsing.
- Be fixed-width and predictable, so they sort correctly and import/export cleanly
  to Excel, the FTA VAT return, and bank files.
- Support the granular **charge codes** operators need (Salik, fines, tolls,
  driver deductions, COGS lines, etc.).
- Leave headroom: the group adds entities within a category and may add new
  categories over time.

A 2-digit entity segment (original revision) capped the group at 99 entities with
no category meaning in the code and no category-banding headroom. Widening the
entity segment to 3 digits with a category band solves both.

---

## Decision

Adopt a fixed four-segment account code: **`EEE-MMM-SSS-CCC`** (12 digits, 15
chars incl. dashes).

```
1 01 - 400 - 410 - 001
│ │     │     │     └─ Charge Code   (3 digits) → postable leaf  (accounts_account)
│ │     │     └─────── Sub-Account   (3 digits) → level-2 group
│ │     └───────────── Main Account  (3 digits) → level-1 group; 1st digit = nature
│ └─────────────────── Entity seq    (2 digits) → entity number within its category (01–99)
└───────────────────── Category band (1 digit)  → business category (0–9)
```

The **Entity segment (`EEE`)** = **category band (`C`, 1 digit)** + **entity
sequence (`NN`, 2 digits)**.

| Segment | Width | Source | Meaning |
|---|---|---|---|
| Category band | 1 | `tenants_business_category.band` | Business category (0–9) |
| Entity sequence | 2 | `tenants_entity` (per-category counter) | Entity # within the category (01–99) |
| Main Account | 3 | `accounts_account_group` level 1 | Primary class; **first digit = nature** |
| Sub-Account | 3 | `accounts_account_group` level 2 | Category within the main account |
| Charge Code | 3 | `accounts_account.charge_segment` | The specific postable account |

`tenants_entity.numeric_code` (`char(3)`) stores the full `EEE` entity segment.

### Category band assignment

| Band | Category | Live entities (target) |
|---|---|---|
| 1 | Transport | 7 |
| 2 | Cafeteria | 4 |
| 3 | Baqala / Grocery | 4 |
| 4 | Salon | 3 |
| 5 | Tour & Travel | 2 |
| 6 | Restaurant | 1 |
| 7 | Car Rental | 1 |
| 8 | Typing | 1 |
| 9 | Pharmacy | 1 |
| 0 | Auto Workshop | 1 |

> Bands 0–9 are all assigned (10 categories). Auto Workshop is confirmed as a
> live category at band 0.

### Nature derived from the Main Account first digit

| 1st digit | Nature | Normal balance |
|---|---|---|
| 1 | Asset | Debit |
| 2 | Liability | Credit |
| 3 | Equity | Credit |
| 4 | Income / Revenue | Credit |
| 5 | Cost of Sales / Direct Cost | Debit |
| 6 | Operating / Overhead Expense | Debit |
| 7 | Finance Cost & Tax | Debit |

### Storage & generation rules

1. Each segment is stored discretely **and** the full 15-character code is
   persisted (`accounts_account.code`, `char(15)`, globally unique).
2. The Entity segment is **always** the entity's `numeric_code`; users never type
   it. A row whose `entity_id` disagrees with its leading segment is rejected.
3. The composed code is built and validated only in
   `apps/accounts/services/coding.py` — never in views, serializers, or frontend.
4. A DB `CHECK` constraint and a serializer validator both enforce
   `^\d{3}-\d{3}-\d{3}-\d{3}$`.
5. The category band is taken from the entity's category
   (`tenants_business_category.band`); the 2-digit sequence is allocated per
   category via a gap-safe `core_number_sequence`.
6. The next free Charge Code within a Sub-Account is allocated via a separate
   gap-safe `core_number_sequence` (`code="COA"`, `period_key="<entity>-<main>-<sub>"`).
7. `normal_balance` is derived from the Main segment's first digit, not entered
   manually.

### Reserved Main Account bands (group convention, configurable per entity)

| Band | Purpose |
|---|---|
| 100–199 | Assets (cash, bank, receivables, inventory, fixed assets, vehicles) |
| 200–299 | Liabilities (payables, loans, VAT, accruals) |
| 300–399 | Equity |
| 400–499 | Income (operating revenue, recoveries, other income) |
| 500–599 | Direct costs / COGS |
| 600–699 | Operating / overhead expenses |
| 700–799 | Finance cost, tax, exceptional |

---

## Worked example (transport entity, `numeric_code = 101`)

| Code | Main | Sub | Charge | Account | Type |
|---|---|---|---|---|---|
| `101-100-110-001` | 100 Assets | 110 Cash & Bank | 001 | Petty Cash | cash |
| `101-100-110-010` | 100 Assets | 110 Cash & Bank | 010 | ENBD Current A/C | bank |
| `101-100-120-001` | 100 Assets | 120 Receivables | 001 | Trade Receivables (control) | receivable |
| `101-100-150-001` | 100 Assets | 150 PPE | 001 | Motor Vehicles – Cost | fixed_asset |
| `101-200-230-001` | 200 Liabilities | 230 VAT | 001 | Output VAT | vat_output |
| `101-200-220-001` | 200 Liabilities | 220 Loans | 001 | Vehicle Loan Payable | loan |
| `101-400-410-001` | 400 Income | 410 Operating Revenue | 001 | Uber Earnings | revenue |
| `101-500-510-001` | 500 Direct Cost | 510 Vehicle Running | 001 | Salik Charges | expense |
| `101-500-530-001` | 500 Direct Cost | 530 Driver Cost | 001 | Driver Salary | expense |
| `101-600-630-003` | 600 Opex | 630 Vehicle Ownership | 003 | Vehicle Depreciation | expense |

A second transport entity is `102-…`; a cafeteria is `201-…`; a restaurant is
`601-…`. The backbone (assets/liabilities/equity/overheads/finance) is identical
across categories; only 400/500 blocks differ (ADR-0005).

---

## Alternatives Considered

| Option | Rejected Because |
|---|---|
| 2-digit sequential entity (`11`) | No category meaning in code; matches register but no banding/roll-up by code |
| 2-digit banded (`C`+`E`) | Only 9 categories × 9 entities — at the ceiling on day one |
| **3-digit banded (`C`+`NN`)** | **Chosen** — category readable from code, 99 entities/category headroom |
| Category in a separate column only | Codes not self-identifying; weaker cross-entity reporting/exports |
| Storing only the composed string | Forces string parsing for every roll-up; fragile |

---

## Consequences

**Easier:**
- Category is readable from the first digit; transport = `1xx`, cafeteria = `2xx`.
- Reports roll up by band / entity / main / sub with simple segment filters.
- 99 entities per category of headroom; codes sort and export cleanly.
- Entity + category ownership visible on every code; consolidation is mechanical.

**Harder:**
- Fixed width caps categories at 10 bands (0–9) and 99 entities each — plan bands.
- The earlier 2-digit codes (workbook v1) are superseded; any draft data must be
  re-coded (no posted data exists yet).
- Service-layer code generation is mandatory — manual code entry is disallowed.

---

## Risks

- **Band exhaustion** (>10 categories) — mitigated by the fact that the group has
  ~9–10 categories; a future ADR can widen the band if ever needed.
- **Entity-sequence exhaustion** (>99 in one category) — unlikely; flagged here.
- **`numeric_code` drift** — `numeric_code` is immutable once any account exists
  for the entity; band changes require a dedicated re-coding migration.
- **Cross-entity uniqueness** — enforced by the global unique constraint on `code`.

---

## Migration Notes

Initial structure — no posted data to migrate. The seed COA management command
(build step 3) generates codes through `apps/accounts/services/coding.py`, so the
scheme is enforced from the first row. The seed workbook
`FinCare_Chart_of_Accounts.xlsx` reflects this 3-digit banded scheme. If a band or
`numeric_code` must change later, provide a dedicated re-coding migration that
rewrites `code` for all affected accounts inside one transaction; never edit codes
ad hoc.
