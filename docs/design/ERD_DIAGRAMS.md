# FinCare — ERD Diagrams

Visual entity-relationship diagrams for the Phase-1 schema, grouped by domain
(matching design docs 01–07). Mermaid renders on GitHub and in most Markdown
viewers. Each diagram shows primary keys (PK), unique keys (UK), and the key
foreign keys (FK); full columns are in the design docs and `DATA_DICTIONARY.md`,
all relationships in `FinCare_Relationships.xlsx`.

Crow's-foot reading: `||--o{` = one-to-many (parent to child); `||--o|` =
one-to-(zero/one); `}o--||` = many-to-one.

---

## 0. Module overview

How the apps depend on one another. Everything monetary posts through `ledger`
(ADR-0007).

```mermaid
flowchart TD
  core --> users
  core --> tenants
  core --> settings
  users --> audit
  users --> tenants
  tenants --> accounts
  accounts --> ledger
  ledger --> vouchers
  ledger --> ar
  ledger --> ap
  ar --> tax
  ap --> tax
  ledger --> banking
  banking --> cashbook
  ledger --> fleet
  ledger --> drivers
  fleet --> bookings
  drivers --> bookings
  platforms --> bookings
  ledger --> payroll
  ledger --> reports
  ar --> reports
  ap --> reports
  tax --> reports
  reports --> exports
  banking --> integrations
  platforms --> integrations

  classDef keystone fill:#FCE4D6,stroke:#C55A11,stroke-width:2px;
  class ledger keystone;
```

---

## 1. Core · Tenants · Accounts (doc 01)

```mermaid
erDiagram
  core_currency ||--o{ tenants_entity : "base ccy"
  core_currency ||--o{ accounts_account : "ccy"
  core_currency ||--o{ core_exchange_rate : "from/to"
  tenants_business_category ||--o{ tenants_entity : "category+band"
  tenants_vat_group ||--o{ tenants_entity : "shared TRN"
  tenants_entity ||--o{ tenants_branch : has
  tenants_entity ||--o{ tenants_cost_center : has
  tenants_entity ||--o{ tenants_department : has
  tenants_entity ||--o{ core_number_sequence : numbers
  tenants_entity ||--o{ accounts_account_group : owns
  tenants_entity ||--o{ accounts_tax_code : owns
  tenants_entity ||--o| tenants_entity : "parent (consolidation)"
  tenants_intercompany_map }o--|| tenants_entity : "from / to"
  accounts_account_group ||--o{ accounts_account_group : "Main to Sub"
  accounts_account_group ||--o{ accounts_account : "charge leaf"
  accounts_account ||--o{ accounts_tax_code : "VAT control"

  tenants_business_category {
    uuid id PK
    varchar key UK
    char band UK
    varchar coa_template_key
  }
  tenants_vat_group {
    uuid id PK
    varchar code UK
    varchar trn UK
  }
  tenants_entity {
    uuid id PK
    char numeric_code UK
    uuid category_id FK
    uuid vat_group_id FK
    varchar corporate_tax_trn
    varchar accounting_basis
  }
  accounts_account_group {
    uuid id PK
    smallint level
    char segment
    uuid parent_id FK
    varchar nature
  }
  accounts_account {
    uuid id PK
    char code UK
    uuid sub_group_id FK
    char charge_segment
    varchar account_type
    char normal_balance
    bool is_control_account
  }
  accounts_tax_code {
    uuid id PK
    varchar code
    decimal rate
    varchar treatment
  }
```

---

## 2. Ledger · Vouchers — the posting engine (doc 02)

```mermaid
erDiagram
  tenants_entity ||--o{ ledger_accounting_period : has
  ledger_accounting_period ||--o{ ledger_journal_entry : gates
  ledger_journal_entry ||--o{ ledger_journal_line : lines
  ledger_journal_entry ||--o| ledger_journal_entry : "reversal_of"
  accounts_account ||--o{ ledger_journal_line : posts
  vouchers_voucher ||--o{ vouchers_voucher_line : lines
  vouchers_voucher ||--o| ledger_journal_entry : "posts (1:1)"
  accounts_account ||--o{ vouchers_voucher_line : uses

  ledger_accounting_period {
    uuid id PK
    smallint fiscal_year
    smallint period_no
    varchar status
  }
  ledger_journal_entry {
    uuid id PK
    varchar entry_no
    date entry_date
    varchar basis
    varchar source_type
    decimal total_debit
    decimal total_credit
    varchar status
    uuid reversal_of_id FK
  }
  ledger_journal_line {
    uuid id PK
    uuid entry_id FK
    uuid account_id FK
    decimal base_debit
    decimal base_credit
    uuid cost_center_id FK
    uuid vehicle_id FK
    uuid driver_id FK
    uuid platform_id FK
    uuid tax_code_id FK
  }
  vouchers_voucher {
    uuid id PK
    varchar voucher_type
    varchar voucher_no
    date voucher_date
    decimal amount
    varchar status
    uuid journal_entry_id FK
  }
```

---

## 3. AR · AP · Tax (doc 03)

```mermaid
erDiagram
  ar_customer ||--o{ ar_sales_invoice : bills
  ar_sales_invoice ||--o{ ar_sales_invoice_line : lines
  ar_customer ||--o{ ar_credit_note : issues
  ar_credit_note ||--o{ ar_credit_note_line : lines
  ar_sales_invoice ||--o{ ar_receipt_allocation : settled_by
  ar_sales_invoice ||--o| ledger_journal_entry : posts
  ap_supplier ||--o{ ap_purchase_bill : bills
  ap_purchase_bill ||--o{ ap_purchase_bill_line : lines
  ap_supplier ||--o{ ap_debit_note : issues
  ap_debit_note ||--o{ ap_debit_note_line : lines
  ap_purchase_bill ||--o{ ap_payment_allocation : settled_by
  ap_purchase_bill ||--o| ledger_journal_entry : posts
  tenants_vat_group ||--o{ tax_return : files
  tax_return ||--o{ tax_return_box : "VAT 201 boxes"
  tenants_entity ||--o{ corporate_tax_return : files
  accounts_tax_code ||--o{ tax_code_rate_history : history

  ar_customer {
    uuid id PK
    varchar code
    varchar trn
    uuid receivable_account_id FK
  }
  ar_sales_invoice {
    uuid id PK
    varchar invoice_no
    date invoice_date
    varchar place_of_supply
    decimal total
    decimal balance
    varchar status
  }
  ap_purchase_bill {
    uuid id PK
    varchar bill_no
    date bill_date
    decimal total
    bool is_reverse_charge
    varchar status
  }
  tax_return {
    uuid id PK
    uuid vat_group_id FK
    date period_start
    date period_end
    decimal output_vat
    decimal input_vat
    decimal net_payable
  }
  corporate_tax_return {
    uuid id PK
    uuid entity_id FK
    smallint fiscal_year
    decimal taxable_income
    decimal tax_payable
  }
```

---

## 4. Fleet · Drivers · Platforms · Bookings (doc 04)

```mermaid
erDiagram
  tenants_entity ||--o{ fleet_vehicle : owns
  fleet_vehicle ||--o{ fleet_vehicle_document : docs
  fleet_vehicle ||--o{ fleet_vehicle_loan : finance
  fleet_vehicle }o--o| drivers_driver : "current driver"
  fleet_depreciation_run ||--o| ledger_journal_entry : posts
  drivers_driver ||--o{ drivers_driver_document : docs
  drivers_driver ||--o{ drivers_advance : advances
  drivers_driver ||--o{ drivers_settlement : settles
  drivers_settlement ||--o| ledger_journal_entry : posts
  platforms_platform ||--o{ platforms_settlement : settles
  platforms_settlement ||--o{ platforms_earning_import : imports
  platforms_settlement ||--o| ledger_journal_entry : posts
  bookings_trip }o--o| fleet_vehicle : on
  bookings_trip }o--o| drivers_driver : by
  bookings_trip }o--o| platforms_platform : via
  bookings_trip }o--o| ar_customer : for
  bookings_contract }o--|| ar_customer : bills

  fleet_vehicle {
    uuid id PK
    varchar plate_no
    varchar ownership_type
    uuid current_driver_id FK
    varchar status
  }
  drivers_driver {
    uuid id PK
    varchar code
    varchar pay_type
    decimal commission_pct
    uuid payable_account_id FK
  }
  drivers_settlement {
    uuid id PK
    date period_start
    decimal gross_earnings
    decimal net_payable
    uuid journal_entry_id FK
  }
  platforms_settlement {
    uuid id PK
    decimal gross_earnings
    decimal commission
    decimal net_received
    decimal variance
  }
  bookings_trip {
    uuid id PK
    date trip_date
    varchar trip_type
    decimal fare
    decimal net_revenue
  }
```

---

## 5. Banking · Cashbook (doc 06)

```mermaid
erDiagram
  accounts_account ||--|| banking_bank_account : "GL 1:1"
  banking_bank_account ||--o{ banking_bank_statement : statements
  banking_bank_statement ||--o{ banking_statement_line : lines
  banking_statement_line }o--o| ledger_journal_line : "matched to"
  banking_bank_account ||--o{ banking_reconciliation : recon
  banking_reconciliation ||--o{ banking_reconciliation_item : items
  banking_bank_transfer ||--o| ledger_journal_entry : posts
  banking_pos_settlement ||--o| ledger_journal_entry : posts
  accounts_account ||--|| cashbook_cash_account : "GL 1:1"
  cashbook_cash_account ||--o{ cashbook_petty_cash_float : float
  cashbook_cash_account ||--o{ cashbook_replenishment : topups
  cashbook_cash_account ||--o{ cashbook_cash_count : counts
  cashbook_cash_count ||--o{ cashbook_cash_count_denomination : notes
  cashbook_replenishment ||--o| ledger_journal_entry : posts
  cashbook_cash_count ||--o| ledger_journal_entry : "variance"

  banking_bank_account {
    uuid id PK
    uuid gl_account_id FK
    varchar iban UK
    varchar bank_name
  }
  banking_bank_statement {
    uuid id PK
    date statement_date
    decimal closing_balance
  }
  banking_reconciliation {
    uuid id PK
    date recon_date
    decimal difference
    varchar status
  }
  cashbook_cash_account {
    uuid id PK
    uuid gl_account_id FK
    bool is_petty_cash
  }
  cashbook_cash_count {
    uuid id PK
    date count_date
    decimal variance
  }
```

---

## 6. Payroll · WPS (doc 07)

```mermaid
erDiagram
  payroll_employee ||--o{ payroll_employee_salary : structure
  payroll_salary_component ||--o{ payroll_employee_salary : component
  payroll_employee }o--o| drivers_driver : "is driver"
  payroll_run ||--o{ payroll_payslip : payslips
  payroll_payslip ||--o{ payroll_payslip_line : lines
  payroll_salary_component ||--o{ payroll_payslip_line : component
  payroll_run ||--o{ payroll_wps_batch : "WPS SIF"
  payroll_wps_batch ||--o{ payroll_wps_record : records
  payroll_employee ||--o{ payroll_wps_record : paid
  payroll_employee ||--o{ payroll_gratuity : gratuity
  payroll_employee ||--o{ payroll_leave : leave
  payroll_employee ||--o{ payroll_advance : advances
  payroll_run ||--o| ledger_journal_entry : posts
  payroll_gratuity ||--o| ledger_journal_entry : posts

  payroll_employee {
    uuid id PK
    varchar code
    uuid driver_id FK
    varchar mol_personal_no
    varchar pay_method
    varchar iban
  }
  payroll_run {
    uuid id PK
    char salary_month
    decimal net_total
    varchar status
    uuid journal_entry_id FK
  }
  payroll_wps_batch {
    uuid id PK
    varchar employer_eid
    int total_records
    decimal total_salary
  }
  payroll_gratuity {
    uuid id PK
    decimal service_years
    decimal amount
    varchar type
  }
```

---

## 7. Reports (doc 05)

```mermaid
erDiagram
  reports_statement_template ||--o{ reports_statement_line : lines
  reports_statement_line ||--o{ reports_statement_line : "parent (tree)"
  tenants_entity ||--o{ reports_balance_snapshot : balances
  tenants_entity ||--o{ reports_profit_snapshot : profitability
  tenants_entity ||--o{ reports_report_run : runs
  tenants_entity ||--o{ reports_report_schedule : schedules
  ledger_accounting_period ||--o{ reports_balance_snapshot : period
  ledger_accounting_period ||--o{ reports_profit_snapshot : period
  reports_report_run ||--o| reports_report_schedule : "from schedule"

  reports_statement_template {
    uuid id PK
    varchar code
    varchar name
  }
  reports_statement_line {
    uuid id PK
    uuid template_id FK
    varchar line_type
    char main_from
    char main_to
  }
  reports_profit_snapshot {
    uuid id PK
    varchar dim_type
    uuid dim_id
    decimal revenue
    decimal net_profit
  }
  reports_report_run {
    uuid id PK
    varchar report_code
    varchar format
    varchar status
  }
```

---

> These diagrams are domain views; cross-domain FKs (e.g. every transactional
> table → `tenants_entity`, every posting line → `accounts_account`,
> document → `ledger_journal_entry`) are summarised here and listed in full in
> `FinCare_Relationships.xlsx`.
