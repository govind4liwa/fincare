# Commit Message Convention — Conventional Commits

FinCare uses [Conventional Commits 1.0.0](https://www.conventionalcommits.org/).
Enforced by a pre-commit hook (`conventional-pre-commit`).

---

## Format

```
<type>(<scope>): <subject>

<body — optional, what & why, not how>

<footer — optional, refs/breaking changes>
```

- **type** — required, lowercase, from the list below.
- **scope** — optional but encouraged; a FinCare module name.
- **subject** — required, imperative, lowercase, no trailing period, ≤ 72 chars.
- **body** — wrap at 100 chars; one blank line after subject.
- **footer** — `Refs:`, `Closes:`, `BREAKING CHANGE:`.

---

## Types

| Type | Use For |
|---|---|
| `feat` | New feature |
| `fix` | Bug fix |
| `refactor` | Code restructuring, no behavior change |
| `perf` | Performance improvement |
| `test` | Adding or updating tests |
| `docs` | Documentation only |
| `chore` | Build, tooling, dependencies, misc |
| `ci` | CI/CD pipeline changes |
| `style` | Formatting only (whitespace, etc.) |
| `revert` | Reverting a prior commit |
| `build` | Build system or dependencies (alt. of chore) |

---

## Scopes (FinCare Modules)

`core` · `users` · `tenants` · `settings` · `audit` · `accounts` · `ledger` · `vouchers` · `ar` · `ap` · `banking` · `cashbook` · `tax` · `fleet` · `drivers` · `bookings` · `platforms` · `payroll` · `reports` · `exports` · `integrations` · `ci` · `docker` · `docs` · `deps`

Multiple scopes use commas: `feat(ar,ledger): post AR invoice via central posting engine`.

---

## Examples — Good

```
feat(ledger): implement double-entry posting engine with period guard

Centralizes all GL writes through post_entry() with these invariants:
- sum(debit) == sum(credit) in base currency
- period must be open
- only leaf accounts can be posted
- control accounts require sub-ledger reference

Refs: LED-12
```

```
fix(ar): correct aging bucket boundaries for end-of-month invoices

Previously an invoice dated on the last day of the month was being
double-counted between the 30-day and 60-day buckets due to inclusive
range comparison.

Closes: AR-47
```

```
docs(adr): record decision to use single accrual ledger with cash basis as report filter
```

```
chore(deps): bump Django from 5.0.4 to 5.0.6
```

```
ci: add coverage gate at 80% in pytest config
```

---

## Examples — Bad (and Why)

| Message | Why bad |
|---|---|
| `Fixed bug` | No type/scope; not imperative; vague |
| `feat: stuff` | No useful subject |
| `feat(ledger): Implements the posting engine.` | Capitalized + trailing period + non-imperative |
| `WIP` | Use draft PRs instead; squash before merge |
| `Merge branch 'feature/x' into develop` | Use squash merge to avoid these |

---

## Breaking Changes

Append `!` after the scope **and** add a `BREAKING CHANGE:` footer:

```
feat(accounts)!: switch COA codes from 4 to 5 digits

BREAKING CHANGE: existing 4-digit account codes must be migrated via
scripts/migrate_coa.py before applying this release. Old API endpoints
returning 4-digit codes remain available under /api/v1/ until v2.0.
```

Breaking changes trigger a **major version** bump under SemVer.

---

## Multi-line Body

```
refactor(ledger): extract balance assertion into separate validator

Splits the previously monolithic post_entry() into:
- validator.assert_balanced()
- validator.assert_period_open()
- posting.write_lines()

This makes each invariant independently testable and allows the
validator to be called in draft preview mode.

No behavior change. Test suite unchanged and green.
```

---

## Tooling

- **Local enforcement:** `pre-commit install --hook-type commit-msg`
- **CI enforcement:** `commitlint` step in `ci.yml` (Phase 1.1)
- **Changelog generation:** future — `git-cliff` or `release-please`
