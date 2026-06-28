# ERD — `ar`, `ap` & `tax` (Receivables, Payables, UAE VAT)

**Project:** FinCare · **Phase:** 1 (foundation) · **Status:** Draft for review
**Scope:** customer & supplier subledgers and the documents that drive them
(invoices, bills, credit/debit notes, allocations), plus UAE VAT return
generation and Corporate Tax tagging. All documents post **through** the ledger
engine (`02-erd-ledger-vouchers.md`); none write GL rows directly.
**Depends on:** `core`, `tenants`, `accounts`, `ledger`, `vouchers`.

Conventions (doc 01): UUID `id`; audit mixin; soft delete where noted;
money = `numeric(18,2)`; rate/qty = `numeric(18,6)`; every row carries
`entity_id`. Audit/soft-delete columns omitted from grids.

> Posting recap (CLAUDE.md §4): Sales Invoice → DR AR / CR Revenue / CR Output
> VAT. Purchase Bill → DR Expense or Asset / DR Input VAT / CR AP. Receipts &
> payments are vouchers; this app records the **allocation** of those vouchers
> against open invoices/bills.

---

## App: `ar` (Accounts Receivable)

### `ar_customer`

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| entity_id | uuid | no | FK → tenants_entity | per-entity master (shared option via group flag) |
| code | varchar(24) | no | | unique within entity |
| name | varchar(255) | no | | |
| trn | varchar(15) | yes | IX | customer VAT TRN (for B2B / reverse charge) |
| customer_type | varchar(12) | no | | b2b / b2c / corporate / platform |
| receivable_account_id | uuid | no | FK → accounts_account | AR control account (subledger=customer) |
| currency_id | uuid | no | FK → core_currency | default billing currency |
| credit_limit | numeric(18,2) | yes | | |
| credit_days | smallint | yes | | payment terms |
| email | varchar(255) | yes | | |
| phone | varchar(32) | yes | | |
| address | varchar(512) | yes | | |
| emirate | varchar(32) | yes | | default place of supply |
| opening_balance | numeric(18,2) | no | | posted via opening journal |
| is_active | boolean | no | | |

> Unique: (`entity_id`, `code`). Balances are derived from the ledger control
> account filtered by `party_id`; not stored here.

### `ar_sales_invoice`

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| entity_id | uuid | no | FK → tenants_entity | |
| branch_id | uuid | yes | FK → tenants_branch | |
| customer_id | uuid | no | FK → ar_customer | |
| invoice_no | varchar(24) | no | | gap-safe per entity+year (core_number_sequence); assigned at post |
| invoice_date | date | no | IX | tax point |
| due_date | date | yes | | from credit_days |
| place_of_supply | varchar(32) | no | | emirate — drives VAT 201 box (1a–1g) |
| currency_id | uuid | no | FK → core_currency | |
| fx_rate | numeric(18,6) | no | | doc→base |
| subtotal | numeric(18,2) | no | | sum of line amounts (pre-VAT) |
| tax_total | numeric(18,2) | no | | sum of line VAT |
| total | numeric(18,2) | no | | subtotal + tax_total |
| amount_allocated | numeric(18,2) | no | | receipts/credit notes applied |
| balance | numeric(18,2) | no | | total − amount_allocated |
| status | varchar(16) | no | IX | draft / validated / posted / partially_paid / paid / cancelled |
| journal_entry_id | uuid | yes | FK → ledger_journal_entry | set at post |
| narration | varchar(512) | yes | | |

> Unique: (`entity_id`, `invoice_no`). `balance`/`amount_allocated` maintained by
> the allocation service; `paid` when balance = 0.

### `ar_sales_invoice_line`

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| invoice_id | uuid | no | FK → ar_sales_invoice | |
| line_no | smallint | no | | |
| revenue_account_id | uuid | no | FK → accounts_account | a 400-band income account |
| description | varchar(512) | yes | | |
| quantity | numeric(18,6) | no | | default 1 |
| unit_price | numeric(18,2) | no | | |
| line_amount | numeric(18,2) | no | | qty × unit_price (pre-VAT) |
| tax_code_id | uuid | no | FK → accounts_tax_code | SR/ZR/EX/OS/RC |
| tax_rate | numeric(6,3) | no | | snapshot of code rate at invoice date |
| tax_amount | numeric(18,2) | no | | line_amount × tax_rate |
| cost_center_id | uuid | yes | FK → tenants_cost_center | |
| vehicle_id | uuid | yes | FK → fleet_vehicle | profitability dim |
| driver_id | uuid | yes | FK → drivers_driver | profitability dim |
| platform_id | uuid | yes | FK → platforms_platform | profitability dim |

### `ar_credit_note` / `ar_credit_note_line`

Mirror of invoice/line; reduces receivable and reverses output VAT. Header adds
`original_invoice_id` (FK → ar_sales_invoice, nullable) and `reason`. Posts:
DR Sales Revenue / DR Output VAT / CR Accounts Receivable.

### `ar_receipt_allocation`

Links money/credit (a receipt voucher, credit note, or advance) to specific open
invoices. The cash side is the receipt **voucher** (doc 02); this row records
*how much of it* settles *which* invoice.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| entity_id | uuid | no | FK → tenants_entity | |
| customer_id | uuid | no | FK → ar_customer | |
| source_type | varchar(16) | no | | receipt_voucher / credit_note / advance |
| source_id | uuid | no | IX | the voucher / credit note id |
| invoice_id | uuid | no | FK → ar_sales_invoice | invoice being settled |
| amount_allocated | numeric(18,2) | no | | |
| allocation_date | date | no | | |

> Sum of allocations against an invoice ≤ invoice.total. Unallocated receipts =
> customer advance (sits on AR control as a credit until applied).

---

## App: `ap` (Accounts Payable)

Structural mirror of `ar`.

### `ap_supplier`

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| entity_id | uuid | no | FK → tenants_entity | |
| code | varchar(24) | no | | unique within entity |
| name | varchar(255) | no | | |
| trn | varchar(15) | yes | IX | supplier TRN (input VAT claim, reverse charge) |
| payable_account_id | uuid | no | FK → accounts_account | AP control (subledger=supplier) |
| currency_id | uuid | no | FK → core_currency | |
| credit_days | smallint | yes | | |
| email / phone / address | varchar | yes | | contact |
| opening_balance | numeric(18,2) | no | | |
| is_active | boolean | no | | |

> Unique: (`entity_id`, `code`).

### `ap_purchase_bill`

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| entity_id | uuid | no | FK → tenants_entity | |
| branch_id | uuid | yes | FK → tenants_branch | |
| supplier_id | uuid | no | FK → ap_supplier | |
| bill_no | varchar(24) | no | | internal gap-safe no; assigned at post |
| supplier_invoice_no | varchar(64) | yes | | supplier's own reference |
| bill_date | date | no | IX | tax point |
| due_date | date | yes | | |
| currency_id | uuid | no | FK → core_currency | |
| fx_rate | numeric(18,6) | no | | |
| subtotal | numeric(18,2) | no | | |
| tax_total | numeric(18,2) | no | | recoverable input VAT |
| total | numeric(18,2) | no | | |
| amount_allocated | numeric(18,2) | no | | payments/debit notes applied |
| balance | numeric(18,2) | no | | |
| is_reverse_charge | boolean | no | | import / RCM: input + output VAT both raised |
| status | varchar(16) | no | IX | draft / validated / posted / partially_paid / paid / cancelled |
| journal_entry_id | uuid | yes | FK → ledger_journal_entry | |

> Unique: (`entity_id`, `bill_no`).

### `ap_purchase_bill_line`

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| bill_id | uuid | no | FK → ap_purchase_bill | |
| line_no | smallint | no | | |
| account_id | uuid | no | FK → accounts_account | expense (500/600) or asset (100) |
| description | varchar(512) | yes | | |
| quantity | numeric(18,6) | no | | |
| unit_price | numeric(18,2) | no | | |
| line_amount | numeric(18,2) | no | | |
| tax_code_id | uuid | no | FK → accounts_tax_code | |
| tax_rate | numeric(6,3) | no | | snapshot |
| tax_amount | numeric(18,2) | no | | |
| recoverable | boolean | no | | input VAT recoverable? (blocked items not) |
| cost_center_id | uuid | yes | FK → tenants_cost_center | |
| vehicle_id | uuid | yes | FK → fleet_vehicle | per-vehicle cost capture |
| driver_id | uuid | yes | FK → drivers_driver | per-driver cost capture |

### `ap_debit_note` / `ap_debit_note_line`

Mirror; reduces payable and reverses input VAT. Adds `original_bill_id`, `reason`.

### `ap_payment_allocation`

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| entity_id | uuid | no | FK → tenants_entity | |
| supplier_id | uuid | no | FK → ap_supplier | |
| source_type | varchar(16) | no | | payment_voucher / debit_note / advance |
| source_id | uuid | no | IX | |
| bill_id | uuid | no | FK → ap_purchase_bill | |
| amount_allocated | numeric(18,2) | no | | |
| allocation_date | date | no | | |

---

## Aging (derived, not stored)

Customer and supplier aging (current / 30 / 60 / 90 / 120+) are **computed** from
open invoices/bills (`balance > 0`) bucketed by `due_date` vs. report date. No
aging tables; a service/query produces the report and Excel/PDF export.

---

## App: `tax` (UAE VAT & Corporate Tax)

VAT is reported **per VAT group** (shared TRN, ADR-0006), aggregating all member
entities for the period. Rates and box structure are configuration/data — never
hardcoded literals (CLAUDE.md §4.8).

### `tax_code_rate_history`

Effective-dated rates for `accounts_tax_code` (resolves doc 01 open decision #3).

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| tax_code_id | uuid | no | FK → accounts_tax_code | |
| rate | numeric(6,3) | no | | e.g. 5.000 |
| effective_from | date | no | | |
| effective_to | date | yes | | null = current |

> A document line snapshots the rate effective on its tax point (`tax_rate` on
> the invoice/bill line) so historical returns stay correct.

### `tax_return`

One VAT return per VAT group per tax period.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| vat_group_id | uuid | no | FK → tenants_vat_group | the shared TRN |
| period_start | date | no | | |
| period_end | date | no | | monthly / quarterly per FTA |
| status | varchar(12) | no | IX | draft / finalised / filed |
| output_vat | numeric(18,2) | no | | total VAT on sales (Box 8 area) |
| input_vat | numeric(18,2) | no | | recoverable VAT on purchases (Box 11 area) |
| adjustments | numeric(18,2) | no | | corrections / bad-debt relief |
| net_payable | numeric(18,2) | no | | output − input ± adjustments |
| filed_at | timestamptz | yes | | |
| filed_by | uuid | yes | FK → users_user | |

> Unique: (`vat_group_id`, `period_start`, `period_end`). Figures are aggregated
> from posted ledger lines carrying a `tax_code`, across **all member entities**.

### `tax_return_box`

The FTA VAT 201 box breakdown for a return (data-driven template, incl. the
emirate split for standard-rated supplies).

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| tax_return_id | uuid | no | FK → tax_return | |
| box_code | varchar(8) | no | | "1a".."1g", "3", "4", "5", "6", "9", … |
| label | varchar(128) | no | | "Standard rated supplies — Dubai" |
| emirate | varchar(32) | yes | | for box 1a–1g |
| net_amount | numeric(18,2) | no | | taxable base |
| vat_amount | numeric(18,2) | no | | VAT amount |

> Box rows are generated from configuration + the period's tax lines, so the
> return structure can track FTA changes without code edits.

### `corporate_tax_return`

Per **entity** (CT is per entity, never shared — ADR-0006), per fiscal year.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| entity_id | uuid | no | FK → tenants_entity | |
| fiscal_year | smallint | no | | |
| accounting_profit | numeric(18,2) | no | | from P&L |
| adjustments | numeric(18,2) | no | | add-backs / exemptions |
| taxable_income | numeric(18,2) | no | | |
| tax_rate | numeric(6,3) | no | | config-driven (e.g. 9% above threshold) |
| tax_payable | numeric(18,2) | no | | |
| status | varchar(12) | no | | draft / filed |

> Unique: (`entity_id`, `fiscal_year`). Small Business Relief / thresholds are
> configuration, evaluated by a service — not hardcoded.

---

## VAT computation flow

```
posted ledger_journal_line (tax_code_id, tax_amount, account nature)
        │  filter: period, member entities of the VAT group
        ▼
   classify by tax_code.treatment + account direction (output vs input)
        │
        ├─► output VAT  ─┐
        ├─► input VAT   ─┤→ tax_return_box rows (incl. emirate split)
        └─► adjustments ─┘
        ▼
   tax_return totals  →  VAT 201 export (Excel / FTA file)
```

---

## Relationship summary

```
ar_customer ──< ar_sales_invoice ──< ar_sales_invoice_line >── accounts_account, accounts_tax_code
ar_customer ──< ar_credit_note ──< ar_credit_note_line
ar_receipt_allocation >── ar_sales_invoice, vouchers_voucher (receipt)
ap_supplier ──< ap_purchase_bill ──< ap_purchase_bill_line
ap_payment_allocation >── ap_purchase_bill, vouchers_voucher (payment)
ar_sales_invoice / ap_purchase_bill ──(1:1 at post)── ledger_journal_entry
tenants_vat_group ──< tax_return ──< tax_return_box
tenants_entity ──< corporate_tax_return
accounts_tax_code ──< tax_code_rate_history
```

## Open decisions

1. **Shared masters:** customer/supplier per-entity (shown) vs. group-shared with
   per-entity AR/AP accounts. Default: per-entity, with a future "shared party"
   flag. (Ties to multi-entity §5.)
2. **Allocation granularity:** explicit allocation rows (shown, supports partial &
   cross-document) vs. simple FIFO auto-match. Default: explicit allocations.
3. **VAT period:** monthly vs. quarterly — per FTA assignment; store on the VAT
   group. Default: configurable per group.
4. **Reverse charge / import VAT:** modelled via `is_reverse_charge` raising both
   output and input VAT lines. Confirm treatment for tour (margin scheme) and
   pharmacy (zero-rated) categories with the tax advisor.
