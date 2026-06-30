"""Tests for the append-only audit log and capture service."""

import uuid

import pytest

from apps.audit.models import AuditLog
from apps.audit.services import diff, record, snapshot
from apps.core.models import Currency
from apps.tenants.models import Branch, BusinessCategory, Entity

pytestmark = pytest.mark.django_db


def test_record_create_captures_object_and_repr():
    cur = Currency.objects.create(code="AED", name="UAE Dirham", symbol="AED")
    log = record(action=AuditLog.Action.CREATE, instance=cur, message="seed")

    assert log.action == "create"
    assert log.object_id == str(cur.pk)
    assert log.object_repr == "AED"
    assert log.content_object == cur
    assert log.message == "seed"


def test_record_resolves_entity_id_from_instance():
    cat = BusinessCategory.objects.create(
        key="transport", label="Transport", band="1", coa_template_key="transport"
    )
    entity = Entity.objects.create(
        code="RGT", numeric_code="101", legal_name="Regency", category=cat
    )
    branch = Branch.objects.create(entity=entity, code="DXB", name="Dubai")

    log = record(action=AuditLog.Action.CREATE, instance=branch)
    assert log.entity_id == entity.id


def test_diff_reports_changed_fields_only():
    before = {"name": "A", "rate": "5.0", "active": True}
    after = {"name": "B", "rate": "5.0", "active": False}
    assert diff(before, after) == {"name": ["A", "B"], "active": [True, False]}


def test_snapshot_is_json_safe():
    cur = Currency.objects.create(code="USD", name="US Dollar", symbol="$")
    snap = snapshot(cur, fields=["code", "name", "decimal_places"])
    assert snap["code"] == "USD"
    # all values must be JSON-serialisable primitives
    assert all(isinstance(v, str | int | float | bool | type(None)) for v in snap.values())


def test_log_is_append_only_no_update():
    cur = Currency.objects.create(code="EUR", name="Euro", symbol="€")
    log = record(action=AuditLog.Action.CREATE, instance=cur)
    log.message = "tampered"
    with pytest.raises(ValueError):
        log.save()


def test_log_is_append_only_no_delete():
    cur = Currency.objects.create(code="GBP", name="Pound", symbol="£")
    log = record(action=AuditLog.Action.CREATE, instance=cur)
    with pytest.raises(ValueError):
        log.delete()


def test_record_without_instance_uses_explicit_fields():
    log = record(
        action=AuditLog.Action.LOGIN,
        object_repr="user@example.com",
        entity_id=uuid.uuid4(),
        message="JWT login",
    )
    assert log.action == "login"
    assert log.content_object is None
    assert log.object_repr == "user@example.com"
