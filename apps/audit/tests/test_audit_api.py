"""API tests for the read-only audit-log endpoint."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from rest_framework.test import APIClient

import pytest

from apps.audit.models import AuditLog
from apps.audit.services import record
from apps.core.models import Currency
from apps.tenants.models import BusinessCategory, Entity, UserEntityMembership

pytestmark = pytest.mark.django_db
User = get_user_model()


def _client(entity, role=None):
    user = User.objects.create_user(email=f"{role or 'member'}@example.com", password="pw")
    if entity is not None:
        UserEntityMembership.objects.create(user=user, entity=entity)
    if role:
        user.groups.add(Group.objects.get_or_create(name=role)[0])
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def entity():
    cat = BusinessCategory.objects.create(
        key="transport", label="Transport", band="1", coa_template_key="transport"
    )
    return Entity.objects.create(code="RGT", numeric_code="101", legal_name="Regency", category=cat)


@pytest.fixture
def other_entity():
    cat = BusinessCategory.objects.create(
        key="restaurant", label="Restaurant", band="2", coa_template_key="restaurant"
    )
    return Entity.objects.create(
        code="SPC", numeric_code="201", legal_name="Spice Kitchen", category=cat
    )


def test_member_without_role_cannot_read_audit_logs(entity):
    client = _client(entity, role=None)
    res = client.get("/api/v1/audit-logs/")
    assert res.status_code == 403


def test_accountant_sees_only_own_entity_logs(entity, other_entity):
    cur = Currency.objects.create(code="AED", name="UAE Dirham", symbol="AED")
    record(action=AuditLog.Action.CREATE, instance=cur, entity_id=entity.id, message="mine")
    record(
        action=AuditLog.Action.CREATE, instance=cur, entity_id=other_entity.id, message="not mine"
    )

    client = _client(entity, "accountant")
    res = client.get("/api/v1/audit-logs/")
    assert res.status_code == 200
    messages = {row["message"] for row in res.data["results"]}
    assert messages == {"mine"}


def test_audit_log_shows_actor_email_and_content_type_label(entity):
    actor = User.objects.create_user(email="poster@example.com", password="pw")
    cur = Currency.objects.create(code="USD", name="US Dollar", symbol="$")
    record(action=AuditLog.Action.POST, instance=cur, actor=actor, entity_id=entity.id)

    client = _client(entity, "accountant")
    res = client.get("/api/v1/audit-logs/")
    assert res.status_code == 200
    row = res.data["results"][0]
    assert row["actor_email"] == "poster@example.com"
    assert row["content_type_label"] == "core.currency"


def test_null_entity_logs_hidden_from_regular_members(entity):
    record(action=AuditLog.Action.LOGIN, object_repr="someone@example.com")

    client = _client(entity, "accountant")
    res = client.get("/api/v1/audit-logs/")
    assert res.status_code == 200
    assert res.data["results"] == []


def test_audit_log_is_read_only(entity):
    cur = Currency.objects.create(code="EUR", name="Euro", symbol="€")
    log = record(action=AuditLog.Action.CREATE, instance=cur, entity_id=entity.id)

    client = _client(entity, "accountant")
    posted = client.post("/api/v1/audit-logs/", {}, format="json")
    assert posted.status_code == 405
    patched = client.patch(f"/api/v1/audit-logs/{log.id}/", {}, format="json")
    assert patched.status_code == 405
    deleted = client.delete(f"/api/v1/audit-logs/{log.id}/")
    assert deleted.status_code == 405


def test_filter_by_action(entity):
    cur = Currency.objects.create(code="GBP", name="Pound", symbol="£")
    record(action=AuditLog.Action.CREATE, instance=cur, entity_id=entity.id)
    record(action=AuditLog.Action.POST, instance=cur, entity_id=entity.id)

    client = _client(entity, "accountant")
    res = client.get("/api/v1/audit-logs/?action=post")
    assert res.status_code == 200
    assert len(res.data["results"]) == 1
    assert res.data["results"][0]["action"] == "post"
