"""Aggregate trip revenue posting + contract invoice generation tests."""

from datetime import date
from decimal import Decimal

import pytest

from apps.ar.models import InvoiceStatus
from apps.bookings.models import Trip, TripStatus, TripType
from apps.bookings.services.post import BookingError, generate_invoice, post_aggregate_revenue
from apps.bookings.tests.conftest import (
    CONTRACT_REVENUE,
    PLATFORM_CLEARING,
    UBER_COMMISSION,
    UBER_REVENUE,
)

pytestmark = pytest.mark.django_db


def _trip(entity, platform, vehicle, driver, fare, commission):
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


def test_aggregate_trip_revenue_posts_one_balanced_je(entity, platform, vehicle, driver):
    t1 = _trip(entity, platform, vehicle, driver, "100.00", "20.00")
    t2 = _trip(entity, platform, vehicle, driver, "150.00", "30.00")

    entry = post_aggregate_revenue(platform, [t1, t2], date=date(2026, 6, 6))

    # fare 250, commission 50, net 200 -> DR clearing 200 + DR commission 50 = CR revenue 250
    assert entry.total_debit == entry.total_credit == Decimal("250.00")
    lines = {ln.account.code: (ln.debit, ln.credit) for ln in entry.lines.all()}
    assert lines[PLATFORM_CLEARING] == (Decimal("200.00"), Decimal("0.00"))
    assert lines[UBER_COMMISSION] == (Decimal("50.00"), Decimal("0.00"))
    assert lines[UBER_REVENUE] == (Decimal("0.00"), Decimal("250.00"))
    # dims present on every line
    for ln in entry.lines.all():
        assert ln.platform_id == platform.id
        assert ln.vehicle_id == vehicle.id
        assert ln.driver_id == driver.id

    for t in (t1, t2):
        t.refresh_from_db()
        assert t.status == TripStatus.INVOICED
        assert t.revenue_journal_entry_id == entry.id
    t1.refresh_from_db()
    assert t1.net_revenue == Decimal("80.00")


def test_aggregate_groups_by_vehicle_driver(entity, platform, vehicle, driver):
    from apps.fleet.models import Vehicle

    v2 = Vehicle.objects.create(entity=entity, code="V002", plate_no="B54321")
    t1 = _trip(entity, platform, vehicle, driver, "100.00", "20.00")
    t2 = _trip(entity, platform, v2, driver, "200.00", "40.00")

    entry = post_aggregate_revenue(platform, [t1, t2], date=date(2026, 6, 6))

    # net 80 + 160 = 240 clearing; commission 60; revenue 300
    assert entry.total_debit == entry.total_credit == Decimal("300.00")
    clearing = sum(
        ln.debit for ln in entry.lines.all() if ln.account.code == PLATFORM_CLEARING
    )
    assert clearing == Decimal("240.00")
    # two distinct vehicle dims among clearing lines
    veh_ids = {ln.vehicle_id for ln in entry.lines.all() if ln.account.code == PLATFORM_CLEARING}
    assert veh_ids == {vehicle.id, v2.id}


def test_aggregate_rejects_already_invoiced_trip(entity, platform, vehicle, driver):
    t1 = _trip(entity, platform, vehicle, driver, "100.00", "20.00")
    post_aggregate_revenue(platform, [t1], date=date(2026, 6, 6))
    with pytest.raises(BookingError):
        post_aggregate_revenue(platform, [t1], date=date(2026, 6, 7))


def test_contract_invoice_generation(entity, contract, customer, acct):
    invoice = generate_invoice(contract, invoice_date=date(2026, 6, 30), period_label="Jun-2026")

    assert invoice.status == InvoiceStatus.POSTED
    assert invoice.invoice_no.startswith("INV-")
    assert invoice.subtotal == Decimal("5000.00")
    assert invoice.tax_total == Decimal("250.00")  # 5% SR
    assert invoice.total == Decimal("5250.00")

    je = invoice.journal_entry
    assert je.total_debit == je.total_credit == Decimal("5250.00")
    ar_line = je.lines.get(account=customer.receivable_account)
    assert ar_line.debit == Decimal("5250.00")
    assert ar_line.party_type == "customer"
    assert ar_line.party_id == customer.id
    rev_line = je.lines.get(account=acct(CONTRACT_REVENUE))
    assert rev_line.credit == Decimal("5000.00")
