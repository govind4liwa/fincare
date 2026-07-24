"""API tests for the tenancy endpoints — membership scoping and auth."""

from django.contrib.auth import get_user_model

from rest_framework.test import APIClient

import pytest

from apps.tenants.models import BusinessCategory, Entity, UserEntityMembership

pytestmark = pytest.mark.django_db
User = get_user_model()


@pytest.fixture
def category():
    return BusinessCategory.objects.create(
        key="transport", label="Transport", band="1", coa_template_key="transport"
    )


@pytest.fixture
def entities(category):
    e1 = Entity.objects.create(
        code="E1", numeric_code="101", legal_name="E1 LLC", category=category
    )
    e2 = Entity.objects.create(
        code="E2", numeric_code="102", legal_name="E2 LLC", category=category
    )
    return e1, e2


def _ids(response):
    return {str(row["id"]) for row in response.data["results"]}


def test_member_sees_only_their_entities(entities):
    e1, _e2 = entities
    user = User.objects.create_user(email="acct@example.com", password="pw")
    UserEntityMembership.objects.create(user=user, entity=e1)

    client = APIClient()
    client.force_authenticate(user=user)
    res = client.get("/api/v1/tenants/entities/")

    assert res.status_code == 200
    assert _ids(res) == {str(e1.id)}


def test_superuser_sees_all_entities(entities):
    e1, e2 = entities
    su = User.objects.create_superuser(email="root@example.com", password="pw")

    client = APIClient()
    client.force_authenticate(user=su)
    res = client.get("/api/v1/tenants/entities/")

    assert res.status_code == 200
    assert _ids(res) == {str(e1.id), str(e2.id)}


def test_inactive_membership_is_excluded(entities):
    e1, _e2 = entities
    user = User.objects.create_user(email="ex@example.com", password="pw")
    UserEntityMembership.objects.create(user=user, entity=e1, is_active=False)

    client = APIClient()
    client.force_authenticate(user=user)
    res = client.get("/api/v1/tenants/entities/")

    assert res.status_code == 200
    assert _ids(res) == set()


def test_unauthenticated_is_rejected():
    res = APIClient().get("/api/v1/tenants/entities/")
    assert res.status_code == 401
