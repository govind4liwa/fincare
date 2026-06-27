# Changelog

All notable changes to FinCare will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial repository scaffold with CI, docs, and Docker baseline.
- GitFlow-Lite branching strategy.
- Conventional Commits enforced via pre-commit hook.
- GitHub Actions: `ci.yml`, `security.yml`, `codeql.yml`.
- Pre-commit config: ruff, black, isort, mypy, bandit, gitleaks.
- Multi-stage Dockerfile and Docker Compose with Postgres 16 + Redis 7.
- Pinned base/dev/prod Python requirements.
- CODEOWNERS, PR template, issue templates.
- ADR 0001 — Record Architecture Decisions.

[Unreleased]: https://github.com/govind4liwa/fincare/commits/develop
