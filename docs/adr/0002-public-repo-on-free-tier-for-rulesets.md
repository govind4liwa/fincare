# ADR-0002 — Public Repository Visibility on GitHub Free Tier

**Status:** Accepted
**Date:** 2026-06-28
**Author:** Govind
**Supersedes:** —
**Superseded by:** —

---

## Context

FinCare needs server-side enforcement of branch protection rules: required PR reviews, required CI status checks, no force pushes, no branch deletion, linear history on `develop`, and code-owner review on `main`. These rules backstop the convention-based controls (CODEOWNERS, PR template, pre-commit hooks) and are non-negotiable for a financial system that will eventually carry production data.

On GitHub Free, neither the classic Branch Protection API nor the newer Repository Rulesets API are available on **private** repositories — both return HTTP 403 with "Upgrade to GitHub Pro or make this repository public." Verified directly on 2026-06-28.

We had three options:

1. **Stay private, defer protection** — relies entirely on developer discipline. Unacceptable for a financial system as the team grows.
2. **Upgrade to GitHub Pro** — ~$4/user/month. Small cost but adds a recurring expense at Phase 1 stage.
3. **Make the repo public** — unlocks free Rulesets immediately. Repo code becomes world-readable.

---

## Decision

Make the FinCare repository **public** while retaining the **Proprietary / All Rights Reserved** license.

This is the "source-available" pattern: the code is visible to anyone, but the LICENSE forbids use, modification, distribution, and the creation of derivative works without explicit written permission. Viewers can read but cannot legally fork, run, or build on the code.

Server-side branch protection is then applied via three Repository Rulesets (`Protect develop`, `Protect main`, `Protect release branches`) as documented in `docs/BRANCHING.md`.

---

## Alternatives Considered

| Option | Rejected Because |
|---|---|
| Stay private, no enforcement | Removes the safety net once more than one person commits |
| Pay for GitHub Pro | Adds a paid dependency early; same outcome achievable for free |
| Switch to GitLab/Bitbucket | Migration cost not justified; GitHub Actions is already wired up |
| Open-source under MIT/Apache | Loses commercial control; FinCare is a product, not a community project |
| BSL 1.1 | Useful future option but introduces conversion-date complexity now |

---

## Consequences

**Easier:**
- Full server-side enforcement of branch protection, required reviews, and required status checks at no cost.
- CodeQL semantic analysis and Dependabot security updates are also free-tier enabled on public repos.
- Future external contractors can view code by URL without being added as collaborators.

**Harder:**
- Code is indexed by GitHub search, search engines, and AI training crawlers.
- Any accidentally committed secret is exposed instantly and globally — rotation must be immediate.
- Test fixtures must never contain real customer data, TRNs, IBANs, or PII.
- Business logic (Chart of Accounts structures, posting rules, profitability formulas) is visible to competitors. Mitigation: business value lives in operational deployment + data, not in the algorithm.

---

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Secrets accidentally committed | Low | `gitleaks` in CI + pre-commit; `.env` in `.gitignore`; rotate immediately if leaked |
| Customer PII in fixtures | Low | Use Faker; never seed from production exports; CI check for known PII patterns |
| Competitor copies architecture | Medium | Proprietary license forbids it legally; enforcement realistically weak |
| License confusion ("public must mean open-source") | Medium | README and LICENSE both state Proprietary clearly |
| Search indexing of internal terminology | Medium | Accept as cost of free Rulesets |

---

## Migration Notes

Cutover steps executed on 2026-06-28:

1. `gh repo edit govind4liwa/fincare --visibility public --accept-visibility-change-consequences`
2. Confirmed `visibility: PUBLIC`, `defaultBranch: develop`
3. Applied three Rulesets via `POST /repos/govind4liwa/fincare/rulesets`
4. Verified Rulesets active via `GET /repos/govind4liwa/fincare/rulesets`

Rollback (if ever needed): `gh repo edit govind4liwa/fincare --visibility private --accept-visibility-change-consequences`. Note that going private will deactivate the Rulesets immediately.

---

## Review Trigger

Revisit this ADR if any of the following becomes true:

- Team grows beyond 3 contributors (consider Pro upgrade for better team controls)
- A real customer onboards (consider Pro + private + paid CI runners)
- A material trade-secret module is added (e.g. proprietary VAT engine logic that we don't want competitors to see)
- GitHub changes Free tier terms to include Rulesets on private repos
