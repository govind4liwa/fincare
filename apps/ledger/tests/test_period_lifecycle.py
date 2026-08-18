"""API tests for the accounting-period lifecycle: open -> closed -> locked."""

from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from rest_framework.test import APIClient

import pytest

from apps.ledger.models import AccountingPeriod
from apps.tenants.models import BusinessCategory, Entity, UserEntityMembership

pytestmark = pytest.mark.django_db
User = get_user_model()


@pytest.fixture
def period():
    cat = BusinessCategory.objects.create(
        key="transport", label="Transport", band="1", coa_template_key="transport"
    )
    ent = Entity.objects.create(code="E1", numeric_code="101", legal_name="E1 LLC", category=cat)
    return AccountingPeriod.objects.create(
        entity=ent,
        fiscal_year=2026,
        period_no=7,
        name="Jul-2026",
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 31),
        status=AccountingPeriod.Status.OPEN,
    )


def _client(entity, role=None):
    user = User.objects.create_user(email=f"{role or 'member'}@example.com", password="pw")
    UserEntityMembership.objects.create(user=user, entity=entity)
    if role:
        user.groups.add(Group.objects.get_or_create(name=role)[0])
    client = APIClient()
    client.force_authenticate(user)
    return client


def test_close_then_reopen(period):
    client = _client(period.entity, "accountant")
    res = client.post(f"/api/v1/periods/{period.id}/close/")
    assert res.status_code == 200, res.content
    period.refresh_from_db()
    assert period.status == AccountingPeriod.Status.CLOSED
    assert period.closed_at is not None

    res = client.post(f"/api/v1/periods/{period.id}/reopen/")
    assert res.status_code == 200, res.content
    period.refresh_from_db()
    assert period.status == AccountingPeriod.Status.OPEN
    assert period.closed_at is None


def test_cannot_reopen_an_open_period(period):
    client = _client(period.entity, "accountant")
    res = client.post(f"/api/v1/periods/{period.id}/reopen/")
    assert res.status_code == 400


def test_cannot_close_a_locked_period(period):
    period.status = AccountingPeriod.Status.LOCKED
    period.save(update_fields=["status"])
    client = _client(period.entity, "manager")
    res = client.post(f"/api/v1/periods/{period.id}/close/")
    assert res.status_code == 400


def test_lock_requires_manager_or_admin(period):
    accountant = _client(period.entity, "accountant")
    denied = accountant.post(f"/api/v1/periods/{period.id}/lock/")
    assert denied.status_code == 403

    manager = _client(period.entity, "manager")
    res = manager.post(f"/api/v1/periods/{period.id}/lock/")
    assert res.status_code == 200, res.content
    period.refresh_from_db()
    assert period.status == AccountingPeriod.Status.LOCKED


def test_locked_period_cannot_be_relocked_or_reopened(period):
    period.status = AccountingPeriod.Status.LOCKED
    period.save(update_fields=["status"])
    client = _client(period.entity, "admin")
    relocked = client.post(f"/api/v1/periods/{period.id}/lock/")
    assert relocked.status_code == 400
    reopened = client.post(f"/api/v1/periods/{period.id}/reopen/")
    assert reopened.status_code == 400


def test_member_without_role_cannot_close(period):
    client = _client(period.entity, role=None)
    res = client.post(f"/api/v1/periods/{period.id}/close/")
    assert res.status_code == 403
