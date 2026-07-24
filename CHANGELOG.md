# Changelog

All notable changes to FinCare will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-07-24

First application release — the complete FinCare accounting backend.

### Added
- **Accounting backend** across 21 Django apps: `core`, `users`, `settings`,
  `audit`, `tenants`, `accounts`, `ledger`, `vouchers`, `ar`, `ap`, `banking`,
  `cashbook`, `tax`, `fleet`, `drivers`, `bookings`, `platforms`, `payroll`,
  `reports`, `exports`, `integrations`.
- Double-entry posting engine (`apps.ledger.services.posting`): atomic, balanced,
  period-gated, immutable with reversal-based corrections (ADR-0007).
- PostgreSQL Row-Level Security multi-tenancy with per-request entity scoping.
- Chart of Accounts with `EEE-MMM-SSS-CCC` account coding (ADR-0004/0005).
- UAE VAT (FTA VAT 201) and Corporate Tax modelling; VAT-group shared TRN (ADR-0006).
- Sub-ledgers: AR/AP with aging, banking with reconciliation, cashbook, vouchers.
- Fleet / driver / bookings / platforms modules with per-vehicle and per-driver
  profitability tagging.
- WPS-ready payroll (gratuity, leave, advances).
- Financial reporting (statements, trial balance, consolidation, profitability) with
  Excel (openpyxl) and PDF (WeasyPrint) exporters.
- JWT auth, role-based access control, OpenAPI schema (drf-spectacular).
- Repository scaffold: CI/security/CodeQL workflows, Docker baseline, GitFlow-Lite,
  Conventional Commits, pre-commit (ruff/black/isort/mypy/bandit/gitleaks), CODEOWNERS,
  and Architecture Decision Records.

### Changed
- Upgraded to **Django 6.0** (from 5.0), including the coupled `django-celery-beat` /
  `redis` bumps and the `CheckConstraint(check=...)` → `condition=` migration.
- Modernised the dev toolchain: pytest 9, black 26, ruff 0.15, isort 8, mypy.
- Updated CI actions: CodeQL v4, setup-python, setup-buildx, gitleaks, dependency-review.
- Corrected the Celery worker/beat Docker healthchecks (worker pings; beat opts out).

### Security
- Resolved all outstanding Dependabot advisories (**80 → 0**; 6 critical, 25 high),
  covering Django, WeasyPrint, and sentry-sdk on the production dependency set.

[Unreleased]: https://github.com/govind4liwa/fincare/compare/v0.1.0...develop
[0.1.0]: https://github.com/govind4liwa/fincare/releases/tag/v0.1.0
