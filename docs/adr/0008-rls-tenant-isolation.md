# ADR-0008 — PostgreSQL Row-Level Security for Tenant Isolation

**Status:** Accepted
**Date:** 2026-06-29
**Author:** Govind
**Supersedes:** —
**Superseded by:** —
**Related:** ADR-0009 (core entity refs), design doc 01 (tenants), CLAUDE.md §5

---

## Context

FinCare hosts many legal entities in one database (one group, ~25 entities).
Every transactional row carries `entity_id`. Application-layer filtering
(`.filter(entity_id=...)`) is necessary but not sufficient — a single missed
filter in any query, report, or admin action leaks one entity's financial data
into another's. For an accounting system this is unacceptable.

We want isolation enforced at the **database layer**, so that even a query that
forgets to filter cannot return another entity's rows.

---

## Decision

Use **PostgreSQL Row-Level Security (RLS)** on every tenant-scoped table, keyed on
`entity_id`, driven by a per-request connection setting.

### 1. Tenant context as a session GUC

A request resolves the set of entities the authenticated user may access and sets
a Postgres run-time parameter for the duration of that request/transaction:

```sql
SET LOCAL app.current_entities = '<comma-separated entity uuids>';
```

A `TenantContextMiddleware` (in `apps.tenants`) wraps each request in a
transaction and issues the `SET LOCAL` based on the user's entity membership
(superusers may set an "all" sentinel that policies treat as unrestricted).

### 2. RLS policies (created via migration `RunSQL`)

For each tenant-scoped table:

```sql
ALTER TABLE <table> ENABLE ROW LEVEL SECURITY;
ALTER TABLE <table> FORCE ROW LEVEL SECURITY;

CREATE POLICY <table>_isolation ON <table>
USING (
    current_setting('app.current_entities', true) IS NULL
    OR entity_id::text = ANY (string_to_array(current_setting('app.current_entities', true), ','))
);
```

`current_setting(..., true)` returns NULL when unset (e.g. migrations, shell), so
unset context = no RLS restriction — keeping management commands and tests
workable. Application requests **always** set the GUC, so they are always scoped.

### 3. Application DB role is non-superuser

`FORCE ROW LEVEL SECURITY` ensures even the table owner is subject to policies.
The runtime app connects as a non-superuser role so RLS always applies; migrations
run as a privileged role that bypasses RLS (acceptable — migrations are trusted).

### 4. What is scoped

All tables with a real `entity_id` FK to `tenants.Entity` (accounts, ledger, AR,
AP, banking, etc.). `core` tables (`NumberSequence`, `Attachment`) carry a UUID
`entity_id` scope key (ADR-0009) and are also covered by an `entity_id`-based
policy. Group-level/reference tables without `entity_id` (e.g. `Currency`,
`BusinessCategory`) are not row-scoped.

---

## Alternatives Considered

| Option | Rejected Because |
|---|---|
| App-layer filtering only | One missed `.filter()` leaks data; no defence in depth |
| Schema-per-tenant | 25 schemas to migrate/maintain; cross-entity consolidation queries become painful |
| Database-per-tenant | Heavy ops burden; consolidation/intercompany across DBs is hard |
| Django-only "current tenant" via threadlocal, no DB enforcement | Same weakness as app-layer filtering; not enforced by the DB |

---

## Consequences

**Easier:**
- A forgotten filter cannot leak another entity's data — the DB refuses.
- Consolidated/group queries work by setting multiple entity ids in the GUC.
- Isolation is uniform across ORM, admin, reports, and ad-hoc SQL in requests.

**Harder:**
- Requests must always set the tenant GUC (handled centrally by middleware).
- Two DB roles (privileged for migrations, restricted for runtime) to provision.
- Tests and management commands run with NULL context (unrestricted) — integration
  tests must explicitly set context to verify isolation.
- Each new tenant-scoped table needs its RLS policy added (migration helper).

---

## Risks

- **Connection pooling leaking context** — mitigated by `SET LOCAL` (transaction-
  scoped) and wrapping each request in a transaction; never `SET` (session-wide).
- **Bypass via the privileged role** — accepted for migrations; runtime never uses it.
- **Performance** — `entity_id` is indexed on every scoped table; policy predicate
  is index-friendly.
- **Forgetting a policy on a new table** — mitigated by a reusable migration helper
  and a test that asserts every `entity_id`-bearing table has RLS enabled.

---

## Migration Notes

Introduced in Phase 3 (commit #2). A reusable helper (`apps/tenants/rls.py`) emits
the enable/force/policy SQL; each tenant-scoped app's migration calls it. Provision
the restricted runtime role in deployment (documented in DEVELOPMENT.md). Until the
restricted role and middleware are wired, context is NULL and behaviour is
unchanged — so this can land incrementally.
