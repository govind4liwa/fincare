# ADR-0001 — Record Architecture Decisions

**Status:** Accepted
**Date:** 2026-06-28
**Author:** Govind
**Supersedes:** —
**Superseded by:** —

---

## Context

FinCare is a long-lived financial system. Architectural choices made in Phase 1 (database design, posting engine, tenancy model, basis handling) will be revisited many times. Without a written record, future contributors have no way to know **why** a decision was made — only **what** the code currently does. This causes regressions when someone "fixes" a constraint that was deliberately in place.

---

## Decision

We will record every significant architectural decision as an **Architecture Decision Record (ADR)** in `docs/adr/`, numbered sequentially. Each ADR follows this template:

```markdown
# ADR-NNNN — Title

**Status:** Proposed | Accepted | Deprecated | Superseded
**Date:** YYYY-MM-DD
**Author:** Name
**Supersedes:** ADR-NNNN
**Superseded by:** ADR-NNNN

## Context
What is the situation? What forces are at play?

## Decision
What is the chosen approach? Be specific and unambiguous.

## Alternatives Considered
What else was on the table? Why were they rejected?

## Consequences
What becomes easier? What becomes harder? What is the migration cost?

## Risks
What could go wrong? What are we betting on?

## Migration Notes
If superseding an earlier ADR, what is the cutover plan?
```

---

## Alternatives Considered

| Option | Rejected Because |
|---|---|
| No formal record, rely on commit messages | Commit messages are not discoverable; rationale gets lost |
| Wiki / Confluence | Lives outside the repo; goes stale; not versioned with code |
| Code comments only | Cannot capture trade-offs or rejected alternatives |

---

## Consequences

**Easier:**
- New contributors can read the history of decisions in chronological order.
- PR reviews can reference ADRs ("this conflicts with ADR-0007").
- Auditors get a clear paper trail of why the system works the way it does.

**Harder:**
- Adds a documentation step to every architectural change.

---

## Risks

- ADRs go stale if not updated when superseded. **Mitigation:** PR template includes an ADR checklist item.

---

## Migration Notes

Not applicable — this is the first ADR.

---

## Pending ADRs (Phase 1 Roadmap)

| # | Title | Phase |
|---|---|---|
| 0002 | Single ledger with accrual basis as canonical; cash basis derived | 1.1 |
| 0003 | UUID primary keys for all financial tables | 1.0 |
| 0004 | PostgreSQL Row-Level Security for multi-tenancy | 1.0 |
| 0005 | Centralized posting engine — no app posts to GL directly | 1.1 |
| 0006 | DECIMAL(18,4) for all monetary fields | 1.0 |
| 0007 | Posted transactions are immutable; correct only via reversal | 1.1 |
| 0008 | Analytical tags on journal_line (vehicle/driver/platform) — no separate analytics schema in Phase 1 | 1.4 |
| 0009 | GitFlow-Lite branching strategy | 1.0 |
| 0010 | JWT auth (SimpleJWT) for API; session for Django admin | 1.0 |
