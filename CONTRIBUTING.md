# Contributing to FinCare

Thank you for contributing. FinCare is a financial system — correctness, traceability, and auditability take precedence over speed.

---

## 1. Code of Conduct

Be professional, precise, and respectful. Disagreements about technical decisions go in PR comments or ADRs, never in commit messages.

---

## 2. Development Workflow

1. **Pick an issue** from GitHub Issues or the project board.
2. **Create a branch** from `develop` following [docs/BRANCHING.md](docs/BRANCHING.md).
3. **Write tests first** for any posting logic, financial calculation, or business rule.
4. **Implement** the change.
5. **Run quality gates locally** (`make lint format typecheck test security`).
6. **Commit** using [Conventional Commits](docs/COMMIT_CONVENTION.md).
7. **Open a Pull Request** into `develop` (or `main` for hotfix).
8. **Address review comments** until approval.
9. **Squash-merge** unless the PR is a release or hotfix.

---

## 3. Local Setup

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

Quick:

```bash
.\scripts\bootstrap.ps1       # Windows
./scripts/bootstrap.sh        # macOS / Linux
docker compose up -d
```

---

## 4. Coding Standards

| Area | Rule |
|---|---|
| Formatting | `black` + `isort` (run `make format`) |
| Linting | `ruff` must pass |
| Typing | `mypy` should not regress; new code adds annotations |
| Tests | New features require tests; coverage stays ≥ 80% |
| Migrations | One migration per concern; never edit applied migrations |
| Money fields | `DECIMAL(18,4)` — never `FLOAT` |
| Posting | All GL writes go through `apps.ledger.services.posting` |
| Tenancy | Every transactional model carries `entity_id`; queries pass through tenant manager |
| Logging | Use `structlog`, not `print` |
| Secrets | Never commit secrets; use `.env`; rotate if leaked |

---

## 5. Pull Request Checklist

Before requesting review:

- [ ] Branch is up-to-date with `develop`
- [ ] All CI checks green
- [ ] Tests added/updated
- [ ] Migrations created if models changed
- [ ] `make check-migrations` returns clean
- [ ] No new TODOs introduced without a tracking issue
- [ ] Docs/ADR updated if architecture changed
- [ ] PR description completed using the template

---

## 6. Reporting Bugs / Requesting Features

Use GitHub Issues with the provided templates (bug report / feature request). For security issues, see [SECURITY.md](SECURITY.md) — do **not** open a public issue.

---

## 7. Reviewer Guidelines

When reviewing:

- **Posting logic** — verify balance invariants, period checks, idempotency.
- **Migrations** — verify reversibility and data preservation.
- **Permissions** — confirm RBAC and tenant scoping applied.
- **Money math** — confirm `Decimal`, not `float`; rounding rules consistent.
- **N+1 queries** — flag in ORM-heavy paths.
- **Tests** — confirm they fail without the fix.
