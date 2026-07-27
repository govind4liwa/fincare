# Design 08 — Customer Vehicle Finance (Receivable) & Direction-Agnostic Schedule Engine

**Status:** Reviewed — Slice A shipped; Slices B+ ready to scope
**Date:** 2026-07-25 · revised 2026-07-26 after implementation review
**Related:** ADR-0010 (engine decision), ADR-0007 (posting engine), ADR-0004/0005
(CoA), design docs 02 (ledger/vouchers), 03 (AR/AP/tax), 04 (fleet/drivers)
**Source document:** `docs/supporting-source/Auto-Loan-Repayment-Schedule-Updated.xlsx`
(Star Regency Limousine → Muhammad Faisal, Lexus ES300H — the reference deal all
numbers in this spec are verified against)

---

## 1. Purpose

Extend the fleet EMI schedule engine (PR #53) so the company can act as the
**financier**: sell/finance a vehicle to a customer or driver on instalments
(rent-to-own / hire-purchase), with

- the same versioned, approval-locked, exactly-reconciling amortization schedule;
- instalment lifecycle driven by **actual receipts** (due, overdue, partially
  paid, paid, reversed) with allocation of one receipt across many instalments;
- **initial-expense recharge** (registration, insurance, permits, kafalath,
  visa, processing fees, refundable deposits) itemized, tracked
  charged → collected → outstanding, separated from principal and interest;
- a **customer running account** (statement) with opening balance, charges,
  receipts, adjustments, closing balance, drill-down to source documents, and
  print/export — with no destructive editing anywhere.

The amortization schedule, the customer ledger, and the accounting postings stay
**connected but separately auditable**: the schedule says what *should* happen,
the GL says what *did* happen, and the statement is derived from the GL.

## 2. Reference deal (acceptance fixture)

All engine work is acceptance-tested against the source workbook:

| Input | Value |
|---|---|
| Vehicle cost | 199,000.00 |
| Down payment (25%) | 49,750.00 |
| Finance principal `P` | 149,250.00 |
| Quoted flat rate | 4.5% / year (stored: 4.503853% back-solved) |
| Tenure `n` | 36 months |
| Total interest (flat) | 20,166.00 |
| Total contract value | 169,416.00 |
| EMI | 4,706.00 |
| Implied monthly IRR `r` | 0.7017579408% |
| Effective annual rate | 8.7538% |
| First EMI date | 2025-08-01 |

Position after 12 paid instalments: cash collected 56,472.00; outstanding
**principal** 103,611.69; remaining **contractual** value 112,944.00 (includes
future interest). The spec keeps both figures distinct everywhere: principal is
the asset; the contractual remainder is memo information.

## 3. Domain model — one engine, two directions

New app **`apps/financing`** (ADR-0010). Direction is data:

```
FinanceAgreement (direction = LOAN_PAYABLE | FINANCE_RECEIVABLE)
 ├── FinanceSchedule (versioned: DRAFT → APPROVED → SUPERSEDED)   ── unchanged mechanics
 │    └── FinanceInstallment (immutable once posted)
 ├── ChargeNote (initial-expense recharge)          ── receivable only
 │    └── ChargeNoteLine
 └── FinanceAllocation (receipt/credit/set-off → instalment or charge note)
```

`apps/financing` is a **new app not listed in CLAUDE.md §3's planned-app set**.
ADR-0010 records the decision to add it; Slice B must also add it to that list
and to `LOCAL_APPS`, or the guardrail and this design disagree about what apps
exist.

- `LOAN_PAYABLE`: counterparty is a lender (free-text or supplier link);
  posting matrix unchanged from PR #53.
- `FINANCE_RECEIVABLE`: counterparty is `ar.Customer` (required) with optional
  `drivers.Driver` link (rent-to-own to an employed driver — enables
  earnings set-off, §10).

## 4. Amortization methods

`REDUCING_BALANCE` and `FLAT_RATE` carry over unchanged. `LENDER_PROVIDED`
(imported rows) remains the documented extension point. One method is added:

### 4.3 `FLAT_QUOTED_EFFECTIVE` (new — reproduces the workbook)

UAE auto-finance convention: the *contract* is quoted flat, but the
*amortization* uses the effective rate implied by that contract.

```
total_interest = q2(P × flat_rate × n/12)          # flat quote fixes the interest
EMI            = q2((P + total_interest) / n)      # equal instalments
r              = IRR solving  P = EMI × (1 − (1+r)^−n) / r    # implied monthly rate
for i in 1..n−1:
    interest_i  = q2(balance × r)
    principal_i = q2(EMI − interest_i)
    balance    -= principal_i
# final instalment absorbs all rounding:
principal_n = balance;  interest_n = EMI − principal_n
```

- `q2` = quantize to 0.01, ROUND_HALF_UP (existing `_q`).
- IRR solved by Newton's method on Decimal (tolerance 1e-12, ≤ 100 iterations;
  falls back to bisection on non-convergence; `r = 0` when flat rate is 0 —
  degrades to `P / n` like the other methods).
- Both rates are **stored**: `quoted_flat_rate` (contract face) and the derived
  `effective_annual_rate = (1+r)^12 − 1` (fields already exist on the loan
  model). Neither is ever recomputed from the other after approval — the
  schedule snapshot is authoritative.
- **Verified:** this algorithm reproduces all 36 workbook rows exactly
  (instalments, splits, opening/closing balances; totals tie to 149,250.00 /
  20,166.00; closes to 0.00). The 36 rows become a golden-file test fixture.
- The workbook's DAYS column is informational (days in the elapsed month); it
  does **not** enter the interest computation and is not modelled.

Existing invariants apply unchanged: exact reconciliation before save, monotonic
version numbers over soft delete, approval locking, posted instalments never
rewritten, day-clamped monthly due dates via `add_months`.

## 5. Data model

Conventions: `BaseModel` (UUID pk, audit, soft delete), `entity` FK for RLS,
`PROTECT` on masters, money `Decimal(18,2)`, rates `Decimal(9,6)` — note the
widened rate precision: 6 dp is required to store 0.701758 %/month faithfully.

### 5.1 `FinanceAgreement` (generalizes `VehicleLoan`)

| Field | Type | Notes |
|---|---|---|
| entity | FK tenants.Entity | RLS scope |
| direction | choice | `loan_payable` / `finance_receivable` |
| agreement_no | char(24), blank | allocated at activation (`FIN-` sequence, ADR-0004) |
| vehicle | FK fleet.Vehicle, null | required for vehicle deals; null keeps engine generic |
| lender | char(128), blank | payable side |
| customer | FK ar.Customer, null | **required when receivable** (CHECK) |
| driver | FK drivers.Driver, null | optional; enables earnings set-off |
| asset_cost | dec | 199,000 — memo for the deal sheet |
| down_payment | dec | 49,750 |
| principal | dec | 149,250 |
| term_months / emi_amount / start_date / first_payment_date | | as today |
| amortization_method | choice | + `flat_quoted_effective` |
| annual_interest_rate | dec(9,6) | reducing-balance input |
| quoted_flat_rate | dec(9,6) | flat / flat-quoted input |
| effective_annual_rate | dec(9,6) | derived at generation, snapshotted |
| principal_account | FK accounts.Account | payable: Loan Payable (liability) · receivable: Finance Receivable – Principal (asset) |
| interest_account | FK accounts.Account | payable: Interest Expense · receivable: Finance/Interest Income |
| instalment_control_account | FK accounts.Account, null | receivable only: Instalment Receivable control |
| status | choice | `draft → active → settled → cancelled` (transitions §5.1.1) |
| journal_entry | FK ledger.JournalEntry, null | activation JE (§7.1) — **required before `active`** |

CHECK constraints: receivable ⇒ customer + instalment_control_account set.
Unique: (entity, agreement_no) when assigned.

`principal > 0` is **not** a CHECK — it only applies from activation onward, and a
status-dependent condition belongs in the activation service, not a table
constraint that would block legitimate drafts.

#### 5.1.1 Status transitions

| To | Trigger | Guard |
|---|---|---|
| `active` | activation (§7.1) | approved schedule exists; activation JE posted; principal > 0 |
| `settled` | last obligation discharged | every instalment on the approved schedule is `paid`, **and** no charge note has an outstanding balance |
| `cancelled` | abandoned before activation | nothing posted against the agreement |

`settled` is computed and set by the allocation service on the write that
discharges the final obligation — never hand-set, and never reached by an
agreement that still has an unpaid charge note. Without this, a completed deal
stays `active` forever and the portfolio report (§14) cannot separate live from
closed. Early settlement is a second route into `settled`; the mechanism is
specified in §6.1 and deferred to a later slice.

### 5.2 `FinanceSchedule` / `FinanceInstallment`

As `LoanSchedule` / `VehicleLoanInstallment` today (version snapshot fields,
unique `(schedule, installment_no)`, monotonic `version_no` via `all_objects`),
plus on the instalment:

| New field | Type | Notes |
|---|---|---|
| billing_status | choice | `scheduled → due → partially_paid → paid`; `reversed` terminal (§6) |
| due_entry | FK ledger.JournalEntry, null | receivable: the "raise due" JE |
| amount_allocated | dec | maintained by allocation service |

The existing `status` (`draft/posted/reversed/cancelled`) keeps meaning
**"posting state of the payable EMI / receivable due-raising"**; `billing_status`
tracks collection. Payable instalments simply never leave
`billing_status = scheduled`.

### 5.3 `ChargeNote` + `ChargeNoteLine` (initial-expense recharge)

Header: entity, agreement, customer, charge_note_no (sequence at post),
charge_date, narration, totals, status (`draft/posted/reversed`),
journal_entry FK, amount_allocated.

Line:

| Field | Notes |
|---|---|
| item_type | choice: `registration, insurance, permit, permit_card, gprs_tracking, kafalath, visa, processing_fee, darb_activation, deposit_refundable, other` |
| description / amount | |
| originally_paid_by | choice: `company_bank, company_cash, petty_cash, other_entity, customer_direct` |
| paid_by_entity | FK tenants.Entity, null — intercompany trace when another group entity paid |
| source_ref | char(64) — voucher/bill no. that originally booked the cost |
| credit_account | FK accounts.Account — expense-recovery or income account; **liability account when `deposit_refundable`** |
| tax_code | FK accounts.TaxCode, null — recharges may be VAT-able; per-line, never hardcoded (§11) |
| recoverable | bool (default true) — non-recoverable lines are excluded from the charge total and exist only as deal-sheet memo |

This separates **recoverable customer charges** from loan principal and
interest completely: they never touch the schedule or the finance-income
account, but they do flow into the same instalment-control account so one
statement and one receipt path covers everything.

### 5.4 `FinanceAllocation` (receipt → instalment/charge)

Follows `ar.ReceiptAllocation`'s shape, with a generic target.

> **Named `FinanceAllocation`, not `SettlementAllocation`.** "Settlement" already
> means a *driver settlement* in this codebase (`drivers.Settlement`), and §7.5 /
> §10 mix the two domains in the same paragraphs. The collision would be
> permanent and confusing; the rename costs nothing before the app exists.

| Field | Notes |
|---|---|
| entity / customer / agreement | scoping |
| source_type | `receipt_voucher, credit_note, advance, earnings_set_off, reversal` |
| source_id | UUID of the source document |
| target_type | `installment, charge_note` |
| target_id | UUID |
| amount_allocated | > 0 always — never negative, never edited |
| reverses | FK self, null — set only on `source_type=reversal` rows; the contra row that backs out an earlier allocation |
| allocation_date | |

Service invariants: Σ allocations per target ≤ target total; Σ allocations per
source ≤ source amount. Unallocated receipt remainder stays on the customer as an
advance (visible in the statement; allocatable later).

**Locking (learned from `post_settlement` / `post_clearing`, which do this
already):**

1. Targets are re-read `SELECT … FOR UPDATE` **ordered by primary key**. A receipt
   spanning instalments #13 and #14 concurrently with another receipt taking them
   in the opposite order will deadlock otherwise.
2. The `amount_allocated` recompute happens **inside the same lock** as the
   allocation write, not after it. Recomputing afterwards lets the denormalized
   figure drift from the rows it summarises under concurrency.

## 6. Instalment lifecycle (receivable)

```
scheduled ──raise due (JE)──▶ due ──allocation──▶ partially_paid ──▶ paid
    ▲                          │
    └──── reversal of due JE ──┴──▶ reversed          overdue = derived, not stored
```

- `scheduled`: exists on an approved schedule; nothing posted. Editable never —
  amendments go through schedule re-versioning as today.
- `due`: the due JE posted (§7.2). From here the row is immutable; corrections
  are reversal-only (ADR-0007).
- `partially_paid` / `paid`: derived from `amount_allocated` vs `total_amount`
  by the allocation service (stored for query speed, recomputed on every
  allocation/reversal — never hand-set).
- `overdue`: **derived flag** (`due_date + grace < today` and not fully paid),
  computed in queryset annotations / serializer — deliberately not a stored
  status, so the state machine has no time-driven transitions to run. The grace
  period is entity configuration (§17.3), not a constant: aging buckets and any
  future dunning both read it.
- `reversed`: due JE reversed via `reverse_journal_entry`; allocations must be
  reversed first (guard). The instalment returns to the pool only via a new
  schedule version, never by editing.

Charge notes follow the same pattern (`draft → posted → partially/paid`,
reversal-only).

### 6.1 Early settlement (mechanism defined, implementation deferred)

Foreclosure re-versions the schedule rather than editing it: generate a new
`FinanceSchedule` version whose remaining rows are replaced by a single
**settlement instalment** carrying the agreed payoff, approve it (which
supersedes the prior version as usual), raise its due, and allocate the receipt.
Already-posted dues on the superseded version stay exactly as they are.

This reuses versioning, approval locking and exact reconciliation unchanged — no
new machinery — and gives §5.1.1 its second legitimate route into `settled`. The
interest-rebate formula is the open policy question (§17.4); the mechanism does
not depend on which formula is chosen.

## 7. Posting matrix (receivable direction)

All events post through `post_journal_entry` (ADR-0007); every line carries
`vehicle_id` (and `driver_id` when linked) for profitability dimensions. Account
codes below are indicative under ADR-0004 (`EEE-MMM-SSS-CCC`); final charge
codes are assigned through the CoA template (ADR-0005).

| # | Account (indicative) | Role |
|---|---|---|
| A1 | `EEE-100-125-001` Vehicle Finance Receivable – Principal | long-term asset (the amortizing principal) |
| A2 | `EEE-100-125-002` Instalment Receivable – Vehicle Finance (control) | current asset; party-tracked (customer) |
| A3 | `EEE-100-125-003` Recoverable Customer Charges | flows via A2; see §7.4 |
| L1 | `EEE-200-230-0xx` Customer Refundable Deposits | liability |
| I1 | `EEE-400-450-001` Vehicle Finance Interest Income | income |
| I2 | `EEE-400-450-002` Initial Expense Recharge Income / recovery | income or expense-contra per line config |

### 7.1 Activation

Policy-dependent (installment-sale derecognition vs vehicle retained until
title transfer). **v1 does not automate derecognition**: activation validates
the agreement, allocates `agreement_no`, and books the opening of A1 via a
guided journal template the accountant confirms:

```
DR  A1 Finance Receivable – Principal      149,250.00
DR  Bank / A2 (down payment path)           49,750.00
CR  Vehicle disposal / contra account      198,xxx.xx   ← policy account mapping
±   Gain/Loss on transfer                        x.xx
```

The system supplies the template with amounts filled; the account mapping and
the derecognition decision are configuration, not code (accounting/tax advisory
stays with the accountant — system logic is separated per project rules).

**Activation is a hard precondition for raising dues**, not an optional step.
§7.2 relieves A1 on every due; if the activation entry was never posted, A1 was
never loaded and each due drives it *negative* with nothing to stop it — A1 is
not a control account, so the posting engine's party guard
(`apps/ledger/services/posting.py`, "control account requires party_type and
party_id") does not fire, and no other check would catch it.

Therefore:

- `agreement.journal_entry` must be set before `status` becomes `active`
  (§5.1.1).
- `raise-dues` and per-instalment due posting refuse unless the agreement is
  `active`.

That single guard is enough — it makes the accountant's confirmation of the
activation template the gate, without the system taking a derecognition position.

### 7.2 Raise instalment due (the accrual event)

On due date (batch job "raise dues" + manual trigger), per instalment:

```
DR  A2 Instalment Receivable (party=customer)   4,706.00
CR  A1 Finance Receivable – Principal           3,658.63
CR  I1 Interest Income                          1,047.37
```

Interest income lands at due date, per the approved schedule. A1 therefore always
equals the schedule's outstanding principal for posted rows — the "Outstanding
principal 103,611.69 after 12" figure is a GL balance, not a spreadsheet cell.

**Known simplification — recognition is at due date, not accrued daily.** An
instalment's whole interest is recognised on its due date, so a period-end
falling *between* due dates under-accrues interest earned but not yet billed. For
a monthly schedule with month-end reporting the two coincide and the difference
is nil; for an off-cycle period end it is not. This is a deliberate policy, not
an oversight: it keeps recognition tied to the approved schedule and avoids a
daily accrual job. Written down here so it is not silently "fixed" later — doing
so would change reported income and the Corporate Tax base (§11). If daily
accrual is ever required, it belongs as a period-end adjusting entry, leaving
§7.2 untouched.

### 7.3 Receipt

Standard receipt voucher (vouchers app): `DR Bank / CR A2 (party=customer)`,
then `FinanceAllocation` rows spread it across instalments and charge notes
(oldest-due default, user-overridable). Advances: unallocated remainder stays
on A2 as customer credit.

### 7.4 Charge note (initial-expense recharge)

```
DR  A2 Instalment Receivable (party=customer)      34,490.00
CR  I2 recharge income / expense recovery           per line
CR  L1 Refundable deposits                          1,000.00   (deposit lines)
CR  VAT output (per line tax_code)                  where applicable
```

`originally_paid_by` + `paid_by_entity` + `source_ref` give the audit answer to
"who funded this cost" — when another group entity paid, the intercompany
entry stays in the existing intercompany map (ADR-0007 §6); the charge note
records the trace but does not post cross-entity lines.

### 7.5 Earnings set-off (driver-customer, §10)

```
DR  Driver Payable (settlement)                 4,706.00
CR  A2 Instalment Receivable (party=customer)   4,706.00
```

with `source_type=earnings_set_off` allocations — the workbook's
"EMI - PMT - 2025-MAY collected from Uber/Careem earnings" pattern.

Set-off is capped at what earnings actually cover — see §10, which is now the
normative statement of how this interacts with the driver receivable that a
negative-net settlement already creates.

### 7.6 Corrections

Reversal-only throughout (ADR-0007 §3): reverse allocations (contra rows),
then reverse the JE (mirror entry), statuses recomputed. No deletes, no edits
of posted rows, anywhere.

## 8. Receipts & allocation rules

1. Allocation is a **service** (`services/allocate.py`), never done in views.
2. Default strategy: oldest `due` instalment first, then charge notes by date;
   the UI shows the proposal and allows manual redistribution before saving.
3. Partial allocations allowed at any level; a receipt may cover instalment #13
   fully and #14 partially (→ `partially_paid`).
4. Over-allocation impossible (Σ per target ≤ total; Σ per source ≤ source),
   enforced under the row locks specified in §5.4 — PK-ordered acquisition, and
   the `amount_allocated` recompute inside the same lock. A property-based test
   hammers this concurrently (§15.4).
5. Payment history per instalment = its allocation rows (date, source doc,
   amount) — the drill-down the statement links to.
6. Remaining balance per instalment/charge = `total − amount_allocated`,
   denormalized and recomputed by the service on every change — see §5.4 for why
   that recompute cannot happen after the lock is released.

## 9. Customer running account (statement)

**The GL is the statement.** The running account is a query over `JournalLine`
rows on the instalment-control account (A2) for the party, not a new ledger:

- **Opening balance** = Σ(debit−credit) on A2 for the customer before the
  from-date. **Nothing else is added.** Migrated opening balances are posted to
  A2 as a dated migration journal, so they are already inside that sum;
  `ar.Customer.opening_balance` (which exists today,
  `apps/ar/models.py`) is a master-data field and is **not** added by the
  statement query. Adding both would double-count every migrated customer — and
  silently, since the two agree exactly when the field happens to be zero.
- **Rows**: due instalments (DR), charge notes (DR), receipts (CR), credit
  notes/adjustments (CR), earnings set-offs (CR), reversals (mirror side) —
  each row carries `source_type` + `source_id` for drill-down to the voucher /
  instalment / charge note.
- **Running balance** computed in the query (window SUM) — matches the
  workbook's CUSTOMER'S STATEMENT section including the 2,534.20 running
  position.
- Date-filtered; renders to screen, **PDF** (print layout with entity
  letterhead) and **Excel** via the exports app.
- Because underlying documents are immutable and corrections are mirrored
  reversals, the statement needs no edit path — a reprint months later shows
  the same history plus any reversals, exactly as an auditor expects.

A memo panel (not part of the ledger balance) shows the schedule-side position:
instalments paid/remaining, outstanding principal (A1 balance), remaining
contractual value — the workbook's "POSITION AFTER 12 PAID INSTALMENTS" block,
with the same principal-vs-contractual distinction.

## 10. Driver earnings set-off (later slice)

When `agreement.driver` is set, the driver-settlement flow (design doc 04) gains
an optional deduction line "vehicle finance instalment": the settlement posts
§7.5 and creates `earnings_set_off` allocations. Guards: never deduct below the
driver's statutory net-pay floor; deduction requires the instalment to be
`due`; WPS-file treatment of the deduction follows the payroll design.

### 10.1 Interaction with the driver receivable (settled — must not be conflated)

`drivers.Settlement` **already** has a negative-net path: when deductions exceed
earnings, it books a **Driver Receivable** (shipped), and `DriverClearing`
settles that by receipt or write-off (shipped). Adding a finance-instalment
deduction line creates an overlap that has to be resolved in code, not left to
chance: one settlement could otherwise produce **both** an `earnings_set_off`
allocation against A2 **and** a driver receivable for the shortfall — two
different "the driver owes us" mechanisms on one document, double-counting the
same unpaid money.

They are genuinely different obligations and must stay distinct:

| | Driver receivable | Finance instalment |
|---|---|---|
| Arises because | deductions exceeded that period's earnings | the driver bought a vehicle on instalments |
| Sits in | the entity's configured Driver Receivable account | A2, party-tracked to the customer |
| Cleared by | `DriverClearing` (receipt / write-off) | `FinanceAllocation` against the instalment |

**Rule: the finance deduction is capped so it can never contribute to a negative
net.** Concretely, the settlement service sizes the finance deduction as

```
min(instalment outstanding, earnings remaining after all other deductions)
```

and allocates only that. Any unpaid remainder of the instalment stays `due` (or
`partially_paid`) on the finance side, where it is already visible in aging and
the statement — it does **not** become a driver receivable.

That keeps the invariant readable in one sentence: *a driver receivable means the
period's own deductions outran its earnings; it never means an unpaid vehicle
instalment.* The statutory net-pay floor still applies on top and binds first
whenever it is the tighter limit.

## 11. VAT & Corporate Tax notes (system logic only)

- Interest/finance income under an instalment credit sale is **generally exempt**
  from UAE VAT; margin-based treatments differ by structure. The system
  therefore puts a `tax_code` on the interest-income account mapping and on
  every charge-note line — **no VAT treatment is hardcoded**. Final
  classification (exempt vs standard-rated recharge vs disbursement) is an
  advisory decision recorded in configuration.
- Charge-note recharges commonly *are* taxable (reimbursement vs disbursement
  rules); per-line tax codes flow to the VAT 201 boxes through the existing tax
  app unchanged.
- Interest income timing follows §7.2: recognised at each instalment's due date
  per the approved schedule. That is the accrual base for Corporate Tax, with the
  known limitation recorded in §7.2 — a period end falling between due dates
  under-accrues interest earned but not yet billed, and is corrected (if the
  accountant requires it) by a period-end adjusting entry rather than by changing
  §7.2. Cash-basis reporting derives from receipts as elsewhere in FinCare.

## 12. API surface (DRF, `/api/v1/financing/`)

| Endpoint | Notes |
|---|---|
| `GET/POST /agreements/` | direction filter; create validates per-direction requireds |
| `POST /agreements/{id}/activate/` | allocates number, optional activation JE from template |
| `POST /agreements/{id}/generate-schedule/` | new draft version (existing semantics) |
| `POST /schedules/{id}/approve/` · `DELETE /schedules/{id}/` | approve/discard (existing semantics) |
| `POST /installments/{id}/post/` | payable: EMI payment (unchanged) · receivable: raise due |
| `POST /agreements/{id}/raise-dues/` | batch: all instalments due ≤ date |
| `POST /charge-notes/` + `/charge-notes/{id}/post/` | recharge lifecycle |
| `POST /allocations/` · `POST /allocations/{id}/reverse/` | allocation service exposure |
| `GET /customers/{id}/finance-statement/?from&to&format=json|xlsx|pdf` | §9 |
| `GET /agreements/{id}/position/` | schedule + GL position (memo panel) |

Existing `/api/fleet/loans/…` delegates during the deprecation window
(ADR-0010). Permissions mirror the fleet slice (entity-scoped, RLS, role gates
on approve/post/reverse — approver ≠ creator enforced for schedules).

## 13. Frontend (Next.js)

- **Financing** nav section: Agreements list (direction toggle) → Agreement
  workspace: deal sheet (§2 block), schedule versions tabs (existing UX),
  instalment table with billing status chips + allocation drill-down,
  charge-note tab, statement tab (date filter, print/PDF/Excel).
- Receipt allocation dialog: proposal (oldest-first) with editable split.
- Vehicle Loans pages repoint to the same components with
  `direction=loan_payable`. **`/loans`, `/loans/new` and `/loans/{id}` are live
  and must keep working throughout Slice B** — the repoint is a refactor behind
  the same routes, not a migration to new ones. Route-level tests stay green
  across the change or the slice is not done.

## 14. Reports

Aging by customer over A2 (bucketed on due date); finance-income earned vs
collected; portfolio position (per agreement: principal outstanding, arrears,
collection %); recharge recovery register (charged/collected/outstanding by
item type — the workbook's INITIAL EXPENSES block, made queryable); statement
export (§9).

## 15. Test plan

1. **Golden workbook test**: the 36 Lexus rows as fixture; generation with
   `FLAT_QUOTED_EFFECTIVE` must match every cell (splits, balances, totals,
   zero close).
2. Method edge cases: zero rate, 1-instalment term, non-convergent IRR fallback,
   day-clamped dates (31st → 28/29/30).
3. State machine: every legal/illegal transition incl. reversal ordering
   (allocations before JE), posted-row immutability, schedule re-versioning
   with posted dues intact. **Agreement statuses too**: dues refused on a
   non-`active` agreement (§7.1), `settled` reached only when every instalment is
   paid *and* no charge note is outstanding (§5.1.1).
4. Allocation: partial/multi-target, over-allocation rejection under
   concurrency, advance remainder, reversal contra rows. The concurrency test
   must assert the **`ORDER BY id` on the locking read**, not only the absence of
   over-allocation — that assertion alone passes for the wrong reasons, and
   mis-ordered locks deadlock rather than over-allocate. Mutation-check it:
   removing the lock must make the test fail.
5. Posting: each matrix entry balanced, party carried on control lines
   (ADR-0007 invariant 4), dimensions on every line. **A1 is never driven
   negative** by a due raised against an unactivated agreement (§7.1).
6. Statement: GL-derived rows equal expected running balance (reproduce the
   workbook's 2,534.20 position from its transactions); reprint stability after
   a reversal. **Opening balance is not double-counted** for a customer holding
   both a non-zero `ar.Customer.opening_balance` and a posted migration journal
   (§9).
7. Migration (Slice B): row counts, checksums of money columns, JE links
   preserved, fleet endpoints still green through delegation, `/loans` routes
   still 200 (§13).
8. Driver interaction (Slice G): a settlement whose other deductions already
   exhaust earnings raises **no** finance set-off and **no** double obligation;
   an unpaid instalment remainder stays on the finance side and never becomes a
   driver receivable (§10.1).

## 16. Implementation slices (reviewable order)

| Slice | Content | Depends on |
|---|---|---|
| **A** | `FLAT_QUOTED_EFFECTIVE` in the existing fleet engine + golden workbook test (immediately useful; zero refactor risk) | — |
| **B** | `apps/financing`: models, migrated data, delegating fleet API (ADR-0010) | A |
| **C** | Receivable agreements: activation, schedule reuse, raise-dues posting (§7.1–7.2) | B |
| **D** | Receipts & allocation service, billing statuses, reversal path (§6, §8) | C |
| **E** | Charge notes: recharge items, deposits, who-paid trace (§5.3, §7.4) | C |
| **F** | Customer statement + position panel + PDF/Excel export (§9, §14) | D (E enriches) |
| **G** | Driver earnings set-off in settlements (§10) | D + settlements slice |

Each slice ships with its tests, lint/mypy clean, and its section of this doc
updated — same bar as PR #53.

## 17. Open policy decisions

Still genuinely open (accounting/tax positions — advisory, not code):

1. **Vehicle derecognition at activation** — installment sale (derecognize,
   book gain/loss) vs retain until title transfer. Affects §7.1's account mapping
   and nothing else, so it stays cheap to defer: the activation template is the
   only place it lands, and §7.1's activation guard works either way.
2. **VAT classification** of finance income and each recharge item type. Already
   deferred structurally by the per-line `tax_code` (§11) — no code waits on this,
   only the configured values.

Resolved during review (recorded here so the decisions are not relitigated):

3. **Overdue grace** — *entity configuration, default 0 days*. Not cosmetic: the
   derived `overdue` flag (§6), the aging buckets (§14) and any future dunning
   must all read one value, so it cannot be a constant in a queryset annotation.
4. **Early settlement** — *mechanism settled, formula still open*. Foreclosure
   re-versions the schedule with a single settlement instalment (§6.1), reusing
   versioning and approval locking rather than adding machinery. Only the
   interest-rebate formula needs a real case to decide, and it does not change
   the mechanism.

## 18. Review log

**2026-07-26 — implementation review** (post Slice A, against the shipped code).
Arithmetic re-verified end to end: the 4.503853% back-solve, EMI 169,416 / 36 =
4,706.00 exactly, the §7.2 split 3,658.63 + 1,047.37, and the after-12
contractual remainder all tie. Changes folded in:

| # | Issue | Resolution |
|---|---|---|
| 1 | Raise-dues assumed an activation entry §7.1 left optional — A1 would go silently negative | Activation is a hard precondition; §5.1.1 + §7.1 |
| 2 | §9 added both the A2 GL sum *and* `ar.Customer.opening_balance` — double-counts migrated openings | GL only; §9 |
| 3 | `status → settled` had no transition; §17.4 deferred the only route to it | §5.1.1 transition table + §6.1 early-settlement mechanism |
| 4 | §10 could produce a finance set-off *and* a driver receivable for the same unpaid money | Set-off capped at earnings actually available; §10.1 |
| 5 | §12 endpoints were unversioned, against CLAUDE.md §6 | `/api/v1/financing/` |
| 6 | `apps/financing` absent from CLAUDE.md §3's app list | Slice B updates the list and `LOCAL_APPS`; §3 |
| 7 | `SettlementAllocation` collided with `drivers.Settlement` | Renamed `FinanceAllocation`; §5.4 |
| 8 | "under row locks" under-specified | PK-ordered acquisition + recompute inside the lock; §5.4, §15.4 |
| 9 | §11 called due-date recognition a "clean accrual base" | Stated as a deliberate simplification with its boundary case; §7.2, §11 |
| 10 | `reverses` FK referenced in prose, missing from the field table | Added; §5.4 |
| 11 | "principal > 0 on activation" listed as a CHECK | Service rule — status-dependent; §5.1 |
| 12 | §13 repoints `/loans` with no note that it is live | Must stay green across Slice B; §13 |
