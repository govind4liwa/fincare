"""API tests for CoA group (Main/Sub) creation — code composed by service, immutable."""

from django.contrib.auth import get_user_model

from rest_framework.test import APIClient

import pytest

from apps.accounts.models import AccountGroup
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
def main_group(entity):
    return AccountGroup.objects.filter(entity=entity, level=1, nature="expense").first()


def _superuser():
    client = APIClient()
    client.force_authenticate(
        User.objects.create_superuser(email="root@example.com", password="pw")
    )
    return client


def test_create_main_group_derives_nature_and_code(entity):
    res = _superuser().post(
        "/api/v1/account-groups/",
        {"entity": str(entity.id), "level": 1, "segment": "150", "name": "New Main"},
        format="json",
    )
    assert res.status_code == 201, res.content
    assert res.data["code"] == "101-150"
    assert res.data["nature"] == "asset"  # first digit 1 -> asset, derived not typed


def test_main_group_rejects_unmapped_nature_digit(entity):
    res = _superuser().post(
        "/api/v1/account-groups/",
        {"entity": str(entity.id), "level": 1, "segment": "990", "name": "Bad"},
        format="json",
    )
    assert res.status_code == 400


def test_create_sub_group_inherits_parent_nature(entity, main_group):
    res = _superuser().post(
        "/api/v1/account-groups/",
        {
            "entity": str(entity.id),
            "level": 2,
            "segment": "991",
            "name": "New Sub",
            "parent": str(main_group.id),
        },
        format="json",
    )
    assert res.status_code == 201, res.content
    assert res.data["code"] == f"{main_group.code}-991"
    assert res.data["nature"] == main_group.nature


def test_sub_group_requires_a_main_parent(entity, main_group):
    sub = AccountGroup.objects.filter(entity=entity, level=2).first()
    res = _superuser().post(
        "/api/v1/account-groups/",
        {
            "entity": str(entity.id),
            "level": 2,
            "segment": "992",
            "name": "Bad",
            "parent": str(sub.id),
        },
        format="json",
    )
    assert res.status_code == 400


def test_duplicate_segment_rejected(entity, main_group):
    payload = {
        "entity": str(entity.id),
        "level": 2,
        "segment": "993",
        "name": "Dup",
        "parent": str(main_group.id),
    }
    client = _superuser()
    first = client.post("/api/v1/account-groups/", payload, format="json")
    assert first.status_code == 201, first.content
    dup = client.post("/api/v1/account-groups/", payload, format="json")
    assert dup.status_code == 400


def test_update_and_delete_disabled(entity, main_group):
    client = _superuser()
    gid = client.post(
        "/api/v1/account-groups/",
        {
            "entity": str(entity.id),
            "level": 2,
            "segment": "994",
            "name": "X",
            "parent": str(main_group.id),
        },
        format="json",
    ).data["id"]
    assert (
        client.patch(f"/api/v1/account-groups/{gid}/", {"name": "Y"}, format="json").status_code
        == 405
    )
    assert client.delete(f"/api/v1/account-groups/{gid}/").status_code == 405


def test_member_without_role_can_read_but_not_write(entity, main_group):
    user = User.objects.create_user(email="viewer@example.com", password="pw")
    UserEntityMembership.objects.create(user=user, entity=entity)
    client = APIClient()
    client.force_authenticate(user)
    read = client.get("/api/v1/account-groups/")
    assert read.status_code == 200
    res = client.post(
        "/api/v1/account-groups/",
        {
            "entity": str(entity.id),
            "level": 2,
            "segment": "995",
            "name": "X",
            "parent": str(main_group.id),
        },
        format="json",
    )
    assert res.status_code == 403
