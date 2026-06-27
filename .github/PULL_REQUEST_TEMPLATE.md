# Pull Request

## Summary

<!-- One or two sentences describing what this PR does and why. -->

## Related Issue / Ticket

<!-- e.g. Closes: LED-12, Refs: AR-47 -->

## Type of Change

- [ ] feat — New feature
- [ ] fix — Bug fix
- [ ] refactor — Code restructuring, no behavior change
- [ ] perf — Performance improvement
- [ ] docs — Documentation only
- [ ] test — Adding or updating tests
- [ ] chore — Build / tooling / deps
- [ ] ci — CI/CD changes
- [ ] BREAKING CHANGE — Backwards-incompatible

## Affected Modules

<!-- Tick all that apply -->

- [ ] `core` · [ ] `users` · [ ] `tenants` · [ ] `audit`
- [ ] `accounts` · [ ] `ledger` · [ ] `vouchers`
- [ ] `ar` · [ ] `ap` · [ ] `banking` · [ ] `cashbook`
- [ ] `tax` · [ ] `payroll`
- [ ] `fleet` · [ ] `drivers` · [ ] `bookings` · [ ] `platforms`
- [ ] `reports` · [ ] `exports` · [ ] `integrations`
- [ ] CI / Docker / Docs

## Checklist

- [ ] Branch named per `docs/BRANCHING.md`
- [ ] Commits follow Conventional Commits (`docs/COMMIT_CONVENTION.md`)
- [ ] Tests added or updated; coverage not regressed
- [ ] `make lint format typecheck test` passes locally
- [ ] `make check-migrations` clean (no missing migrations)
- [ ] Documentation updated (`docs/`, ADR if architectural)
- [ ] No secrets, credentials, or PII committed
- [ ] Money fields use `Decimal`, never `float`
- [ ] All GL writes go through `apps.ledger.services.posting`
- [ ] Tenant scoping (`entity_id`) enforced where applicable
- [ ] Audit trail captured for state changes

## Posting Logic (if applicable)

| Trigger | Debit | Credit |
|---|---|---|
| <!-- e.g. Sales invoice posted --> | <!-- 11000 AR --> | <!-- 40100 Revenue + 22000 Output VAT --> |

## Screenshots / Output (if applicable)

<!-- Drag and drop screenshots, before/after diffs, sample reports. -->

## Migration Notes (if breaking)

<!-- Required if BREAKING CHANGE ticked. Describe the cutover plan. -->

## Reviewer Notes

<!-- Anything specific you want the reviewer to focus on. -->
