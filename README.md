# FinCare

**Professional bookkeeping & accounting system for UAE SMEs and multi-entity groups.**

Built for transportation, limousine, restaurant, workshop, trading, and service businesses. Supports both **cash-basis** and **accrual-basis** accounting, UAE VAT, Corporate Tax tagging, multi-entity consolidation, and per-vehicle / per-driver profitability for transport operators.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, Django 5.x, Django REST Framework |
| Database | PostgreSQL 16 (with Row-Level Security) |
| Cache / Queue | Redis 7, Celery |
| Frontend | Next.js 14, Tailwind CSS, shadcn/ui *(Phase 1.6)* |
| Auth | JWT (SimpleJWT) |
| Reporting | openpyxl (Excel), WeasyPrint (PDF) |
| Deployment | Docker, Docker Compose, Ubuntu VPS |
| CI/CD | GitHub Actions |
| Quality | ruff, black, isort, mypy, pytest, bandit, CodeQL |

---

## Quick Start (Local Development)

```bash
git clone https://github.com/govind4liwa/fincare.git
cd fincare

# Windows
.\scripts\bootstrap.ps1

# Bring up Postgres + Redis + Django
docker compose up -d

# Verify
docker compose ps
docker compose logs -f web
```

App: http://localhost:8000
Admin: http://localhost:8000/admin
API schema: http://localhost:8000/api/schema/swagger/

---

## Repository Layout

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for the full module map. Top level:

```
fincare/
├── .github/          GitHub Actions, CODEOWNERS, templates
├── apps/             Django apps (added in Phase 1.0+)
├── docs/             PRD, SRS, ADR, ERD, SOP
├── requirements/     Pinned dependencies (base / dev / prod)
├── scripts/          Bootstrap, seed, migration helpers
├── tests/            Top-level integration tests
├── docker-compose.yml
├── Dockerfile
├── Makefile
└── pyproject.toml
```

---

## Documentation

| Doc | Purpose |
|---|---|
| [docs/BRANCHING.md](docs/BRANCHING.md) | GitFlow-Lite branch strategy |
| [docs/COMMIT_CONVENTION.md](docs/COMMIT_CONVENTION.md) | Conventional Commits guide |
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | Local setup and contribution flow |
| [docs/adr/](docs/adr/) | Architecture Decision Records |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to contribute |
| [SECURITY.md](SECURITY.md) | Security reporting |

---

## Modules (Planned — Phase 1)

`core` · `users` · `tenants` · `settings` · `audit` · `accounts` · `ledger` · `vouchers` · `ar` · `ap` · `banking` · `cashbook` · `tax` · `fleet` · `drivers` · `bookings` · `platforms` · `payroll` · `reports` · `exports` · `integrations`

---

## License

Proprietary — All Rights Reserved. See [LICENSE](LICENSE).

---

## Maintainer

Govind ([@govind4liwa](https://github.com/govind4liwa)) — govind4liwa@yahoo.com
