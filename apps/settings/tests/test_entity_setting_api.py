"""API tests for EntitySetting — the generic per-entity config override store."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from rest_framework.test import APIClient

import pytest

from apps.settings.models import EntitySetting
from apps.tenants.models import BusinessCategory, Entity, UserEntityMembership

pytestmark = pytest.mark.django_db
User = get_user_model()


@pytest.fixture
def entity():
    cat = BusinessCategory.objects.create(
        key="transport", label="Transport", band="1", coa_template_key="transport"
    )
    return Entity.objects.create(code="RGT", numeric_code="101", legal_name="RGT LLC", category=cat)


def _client(entity, role=None):
    user = User.objects.create_user(email=f"{role or 'member'}@example.com", password="pw")
    UserEntityMembership.objects.create(user=user, entity=entity)
    if role:
        user.groups.add(Group.objects.get_or_create(name=role)[0])
    client = APIClient()
    client.force_authenticate(user)
    return client


def test_manager_can_create_and_update_a_key(entity):
    client = _client(entity, "manager")
    res = client.post(
        "/api/v1/entity-settings/",
        {"entity": str(entity.id), "key": "gratuity_rule", "value": {"cap_years": 3}},
        format="json",
    )
    assert res.status_code == 201, res.content
    row_id = res.data["id"]

    res = client.patch(
        f"/api/v1/entity-settings/{row_id}/", {"value": {"cap_years": 1}}, format="json"
    )
    assert res.status_code == 200, res.content
    assert EntitySetting.objects.get(id=row_id).value == {"cap_years": 1}


def test_duplicate_key_rejected(entity):
    client = _client(entity, "manager")
    payload = {"entity": str(entity.id), "key": "sif_layout", "value": {}}
    first = client.post("/api/v1/entity-settings/", payload, format="json")
    assert first.status_code == 201, first.content
    dup = client.post("/api/v1/entity-settings/", payload, format="json")
    assert dup.status_code == 400


def test_member_without_role_can_read_but_not_write(entity):
    EntitySetting.objects.create(entity=entity, key="gratuity_rule", value={"cap_years": 2})
    client = _client(entity, role=None)
    read = client.get("/api/v1/entity-settings/")
    assert read.status_code == 200
    assert len(read.data["results"]) == 1

    res = client.post(
        "/api/v1/entity-settings/",
        {"entity": str(entity.id), "key": "sif_layout", "value": {}},
        format="json",
    )
    assert res.status_code == 403


def test_accountant_cannot_write(entity):
    client = _client(entity, "accountant")
    res = client.post(
        "/api/v1/entity-settings/",
        {"entity": str(entity.id), "key": "sif_layout", "value": {}},
        format="json",
    )
    assert res.status_code == 403


def test_delete_disabled(entity):
    row = EntitySetting.objects.create(entity=entity, key="gratuity_rule", value={})
    client = _client(entity, "admin")
    deleted = client.delete(f"/api/v1/entity-settings/{row.id}/")
    assert deleted.status_code == 405
