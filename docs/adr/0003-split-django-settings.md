# ADR-0003 — Split Django Settings Module

**Status:** Accepted
**Date:** 2026-06-28
**Author:** Govind
**Supersedes:** —
**Superseded by:** —

---

## Context

FinCare runs in four distinct environments — local dev, CI/test, staging, production — each with different needs around DEBUG, database, cache, logging, throttling, security headers, and feature flags. A single `settings.py` file with conditional branches becomes unreadable fast and is a common source of "works in dev but breaks in prod" bugs.

---

## Decision

Use a **package-based split settings** layout:

```
fincare/settings/
├── __init__.py
├── base.py       # shared defaults — single source of truth
├── dev.py        # local: DEBUG=True, debug toolbar, silk profiler
├── test.py       # CI/pytest: in-memory cache, eager Celery, fast hashers
└── prod.py       # production: HSTS, WhiteNoise, Sentry, hardened cookies
```

Environment selection via `DJANGO_SETTINGS_MODULE`. Each non-base file does `from .base import *` and overrides only what differs. Environment-driven config (DATABASE_URL, REDIS_URL, secret key, allowed hosts, etc.) is loaded via `django-environ` from the OS environment or a `.env` file at repo root.

---

## Alternatives Considered

| Option | Rejected Because |
|---|---|
| Single `settings.py` with `if DEBUG` branches | Becomes a tangle as env count grows; risk of leaking dev defaults into prod |
| YAML/JSON config file loaded by Django | Adds a parser dependency; loses Python expressiveness (timedelta, callables) |
| `django-configurations` (class-based) | Extra dependency; mixin model adds inheritance complexity beyond benefit |
| 12-factor: env only, no split files | Loses the ability to express composed/derived defaults; harder to review env-specific behavior |

---

## Consequences

**Easier:**
- One file per environment, each easy to read end-to-end.
- Production secrets cannot leak into dev defaults.
- New environments (e.g. `staging.py`) can be added without touching the others.
- CI test settings are explicit and stable.

**Harder:**
- Slight boilerplate: every env file starts with `from .base import *`.
- Developers must remember to set `DJANGO_SETTINGS_MODULE` correctly (handled by Docker, Makefile, manage.py, and CI workflow).

---

## Risks

- A change to `base.py` affects all environments simultaneously — mitigated by CI running the test settings on every PR.
- `from .base import *` masks where a setting was defined — mitigated by keeping overrides narrow and commented.

---

## Migration Notes

Not applicable — this is the initial structure.
