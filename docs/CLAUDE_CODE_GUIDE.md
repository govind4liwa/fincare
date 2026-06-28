# Using Claude Code on FinCare

A practical playbook for driving FinCare development with Claude Code. Pair this
with the root `CLAUDE.md`, which Claude Code loads automatically each session.

---

## 1. Install & Authenticate (Windows)

The native installer is the recommended method in 2026 (no Node.js / PATH setup,
auto-updates). In PowerShell:

```powershell
irm https://claude.ai/install.ps1 | iex
```

npm alternative (needs Node.js 18+):

```powershell
npm install -g @anthropic-ai/claude-code
```

First run authenticates via browser:

```powershell
cd E:\eSystem\FinCare\fincare-repo
claude
```

---

## 2. Session Workflow

```powershell
cd E:\eSystem\FinCare\fincare-repo
git checkout develop
git pull
claude
```

Claude Code reads `CLAUDE.md` at the repo root on every start, so the accounting
rules, stack, and Definition of Done are always in context.

Useful in-session commands:

| Command | Purpose |
|---|---|
| `/clear` | Reset context between unrelated tasks (keeps token use low) |
| `/init` | Regenerate / refresh `CLAUDE.md` |
| `/review` | Review a diff or PR |
| `@path/to/file` | Pull a specific file into context |
| `claude --resume` | Continue a previous session |

**Discipline that pays off:** one module or one concern per session; run
`make lint && make test` before accepting a change; commit on a feature branch.

---

## 3. Branch & Commit Convention

Follow the existing `docs/BRANCHING.md` and `docs/COMMIT_CONVENTION.md`. Typical
loop with Claude Code:

```powershell
git checkout -b feat/ledger-posting-engine
# ... work with Claude Code ...
make lint && make test
git commit -m "feat(ledger): double-entry posting engine with balance validator"
git push -u origin feat/ledger-posting-engine
```

Ask Claude Code to open the PR description for you, then `/review` the diff before
pushing.

---

## 4. Build Order — Ready-to-Paste Prompts

Work the Phase 1 roadmap in dependency order. Each prompt below is written to be
pasted directly into a Claude Code session. They assume `CLAUDE.md` is in context,
so they stay short and lean on the rules already defined there.

### Step 1 — Core foundation (`apps.core`)

```
Flesh out apps.core with the shared building blocks every other app depends on:
- BaseModel abstract: UUID pk, created_at/updated_at/created_by/updated_by,
  is_deleted + deleted_at soft delete, and a manager that excludes soft-deleted.
- Money helpers: a reusable DecimalField config (18,2) and a Currency model
  (code, name, symbol), default AED.
- A document numbering/sequence service (entity- and series-aware, gap-safe).
Add unit tests for the soft-delete manager and the sequence service.
Update LOCAL_APPS if needed. Run make lint && make test and report results.
```

### Step 2 — Tenancy (`apps.tenants`) + RLS

```
Implement apps.tenants: Entity, Branch, CostCenter, Department, and an
IntercompanyMap. Every model uses apps.core.BaseModel. Then add the PostgreSQL
RLS layer: a per-request tenant context (middleware setting a session GUC) and a
migration enabling RLS + policies on tenant-scoped tables. Write an ADR in
docs/adr/ describing the RLS approach. Add tests proving cross-entity rows are
not visible without the right tenant context.
```

### Step 3 — Chart of Accounts (`apps.accounts`)

```
Implement apps.accounts per docs/design/01-erd-core-tenants-accounts.md and
docs/adr/0004-chart-of-accounts-numbering.md. Enforce the EEE-MMM-SSS-CCC code
scheme (3-digit banded entity = category band + sequence): AccountGroup holds
Main (level 1) and Sub (level 2) segments; Account is the Charge-code leaf. Build
apps/accounts/services/coding.py to compose and validate codes (regex
^\d{3}-\d{3}-\d{3}-\d{3}$, entity segment from tenants_entity.numeric_code, band
from tenants_business_category.band, charge code via core_number_sequence).
Add a seed management command producing the worked-example UAE transport COA from
ADR-0004. Present models as ERD tables first, wait for my ok, then implement with
tests covering code composition and the entity-segment guard.
```

### Step 4 — Posting engine (`apps.ledger`)

```
Implement the heart of the system in apps.ledger:
- JournalEntry (header) + JournalLine (debit/credit, account, entity, branch,
  cost center) with the draft → validated → posted → reversed/cancelled lifecycle.
- A services/posting.py with post_journal_entry() that runs inside
  transaction.atomic(), validates total_debit == total_credit, blocks posting to
  closed periods, and forbids deletion/edit of posted entries (reversal only).
- AccountingPeriod model + close logic.
Tests must cover: balanced post succeeds, unbalanced post raises, posted entry is
immutable, reversal creates a mirror entry. Run make lint && make test.
```

### Step 5 — Vouchers (`apps.vouchers`)

```
Build apps.vouchers on top of the ledger engine: Receipt, Payment, Contra,
Journal, and Expense vouchers. Each voucher posts through
apps.ledger.services.post_journal_entry — do not write ledger rows directly.
Expose DRF ViewSets with a dedicated /post/ action and RBAC permissions. Tests
for each voucher's debit/credit mapping.
```

### Step 6 — AR & AP (`apps.ar`, `apps.ap`)

```
Implement apps.ar (Customer, SalesInvoice, CreditNote, Receipt, aging) and
apps.ap (Supplier, PurchaseBill, DebitNote, Payment, aging). Invoices and bills
post via the ledger engine with Output/Input VAT lines driven by apps.tax config
(no hardcoded rate). Add aging report queries and tests for the standard postings
in CLAUDE.md §4.
```

> Continue the same pattern for `banking`, `cashbook`, `tax`, then the operational
> modules (`fleet`, `drivers`, `bookings`, `platforms`, `payroll`) and finally
> `reports` / `exports`. Always: models → ERD review → service posting → API →
> tests.

---

## 5. Guardrails Recap (enforced by `CLAUDE.md`)

- Double-entry: `debit == credit` on every posting, proven by a test.
- `Decimal` for money, never `float`; default `AED`.
- Posting logic in the service layer, inside `transaction.atomic()`.
- Posted rows are immutable; correct via reversal.
- UUID PKs + audit fields + soft delete.
- No hardcoded UAE constants; everything config-driven.
- ADR for every architectural decision.

If Claude Code ever proposes something that breaks one of these, stop it and ask
for a reversal-safe / config-driven alternative.
