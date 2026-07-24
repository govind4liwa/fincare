"""API tests for supplier master CRUD."""

from django.contrib.auth import get_user_model

from rest_framework.test import APIClient

import pytest

from apps.accounts.models import Account
from apps.ap.models import Supplier

pytestmark = pytest.mark.django_db
User = get_user_model()


def _payload(entity):
    ap_account = Account.objects.get(entity=entity, code="101-200-210-001")
    return {
        "entity": str(entity.id),
        "code": "SUP-100",
        "name": "New Vendor LLC",
        "payable_account": str(ap_account.id),
        "credit_days": 30,
    }


def _superuser():
    client = APIClient()
    client.force_authenticate(
        User.objects.create_superuser(email="root@example.com", password="pw")
    )
    return client


def test_create_and_update(entity):
    client = _superuser()
    res = client.post("/api/v1/suppliers/", _payload(entity), format="json")
    assert res.status_code == 201, res.content
    sid = res.data["id"]
    assert res.data["payable_account_code"] == "101-200-210-001"

    res = client.patch(f"/api/v1/suppliers/{sid}/", {"phone": "050-1112222"}, format="json")
    assert res.status_code == 200
    assert Supplier.objects.get(id=sid).phone == "050-1112222"
