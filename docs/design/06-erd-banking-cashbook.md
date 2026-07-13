# ERD — `banking` & `cashbook` (Bank, Cash, Reconciliation)

**Project:** FinCare · **Phase:** 1 (foundation) · **Status:** Draft for review
**Scope:** management of bank and cash accounts beyond plain receipts/payments —
bank metadata, transfers/deposits, statement import & reconciliation, card/POS
settlement, petty-cash imprest, and physical cash counts. Money still posts
**through** the ledger engine (ADR-0007); these apps add the bank/cash-specific
documents and the reconciliation layer.
**Depends on:** `core`, `tenants`, `accounts`, `ledger`, `vouchers`.

Conventions (doc 01): UUID `id`; audit mixin; soft delete where noted;
money = `numeric(18,2)`; every row carries `entity_id`. Audit/soft-delete columns
omitted from grids.

> A bank/cash **GL account** lives in `accounts_account` (110 Cash & Bank, with
> `is_bank_account` / `account_type='cash'`). The tables below hold the *extra*
> operational data (IBAN, custodian, statements) and link 1:1 to that GL account.

---

## App: `banking`

### `banking_bank_account`

Bank-specific metadata for a GL bank account.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| entity_id | uuid | no | FK → tenants_entity | |
| gl_account_id | uuid | no | FK → accounts_account | the 110 bank account; `is_bank_account=true` |
| bank_name | varchar(128) | no | | ENBD, ADCB, … |
| account_title | varchar(255) | yes | | |
| account_no | varchar(34) | yes | | |
| iban | varchar(34) | yes | UQ | |
| swift | varchar(16) | yes | | |
| branch | varchar(128) | yes | | |
| currency_id | uuid | no | FK → core_currency | |
| is_active | boolean | no | | |

> Unique: (`entity_id`, `gl_account_id`) 1:1. Balance is read from the GL account.

### `banking_bank_transfer`

Movement between two own cash/bank accounts (incl. cash deposit to bank). Posts a
contra entry: DR destination / CR source (+ DR charges if any).

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| entity_id | uuid | no | FK → tenants_entity | |
| transfer_no | varchar(24) | no | | gap-safe; assigned at post |
| transfer_date | date | no | IX | |
| from_account_id | uuid | no | FK → accounts_account | source cash/bank |
| to_account_id | uuid | no | FK → accounts_account | destination cash/bank |
| transfer_type | varchar(16) | no | | bank_transfer / cash_deposit / cash_withdrawal |
| amount | numeric(18,2) | no | | |
| charges | numeric(18,2) | no | | bank charges (DR Bank Charges) |
| charges_account_id | uuid | yes | FK → accounts_account | 640 Bank Charges |
| reference | varchar(64) | yes | | |
| status | varchar(12) | no | IX | draft / validated / posted / reversed / cancelled |
| journal_entry_id | uuid | yes | FK → ledger_journal_entry | |

> Unique: (`entity_id`, `transfer_no`). `from` and `to` must differ.

### `banking_bank_statement`

Imported statement header for one bank account / period.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| entity_id | uuid | no | FK → tenants_entity | |
| bank_account_id | uuid | no | FK → banking_bank_account | |
| statement_date | date | no | | |
| opening_balance | numeric(18,2) | no | | per statement |
| closing_balance | numeric(18,2) | no | | per statement |
| source | varchar(16) | no | | upload / api |
| imported_at | timestamptz | yes | | |

### `banking_statement_line`

Raw statement lines staged for matching.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| statement_id | uuid | no | FK → banking_bank_statement | |
| line_date | date | no | IX | |
| description | varchar(512) | yes | | |
| reference | varchar(64) | yes | | cheque no / ref |
| debit | numeric(18,2) | no | | money out (per bank) |
| credit | numeric(18,2) | no | | money in |
| running_balance | numeric(18,2) | yes | | |
| matched | boolean | no | IX | reconciled? |
| matched_line_id | uuid | yes | FK → ledger_journal_line | the GL line it matched |

### `banking_reconciliation`

A reconciliation of book vs statement for an account up to a date.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| entity_id | uuid | no | FK → tenants_entity | |
| bank_account_id | uuid | no | FK → banking_bank_account | |
| statement_id | uuid | yes | FK → banking_bank_statement | |
| recon_date | date | no | | as-of |
| book_balance | numeric(18,2) | no | | GL balance |
| statement_balance | numeric(18,2) | no | | bank balance |
| reconciled_balance | numeric(18,2) | no | | after items |
| difference | numeric(18,2) | no | | must be 0 to finalise |
| status | varchar(12) | no | IX | in_progress / reconciled |
| reconciled_by | uuid | yes | FK → users_user | |

### `banking_reconciliation_item`

Reconciling items (unpresented cheques, deposits in transit, bank-only charges).

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| reconciliation_id | uuid | no | FK → banking_reconciliation | |
| item_type | varchar(24) | no | | unpresented_cheque / deposit_in_transit / bank_charge / interest / error |
| description | varchar(512) | yes | | |
| amount | numeric(18,2) | no | | signed |
| source | varchar(8) | no | | book / bank |
| resolved | boolean | no | | cleared in a later period? |

### `banking_pos_settlement`

Card-machine / POS settlement to bank, net of fees. Posts: DR Bank + DR POS Fee /
CR POS Clearing (the clearing account credited when card sales were recorded).

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| entity_id | uuid | no | FK → tenants_entity | |
| terminal_ref | varchar(64) | yes | | POS terminal id |
| settlement_date | date | no | IX | |
| gross_amount | numeric(18,2) | no | | card sales settled |
| fee_amount | numeric(18,2) | no | | acquirer fee |
| net_amount | numeric(18,2) | no | | credited to bank |
| bank_account_id | uuid | no | FK → banking_bank_account | |
| clearing_account_id | uuid | no | FK → accounts_account | POS clearing (110-020) |
| fee_account_id | uuid | no | FK → accounts_account | 640 Bank/Card Charges |
| status | varchar(12) | no | | draft / posted |
| journal_entry_id | uuid | yes | FK → ledger_journal_entry | |

### Refunds & duplicate-payment handling (rules, not tables)

- **Refunds** are modelled as a payment voucher to the customer (or a credit-note
  settlement), reversing the original receipt — no special table.
- **Duplicate payments** are guarded at voucher entry: the service warns on a
  matching (party, amount, reference, date-window) and on re-use of a cleared
  cheque/reference. Detected duplicates are corrected by reversal (ADR-0007).

---

## App: `cashbook`

### `cashbook_cash_account`

Operational metadata for a GL cash account (incl. petty cash).

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| entity_id | uuid | no | FK → tenants_entity | |
| gl_account_id | uuid | no | FK → accounts_account | 110 cash account; `account_type='cash'` |
| name | varchar(128) | no | | "Main Cash", "Counter Till 1" |
| branch_id | uuid | yes | FK → tenants_branch | |
| custodian_id | uuid | yes | FK → users_user | accountable person |
| is_petty_cash | boolean | no | | imprest float? |
| is_active | boolean | no | | |

> Unique: (`entity_id`, `gl_account_id`) 1:1.

### `cashbook_petty_cash_float`

Imprest float setup per petty-cash account.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| cash_account_id | uuid | no | FK → cashbook_cash_account | |
| imprest_amount | numeric(18,2) | no | | target float |
| effective_from | date | no | | |
| is_active | boolean | no | | |

### `cashbook_replenishment`

Top-up of a petty-cash float from bank. Posts: DR Petty Cash / CR Bank.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| entity_id | uuid | no | FK → tenants_entity | |
| cash_account_id | uuid | no | FK → cashbook_cash_account | |
| bank_account_id | uuid | no | FK → banking_bank_account | source |
| replenish_date | date | no | | |
| amount | numeric(18,2) | no | | restores float to imprest |
| status | varchar(12) | no | | draft / posted |
| journal_entry_id | uuid | yes | FK → ledger_journal_entry | |

### `cashbook_cash_count`

Physical count vs book balance for a cash account on a date; variance posted to a
cash short/over account.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| entity_id | uuid | no | FK → tenants_entity | |
| cash_account_id | uuid | no | FK → cashbook_cash_account | |
| count_date | date | no | IX | |
| counted_amount | numeric(18,2) | no | | physical total |
| book_balance | numeric(18,2) | no | | GL balance at date |
| variance | numeric(18,2) | no | | counted − book |
| variance_account_id | uuid | yes | FK → accounts_account | Cash Short/Over (640/420) |
| status | varchar(12) | no | | draft / posted |
| journal_entry_id | uuid | yes | FK → ledger_journal_entry | variance adjustment |
| counted_by | uuid | yes | FK → users_user | |

### `cashbook_cash_count_denomination`

Optional denomination breakdown supporting a count.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| count_id | uuid | no | FK → cashbook_cash_count | |
| denomination | numeric(10,2) | no | | 1000/500/200/100/50/20/10/5/1/0.50/0.25 |
| quantity | integer | no | | |
| amount | numeric(18,2) | no | | denomination × quantity |

> `SUM(amount)` must equal the count's `counted_amount`.

---

## Posting & reconciliation flows

```
BANK TRANSFER / CASH DEPOSIT   DR To Account (+ DR Bank Charges)   CR From Account
POS SETTLEMENT                 DR Bank + DR POS Fee                CR POS Clearing
PETTY CASH REPLENISHMENT       DR Petty Cash                       CR Bank
BANK CHARGE (from statement)   DR Bank Charges                     CR Bank
BANK INTEREST (from statement) DR Bank                             CR Interest Income
CASH COUNT VARIANCE (short)    DR Cash Short/Over                  CR Cash
CASH COUNT VARIANCE (over)     DR Cash                             CR Cash Short/Over

RECONCILIATION
  import statement → auto-match statement_line ↔ ledger_journal_line
  (by amount + date window + reference) → unmatched become
  banking_reconciliation_item → finalise when difference = 0
  bank-only items (charges/interest) are posted as adjusting entries
```

---

## Relationship summary

```
accounts_account (110) ──1:1── banking_bank_account / cashbook_cash_account
banking_bank_account ──< banking_bank_statement ──< banking_statement_line >── ledger_journal_line (match)
banking_bank_account ──< banking_reconciliation ──< banking_reconciliation_item
banking_bank_transfer / banking_pos_settlement ──(1:1 at post)── ledger_journal_entry
cashbook_cash_account ──< cashbook_petty_cash_float, cashbook_replenishment, cashbook_cash_count
cashbook_cash_count ──< cashbook_cash_count_denomination
cashbook_replenishment / cashbook_cash_count ──(1:1)── ledger_journal_entry
```

## Open decisions

1. **Statement auto-match:** rule-based (amount + date window + reference, shown)
   vs. ML/fuzzy matching. Default: rule-based with manual override.
2. **Statement import format:** start with CSV/XLSX upload (mapped per bank) and
   add bank APIs later. Default: file upload first.
3. **POS clearing vs direct-to-bank:** route card sales via a POS clearing account
   then settle (shown — supports fee/variance) vs. booking straight to bank.
   Default: clearing account.
4. **Cash short/over treatment:** to an expense/income account (shown) vs. holding
   in a suspense account pending investigation. Default: short/over account, with
   suspense for amounts above a configurable threshold.
