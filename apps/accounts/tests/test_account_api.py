"""API tests for CoA account create/edit — code composed by service, immutable."""

from django.contrib.auth import get_user_model

from rest_framework.test import APIClient

import pytest

from apps.accounts.models import Account, AccountGroup
from apps.accounts.services.seed import seed_entity_coa
from apps.tenants.models import BusinessCategory, Entity, UserEntityMembership

pytestmark = pytest.mark.django_db
User = get_user_model()


@pytest.fixture
def entity(db):
    cat = BusinessCategory.objects.create(
        key="transport", label="Transport", band="1", coa_template_key="transport"
    )
    ent = Entity.objects.create(
        code="RGT", numeric_code="101", legal_name="Regency Transport LLC", category=cat
    )
    seed_entity_coa(ent)
    return ent


@pytest.fixture
def sub_group(entity):
    return AccountGroup.objects.filter(entity=entity, level=2, nature="expense").first()


def _superuser():
    client = APIClient()
    client.force_authenticate(
        User.objects.create_superuser(email="root@example.com", password="pw")
    )
    return client


def _payload(entity, sub_group, charge="990"):
    return {
        "entity": str(entity.id),
        "sub_group": str(sub_group.id),
        "charge_segment": charge,
        "name": "Toll Charges",
        "account_type": "expense",
    }


def test_create_composes_code_and_derives_balance(entity, sub_group):
    res = _superuser().post("/api/v1/accounts/", _payload(entity, sub_group), format="json")
    assert res.status_code == 201, res.content
    assert res.data["code"] == f"{sub_group.code}-990"  # EEE-MMM-SSS-CCC
    assert res.data["normal_balance"] == "D"  # expense band → debit, not typed
    assert res.data["nature"] == "expense"  # inherited from the sub group


def test_duplicate_charge_rejected(entity, sub_group):
    client = _superuser()
    first = client.post("/api/v1/accounts/", _payload(entity, sub_group, "991"), format="json")
    assert first.status_code == 201, first.content
    dup = client.post("/api/v1/accounts/", _payload(entity, sub_group, "991"), format="json")
    assert dup.status_code == 400


def test_edit_name_keeps_code(entity, sub_group):
    client = _superuser()
    aid = client.post("/api/v1/accounts/", _payload(entity, sub_group, "992"), format="json").data[
        "id"
    ]
    res = client.patch(f"/api/v1/accounts/{aid}/", {"name": "Renamed"}, format="json")
    assert res.status_code == 200
    account = Account.objects.get(id=aid)
    assert account.name == "Renamed"
    assert account.code == f"{sub_group.code}-992"


def test_code_is_immutable_on_edit(entity, sub_group):
    client = _superuser()
    aid = client.post("/api/v1/accounts/", _payload(entity, sub_group, "993"), format="json").data[
        "id"
    ]
    other = AccountGroup.objects.filter(entity=entity, level=2).exclude(id=sub_group.id).first()
    res = client.patch(f"/api/v1/accounts/{aid}/", {"sub_group": str(other.id)}, format="json")
    assert res.status_code == 400


def test_delete_disabled(entity, sub_group):
    client = _superuser()
    aid = client.post("/api/v1/accounts/", _payload(entity, sub_group, "994"), format="json").data[
        "id"
    ]
    deleted = client.delete(f"/api/v1/accounts/{aid}/")
    assert deleted.status_code == 405


def test_member_without_role_can_read_but_not_write(entity, sub_group):
    user = User.objects.create_user(email="viewer@example.com", password="pw")
    UserEntityMembership.objects.create(user=user, entity=entity)
    client = APIClient()
    client.force_authenticate(user)
    read = client.get("/api/v1/accounts/")
    assert read.status_code == 200
    res = client.post("/api/v1/accounts/", _payload(entity, sub_group, "995"), format="json")
    assert res.status_code == 403
