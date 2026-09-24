# Development Guide

Local setup and day-to-day workflow for FinCare contributors.

---

## 1. Prerequisites

| Tool | Min Version |
|---|---|
| Git | 2.40 |
| Python | 3.12 |
| Docker Desktop | 4.30 |
| Node.js | 20 LTS (Phase 1.6) |
| Make | GNU Make 4.x (Windows: via Git Bash or `choco install make`) |

---

## 2. First-Time Setup

```bash
# Clone
git clone https://github.com/govind4liwa/fincare.git
cd fincare

# Bootstrap (creates venv, installs deps, sets up pre-commit, copies .env)
# Windows:
.\scripts\bootstrap.ps1
# macOS / Linux:
./scripts/bootstrap.sh

# Start the stack
docker compose up -d

# Verify
docker compose ps
docker compose logs -f web
```

App available at:
- **API:** http://localhost:8005/api/v1/
- **Admin:** http://localhost:8005/admin/
- **Schema (Swagger):** http://localhost:8005/api/schema/swagger/
- **Schema (Redoc):** http://localhost:8005/api/schema/redoc/

---

## 3. Daily Workflow

```bash
# 1. Pull latest develop
git checkout develop
git pull

# 2. Create branch
git checkout -b feature/LED-12-posting-engine

# 3. Run stack
docker compose up -d

# 4. Make changes, run tests
make test
make lint

# 5. Auto-format
make format

# 6. Commit (pre-commit hooks run automatically)
git add .
git commit -m "feat(ledger): implement posting engine balance guard"

# 7. Push
git push -u origin feature/LED-12-posting-engine

# 8. Open PR via GitHub UI or gh CLI
gh pr create --base develop --fill
```

---

## 4. Make Targets

Run `make help` to see all. Common:

| Target | Purpose |
|---|---|
| `make install` | Install dev deps + pre-commit hooks |
| `make up` / `make down` | Start / stop Docker stack |
| `make logs` | Tail container logs |
| `make shell` | Django shell in `web` container |
| `make db-shell` | psql in `db` container |
| `make migrate` | Apply migrations |
| `make makemigrations` | Create new migrations |
| `make check-migrations` | Verify no pending migrations |
| `make test` | Run pytest |
| `make test-cov` | Run pytest with coverage |
| `make lint` | Run all linters |
| `make format` | Auto-format with black + ruff + isort |
| `make typecheck` | Run mypy |
| `make security` | Run bandit + safety |
| `make seed` | Seed COA and tax data |
| `make reset-db` | DROP and recreate database (DESTRUCTIVE) |

---

## 5. Directory Map

```
fincare/
├── .github/              CI workflows, CODEOWNERS, templates
├── apps/                 Django apps (created from Phase 1.0 onward)
│   ├── core/             Base models, mixins, services
│   ├── users/            Auth, RBAC
│   ├── tenants/          Entities, branches, cost centers
│   ├── accounts/         Chart of Accounts
│   ├── ledger/           Journal entries, posting engine
│   ├── vouchers/         Receipt/Payment/Journal/Contra
│   ├── ar/               Customers, invoices, receipts
│   ├── ap/               Suppliers, bills, payments
│   ├── banking/          Bank accounts, BRS
│   ├── cashbook/         Cash and petty cash
│   ├── tax/              VAT, Corporate Tax
│   ├── fleet/            Vehicles
│   ├── drivers/          Drivers
│   ├── bookings/         Trips, contracts
│   ├── platforms/        Uber/Yango/Bolt
│   ├── payroll/          WPS payroll
│   ├── reports/          Financial statements
│   ├── exports/          Excel/PDF generators
│   ├── audit/            Audit trail
│   └── integrations/     External APIs
├── docs/                 PRD, SRS, ADR, ERD, SOP
├── fincare/              Django project package (settings, urls, wsgi)
├── requirements/         base.txt, dev.txt, prod.txt
├── scripts/              Bootstrap, seed, helpers
├── tests/                Top-level integration tests
└── manage.py
```

---

## 6. Testing

- Unit tests live alongside the app: `apps/<app>/tests/`.
- Cross-app integration tests live in top-level `tests/integration/`.
- Use `factory-boy` for test data, not raw `Model.objects.create`.
- Mark slow tests with `@pytest.mark.slow` and skip in dev loop: `pytest -m "not slow"`.
- **Posting tests** must verify both the journal lines and the resulting account balances.

```bash
# Run subset
pytest apps/ledger/tests/test_posting.py -v
pytest -m posting -v
pytest -m "not slow"
```

---

## 7. Database

| Task | Command |
|---|---|
| Open psql | `make db-shell` |
| Apply migrations | `make migrate` |
| Create migrations | `make makemigrations` |
| Verify no pending | `make check-migrations` |
| Reset (DESTRUCTIVE) | `make reset-db` |
| Seed COA | `make seed` |

Migration rules:

1. One migration per concern.
2. Never edit a migration that has been merged to `develop` or `main`.
3. For data migrations, write idempotent reverse operations.
4. Run `check-migrations` before every commit.

---

## 7b. Row-Level Security rollout (ADR-0008)

Tenant isolation is enforced in the database by PostgreSQL RLS, but it is gated
by `RLS_ENABLED` (default `False`) so it can be switched on deliberately. Two
things must be true before enabling it in an environment.

**1. The application must connect as a non-superuser.** A superuser bypasses RLS
entirely, so leaving the app on a superuser login silently defeats the policies
even with `RLS_ENABLED=True`.

**2. That login role must be allowed to assume the restricted role.** The
middleware issues `SET LOCAL ROLE fincare_app` on every request. Migration
`0003_rls` creates `fincare_app` and grants it table privileges, but it cannot
grant *membership* — the login role's name is environment-specific. Run once,
as a superuser, against each environment's database:

```sql
GRANT fincare_app TO <application_login_role>;
```

Without it every request fails with `permission denied to set role "fincare_app"`.

Then set `RLS_ENABLED=true` in the environment and restart. To confirm it is
actually on, check that a request is scoped rather than trusting the setting:

```sql
-- inside a request the app should be fincare_app, not the login role
SELECT current_user, current_setting('app.current_entities', true);
```

An unset (or empty) context means *unrestricted* — that is the sentinel for
migrations, shell sessions and superusers. A request that resolves to no
accessible entities is given an explicit no-access sentinel instead, so "no
entities" can never be mistaken for "no context".

---

## 8. Pre-commit Hooks

Installed automatically by `make install` or `bootstrap` scripts. Hooks run:

- `trailing-whitespace`, `end-of-file-fixer`
- `check-yaml`, `check-toml`, `check-json`
- `check-added-large-files` (1 MB cap)
- `detect-private-key`, `gitleaks`
- `ruff` (lint + format)
- `black`, `isort`
- `mypy`
- `bandit`
- `conventional-pre-commit` (commit message format)

Bypass only in genuine emergencies: `git commit --no-verify`.

---

## 9. Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| `psycopg.OperationalError: connection refused` | DB not ready | `docker compose logs db`; wait for healthcheck |
| `relation "..." does not exist` | Missing migrations | `make migrate` |
| `port 55432 already in use` | Another FinCare/PostgreSQL mapping is running | Change `POSTGRES_HOST_PORT` in `.env` |
| Pre-commit hook fails on commit | Style/lint issue | `make format`, recommit |
| `make` not found on Windows | Make not installed | `choco install make` or use Git Bash |

---

## 10. Editor Setup

VS Code recommended extensions (auto-suggested when opening the repo):

- `ms-python.python`
- `charliermarsh.ruff`
- `ms-python.black-formatter`
- `ms-python.mypy-type-checker`
- `batisteo.vscode-django`
- `redhat.vscode-yaml`
- `editorconfig.editorconfig`
