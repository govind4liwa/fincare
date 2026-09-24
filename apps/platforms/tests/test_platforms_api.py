"""API tests for platforms: master CRUD, earning imports, settlement lifecycle."""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from rest_framework.test import APIClient

import pytest

from apps.platforms.models import EarningImport, PlatformDocStatus, PlatformSettlement
from apps.platforms.tests.conftest import PLATFORM_CLEARING
from apps.tenants.models import UserEntityMembership

pytestmark = pytest.mark.django_db
User = get_user_model()


def _client(entity, role=None):
    user = User.objects.create_user(email=f"{role or 'member'}@example.com", password="pw")
    UserEntityMembership.objects.create(user=user, entity=entity)
    if role:
        user.groups.add(Group.objects.get_or_create(name=role)[0])
    client = APIClient()
    client.force_authenticate(user)
    return client


def test_member_without_role_can_read_but_not_write_platform(entity, platform):
    client = _client(entity, role=None)
    read = client.get("/api/v1/platforms/")
    assert read.status_code == 200
    assert {p["name"] for p in read.data["results"]} == {"Uber"}

    res = client.post(
        "/api/v1/platforms/",
        {
            "entity": str(entity.id),
            "name": "Bolt",
            "revenue_account": str(platform.revenue_account_id),
            "commission_account": str(platform.commission_account_id),
            "clearing_account": str(platform.clearing_account_id),
        },
        format="json",
    )
    assert res.status_code == 403


def test_create_earning_import(entity, platform):
    client = _client(entity, "accountant")
    res = client.post(
        "/api/v1/earning-imports/",
        {
            "entity": str(entity.id),
            "platform": str(platform.id),
            "trip_ref": "T-1",
            "earning_date": "2026-06-03",
            "gross": "100.00",
            "commission": "20.00",
            "net": "80.00",
        },
        format="json",
    )
    assert res.status_code == 201, res.content
    assert res.data["matched"] is False
    assert res.data["platform_name"] == "Uber"


def test_settlement_reconcile_then_post_flow(entity, platform, bank_enbd, acct):
    EarningImport.objects.create(
        entity=entity,
        platform=platform,
        earning_date=date(2026, 6, 3),
        gross=Decimal("500.00"),
        commission=Decimal("100.00"),
        net=Decimal("400.00"),
    )
    EarningImport.objects.create(
        entity=entity,
        platform=platform,
        earning_date=date(2026, 6, 5),
        gross=Decimal("500.00"),
        commission=Decimal("100.00"),
        net=Decimal("400.00"),
    )
    client = _client(entity, "accountant")

    res = client.post(
        "/api/v1/platform-settlements/",
        {
            "entity": str(entity.id),
            "platform": str(platform.id),
            "period_start": "2026-06-01",
            "period_end": "2026-06-07",
            "settlement_date": "2026-06-08",
            "net_received": "800.00",
            "bank_account": str(bank_enbd.id),
        },
        format="json",
    )
    assert res.status_code == 201, res.content
    settlement_id = res.data["id"]
    assert res.data["status"] == PlatformDocStatus.DRAFT

    res = client.post(f"/api/v1/platform-settlements/{settlement_id}/reconcile/")
    assert res.status_code == 200, res.content
    assert res.data["status"] == PlatformDocStatus.RECONCILED
    assert res.data["gross_earnings"] == "1000.00"
    assert res.data["commission"] == "200.00"
    assert EarningImport.objects.filter(matched=True).count() == 2

    res = client.post(f"/api/v1/platform-settlements/{settlement_id}/post/")
    assert res.status_code == 200, res.content
    assert res.data["status"] == PlatformDocStatus.POSTED
    assert res.data["settlement_no"].startswith("PSL-")

    settlement = PlatformSettlement.objects.get(id=settlement_id)
    je = settlement.journal_entry
    assert je.total_debit == je.total_credit == Decimal("800.00")
    lines = {ln.account.code: (ln.debit, ln.credit) for ln in je.lines.all()}
    assert lines[PLATFORM_CLEARING] == (Decimal("0.00"), Decimal("800.00"))


def test_post_without_bank_account_rejected(entity, platform):
    client = _client(entity, "accountant")
    res = client.post(
        "/api/v1/platform-settlements/",
        {
            "entity": str(entity.id),
            "platform": str(platform.id),
            "period_start": "2026-06-01",
            "period_end": "2026-06-07",
            "settlement_date": "2026-06-08",
            "net_received": "800.00",
        },
        format="json",
    )
    assert res.status_code == 201, res.content
    settlement_id = res.data["id"]

    res = client.post(f"/api/v1/platform-settlements/{settlement_id}/post/")
    assert res.status_code == 400


def test_settlement_write_requires_role(entity, platform, bank_enbd):
    client = _client(entity, role=None)
    res = client.post(
        "/api/v1/platform-settlements/",
        {
            "entity": str(entity.id),
            "platform": str(platform.id),
            "period_start": "2026-06-01",
            "period_end": "2026-06-07",
            "settlement_date": "2026-06-08",
            "net_received": "800.00",
            "bank_account": str(bank_enbd.id),
        },
        format="json",
    )
    assert res.status_code == 403
