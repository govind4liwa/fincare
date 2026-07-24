# ADR-0009 — Core Forward-Dependency Strategy

**Status:** Accepted
**Date:** 2026-06-29
**Author:** Govind
**Supersedes:** —
**Superseded by:** —
**Related:** ADR-0008 (RLS), design doc 01, BUILD_ROADMAP (Phases 1–3)

---

## Context

`apps.core` is the dependency root: `users`, `tenants`, and every other app build
on its `BaseModel`. But two of `core`'s own fields naturally point "upward" to
apps that depend on core:

1. `BaseModel.created_by` / `updated_by` → the user model.
2. `NumberSequence.entity_id` / `Attachment.entity_id` → the owning entity
   (`tenants.Entity`), per design doc 01.

If `core` imported `users` or `tenants` directly, we'd have an import cycle, and
`core` could not be migrated on its own. We need `core` to stay self-contained
while still expressing these relationships sensibly.

---

## Decision

### 1. Audit FKs target `settings.AUTH_USER_MODEL` (string, lazy)

`created_by` / `updated_by` are `ForeignKey(settings.AUTH_USER_MODEL, ...)`,
nullable, `on_delete=SET_NULL`, `related_name="+"`. Django resolves the swappable
user model at migration time, so `core` never imports `users`. (Phase 2 set
`AUTH_USER_MODEL = "users.User"`; the FK now targets the UUID custom user.)

### 2. `core` entity references stay **UUID scope keys**, not FKs

`NumberSequence.entity_id` and `Attachment.entity_id` are `UUIDField(db_index=True)`
— **deliberately not** ForeignKeys to `tenants.Entity`. This is the final
decision (it overrides the earlier "promote to FK in Phase 3" note in the code
docstring and roadmap).

Rationale:
- Keeps `core` at the true root of the dependency graph — nothing below it,
  no cycle, `core` migrates and tests in isolation.
- **RLS does not require a FK.** Tenant isolation (ADR-0008) is enforced by an
  `entity_id`-based policy on the UUID column, identical to FK-backed tables.
- `NumberSequence` and `Attachment` are infrastructure tables, not financial
  postings; the marginal benefit of DB-level referential integrity there is low.
- Avoids coupling `core`'s unit tests to `tenants` (tests allocate sequences
  against synthetic UUIDs without needing an `Entity` fixture).

Referential validity of these `entity_id`s is ensured at the **service layer**
(callers pass a real entity id) rather than by a DB constraint.

### 3. Financial/tenant-scoped tables elsewhere DO use real FKs

This decision is scoped to `core` only. Every tenant-scoped table in `tenants`,
`accounts`, `ledger`, AR/AP, etc. uses a real `entity_id` FK to `tenants.Entity`
(those apps already depend on `tenants`, so there is no cycle).

---

## Alternatives Considered

| Option | Rejected Because |
|---|---|
| Promote `core` entity refs to FK → `tenants.Entity` (string) | Couples core to tenants; breaks core's isolated unit tests (need Entity fixtures); no integrity benefit that RLS doesn't already cover for these infra tables |
| Move `NumberSequence`/`Attachment` out of `core` into `tenants` | They are genuinely shared primitives used before tenants in the graph; relocating muddies layering |
| Hardcode FK to `auth.User` for audit fields | Breaks the moment a custom user model is introduced (it was, in Phase 2) |
| Make audit FKs generic (content-type) | Over-engineered; the user model is singular and well-defined |

---

## Consequences

**Easier:**
- `core` is buildable, migratable, and testable with zero dependencies on
  higher layers.
- The user-model swap in Phase 2 required no `core` code change (only
  `AUTH_USER_MODEL` + a DB rebuild).
- No import cycles anywhere in the app graph.

**Harder:**
- `NumberSequence`/`Attachment` lack DB-enforced FK integrity on `entity_id`;
  the service layer must pass valid entity ids (and RLS scopes reads/writes).
- A reader must know that `entity_id` on those two tables is a scope key, not a
  FK — documented in the model docstrings.

---

## Migration Notes

No schema change in Phase 3 for `core` (the fields remain `UUIDField`). The
`core` model docstring is updated to state this is the final decision rather than
a pending promotion. RLS policies (ADR-0008) will include `core_numbersequence`
and `core_attachment` using their `entity_id` column.
