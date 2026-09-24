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

---

## Amendment — Phase 18 (2026-09-20)

The decision above is unchanged; this records how the implementation caught up
with it, and one correction.

### Coverage gap closed

`0003_rls` applied policies to the ten tables that existed when RLS landed
(core, tenants, settings). Every app built afterwards — accounts, ledger,
vouchers, AR/AP, banking, cashbook, tax, fleet, drivers, bookings, platforms,
payroll, reports, integrations, audit — shipped tables carrying `entity_id` with
**no policy at all**, so §4's "all tables with a real `entity_id` FK" was
aspirational rather than true: 53 of 62 were unprotected.

`0006_rls_transactional_tables` applies the policy to all of them. The table
lists now live in `apps/tenants/rls.py` as `INITIAL_SCOPED_TABLES` (frozen: the
set `0003_rls` applied) and `TRANSACTIONAL_SCOPED_TABLES`. The split matters —
migrations must keep applying exactly the set they applied when written, or a
fresh database fails when an early migration tries to `ALTER` a table a later
app has not created yet.

The **Risks** section above named "forgetting a policy on a new table" and
claimed a test asserting every `entity_id`-bearing table has RLS as the
mitigation. That test did not exist, which is precisely how the gap opened. It
exists now (`test_no_entity_bearing_table_is_left_unprotected`), and it
introspects the models rather than trusting the curated list, so registering a
new model without a policy fails the suite.

### Correction: "no context" must also mean the empty string

§2 specified `current_setting('app.current_entities', true) IS NULL` as the
unrestricted sentinel. That is correct only on a connection where the GUC has
**never** been set. A custom GUC reverts to the **empty string**, not NULL, once
it has been set and that transaction has ended — so on a pooled connection that
had already served one scoped request, an unset context matched *nothing*
instead of everything.

That inverts the intended failure mode, and it silently broke the superuser
path, since the middleware's way of saying "unrestricted" is to leave the GUC
unset. The predicate is now `NULLIF(current_setting(...), '') IS NULL`, and
`0006` re-creates the `0003` policies so existing databases pick up the fix.

### Deliberately not scoped

- `tenants_userentitymembership` — defines a user's entity scope and is read by
  the middleware to build the GUC, before the restricted role is assumed.
  Scoping it would be circular.
- **Child tables with no `entity_id`** (`ledger_journalline`,
  `ar_salesinvoiceline`, `banking_statementline`, `payroll_payslip`, …). An
  `entity_id`-keyed policy cannot express them; they are reachable only through
  a scoped parent, so an unfiltered query directly against one of them is still
  a leak. Covering them needs a parent-join policy whose per-row subquery cost
  must be weighed against the reporting performance budget — **resolved in the
  2026-09-24 amendment below**.
- Group-level reference data with no entity (`core_currency`,
  `tenants_businesscategory`, `tenants_vatgroup`, `users_user`).

A VAT-group `tax_taxreturn` row carries `entity_id` NULL (it belongs to the
group, not one entity) and the policy always admits NULL, so RLS isolates
standalone filers while group returns stay scoped at the application layer by
VAT-group membership. Intentional, and asserted by test.

---

## Amendment — child tables (2026-09-24)

The previous amendment left 24 tables with no `entity_id` of their own
unprotected — journal lines, invoice/bill/voucher/credit-note lines, statement
lines, reconciliation items, payslips and their lines, WPS records, documents,
loan schedules, tax boxes. They were reachable only through a scoped parent, so
an unfiltered query aimed straight at one still returned every entity's rows.
For `ledger_journalline` that is the actual postings. `0007_rls_child_tables`
closes it.

### Policy: "my parent row is visible to you"

```sql
CREATE POLICY <child>_rls ON <child>
USING (EXISTS (SELECT 1 FROM <parent> p WHERE p.id = <child>.<fk>));
```

Nothing about entities is restated. PostgreSQL applies the parent's own policy
inside that subquery, so the unset-context sentinel, NULL-entity rows and
multi-level chains all compose from the parent. A grandchild (payslip line →
payslip → run) therefore needs one level of `EXISTS`, not a nested one, because
its parent is itself policy-scoped. A test walks every chain and asserts it
terminates at an entity-scoped table, so a mis-specified parent fails the suite
rather than silently hiding or exposing rows.

### Why not denormalise `entity_id` onto each child

CLAUDE.md §5 says every transactional table carries `entity_id`, which these
child tables do not, so denormalising was the obvious candidate. It was measured
rather than assumed, on 500k journal lines across 10 entities:

| Query shape | Parent-visibility policy | Denormalised `entity_id` |
|---|---|---|
| Bare `SUM` over the child table | ~430 ms (no parallelism) | ~165 ms |
| Report shape: lines joined to entries, date-filtered | ~74–83 ms | ~49–72 ms |

The first row looks damning, but no caller issues that query. Every read of
`JournalLine` in `apps/reports` and `apps/banking` filters through `entry__`
(`entry__status`, `entry__entity_id`, `entry__entry_date`), which is the second
row — and a bare unfiltered scan of a child table is precisely what these
policies exist to block, so optimising for it is optimising for the attack.

Against a modest cost on the shapes that actually run, denormalising would mean
a schema change, backfill and write-path guarantee across 24 tables, plus
ongoing drift risk between a child's `entity_id` and its parent's. The
parent-visibility policy needs none of that: no schema change, no backfill, no
write-path change, and drift is impossible because there is nothing duplicated.

If profiling ever shows a hot path scanning a child directly, denormalise **that
table** — with a composite foreign key to its parent on `(id, entity_id)` so the
database makes drift impossible — rather than doing it wholesale.

### Coverage guard

`test_no_transactional_table_is_left_unprotected` now requires every table in a
business app to have a policy or appear in an explicit reference-data list with
a reason. The earlier guard only checked `entity_id`-bearing tables, which is
why `ledger_journalline` stayed unprotected through five releases.

---

## Amendment — fail-closed context, and the role grant (2026-09-24)

Found while writing the first test to exercise `TenantContextMiddleware` itself
rather than setting the role by hand in SQL. Until then every RLS test proved
the *policies* worked; none proved a real request ever reached them.

### "No entities" is not "no context"

`_allowed_entity_ids` returns `[]` for a user with no active memberships, and
the middleware wrote `",".join([])` — the **empty string** — into the GUC. The
2026-09-20 amendment had just made the policy treat an empty GUC as "unset,
therefore unrestricted", to fix the superuser sentinel on pooled connections.
Together those two correct-looking decisions meant a request with **zero**
accessible entities bypassed RLS completely: fail-open, in precisely the case
that should be most closed.

Before that amendment the empty string matched nothing and failed closed, so
this was introduced by the fix, not by the original design — a good argument for
testing the enforcement path and not only the policy.

The middleware now writes `rls.NO_ACCESS_SENTINEL`
(`00000000-…-0`) when the list is empty: a valid UUID, so the
`entity_id::text = ANY(...)` comparison stays well-typed, and one that can never
be a real entity id. The unset-means-unrestricted sentinel is unchanged for
migrations, shell and superusers.

Regression tests cover an anonymous request, an authenticated user with no
memberships, and a user whose membership has been deactivated — all must see
zero rows through a deliberately unfiltered query.

### Deployment: the app role must be grantable

`0003_rls` creates `fincare_app` and grants it table privileges, but never
grants **membership** of it to the login role. `SET LOCAL ROLE fincare_app`
therefore succeeds today only because the development login role is a
superuser. On a hardened deployment, where the app connects as a non-superuser
(which is the point — a superuser bypasses RLS entirely), every request would
fail with *permission denied to set role* until an operator runs:

```sql
GRANT fincare_app TO <application_login_role>;
```

This is deliberately left to deployment rather than baked into a migration: the
login role's name is environment-specific and is not known to the codebase. It
is called out in DEVELOPMENT.md alongside the rest of the RLS rollout.
