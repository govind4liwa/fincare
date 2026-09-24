"""End-to-end RLS: the middleware path that actually runs in production.

Every other RLS test sets the role and context by hand in SQL, which proves the
*policies* work but not that a real request ever reaches them. This exercises
TenantContextMiddleware itself with ``RLS_ENABLED=True``: resolve the user from
a JWT, assume the restricted role, set the entity context, and confirm that a
deliberately unfiltered query inside that request sees only permitted rows.

That is the whole point of RLS — the guarantee that holds when application-layer
filtering is missing or wrong. A test that filters by entity in the ORM would
pass with RLS switched off and prove nothing.
"""

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import RequestFactory, override_settings

import pytest
from rest_framework_simplejwt.tokens import RefreshToken

from apps.fleet.models import Vehicle
from apps.tenants.middleware import TenantContextMiddleware
from apps.tenants.models import BusinessCategory, Entity, UserEntityMembership

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


def _seed_two_entities_with_vehicles():
    category = BusinessCategory.objects.create(
        key="transport", label="Transport", band="1", coa_template_key="transport"
    )
    e1 = Entity.objects.create(code="E1", numeric_code="101", legal_name="E1", category=category)
    e2 = Entity.objects.create(code="E2", numeric_code="102", legal_name="E2", category=category)
    Vehicle.objects.create(entity=e1, code="V1")
    Vehicle.objects.create(entity=e2, code="V2")
    return e1, e2


def _request_for(user):
    """A request carrying a real bearer token, as the middleware expects."""
    factory = RequestFactory()
    request = factory.get("/api/v1/vehicles/")
    if user is not None:
        token = RefreshToken.for_user(user).access_token
        request.META["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    return request


def _unfiltered_counts():
    """Deliberately unfiltered reads — what a missed .filter() would produce."""
    with connection.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM fleet_vehicle")
        vehicles = cur.fetchone()[0]
        cur.execute("SELECT current_setting('app.current_entities', true)")
        guc = cur.fetchone()[0]
        cur.execute("SELECT current_user")
        role = cur.fetchone()[0]
    return vehicles, guc, role


@override_settings(RLS_ENABLED=True)
def test_middleware_scopes_an_unfiltered_query_to_the_users_entities():
    e1, _e2 = _seed_two_entities_with_vehicles()
    user = User.objects.create_user(email="member@example.com", password="pw")
    UserEntityMembership.objects.create(user=user, entity=e1)

    captured = {}

    def view(request):
        captured["counts"] = _unfiltered_counts()
        return "ok"

    TenantContextMiddleware(view)(_request_for(user))

    vehicles, guc, role = captured["counts"]
    assert role == "fincare_app", "middleware must assume the restricted role"
    assert guc == str(e1.id), "entity context must be set from the user's membership"
    assert vehicles == 1, "an unfiltered read must still see only the member's entity"


@override_settings(RLS_ENABLED=True)
def test_superuser_sees_everything():
    """The sentinel is 'leave the context unset', which must mean unrestricted.

    This is the case the pre-NULLIF policy broke on a reused connection.
    """
    _seed_two_entities_with_vehicles()
    root = User.objects.create_superuser(email="root@example.com", password="pw")

    captured = {}

    def view(request):
        captured["counts"] = _unfiltered_counts()
        return "ok"

    TenantContextMiddleware(view)(_request_for(root))

    vehicles, guc, role = captured["counts"]
    assert role == "fincare_app"
    assert guc in (None, ""), "superuser context is deliberately unset"
    assert vehicles == 2


@override_settings(RLS_ENABLED=True)
def test_writes_still_work_under_the_restricted_role():
    """Catches a missing GRANT: RLS is useless if it breaks every write."""
    e1, _e2 = _seed_two_entities_with_vehicles()
    user = User.objects.create_user(email="writer@example.com", password="pw")
    UserEntityMembership.objects.create(user=user, entity=e1)

    def view(request):
        Vehicle.objects.create(entity=e1, code="V-NEW")
        return "ok"

    TenantContextMiddleware(view)(_request_for(user))
    assert Vehicle.objects.filter(code="V-NEW").exists()


@override_settings(RLS_ENABLED=True)
def test_anonymous_request_sees_nothing():
    """No membership means no entities, which must be empty, not unrestricted."""
    _seed_two_entities_with_vehicles()

    captured = {}

    def view(request):
        captured["counts"] = _unfiltered_counts()
        return "ok"

    TenantContextMiddleware(view)(_request_for(None))
    vehicles, _guc, _role = captured["counts"]
    assert vehicles == 0


@override_settings(RLS_ENABLED=True)
def test_authenticated_user_with_no_memberships_sees_nothing():
    """The case that made the empty-string context dangerous.

    An anonymous request is already stopped by IsAuthenticated, but a *real*
    logged-in user who has not been assigned to any entity reaches the database.
    `",".join([])` is the empty string, which the policy reads as "no tenant
    context set" — i.e. unrestricted — so RLS silently switched off for exactly
    the user who should see least. The middleware now writes an explicit
    no-access sentinel instead.
    """
    _seed_two_entities_with_vehicles()
    stranger = User.objects.create_user(email="nobody@example.com", password="pw")
    assert not UserEntityMembership.objects.filter(user=stranger).exists()

    captured = {}

    def view(request):
        captured["counts"] = _unfiltered_counts()
        return "ok"

    TenantContextMiddleware(view)(_request_for(stranger))

    vehicles, guc, _role = captured["counts"]
    assert guc == "00000000-0000-0000-0000-000000000000"
    assert vehicles == 0, "a user with no entity memberships must see no rows"


@override_settings(RLS_ENABLED=True)
def test_membership_must_be_active_to_grant_access():
    """A deactivated membership must not keep granting database access."""
    e1, _e2 = _seed_two_entities_with_vehicles()
    user = User.objects.create_user(email="ex@example.com", password="pw")
    UserEntityMembership.objects.create(user=user, entity=e1, is_active=False)

    captured = {}

    def view(request):
        captured["counts"] = _unfiltered_counts()
        return "ok"

    TenantContextMiddleware(view)(_request_for(user))
    vehicles, _guc, _role = captured["counts"]
    assert vehicles == 0
