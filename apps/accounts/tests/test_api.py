"""API tests for the Chart of Accounts endpoints — membership scoping + shape."""

from django.contrib.auth import get_user_model

from rest_framework.test import APIClient

import pytest

from apps.accounts.models import Account, AccountGroup
from apps.tenants.models import BusinessCategory, Entity, UserEntityMembership

pytestmark = pytest.mark.django_db
User = get_user_model()


@pytest.fixture
def entity():
    cat = BusinessCategory.objects.create(
        key="transport", label="Transport", band="1", coa_template_key="transport"
    )
    return Entity.objects.create(code="E1", numeric_code="101", legal_name="E1 LLC", category=cat)


@pytest.fixture
def account(entity):
    group = AccountGroup.objects.create(
        entity=entity, level=2, segment="100", code="101-100", name="Current Assets", nature="asset"
    )
    return Account.objects.create(
        entity=entity,
        sub_group=group,
        charge_segment="001",
        code="101-100-100-001",
        name="Cash on Hand",
        account_type="cash",
        normal_balance="D",
    )


def test_member_sees_entity_accounts(account):
    user = User.objects.create_user(email="acct@example.com", password="pw")
    UserEntityMembership.objects.create(user=user, entity=account.entity)

    client = APIClient()
    client.force_authenticate(user=user)
    res = client.get("/api/v1/accounts/")

    assert res.status_code == 200
    row = next(r for r in res.data["results"] if r["code"] == account.code)
    # nature is surfaced from the account's group; type has a human label
    assert row["nature"] == "asset"
    assert row["account_type_display"] == "Cash"
    assert row["sub_group_code"] == "101-100"


def test_non_member_sees_nothing(account):
    user = User.objects.create_user(email="none@example.com", password="pw")
    client = APIClient()
    client.force_authenticate(user=user)
    res = client.get("/api/v1/accounts/")
    assert res.status_code == 200
    assert res.data["results"] == []


def test_entity_filter(account):
    su = User.objects.create_superuser(email="root@example.com", password="pw")
    client = APIClient()
    client.force_authenticate(user=su)
    res = client.get(f"/api/v1/accounts/?entity={account.entity_id}")
    assert res.status_code == 200
    assert {r["code"] for r in res.data["results"]} == {account.code}


def test_account_groups_endpoint(account):
    su = User.objects.create_superuser(email="root2@example.com", password="pw")
    client = APIClient()
    client.force_authenticate(user=su)
    res = client.get("/api/v1/account-groups/")
    assert res.status_code == 200
    assert any(g["code"] == "101-100" for g in res.data["results"])


def test_unauthenticated_is_rejected():
    assert APIClient().get("/api/v1/accounts/").status_code == 401
