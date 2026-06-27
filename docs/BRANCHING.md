# Branching Strategy — GitFlow-Lite

FinCare uses a **GitFlow-Lite** model: a simplified GitFlow that keeps the stability of release branches without the overhead of long-running feature integration branches.

---

## Branches

| Branch | Lifetime | Source | Merges Into | Protected |
|---|---|---|---|---|
| `main` | Permanent | — | — | ✅ Strict |
| `develop` | Permanent | `main` | `release/*`, `hotfix/*` | ✅ |
| `feature/*` | Short-lived | `develop` | `develop` | ❌ |
| `fix/*` | Short-lived | `develop` | `develop` | ❌ |
| `chore/*` | Short-lived | `develop` | `develop` | ❌ |
| `docs/*` | Short-lived | `develop` | `develop` | ❌ |
| `release/vX.Y.Z` | Short-lived | `develop` | `main` + back to `develop` | ✅ |
| `hotfix/*` | Short-lived | `main` | `main` + back to `develop` | ❌ |

---

## Flow

```
main         ──●──────────────●──────────────●─────── (tagged releases v1.0.0, v1.0.1, v1.1.0)
                ↑              ↑              ↑
release/v1.0.0  ●━━━━━━━━━━━━━━●              │
                ↑              ↑    hotfix    │
develop      ──●──●──●──●──●──●──●──●──●──●──●─────── (integration)
                  ↑     ↑              ↑
feature/COA-12    ●━━━━━●              │
fix/AR-47                  ●━━━━━━━━━━━●
```

---

## Branch Naming

Format: `<type>/<ticket-id>-<short-slug>`

| Type | Example |
|---|---|
| `feature/` | `feature/COA-12-account-master-crud` |
| `fix/` | `fix/AR-47-aging-rounding` |
| `hotfix/` | `hotfix/LED-91-trial-balance-discrepancy` |
| `release/` | `release/v0.1.0` |
| `chore/` | `chore/upgrade-django-5.0` |
| `docs/` | `docs/erd-accounting-core` |

Rules:
- Lowercase, kebab-case after the type prefix.
- Include ticket ID matching the issue/board tracker.
- Max 60 characters total.

---

## Merge Strategy

| From → To | Method | Why |
|---|---|---|
| `feature/*` → `develop` | **Squash merge** | Keep `develop` linear and readable |
| `fix/*` → `develop` | **Squash merge** | Same |
| `release/*` → `main` | **Merge commit** | Preserve release branch history |
| `release/*` → `develop` | **Merge commit** | Bring back release commits |
| `hotfix/*` → `main` | **Merge commit** | Audit trail of the hotfix |
| `hotfix/*` → `develop` | **Merge commit** | Sync the fix |

---

## Release Process

1. Stabilize `develop`. All targeted features merged.
2. Cut `release/vX.Y.Z` from `develop`.
3. On the release branch:
   - Bump version in `pyproject.toml`.
   - Update `CHANGELOG.md` — move `[Unreleased]` to new version.
   - Run full QA / UAT.
   - Apply only bug fixes; **no new features**.
4. Open PR `release/vX.Y.Z` → `main`. Merge with **merge commit**.
5. Tag `main` as `vX.Y.Z` (signed tag preferred).
6. Open PR `release/vX.Y.Z` → `develop`. Merge with **merge commit** to sync.
7. Delete the release branch.

---

## Hotfix Process

1. Cut `hotfix/<id>-<slug>` from `main`.
2. Fix, test, bump patch version, update `CHANGELOG.md`.
3. Open PR `hotfix/*` → `main`. Merge, tag a new patch version.
4. Open PR `hotfix/*` → `develop`. Merge to sync.
5. Delete the hotfix branch.

---

## Branch Protection (Enforced in GitHub)

Configured under **Settings → Branches**. See `02_FinCare_Repo_Setup_Guide.md` (planning doc) for the full rule set.

Summary:

| Rule | `main` | `develop` | `release/*` |
|---|---|---|---|
| Require PR | ✅ | ✅ | ✅ |
| Required reviewers | 1 | 1 | 1 |
| Required status checks | All | All | All |
| Dismiss stale approvals | ✅ | ✅ | ✅ |
| Require Code Owner review | ✅ | ⬜ | ✅ |
| Require linear history | ⬜ | ✅ | ⬜ |
| Require signed commits | ✅ | ⬜ | ⬜ |
| Allow force push | ❌ | ❌ | ❌ |
| Allow deletion | ❌ | ❌ | ❌ |

---

## Default Branch

`develop` is the **default branch** for day-to-day work. Configure under **Settings → General → Default branch**.

`main` represents what is in production.
