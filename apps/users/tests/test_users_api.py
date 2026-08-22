"""API tests for the self-profile endpoint (/api/v1/users/me/)."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from rest_framework.test import APIClient

import pytest

from apps.tenants.models import BusinessCategory, Entity, UserEntityMembership

pytestmark = pytest.mark.django_db
User = get_user_model()


@pytest.fixture
def entity():
    cat = BusinessCategory.objects.create(
        key="transport", label="Transport", band="1", coa_template_key="transport"
    )
    return Entity.objects.create(code="RGT", numeric_code="101", legal_name="Regency", category=cat)


def test_me_returns_own_profile_and_roles(entity):
    user = User.objects.create_user(email="me@example.com", password="pw", full_name="Jane Doe")
    user.groups.add(Group.objects.get_or_create(name="accountant")[0])
    UserEntityMembership.objects.create(user=user, entity=entity)

    client = APIClient()
    client.force_authenticate(user)
    res = client.get("/api/v1/users/me/")

    assert res.status_code == 200
    assert res.data["email"] == "me@example.com"
    assert res.data["full_name"] == "Jane Doe"
    assert res.data["is_staff"] is False
    assert res.data["is_superuser"] is False
    assert res.data["roles"] == ["accountant"]
    assert res.data["entities"] == [str(entity.id)]


def test_me_with_no_roles_or_memberships(entity):
    user = User.objects.create_user(email="plain@example.com", password="pw")
    client = APIClient()
    client.force_authenticate(user)
    res = client.get("/api/v1/users/me/")

    assert res.status_code == 200
    assert res.data["roles"] == []
    assert res.data["entities"] == []


def test_me_superuser_sees_unrestricted_entities():
    admin = User.objects.create_superuser(email="admin@example.com", password="pw")
    client = APIClient()
    client.force_authenticate(admin)
    res = client.get("/api/v1/users/me/")

    assert res.status_code == 200
    assert res.data["is_superuser"] is True
    assert res.data["entities"] is None


def test_me_requires_authentication():
    client = APIClient()
    res = client.get("/api/v1/users/me/")
    assert res.status_code == 401


def test_me_is_read_only():
    user = User.objects.create_user(email="ro@example.com", password="pw")
    client = APIClient()
    client.force_authenticate(user)
    patched = client.patch("/api/v1/users/me/", {"full_name": "Hacked"}, format="json")
    assert patched.status_code == 405
