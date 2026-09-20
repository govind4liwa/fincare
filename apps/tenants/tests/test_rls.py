"""Row-Level Security isolation tests (ADR-0008).

These verify the policy directly: become the restricted role, set the entity
context, and confirm only that entity's rows are visible. Requires the
``0003_rls`` migration (role + policies) to have run on the test DB.
Uses ``transaction=True`` so SET LOCAL ROLE behaves like a real request.
"""

from datetime import date

from django.db import connection, transaction

import pytest

from apps.integrations.models import ImportKind, ImportProfile
from apps.ledger.models import AccountingPeriod, JournalEntry
from apps.tenants.models import Branch, BusinessCategory, Entity

pytestmark = pytest.mark.django_db(transaction=True)


def _seed():
    cat = BusinessCategory.objects.create(
        key="transport", label="Transport", band="1", coa_template_key="transport"
    )
    e1 = Entity.objects.create(code="E1", numeric_code="101", legal_name="E1", category=cat)
    e2 = Entity.objects.create(code="E2", numeric_code="201", legal_name="E2", category=cat)
    Branch.objects.create(entity=e1, code="B1", name="Branch 1")
    Branch.objects.create(entity=e2, code="B2", name="Branch 2")
    return e1, e2


def _count_branches_as_role(entity_ids):
    """Count branches under the restricted role with the given entity context."""
    with transaction.atomic(), connection.cursor() as cur:
        cur.execute('SET LOCAL ROLE "fincare_app"')
        if entity_ids is not None:
            cur.execute(
                "SELECT set_config('app.current_entities', %s, true)",
                [",".join(str(e) for e in entity_ids)],
            )
        cur.execute("SELECT COUNT(*) FROM tenants_branch")
        return cur.fetchone()[0]


def test_context_scopes_to_single_entity():
    e1, e2 = _seed()
    assert _count_branches_as_role([e1.id]) == 1
    assert _count_branches_as_role([e2.id]) == 1


def test_context_with_both_entities_sees_all():
    e1, e2 = _seed()
    assert _count_branches_as_role([e1.id, e2.id]) == 2


def test_unset_context_is_unrestricted():
    _seed()
    # No GUC set -> policy permits (migrations/shell behaviour).
    assert _count_branches_as_role(None) == 2


def test_superuser_connection_bypasses_rls():
    """The ORM (superuser connection, no role switch) sees everything."""
    _seed()
    assert Branch.objects.count() == 2


# ---------------------------------------------------------------------------
# Transactional-table coverage (0006_rls_transactional_tables)
# ---------------------------------------------------------------------------


def _count_as_role(table, entity_ids):
    """COUNT(*) on `table` under the restricted role with the given context."""
    with transaction.atomic(), connection.cursor() as cur:
        cur.execute('SET LOCAL ROLE "fincare_app"')
        if entity_ids is not None:
            cur.execute(
                "SELECT set_config('app.current_entities', %s, true)",
                [",".join(str(e) for e in entity_ids)],
            )
        cur.execute(f"SELECT COUNT(*) FROM {table}")  # noqa: S608 - table from a fixed list
        return cur.fetchone()[0]


def _rls_tables():
    """Tables that actually have an RLS policy attached, per pg_policies."""
    with connection.cursor() as cur:
        cur.execute("SELECT tablename FROM pg_policies WHERE schemaname = 'public'")
        return {row[0] for row in cur.fetchall()}


def test_every_scoped_table_has_a_policy():
    """Each table listed in rls.SCOPED_TABLES is actually protected in the DB.

    Guards the failure mode this migration existed to fix: a new app ships a
    table with entity_id, nobody adds a policy, and a missed .filter() leaks.
    """
    from apps.tenants import rls

    with_policies = _rls_tables()
    missing = sorted(t for t, _ in rls.SCOPED_TABLES if t not in with_policies)
    assert missing == [], f"tables listed as scoped but with no RLS policy: {missing}"


def test_transactional_rows_are_isolated_by_entity():
    """A journal entry belonging to E2 is invisible in E1's context."""
    e1, e2 = _seed()
    for entity, ref in ((e1, "JE-E1"), (e2, "JE-E2")):
        AccountingPeriod.objects.create(
            entity=entity,
            fiscal_year=2026,
            period_no=6,
            name="Jun-2026",
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 30),
            status=AccountingPeriod.Status.OPEN,
        )
        JournalEntry.objects.create(
            entity=entity,
            entry_date=date(2026, 6, 15),
            narration=ref,
            source_type="test",
        )

    assert _count_as_role("ledger_journalentry", [e1.id]) == 1
    assert _count_as_role("ledger_journalentry", [e2.id]) == 1
    assert _count_as_role("ledger_journalentry", [e1.id, e2.id]) == 2
    assert _count_as_role("ledger_journalentry", None) == 2  # unset context = unrestricted
    assert _count_as_role("ledger_accountingperiod", [e1.id]) == 1


def test_null_entity_rows_stay_visible():
    """Group-wide rows (entity_id NULL) are visible in any context.

    Relied on by group-wide import profiles and salary components, and by
    VAT-group returns, whose entity is the group rather than one entity.
    """
    e1, _e2 = _seed()
    ImportProfile.objects.create(
        entity=None,
        kind=ImportKind.BANK_STATEMENT,
        name="Group-wide",
        source_key="GLOBAL",
        column_map={"txn_date": "Date"},
    )
    assert _count_as_role("integrations_importprofile", [e1.id]) == 1


def test_context_reset_to_empty_string_is_unrestricted():
    """A reused connection whose GUC has reverted to '' must not hide everything.

    A custom GUC reverts to the empty string, not NULL, once it has been set and
    the transaction has ended. The policy's unset check is NULLIF(...) IS NULL
    for exactly this reason: with a bare IS NULL, the second call below returned
    0 rows, silently breaking the superuser sentinel (which is "leave the GUC
    unset") on any pooled connection that had already served a scoped request.
    """
    e1, _e2 = _seed()
    assert _count_branches_as_role([e1.id]) == 1  # sets the GUC on this connection
    assert _count_branches_as_role(None) == 2  # ... now reverted to '', not NULL


# Tables that carry entity_id but are deliberately NOT row-scoped.
# Keep in sync with the rationale in apps/tenants/rls.py.
RLS_EXEMPT_TABLES = {
    # Defines a user's entity scope; the middleware reads it to build the GUC
    # before assuming the restricted role. Scoping it would be circular.
    "tenants_userentitymembership",
}


def test_no_entity_bearing_table_is_left_unprotected():
    """Every model with an entity_id column has an RLS policy, or is listed exempt.

    This is the guard ADR-0008 named as its mitigation for "forgetting a policy
    on a new table" — and which did not exist until Phase 18, which is how 53
    transactional tables ended up with no policy at all. It introspects the
    models rather than trusting rls.SCOPED_TABLES, so adding a model with
    entity_id and forgetting to register it fails here.
    """
    from django.apps import apps as django_apps

    with_policies = _rls_tables()
    unprotected = sorted(
        m._meta.db_table
        for m in django_apps.get_models()
        if m._meta.managed
        and not m._meta.proxy
        and any(getattr(f, "attname", None) == "entity_id" for f in m._meta.get_fields())
        and m._meta.db_table not in with_policies
        and m._meta.db_table not in RLS_EXEMPT_TABLES
    )
    assert unprotected == [], (
        "these tables have entity_id but no RLS policy — add them to "
        f"rls.TRANSACTIONAL_SCOPED_TABLES with a migration, or to RLS_EXEMPT_TABLES: {unprotected}"
    )
