"""API tests for the trip register (aggregate revenue posting) and contracts."""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from rest_framework.test import APIClient

import pytest

from apps.ar.models import InvoiceStatus
from apps.bookings.models import Trip, TripStatus, TripType
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


def _trip(entity, platform, vehicle, driver, fare="100.00", commission="20.00"):
    return Trip.objects.create(
        entity=entity,
        trip_date=date(2026, 6, 5),
        trip_type=TripType.PLATFORM,
        vehicle=vehicle,
        driver=driver,
        platform=platform,
        fare=Decimal(fare),
        commission=Decimal(commission),
    )


def test_member_without_role_can_read_but_not_write_trip(entity, platform, vehicle, driver):
    _trip(entity, platform, vehicle, driver)
    client = _client(entity, role=None)
    read = client.get("/api/v1/trips/")
    assert read.status_code == 200
    assert len(read.data["results"]) == 1

    res = client.post(
        "/api/v1/trips/",
        {
            "entity": str(entity.id),
            "trip_date": "2026-06-06",
            "trip_type": "personal",
            "fare": "50",
        },
        format="json",
    )
    assert res.status_code == 403


def test_post_revenue_aggregates_trips(entity, platform, vehicle, driver):
    t1 = _trip(entity, platform, vehicle, driver, "100.00", "20.00")
    t2 = _trip(entity, platform, vehicle, driver, "150.00", "30.00")
    client = _client(entity, "accountant")

    res = client.post(
        "/api/v1/trips/post-revenue/",
        {
            "platform": str(platform.id),
            "trip_ids": [str(t1.id), str(t2.id)],
            "date": "2026-06-06",
        },
        format="json",
    )
    assert res.status_code == 200, res.content
    assert res.data["entry_no"]
    assert len(res.data["trips"]) == 2

    t1.refresh_from_db()
    t2.refresh_from_db()
    assert t1.status == TripStatus.INVOICED
    assert t2.status == TripStatus.INVOICED
    assert t1.net_revenue == Decimal("80.00")


def test_post_revenue_rejects_mismatched_platform(entity, platform, vehicle, driver):
    other_trip = _trip(entity, None, vehicle, driver)  # personal trip, no platform
    client = _client(entity, "accountant")

    res = client.post(
        "/api/v1/trips/post-revenue/",
        {"platform": str(platform.id), "trip_ids": [str(other_trip.id)], "date": "2026-06-06"},
        format="json",
    )
    assert res.status_code == 400


def test_post_revenue_requires_date(entity, platform, vehicle, driver):
    t1 = _trip(entity, platform, vehicle, driver)
    client = _client(entity, "accountant")

    res = client.post(
        "/api/v1/trips/post-revenue/",
        {"platform": str(platform.id), "trip_ids": [str(t1.id)]},
        format="json",
    )
    assert res.status_code == 400


def test_generate_invoice_from_contract(entity, contract):
    client = _client(entity, "accountant")
    res = client.post(
        f"/api/v1/contracts/{contract.id}/generate-invoice/",
        {"invoice_date": "2026-06-30", "period_label": "Jun-2026"},
        format="json",
    )
    assert res.status_code == 200, res.content
    assert res.data["invoice_no"]

    from apps.ar.models import SalesInvoice

    invoice = SalesInvoice.objects.get(id=res.data["invoice_id"])
    assert invoice.status == InvoiceStatus.POSTED
    assert invoice.total == Decimal("5250.00")  # 5000 + 5% VAT


def test_generate_invoice_requires_date(entity, contract):
    client = _client(entity, "accountant")
    res = client.post(f"/api/v1/contracts/{contract.id}/generate-invoice/", {}, format="json")
    assert res.status_code == 400


def test_contract_write_requires_role(entity):
    client = _client(entity, role=None)
    res = client.get("/api/v1/contracts/")
    assert res.status_code == 200

    res = client.post("/api/v1/contracts/", {"entity": str(entity.id)}, format="json")
    assert res.status_code == 403
