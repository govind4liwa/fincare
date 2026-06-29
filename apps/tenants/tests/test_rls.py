"""Row-Level Security isolation tests (ADR-0008).

These verify the policy directly: become the restricted role, set the entity
context, and confirm only that entity's rows are visible. Requires the
``0003_rls`` migration (role + policies) to have run on the test DB.
Uses ``transaction=True`` so SET LOCAL ROLE behaves like a real request.
"""

from django.db import connection, transaction

import pytest

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
