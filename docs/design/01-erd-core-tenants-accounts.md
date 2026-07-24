# ERD — `core`, `tenants`, `accounts`

**Project:** FinCare · **Phase:** 1 (foundation) · **Status:** Draft for review
**Scope:** the three apps that everything else depends on. Approve the tables here
before Claude Code generates models (build steps 1–3 in `CLAUDE_CODE_GUIDE.md`).

Conventions used throughout (defined once, applied everywhere):

- **PK** = UUID (`uuid4`), column `id`.
- **Audit mixin** (every table): `created_at`, `updated_at` (timestamptz),
  `created_by`, `updated_by` (FK → `users.user`, nullable).
- **Soft delete** (where noted): `is_deleted` (bool, default false),
  `deleted_at` (timestamptz, null).
- **Money**: `numeric(18,2)`, never float. **Rates/qty**: `numeric(18,6)`.
- Audit + soft-delete columns are omitted from the per-table grids below to keep
  them readable; assume them present per the rule above. Only deviations are noted.

---

## App: `core`

Base building blocks reused by all other apps. No business logic — primitives only.

### `core_currency`

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| code | char(3) | no | UQ | ISO 4217 (AED, USD, EUR) |
| name | varchar(64) | no | | "UAE Dirham" |
| symbol | varchar(8) | no | | "AED" / "د.إ" |
| decimal_places | smallint | no | | default 2 |
| is_base | boolean | no | | exactly one true (group base = AED) |
| is_active | boolean | no | | |

### `core_exchange_rate`

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| from_currency_id | uuid | no | FK → core_currency | |
| to_currency_id | uuid | no | FK → core_currency | |
| rate | numeric(18,6) | no | | units of `to` per 1 `from` |
| rate_date | date | no | IX | rate effective date |
| source | varchar(32) | yes | | "manual" / "ecb" / "uaecb" |

> Unique: (`from_currency_id`, `to_currency_id`, `rate_date`).

### `core_number_sequence`

Gap-safe document numbering, scoped per entity + series. Drives invoice/voucher numbers.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| entity_id | uuid | no | FK → tenants_entity | per-entity counters |
| code | varchar(32) | no | | series key, e.g. "SALES_INV" |
| prefix | varchar(16) | yes | | e.g. "INV-" |
| suffix | varchar(16) | yes | | optional |
| padding | smallint | no | | zero-pad width, default 6 |
| next_value | bigint | no | | incremented under row lock |
| reset_policy | varchar(16) | no | | never / yearly / monthly |
| period_key | varchar(7) | yes | | "2026" or "2026-06" for reset tracking |

> Unique: (`entity_id`, `code`, `period_key`). Allocation uses
> `SELECT … FOR UPDATE` inside the posting transaction.

### `core_attachment`

Generic file attachment for any document (invoices, vouchers, KYC docs).

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| entity_id | uuid | no | FK → tenants_entity | |
| content_type_id | int | no | FK → django_content_type | generic relation |
| object_id | uuid | no | IX | target row id |
| file | varchar(512) | no | | storage path / key |
| original_name | varchar(255) | no | | |
| mime_type | varchar(128) | yes | | |
| size_bytes | bigint | yes | | |

---

## App: `tenants`

Multi-entity / multi-branch master. Carries the dimensions every posting tags.

### `tenants_business_category`

The business type that drives a COA template (transport, restaurant, baqala,
salon, cafeteria, tour, typing, pharmacy, car_rental, workshop, …). New
categories can be added without code changes; see ADR-0005.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| key | varchar(32) | no | UQ | machine key, e.g. "transport" |
| label | varchar(64) | no | | display name, e.g. "Transport" |
| band | char(1) | no | UQ | category band digit (0–9); first digit of every entity code in this category |
| coa_template_key | varchar(32) | no | | which COA template seeds entities of this category |
| is_active | boolean | no | | |

### `tenants_vat_group`

A UAE VAT group sharing **one TRN** across its member entities. An entity that
registers individually still has a group-of-one. See ADR-0006.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| code | varchar(16) | no | UQ | e.g. "VG-01" |
| name | varchar(128) | no | | "Regency Group VAT Group" |
| trn | varchar(15) | yes | UQ | the shared UAE VAT TRN (config, not literal) |
| representative_entity_id | uuid | yes | FK → tenants_entity | group representative member |
| is_active | boolean | no | | |

### `tenants_entity`

A legal company in the group (e.g. each Regency Group business).

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| code | varchar(16) | no | UQ | short group code, e.g. "RGT" |
| numeric_code | char(3) | no | UQ | COA entity segment "101" = category band (1) + entity sequence (2); first segment of every account code; immutable once accounts exist |
| legal_name | varchar(255) | no | | as per trade licence |
| trade_name | varchar(255) | yes | | |
| category_id | uuid | no | FK → tenants_business_category | drives the COA template + band; first digit of numeric_code = category band |
| vat_group_id | uuid | yes | FK → tenants_vat_group | null if not VAT-registered; TRN is read from the group |
| corporate_tax_trn | varchar(20) | yes | | **per-entity** CT registration (never shared) |
| licence_no | varchar(64) | yes | | trade licence number |
| base_currency_id | uuid | no | FK → core_currency | default AED |
| fiscal_year_start_month | smallint | no | | 1–12, default 1 |
| accounting_basis | varchar(8) | no | | cash / accrual |
| parent_entity_id | uuid | yes | FK → tenants_entity (self) | group consolidation tree |
| is_active | boolean | no | | |

> The entity's effective VAT TRN is resolved from `vat_group_id → trn`, never
> stored on the entity. Corporate Tax number is always per entity.

### `tenants_branch`

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| entity_id | uuid | no | FK → tenants_entity | |
| code | varchar(16) | no | | unique within entity |
| name | varchar(128) | no | | |
| emirate | varchar(32) | yes | | Dubai / Abu Dhabi / Sharjah … |
| address | varchar(512) | yes | | |
| is_active | boolean | no | | |

> Unique: (`entity_id`, `code`).

### `tenants_cost_center`

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| entity_id | uuid | no | FK → tenants_entity | |
| code | varchar(16) | no | | unique within entity |
| name | varchar(128) | no | | e.g. "Fleet-A", "Kitchen" |
| parent_id | uuid | yes | FK → tenants_cost_center (self) | hierarchy |
| is_active | boolean | no | | |

> Unique: (`entity_id`, `code`).

### `tenants_department`

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| entity_id | uuid | no | FK → tenants_entity | |
| code | varchar(16) | no | | |
| name | varchar(128) | no | | |
| is_active | boolean | no | | |

> Unique: (`entity_id`, `code`).

### `tenants_intercompany_map`

Pairs two entities for intercompany recharge / settlement; both legs must balance.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| from_entity_id | uuid | no | FK → tenants_entity | initiating entity |
| to_entity_id | uuid | no | FK → tenants_entity | counterparty entity |
| due_to_account_id | uuid | no | FK → accounts_account | payable leg (from side) |
| due_from_account_id | uuid | no | FK → accounts_account | receivable leg (to side) |
| is_active | boolean | no | | |

> Unique: (`from_entity_id`, `to_entity_id`).

### RLS note

`tenants_*` and all downstream transactional tables are protected by PostgreSQL
Row-Level Security keyed on `entity_id`, set via a per-request session GUC
(e.g. `SET app.current_entities = '…'`). Policy and middleware design will be
captured in an ADR during build step 2.

---

## App: `accounts`

Chart of Accounts. Pure structure — balances are derived from `ledger`, never
stored here.

### Account code structure (binding)

Every account code follows the fixed pattern **`EEE-MMM-SSS-CCC`** — see
`docs/adr/0004-chart-of-accounts-numbering.md` for the full rules.

```
101 - 400 - 410 - 001
│      │     │     └─ Charge Code   (3) → the postable leaf (accounts_account)
│      │     └─────── Sub-Account   (3) → level-2 group
│      └───────────── Main Account  (3) → level-1 group; first digit = nature
└──────────────────── Entity (3)    → tenants_entity.numeric_code
                       = category band (1 digit) + entity sequence (2 digits)
```

Each segment is stored discretely **and** persisted as the composed display
code, so the system never parses a string to know an account's place in the
hierarchy. The composed `code` is generated by the service layer, never typed
by a user.

### `accounts_account_group`

Holds the **Main** (level 1) and **Sub** (level 2) tiers of the structure.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| entity_id | uuid | no | FK → tenants_entity | per-entity COA |
| level | smallint | no | | 1 = Main, 2 = Sub |
| segment | char(3) | no | | this tier's 3-digit segment ("100", "110") |
| parent_id | uuid | yes | FK → accounts_account_group (self) | null for Main; the Main for a Sub |
| code | varchar(7) | no | | composed up to this tier: "11-100" or "11-100-110" |
| name | varchar(128) | no | | |
| nature | varchar(12) | no | | asset / liability / equity / income / expense |
| is_active | boolean | no | | |

> Unique: (`entity_id`, `level`, `segment`, `parent_id`). A Sub's `nature` must
> equal its Main's; a Main's `nature` is derived from the first digit of
> `segment` (1=asset, 2=liability, 3=equity, 4=income, 5–6=expense).

### `accounts_account`

The postable ledger account — the **Charge Code** leaf of the COA.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| entity_id | uuid | no | FK → tenants_entity | |
| sub_group_id | uuid | no | FK → accounts_account_group | must be a level-2 (Sub) row |
| charge_segment | char(3) | no | | 3-digit Charge Code ("001") |
| code | char(15) | no | UQ | full composed code "101-400-410-001"; service-generated |
| name | varchar(128) | no | | |
| account_type | varchar(24) | no | | bank / cash / receivable / payable / vat_input / vat_output / fixed_asset / loan / revenue / expense / equity / general |
| normal_balance | char(1) | no | | 'D' or 'C' — derived from Main nature |
| currency_id | uuid | no | FK → core_currency | default = entity base |
| is_control_account | boolean | no | | true for AR/AP control (subledger-backed) |
| subledger | varchar(16) | yes | | "customer" / "supplier" / null |
| is_bank_account | boolean | no | | drives reconciliation features |
| allow_manual_posting | boolean | no | | false for control accounts |
| is_postable | boolean | no | | leaf accounts are postable; default true |
| is_active | boolean | no | | |

> Unique: (`entity_id`, `sub_group_id`, `charge_segment`) and global Unique on
> `code`. Control accounts (`is_control_account = true`) set
> `allow_manual_posting = false` — entries arrive only via AR/AP services.

### Code composition & validation (service layer)

- The Entity segment is **always** taken from `tenants_entity.numeric_code`;
  a user never supplies it. Mismatch between a row's `entity_id` and the leading
  segment is rejected at save.
- `accounts_account.code = entity.numeric_code + '-' + main.segment + '-' +
  sub.segment + '-' + charge_segment`, assembled and validated in
  `apps/accounts/services/coding.py`. `numeric_code` (3 digits) = category band
  (1) + entity sequence (2).
- A regex check `^\d{3}-\d{3}-\d{3}-\d{3}$` guards every persisted code (DB
  `CHECK` constraint + serializer validator).
- Next free Charge Code within a Sub-Account is allocated via a
  `core_number_sequence` row keyed `code="COA"` and `period_key=<entity-main-sub>`,
  so charge numbering is gap-safe and resettable independently per sub-account.

### `accounts_tax_code`

VAT treatment attachable to accounts and document lines (config-driven, no literal rates).

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| id | uuid | no | PK | |
| entity_id | uuid | no | FK → tenants_entity | |
| code | varchar(16) | no | | "SR5", "ZR", "EX", "OS", "RC" |
| name | varchar(64) | no | | "Standard Rated 5%", "Zero Rated"… |
| rate | numeric(6,3) | no | | e.g. 5.000; 0 for zero/exempt |
| treatment | varchar(16) | no | | standard / zero / exempt / out_of_scope / reverse_charge |
| direction | varchar(8) | no | | input / output / both |
| account_id | uuid | yes | FK → accounts_account | VAT control account to post to |
| is_active | boolean | no | | |

> Unique: (`entity_id`, `code`). Effective-dating of rate changes can be added in
> the `tax` app; this table holds the current configured set.

---

## Relationship summary

```
tenants_business_category ──< tenants_entity   (category drives COA template)
tenants_vat_group         ──< tenants_entity   (shared TRN; CT no stays per entity)
tenants_entity ──< tenants_branch
tenants_entity ──< tenants_cost_center (self-tree)
tenants_entity ──< tenants_department
tenants_entity ──< accounts_account_group (Main →< Sub) ──< accounts_account (Charge leaf)
tenants_entity ──< accounts_tax_code >── accounts_account   (VAT control)
tenants_intercompany_map >── tenants_entity (x2), accounts_account (x2)
core_currency ──< core_exchange_rate (x2), accounts_account, tenants_entity
core_number_sequence >── tenants_entity
core_attachment >── tenants_entity (+ generic FK to any document)
```

## Open decisions

1. ~~**COA scope.**~~ **Resolved:** per-entity COA — the 2-digit entity segment is
   baked into every account code, so each entity owns its codes. Confirmed by the
   `XX-XXX-XXX-XXX` scheme.
2. ~~**Account code length / scheme.**~~ **Resolved:** fixed `XX-XXX-XXX-XXX`
   (Entity-Main-Sub-Charge), `char(14)` composed code + discrete segment columns.
   See `docs/adr/0004-chart-of-accounts-numbering.md`.
3. **Tax effective-dating:** keep current-set only here, or model rate history
   now? Default: history lives in `tax` app later.
4. **RLS context key:** single `entity_id` vs. a list (for users who view several
   group entities at once). Default assumption: list, set per request.
