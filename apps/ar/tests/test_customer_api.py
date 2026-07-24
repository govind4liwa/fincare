"""API tests for customer master CRUD — reads open, writes role-gated, no delete."""

from django.contrib.auth import get_user_model

from rest_framework.test import APIClient

import pytest

from apps.accounts.models import Account
from apps.ar.models import Customer
from apps.tenants.models import UserEntityMembership

pytestmark = pytest.mark.django_db
User = get_user_model()


def _ar_account(entity):
    return Account.objects.get(entity=entity, code="101-100-120-001")


def _payload(entity):
    return {
        "entity": str(entity.id),
        "code": "CUS-100",
        "name": "New Client LLC",
        "customer_type": "b2b",
        "receivable_account": str(_ar_account(entity).id),
        "credit_days": 30,
        "emirate": "Dubai",
    }


def _superuser():
    client = APIClient()
    client.force_authenticate(
        User.objects.create_superuser(email="root@example.com", password="pw")
    )
    return client


def test_create_and_update(entity):
    client = _superuser()
    res = client.post("/api/v1/customers/", _payload(entity), format="json")
    assert res.status_code == 201, res.content
    cid = res.data["id"]
    assert res.data["receivable_account_code"] == "101-100-120-001"

    res = client.patch(f"/api/v1/customers/{cid}/", {"name": "Renamed LLC"}, format="json")
    assert res.status_code == 200
    assert Customer.objects.get(id=cid).name == "Renamed LLC"


def test_member_without_role_can_read_but_not_write(entity):
    user = User.objects.create_user(email="viewer@example.com", password="pw")
    UserEntityMembership.objects.create(user=user, entity=entity)
    client = APIClient()
    client.force_authenticate(user)
    assert client.get("/api/v1/customers/").status_code == 200
    res = client.post("/api/v1/customers/", _payload(entity), format="json")
    assert res.status_code == 403


def test_delete_is_disabled(entity):
    client = _superuser()
    cid = client.post("/api/v1/customers/", _payload(entity), format="json").data["id"]
    # Masters are deactivated (is_active=False), never hard-deleted.
    assert client.delete(f"/api/v1/customers/{cid}/").status_code == 405
