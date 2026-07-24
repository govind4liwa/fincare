"""API test for the ledger accounting-periods endpoint (membership scoping)."""

from datetime import date

from django.contrib.auth import get_user_model

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


def test_member_sees_periods(period):
    user = User.objects.create_user(email="p@example.com", password="pw")
    UserEntityMembership.objects.create(user=user, entity=period.entity)
    client = APIClient()
    client.force_authenticate(user)
    res = client.get("/api/v1/periods/")
    assert res.status_code == 200
    assert {p["name"] for p in res.data["results"]} == {"Jul-2026"}


def test_non_member_sees_nothing(period):
    user = User.objects.create_user(email="x@example.com", password="pw")
    client = APIClient()
    client.force_authenticate(user)
    assert client.get("/api/v1/periods/").data["results"] == []


def test_unauthenticated_is_rejected():
    assert APIClient().get("/api/v1/periods/").status_code == 401
