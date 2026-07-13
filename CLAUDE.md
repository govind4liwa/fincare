# CLAUDE.md — FinCare Engineering Guardrails

> This file is read automatically by Claude Code at the start of every session.
> It encodes the non-negotiable rules for FinCare. Treat everything here as
> binding unless the human explicitly overrides it in-session.

---

## 1. Project

**FinCare** — professional bookkeeping & accounting system for UAE SMEs and
multi-entity groups (transport, limousine, restaurant, workshop, tours and travels, baqala,
grocery shop, trading, service). Supports **cash-basis** and **accrual-basis** accounting, UAE VAT,
Corporate Tax tagging, multi-entity consolidation, and per-vehicle / per-driver
profitability for transport operators.

Repo: `github.com/govind4liwa/fincare` · Default branch: `develop`

---

## 2. Stack (do not substitute without an ADR)

| Layer | Technology |
|---|---|
| Backend | Python 3.14.6, Django 6.x, Django REST Framework |
| Database | PostgreSQL 18.4 with Row-Level Security (RLS) |
| Cache / Queue | Redis 8.8, Celery |
| Auth | JWT (djangorestframework-simplejwt) |
| Frontend | Next.js 16.3, Tailwind CSS, shadcn/ui *(Phase 1.6)* |
| Reporting | openpyxl (Excel), WeasyPrint (PDF) |
| Deployment | Docker, Docker Compose, Ubuntu VPS |
| Quality | ruff, black, isort, mypy, pytest, bandit, CodeQL |

---

## 3. Repository Layout

```
fincare-repo/
├── apps/                # all Django apps live here (apps.<name>)
│   └── core/            # base models, mixins, currency, sequences
├── fincare/             # project package
│   └── settings/        # split: base.py, dev.py, prod.py, test.py
├── docs/                # ADRs, dev guide, conventions, this playbook
├── requirements/        # base.txt, dev.txt, prod.txt
├── scripts/             # bootstrap.ps1 / bootstrap.sh
├── docker-compose.yml
├── Makefile
└── manage.py
```

**App naming:** apps are referenced as `apps.<name>` (e.g. `apps.ledger`).
New apps go under `apps/` and must be added to `LOCAL_APPS` in
`fincare/settings/base.py`.

**Planned apps (one domain each — do not collapse):**
`core, users, settings, audit, tenants, accounts, ledger, vouchers, ar, ap,`
`banking, cashbook, tax, fleet, drivers, bookings, platforms, payroll,`
`reports, exports, integrations`

---

## 4. Accounting Rules — NON-NEGOTIABLE

These protect the integrity of the books. Never relax them to make a test pass.

1. **Double-entry only.** Every posting must satisfy `total_debit == total_credit`.
   Validate this in the service layer before writing, and assert it in tests.
2. **Money is `Decimal`, never `float`.** Use `DecimalField(max_digits=18, decimal_places=2)`.
   Default currency `AED`; every monetary row carries a `currency` field.
3. **Posting logic lives in a services layer** (`apps/<app>/services/`), never in
   views or serializers. Views call services; services own the transaction.
4. **Wrap all financial posting in `transaction.atomic()`.** A partially-posted
   document is a bug.
5. **Posted transactions are immutable.** Never `DELETE` a posted accounting row.
   Lifecycle is `draft → validated → posted → (reversed | cancelled)`.
   Corrections happen via reversing entries, not edits.
6. **UUID primary keys** on all transactional models.
7. **Audit fields on every model:** `created_at`, `updated_at`, `created_by`,
   `updated_by`; soft delete (`is_deleted` / `deleted_at`) where appropriate.
8. **No hardcoded UAE values.** VAT rate, TRN, fiscal year, numbering series, and
   account codes are configuration-driven (in `settings`/`tenants`), never literals.

### Standard postings (reference)

```
Sales Invoice (post):   DR Accounts Receivable
                        CR Sales Revenue
                        CR Output VAT            (if taxable)

Customer Receipt:       DR Bank / Cash
                        CR Accounts Receivable

Expense Payment:        DR Expense Account
                        DR Input VAT             (if recoverable)
                        CR Cash / Bank / Supplier

Vehicle EMI Payment:    DR Vehicle Loan Payable
                        DR Loan Interest Expense
                        CR Bank
```

---

## 5. Multi-Entity / Tenancy

- Every transactional table carries `entity_id` (+ `branch_id` where relevant).
- Tenant isolation is enforced at the DB layer via **PostgreSQL RLS**, not only in
  Python. Do not bypass RLS in queries; set the tenant context per request.
- Intercompany transactions are explicit and balanced on both entities.
- Reports support both entity-level and consolidated group-level views.

---

## 6. API Conventions

- REST, versioned under `/api/v1/`.
- One DRF `ViewSet` per resource; **serializer + permission class on every endpoint**.
- Permissions are role-based (RBAC); posting/approval actions require explicit perms.
- Document state transitions are dedicated actions (e.g. `POST .../{id}/post/`),
  not generic `PATCH` of a `status` field.
- All list endpoints: pagination, filtering, ordering. Schema via drf-spectacular.

---

## 7. Definition of Done

A change is complete only when **all** of these hold:

- [ ] Migration-safe (no destructive op without a documented plan)
- [ ] Service layer owns the posting; view is thin
- [ ] Serializer + permission on every new endpoint
- [ ] Unit test proving `debit == credit` for any new posting path
- [ ] `make lint` (ruff/black/isort/mypy) and `make test` (pytest) pass
- [ ] No floats for money; no deletion of posted rows
- [ ] Config-driven (no hardcoded UAE constants)
- [ ] ADR added under `docs/adr/` for any architectural decision

---

## 8. Working Style for Claude Code

- **Do not start coding a module until its models + posting logic are agreed.**
  When asked for a new module, first propose: models (ERD table form) → service
  posting logic → API → tests, then implement.
- Prefer small, reviewable diffs. One module or one concern per change.
- Run `make lint && make test` before declaring a task done; report results.
- When you make an architectural choice, write an ADR (`docs/adr/NNNN-title.md`)
  following the existing format.
- Use `Decimal`, `transaction.atomic`, and the audit mixins from `apps.core`.
- If a request conflicts with the accounting rules in §4, stop and flag it.

### Common commands

```bash
make lint              # ruff + black + isort + mypy
make test              # pytest
make migrations        # makemigrations
make migrate           # migrate
docker compose up -d   # Postgres + Redis + web
```

---

## 9. Compliance Note

FinCare implements system logic for UAE VAT and Corporate Tax. It does **not**
provide tax advisory. Keep the boundary clear: the system computes and reports;
final tax positions are the user's advisory decision. Maintain an audit-ready
transaction trail for everything posted.

## 10. Chart of Accounts Numbering (binding — see ADR-0004)

All account codes follow the fixed pattern **`EEE-MMM-SSS-CCC`**
(example: `101-400-410-001`). Segments:

- **Entity (3 digits)** = category band (1 digit) + entity sequence (2 digits),
  e.g. `101` = transport entity #01. Stored as `tenants_entity.numeric_code`.
- **Main Account (3 digits)** — level-1 group; first digit = nature
  (1 asset, 2 liability, 3 equity, 4 income, 5 direct cost, 6 expense, 7 finance/tax).
- **Sub-Account (3 digits)** — level-2 group.
- **Charge Code (3 digits)** — the postable leaf account.

Rules: codes are generated and validated only in
`apps/accounts/services/coding.py` (regex `^\d{3}-\d{3}-\d{3}-\d{3}$`, DB CHECK +
serializer). The entity segment is copied from the entity master, never typed.
Codes are immutable once posted to. Category bands and the COA template per
category are defined in ADR-0005; VAT grouping in ADR-0006.