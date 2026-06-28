# ERD — `ledger` & `vouchers` (Posting Engine)

**Project:** FinCare · **Phase:** 1 (foundation) · **Status:** Draft for review
**Scope:** the double-entry core. `ledger` owns journal entries, lines, periods
and the posting service; `vouchers` is the first set of source documents that
post *through* the ledger. AR/AP/banking documents (later) post the same way.
**Depends on:** `core`, `tenants`, `accounts` (see `01-erd-core-tenants-accounts.md`).

Conventions (from doc 01, applied here): UUID `id`; audit mixin
(`created_at/updated_at/created_by/updated_by`); soft delete where noted;
money = `numeric(18,2)`; rates = `numeric(18,6)`; every transactional row carries
`entity_id`. Audit/soft-delete columns omitted from grids for readability.

> **Golden rule (CLAUDE.md §4):** a journal entry may be posted only if
> `SUM(debit) == SUM(credit)`. Posted entries are immutable — corrected by
> reversal, never edited or deleted.

---

## App: `ledger`

### `ledger_accounting_period`

Fiscal periods per entity; posting is blocked outside an open period.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| entity_id | uuid | no | FK → tenants_entity | |
| fiscal_year | smallint | no | | e.g. 2026 |
| period_no | smallint | no | | 1–12 (or 1–13 with adjustment period) |
| name | varchar(32) | no | | "Jun-2026" |
| start_date | date | no | | |
| end_date | date | no | | |
| status | varchar(12) | no | IX | open / closed / locked |
| closed_at | timestamptz | yes | | |
| closed_by | uuid | yes | FK → users_user | |

> Unique: (`entity_id`, `fiscal_year`, `period_no`). `closed` blocks new postings
> but allows adjustments by a privileged role; `locked` blocks all.

### `ledger_journal_entry`

The posting header. Created by manual entry, a voucher, an AR/AP document, or a
system process; all converge here.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| entity_id | uuid | no | FK → tenants_entity | |
| branch_id | uuid | yes | FK → tenants_branch | |
| period_id | uuid | no | FK → ledger_accounting_period | resolved from entry_date |
| entry_no | varchar(24) | no | | gap-safe per entity+year via core_number_sequence; assigned at post |
| entry_date | date | no | IX | accounting date |
| basis | varchar(8) | no | | accrual / cash (see §Cash vs accrual) |
| source_type | varchar(16) | no | IX | manual / voucher / sales_invoice / purchase_bill / system / opening |
| source_id | uuid | yes | IX | id of the originating document (e.g. voucher) |
| narration | varchar(512) | yes | | |
| currency_id | uuid | no | FK → core_currency | document currency; default entity base |
| total_debit | numeric(18,2) | no | | base-currency total; must equal total_credit |
| total_credit | numeric(18,2) | no | | |
| status | varchar(12) | no | IX | draft / validated / posted / reversed / cancelled |
| reversal_of_id | uuid | yes | FK → ledger_journal_entry (self) | set on a reversing entry |
| reversed_by_id | uuid | yes | FK → ledger_journal_entry (self) | set on the original when reversed |
| posted_at | timestamptz | yes | | |
| posted_by | uuid | yes | FK → users_user | |

> A posted entry's rows are immutable (no soft delete, no edit). Indexes:
> (`entity_id`,`entry_date`), (`source_type`,`source_id`), (`status`).

### `ledger_journal_line`

The debit/credit lines. Carries the analytic dimensions that drive profitability.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| entry_id | uuid | no | FK → ledger_journal_entry | cascade with header lifecycle |
| line_no | smallint | no | | order within entry |
| account_id | uuid | no | FK → accounts_account | must be postable & active |
| description | varchar(512) | yes | | |
| debit | numeric(18,2) | no | | document currency; one of debit/credit is 0 |
| credit | numeric(18,2) | no | | |
| fx_rate | numeric(18,6) | no | | doc→base; 1 if same currency |
| base_debit | numeric(18,2) | no | | debit × fx_rate |
| base_credit | numeric(18,2) | no | | credit × fx_rate |
| cost_center_id | uuid | yes | FK → tenants_cost_center | |
| party_type | varchar(12) | yes | | customer / supplier / null (for control accounts) |
| party_id | uuid | yes | IX | FK to ar_customer / ap_supplier (resolved by party_type) |
| vehicle_id | uuid | yes | FK → fleet_vehicle | profitability dim (nullable) |
| driver_id | uuid | yes | FK → drivers_driver | profitability dim (nullable) |
| platform_id | uuid | yes | FK → platforms_platform | profitability dim (nullable) |
| tax_code_id | uuid | yes | FK → accounts_tax_code | VAT treatment for this line |
| tax_amount | numeric(18,2) | yes | | VAT portion, if any |

> Line rule: exactly one of (`debit`,`credit`) is non-zero. Control accounts
> require `party_type`+`party_id`. Profitability dims are optional and populated
> when the line belongs to a vehicle/driver/platform.

### Journal entry lifecycle

```
        ┌─────────┐  validate   ┌───────────┐   post    ┌────────┐
        │  draft  ├────────────►│ validated ├──────────►│ posted │
        └────┬────┘             └─────┬─────┘           └───┬────┘
             │ cancel                 │ cancel              │ reverse
             ▼                        ▼                     ▼
        ┌───────────┐           ┌───────────┐         ┌──────────┐
        │ cancelled │           │ cancelled │         │ reversed │  (+ new reversing entry, posted)
        └───────────┘           └───────────┘         └──────────┘
```

- `draft` → editable.
- `validate` → checks balance, accounts, period; no GL effect yet.
- `post` → assigns `entry_no`, sets `posted_at/by`, becomes immutable; this is
  the point of GL effect.
- `reverse` → original → `reversed`; a new mirror entry (debits/credits swapped)
  is created and posted, linked via `reversal_of_id` / `reversed_by_id`.
- `cancel` → only from draft/validated (never from posted).

### Posting service contract (`apps/ledger/services/posting.py`)

```python
def post_journal_entry(entry: JournalEntry, *, user) -> JournalEntry:
    """Atomic. Raises if invalid. Returns the posted entry."""
    with transaction.atomic():
        _assert_status(entry, in_={"draft", "validated"})
        _assert_balanced(entry)            # SUM(base_debit) == SUM(base_credit), != 0
        _assert_lines_valid(entry)         # each line: one side only; account postable & active
        _assert_period_open(entry)         # period for entry_date is open
        _assert_control_party(entry)       # control accounts carry party_type+party_id
        entry.entry_no = sequences.next("JE", entity=entry.entity_id, year=...)
        entry.status = "posted"
        entry.posted_at, entry.posted_by = now(), user
        entry.save(); entry.lines.bulk_save()
    return entry

def reverse_journal_entry(entry, *, user, date=None) -> JournalEntry: ...
```

Rules: no `DELETE` of posted rows; reversal only. All money math in `Decimal`.
Every new posting path ships with a unit test proving `debit == credit`
(CLAUDE.md §7).

---

## App: `vouchers`

A single `Voucher` model with a `voucher_type` discriminator covers the five
voucher kinds; each posts **through** `ledger.services.posting`, never writing GL
rows directly.

### `vouchers_voucher`

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| entity_id | uuid | no | FK → tenants_entity | |
| branch_id | uuid | yes | FK → tenants_branch | |
| voucher_type | varchar(12) | no | IX | receipt / payment / contra / journal / expense |
| voucher_no | varchar(24) | no | | gap-safe per entity+type+year; assigned at post |
| voucher_date | date | no | IX | |
| party_type | varchar(12) | yes | | customer / supplier / other |
| party_id | uuid | yes | | resolved by party_type |
| payment_mode | varchar(12) | yes | | cash / bank / card / cheque / online |
| bank_account_id | uuid | yes | FK → accounts_account | cash/bank account (is_bank_account or cash) |
| cheque_no | varchar(32) | yes | | |
| reference | varchar(64) | yes | | external ref |
| narration | varchar(512) | yes | | |
| currency_id | uuid | no | FK → core_currency | |
| amount | numeric(18,2) | no | | header total (sum of lines) |
| status | varchar(12) | no | IX | draft / validated / posted / reversed / cancelled |
| journal_entry_id | uuid | yes | FK → ledger_journal_entry | the posted JE (set at post) |
| posted_at | timestamptz | yes | | |
| posted_by | uuid | yes | FK → users_user | |

> Unique: (`entity_id`, `voucher_type`, `voucher_no`).

### `vouchers_voucher_line`

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| voucher_id | uuid | no | FK → vouchers_voucher | |
| line_no | smallint | no | | |
| account_id | uuid | no | FK → accounts_account | |
| description | varchar(512) | yes | | |
| debit | numeric(18,2) | no | | one side only |
| credit | numeric(18,2) | no | | |
| cost_center_id | uuid | yes | FK → tenants_cost_center | |
| vehicle_id | uuid | yes | FK → fleet_vehicle | |
| driver_id | uuid | yes | FK → drivers_driver | |
| platform_id | uuid | yes | FK → platforms_platform | |
| tax_code_id | uuid | yes | FK → accounts_tax_code | |

### Voucher posting (`apps/vouchers/services/post.py`)

On `post`, the service builds a `JournalEntry` (header + lines mapped 1:1 from
voucher lines, dimensions copied) with `source_type="voucher"`,
`source_id=voucher.id`, then calls `ledger.services.posting.post_journal_entry`.
The returned entry id is stored on `voucher.journal_entry_id`. Voucher and entry
share the same lifecycle; reversing the voucher reverses its entry.

Standard mappings (CLAUDE.md §4):

| Voucher | Debit | Credit |
|---|---|---|
| Receipt | Bank / Cash | Customer (AR) / Income |
| Payment | Supplier (AP) / Expense | Bank / Cash |
| Contra | Bank/Cash A | Bank/Cash B (e.g. cash deposit to bank) |
| Expense | Expense + Input VAT | Cash / Bank / Supplier |
| Journal | per lines | per lines |

---

## Cash vs accrual handling

- Every entry records `basis`. Accrual documents (invoices, bills, accruals) post
  with `basis="accrual"`; pure cash movements (cash receipts/payments) with
  `basis="cash"`.
- **Accrual reports** use all posted entries. **Cash-basis reports** are derived
  by following cash/bank-affecting postings (entries that touch a `cash`/`bank`
  account), so the same ledger serves both views without duplicate books.
- Entity default basis is `tenants_entity.accounting_basis`; an entry may override
  per document type.

> **Open decision (CB-1):** confirm cash-basis P&L is derived (recommended) vs.
> maintaining parallel cash-basis entries. Default: derived.

---

## Validation rules (enforced in services, asserted in tests)

1. `SUM(base_debit) == SUM(base_credit)` and total ≠ 0.
2. Each line has exactly one of debit/credit non-zero.
3. `account.is_postable` and `account.is_active`; manual posting blocked on
   control accounts (`allow_manual_posting = false`).
4. Control-account lines carry `party_type` + `party_id`.
5. `entry_date` falls in an `open` period (or `closed` with adjustment right).
6. Currency lines carry `fx_rate`; base amounts = amount × fx_rate.
7. Posted entries cannot be edited, soft-deleted, or hard-deleted — reversal only.
8. `voucher.amount` equals the sum of its lines and the resulting entry total.

---

## Relationship summary

```
tenants_entity ──< ledger_accounting_period ──< ledger_journal_entry ──< ledger_journal_line >── accounts_account
ledger_journal_entry ──(reversal_of / reversed_by)── ledger_journal_entry  (self)
vouchers_voucher ──< vouchers_voucher_line >── accounts_account
vouchers_voucher ──(1:1 at post)── ledger_journal_entry
ledger_journal_line >── tenants_cost_center, fleet_vehicle, drivers_driver,
                        platforms_platform, accounts_tax_code, (party: ar_customer/ap_supplier)
```

## Open decisions

1. **CB-1 — Cash basis:** derived from cash/bank-touching entries (recommended)
   vs. parallel cash-basis books. Default: derived.
2. **Voucher model:** single `Voucher` + `voucher_type` (shown, recommended) vs.
   one model per voucher type. Default: single, polymorphic by type.
3. **Profitability dims on the line:** explicit FKs (`vehicle_id`, `driver_id`,
   `platform_id`, shown) vs. a generic analytic-tag table. Default: explicit FKs
   for the known Phase-1 dims; revisit if dims proliferate.
4. **entry_no scope:** per entity + fiscal year (shown) vs. per entity + period.
   Default: per entity + fiscal year.
