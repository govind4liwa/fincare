# FinCare — Data Dictionary (Table Inventory)

Module-wise list of every table across the Phase-1 design. Full column grids live
in the design docs (`docs/design/01`–`07`); this is the consolidated index with
each table's purpose, key columns, and lifecycle/posting notes.

**Conventions (all tables):** UUID `id` PK; audit mixin (`created_at`,
`updated_at`, `created_by`, `updated_by`); soft delete where noted; money =
`numeric(18,2)`; every transactional row carries `entity_id`.

**Legend:** ★ = posts to the GL via the ledger engine (ADR-0007). § = indicative
(to be finalised when its app is built — not yet fully tabled in a design doc).

---

## Summary

| Module | Tables | Design doc |
|---|---|---|
| core | 4 | 01 |
| users § | 2 | Phase 2 |
| tenants | 7 | 01 |
| settings § | 4 | Phase 3 |
| audit | 1 | Phase 4 |
| accounts | 3 | 01 |
| ledger | 3 | 02 |
| vouchers | 2 | 02 |
| ar | 6 | 03 |
| ap | 6 | 03 |
| tax | 4 | 03 |
| banking | 7 | 06 |
| cashbook | 5 | 06 |
| fleet | 4 | 04 |
| drivers | 4 | 04 |
| platforms | 3 | 04 |
| bookings | 2 | 04 |
| payroll | 11 | 07 |
| reports | 6 | 05 |
| exports § | 1 | 05 |
| integrations § | 1 | 16 |
| **Total** | **~86** | |

---

## core (4)

| Table | Purpose | Key columns |
|---|---|---|
| `core_currency` | Currency master | code (UQ), name, symbol, decimal_places, is_base |
| `core_exchange_rate` | FX rates by date | from_currency, to_currency, rate, rate_date |
| `core_number_sequence` | Gap-safe document numbering | entity_id, code, prefix, next_value, reset_policy, period_key |
| `core_attachment` | Generic file attachment | entity_id, content_type, object_id, file, mime_type |

> `BaseModel` is an abstract mixin (UUID + audit + soft delete), not a table.

## users § (2, indicative)

| Table | Purpose | Key columns |
|---|---|---|
| `users_user` | Custom user account | email, name, is_active, MFA fields |
| `users_role` | RBAC role / permission group | name, permissions (M2M) |

## tenants (7)

| Table | Purpose | Key columns |
|---|---|---|
| `tenants_business_category` | Business type + COA band | key (UQ), label, **band (UQ, 0–9)**, coa_template_key |
| `tenants_vat_group` | Shared VAT TRN group | code (UQ), name, **trn (UQ)**, representative_entity_id |
| `tenants_entity` | Legal company | code, **numeric_code (char3, UQ)**, legal_name, category_id, vat_group_id, corporate_tax_trn, accounting_basis |
| `tenants_branch` | Branch / location | entity_id, code, name, emirate |
| `tenants_cost_center` | Cost center (tree) | entity_id, code, name, parent_id |
| `tenants_department` | Department | entity_id, code, name |
| `tenants_intercompany_map` | Intercompany due-to/due-from | from_entity, to_entity, due_to_account, due_from_account |

## settings § (4, indicative)

| Table | Purpose | Key columns |
|---|---|---|
| `settings_entity_setting` | Per-entity config (fiscal year, defaults) | entity_id, key, value |
| `settings_numbering_series` | Document numbering config | entity_id, doc_type, format, reset_policy |
| `settings_vat_config` | VAT/CT parameters (rates, thresholds) | entity_id/group, key, value, effective_from |
| `settings_feature_flag` | Feature toggles | entity_id, flag, enabled |

## audit (1)

| Table | Purpose | Key columns |
|---|---|---|
| `audit_log` | Append-only change/activity log | actor, action, content_type, object_id, diff (jsonb), entity_id, timestamp |

## accounts (3)

| Table | Purpose | Key columns |
|---|---|---|
| `accounts_account_group` | COA Main (L1) & Sub (L2) tiers | entity_id, level, segment, parent_id, code, nature |
| `accounts_account` | Postable charge-code leaf | entity_id, sub_group_id, charge_segment, **code (char15, UQ)**, account_type, normal_balance, is_control_account, subledger, is_bank_account |
| `accounts_tax_code` | VAT treatment | entity_id, code, rate, treatment, direction, account_id |

## ledger (3)

| Table | Purpose | Key columns |
|---|---|---|
| `ledger_accounting_period` | Fiscal period gating | entity_id, fiscal_year, period_no, start/end, status (open/closed/locked) |
| `ledger_journal_entry` ★ | Posting header | entity_id, period_id, entry_no, entry_date, basis, source_type/source_id, total_debit/credit, status, reversal_of/reversed_by |
| `ledger_journal_line` ★ | Debit/credit lines + dims | entry_id, account_id, debit, credit, fx_rate, base_debit/credit, cost_center, party, vehicle/driver/platform, tax_code |

## vouchers (2)

| Table | Purpose | Key columns |
|---|---|---|
| `vouchers_voucher` ★ | Receipt/Payment/Contra/Expense/Journal | entity_id, voucher_type, voucher_no, voucher_date, party, payment_mode, bank_account, amount, status, journal_entry_id |
| `vouchers_voucher_line` | Voucher line + dims | voucher_id, account_id, debit, credit, cost_center, vehicle/driver/platform, tax_code |

## ar (6)

| Table | Purpose | Key columns |
|---|---|---|
| `ar_customer` | Customer master | entity_id, code, name, trn, receivable_account_id, credit_limit/days, emirate |
| `ar_sales_invoice` ★ | Sales invoice header | customer_id, invoice_no, invoice_date, place_of_supply, subtotal, tax_total, total, balance, status, journal_entry_id |
| `ar_sales_invoice_line` | Invoice line | invoice_id, revenue_account_id, qty, unit_price, line_amount, tax_code, tax_amount, dims |
| `ar_credit_note` ★ | Credit note header | customer_id, original_invoice_id, reason, totals, status |
| `ar_credit_note_line` | Credit note line | credit_note_id, account_id, amounts, tax_code |
| `ar_receipt_allocation` | Apply receipt/credit to invoices | customer_id, source_type/id, invoice_id, amount_allocated |

## ap (6)

| Table | Purpose | Key columns |
|---|---|---|
| `ap_supplier` | Supplier master | entity_id, code, name, trn, payable_account_id, credit_days |
| `ap_purchase_bill` ★ | Purchase bill header | supplier_id, bill_no, supplier_invoice_no, bill_date, totals, balance, is_reverse_charge, status, journal_entry_id |
| `ap_purchase_bill_line` | Bill line | bill_id, account_id, amounts, tax_code, recoverable, vehicle/driver dims |
| `ap_debit_note` ★ | Debit note header | supplier_id, original_bill_id, reason, totals |
| `ap_debit_note_line` | Debit note line | debit_note_id, account_id, amounts, tax_code |
| `ap_payment_allocation` | Apply payment/debit to bills | supplier_id, source_type/id, bill_id, amount_allocated |

## tax (4)

| Table | Purpose | Key columns |
|---|---|---|
| `tax_code_rate_history` | Effective-dated VAT rates | tax_code_id, rate, effective_from/to |
| `tax_return` | VAT return per VAT group | vat_group_id, period_start/end, output_vat, input_vat, adjustments, net_payable, status |
| `tax_return_box` | VAT 201 box breakdown | tax_return_id, box_code (1a–1g…), label, emirate, net_amount, vat_amount |
| `corporate_tax_return` | CT return per entity | entity_id, fiscal_year, accounting_profit, taxable_income, tax_rate, tax_payable |

## banking (7)

| Table | Purpose | Key columns |
|---|---|---|
| `banking_bank_account` | Bank metadata (1:1 GL acct) | entity_id, gl_account_id, bank_name, account_no, iban (UQ), swift, currency |
| `banking_bank_transfer` ★ | Transfer/deposit/withdrawal | transfer_no, from_account, to_account, transfer_type, amount, charges, journal_entry_id |
| `banking_bank_statement` | Imported statement header | bank_account_id, statement_date, opening/closing_balance, source |
| `banking_statement_line` | Statement line (staging) | statement_id, line_date, debit, credit, matched, matched_line_id |
| `banking_reconciliation` | Book vs statement recon | bank_account_id, recon_date, book/statement/reconciled_balance, difference, status |
| `banking_reconciliation_item` | Reconciling items | reconciliation_id, item_type, amount, source, resolved |
| `banking_pos_settlement` ★ | Card/POS settlement | terminal_ref, gross/fee/net, bank_account, clearing_account, fee_account, journal_entry_id |

## cashbook (5)

| Table | Purpose | Key columns |
|---|---|---|
| `cashbook_cash_account` | Cash account metadata (1:1 GL) | entity_id, gl_account_id, custodian_id, is_petty_cash |
| `cashbook_petty_cash_float` | Imprest float setup | cash_account_id, imprest_amount, effective_from |
| `cashbook_replenishment` ★ | Float top-up from bank | cash_account_id, bank_account_id, amount, journal_entry_id |
| `cashbook_cash_count` ★ | Physical count vs book | cash_account_id, count_date, counted_amount, book_balance, variance, variance_account_id |
| `cashbook_cash_count_denomination` | Note-by-note breakdown | count_id, denomination, quantity, amount |

## fleet (4)

| Table | Purpose | Key columns |
|---|---|---|
| `fleet_vehicle` | Vehicle master | entity_id, code, plate_no, ownership_type, purchase_cost, asset/accum_dep accounts, dep_method, current_driver_id, status |
| `fleet_vehicle_document` | Mulkiya/insurance/permit | vehicle_id, doc_type, number, expiry_date, cost, attachment |
| `fleet_vehicle_loan` | EMI / finance | vehicle_id, lender, principal, emi_amount, tenor_months, loan/interest accounts |
| `fleet_depreciation_run` ★ | Periodic depreciation batch | entity_id, period_id, run_date, total_amount, journal_entry_id |

## drivers (4)

| Table | Purpose | Key columns |
|---|---|---|
| `drivers_driver` | Driver master | entity_id, code, name, emirates_id, eid/visa/license expiry, pay_type, basic_salary, commission_pct, payable_account |
| `drivers_driver_document` | Visa/EID/licence/Daman | driver_id, doc_type, number, expiry_date, attachment |
| `drivers_advance` | Driver advance + recovery | driver_id, amount, recovered_amount, balance, voucher_id, status |
| `drivers_settlement` ★ | Periodic payout | driver_id, period, gross_earnings, commission, advance/salik/fine recovery, net_payable, journal_entry_id |

## platforms (3)

| Table | Purpose | Key columns |
|---|---|---|
| `platforms_platform` | Aggregator master | entity_id, name, commission_pct, revenue/commission/clearing accounts |
| `platforms_settlement` ★ | Statement reconciliation | platform_id, period, gross/commission/adjustments/net_received, variance, journal_entry_id |
| `platforms_earning_import` | Raw statement staging | settlement_id, trip_ref, driver_ref, gross/commission/net, matched |

## bookings (2)

| Table | Purpose | Key columns |
|---|---|---|
| `bookings_trip` | Trip register (grain) | entity_id, trip_date, trip_type, vehicle/driver/platform/customer, fare, commission, salik, net_revenue, status |
| `bookings_contract` | Corporate/monthly billing | customer_id, vehicle/driver, contract_no, billing_cycle, monthly_amount, tax_code, status |

## payroll (11)

| Table | Purpose | Key columns |
|---|---|---|
| `payroll_employee` | Employee master | entity_id, code, name, driver_id, mol_personal_no, iban, pay_method, payable_account, status |
| `payroll_salary_component` | Earning/deduction master | code, component_type, is_gratuity_base, is_wps_fixed, expense_account |
| `payroll_employee_salary` | Effective-dated structure | employee_id, component_id, amount, effective_from/to |
| `payroll_run` ★ | Monthly payroll batch | entity_id, period_id, salary_month, gross/deduction/net totals, status, journal_entry_id |
| `payroll_payslip` | Per-employee payslip | run_id, employee_id, working_days, lop_days, gross, deductions, net_pay |
| `payroll_payslip_line` | Component breakdown | payslip_id, component_id, component_type, amount |
| `payroll_wps_batch` | WPS SIF control record (SCR) | run_id, employer_eid, employer_bank_routing, total_records, total_salary, sif_file_ref |
| `payroll_wps_record` | WPS employee record (EDR) | batch_id, employee_id, mol_personal_no, iban, fixed_amount, variable_amount |
| `payroll_gratuity` ★ | EOSB accrual/settlement | employee_id, as_of_date, service_years, eligible_days, amount, type, provision/expense accounts, journal_entry_id |
| `payroll_leave` | Leave balance + accrual | employee_id, leave_type, entitled/taken/balance days, accrued_amount, provision_account |
| `payroll_advance` ★ | Salary advance + recovery | employee_id, amount, installments, recovered_amount, balance, advance_account, voucher_id |

## reports (6)

| Table | Purpose | Key columns |
|---|---|---|
| `reports_statement_template` | Statement layout (PNL/BS/CF/TB) | entity_id (null=group), code, name |
| `reports_statement_line` | Template lines → COA ranges | template_id, line_no, parent_id, label, line_type, main/sub from-to, sign, formula |
| `reports_balance_snapshot` | Period-end balances (perf) | entity_id, period_id, account_id, opening/period/closing |
| `reports_profit_snapshot` | Profitability by dimension | entity_id, dim_type, dim_id, period_id, revenue, direct_cost, overhead, net_profit |
| `reports_report_run` | Generated report log | entity_scope, report_code, params (jsonb), format, file_ref, status |
| `reports_report_schedule` | Recurring MIS schedule | report_code, entity_scope, params, cron, recipients, format |

## exports § (1, indicative)

| Table | Purpose | Key columns |
|---|---|---|
| `exports_export_job` | Excel/PDF generation job log | report_run_id, format, file_ref, status (often folded into reports_report_run) |

## integrations § (1, indicative)

| Table | Purpose | Key columns |
|---|---|---|
| `integrations_import_log` | Bank/platform file import audit | source_type, file_ref, rows_total, rows_imported, rows_failed, status |

---

## Notes

- ★ tables are written **only** by `apps/ledger/services/posting.py` (ADR-0007);
  source documents build a `JournalEntry` and call the posting service.
- § tables are indicative — finalised when their app is built (`users` Phase 2,
  `settings` Phase 3, `exports`/`integrations` Phases 15–16). `exports` may have
  no own table if it reuses `reports_report_run`.
- Aging (AR/AP) and most statements are **derived queries**, not tables.
- Full column definitions: `docs/design/01`–`07`. Build order: `BUILD_ROADMAP.md`.
  App overview: `APP_INVENTORY.md`.
