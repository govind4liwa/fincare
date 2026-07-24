"""API tests for AR customers — membership scoping + shape."""

from django.contrib.auth import get_user_model

from rest_framework.test import APIClient

import pytest

from apps.accounts.models import Account, AccountGroup
from apps.ar.models import Customer
from apps.tenants.models import BusinessCategory, Entity, UserEntityMembership

pytestmark = pytest.mark.django_db
User = get_user_model()


@pytest.fixture
def ar_customer():
    cat = BusinessCategory.objects.create(
        key="transport", label="Transport", band="1", coa_template_key="transport"
    )
    ent = Entity.objects.create(code="E1", numeric_code="101", legal_name="E1 LLC", category=cat)
    group = AccountGroup.objects.create(
        entity=ent, level=2, segment="120", code="101-100-120", name="Receivables", nature="asset"
    )
    acct = Account.objects.create(
        entity=ent,
        sub_group=group,
        charge_segment="001",
        code="101-100-120-001",
        name="Trade Receivables",
        account_type="receivable",
        normal_balance="D",
    )
    return Customer.objects.create(
        entity=ent, code="C001", name="Acme Corp", receivable_account=acct
    )


def test_member_sees_customers(ar_customer):
    user = User.objects.create_user(email="ar@example.com", password="pw")
    UserEntityMembership.objects.create(user=user, entity=ar_customer.entity)
    client = APIClient()
    client.force_authenticate(user)
    res = client.get("/api/v1/customers/")
    assert res.status_code == 200
    row = res.data["results"][0]
    assert row["code"] == "C001"
    assert row["receivable_account_code"] == "101-100-120-001"


def test_non_member_sees_nothing(ar_customer):
    user = User.objects.create_user(email="x@example.com", password="pw")
    client = APIClient()
    client.force_authenticate(user)
    assert client.get("/api/v1/customers/").data["results"] == []


def test_unauthenticated_is_rejected():
    assert APIClient().get("/api/v1/customers/").status_code == 401
