# Security Policy

## Supported Versions

Phase 1 is in active development. Only `main` and `develop` are supported.

| Version | Supported |
|---|---|
| main (production) | ✅ |
| develop | ✅ |
| Older tags | ❌ |

---

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Report privately to: **govind4liwa@yahoo.com**

Include:

- Affected component / module
- Steps to reproduce
- Impact assessment (data exposure, integrity, availability)
- Suggested mitigation, if known

You will receive an acknowledgement within **3 business days** and a remediation plan within **10 business days** for confirmed issues.

---

## Scope

In scope:

- The FinCare backend (Django, DRF, Celery)
- Frontend (when deployed)
- CI/CD pipeline
- Default Docker deployment

Out of scope:

- Self-hosted, modified, or forked deployments
- Third-party dependencies (report to upstream)
- Social engineering of contributors

---

## Disclosure Policy

Coordinated disclosure. We will credit reporters in release notes unless anonymity is requested.

---

## Security Practices

- All dependencies are pinned and monitored via Dependabot.
- CI runs `bandit`, `safety`, `gitleaks`, and CodeQL on every PR.
- Posted accounting transactions are immutable; only reversal entries allow correction.
- All financial state changes are logged in the `audit` app with user attribution.
- Row-Level Security in PostgreSQL provides defense-in-depth on multi-tenant data.
- Secrets are managed via environment variables, never committed.
- Authentication uses JWT with short access tokens and rotating refresh tokens.
- Brute-force protection via `django-axes`.
- Content Security Policy enforced via `django-csp`.
