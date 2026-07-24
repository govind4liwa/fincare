"""API tests for AP suppliers — membership scoping + shape."""

from django.contrib.auth import get_user_model

from rest_framework.test import APIClient

import pytest

from apps.accounts.models import Account, AccountGroup
from apps.ap.models import Supplier
from apps.tenants.models import BusinessCategory, Entity, UserEntityMembership

pytestmark = pytest.mark.django_db
User = get_user_model()


@pytest.fixture
def ap_supplier():
    cat = BusinessCategory.objects.create(
        key="transport", label="Transport", band="1", coa_template_key="transport"
    )
    ent = Entity.objects.create(code="E1", numeric_code="101", legal_name="E1 LLC", category=cat)
    group = AccountGroup.objects.create(
        entity=ent, level=2, segment="210", code="101-200-210", name="Payables", nature="liability"
    )
    acct = Account.objects.create(
        entity=ent,
        sub_group=group,
        charge_segment="001",
        code="101-200-210-001",
        name="Trade Payables",
        account_type="payable",
        normal_balance="C",
    )
    return Supplier.objects.create(entity=ent, code="S001", name="ENOC", payable_account=acct)


def test_member_sees_suppliers(ap_supplier):
    user = User.objects.create_user(email="ap@example.com", password="pw")
    UserEntityMembership.objects.create(user=user, entity=ap_supplier.entity)
    client = APIClient()
    client.force_authenticate(user)
    res = client.get("/api/v1/suppliers/")
    assert res.status_code == 200
    row = res.data["results"][0]
    assert row["code"] == "S001"
    assert row["payable_account_code"] == "101-200-210-001"


def test_non_member_sees_nothing(ap_supplier):
    user = User.objects.create_user(email="x@example.com", password="pw")
    client = APIClient()
    client.force_authenticate(user)
    assert client.get("/api/v1/suppliers/").data["results"] == []


def test_unauthenticated_is_rejected():
    assert APIClient().get("/api/v1/suppliers/").status_code == 401
