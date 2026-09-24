"""API tests for AR allocation — settle a credit note against an invoice."""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model

from rest_framework.test import APIClient

import pytest

from apps.ar.models import (
    CreditNote,
    CreditNoteLine,
    InvoiceStatus,
    SalesInvoice,
    SalesInvoiceLine,
)
from apps.ar.services.post import post_credit_note, post_invoice

pytestmark = pytest.mark.django_db
User = get_user_model()


def _superuser():
    client = APIClient()
    client.force_authenticate(
        User.objects.create_superuser(email="root@example.com", password="pw")
    )
    return client


def _invoice(entity, customer, sr_tax, revenue_account):
    inv = SalesInvoice.objects.create(
        entity=entity,
        customer=customer,
        invoice_date=date(2026, 6, 15),
        currency=entity.base_currency,
    )
    SalesInvoiceLine.objects.create(
        invoice=inv,
        line_no=1,
        revenue_account=revenue_account,
        quantity=Decimal("1"),
        unit_price=Decimal("1000"),
        tax_code=sr_tax,
    )
    return post_invoice(inv)


def _credit_note(entity, customer, sr_tax, revenue_account):
    cn = CreditNote.objects.create(
        entity=entity, customer=customer, credit_note_date=date(2026, 6, 16)
    )
    CreditNoteLine.objects.create(
        credit_note=cn,
        line_no=1,
        revenue_account=revenue_account,
        line_amount=Decimal("500"),
        tax_code=sr_tax,
    )
    return post_credit_note(cn)


def test_allocate_credit_note_reduces_balance(entity, customer, sr_tax, revenue_account):
    inv = _invoice(entity, customer, sr_tax, revenue_account)
    cn = _credit_note(entity, customer, sr_tax, revenue_account)
    client = _superuser()

    res = client.get(f"/api/v1/invoices/allocatable-sources/?customer={customer.id}")
    assert res.status_code == 200
    assert any(
        s["source_id"] == str(cn.id) and s["available"] == "525.00" for s in res.data["sources"]
    )

    res = client.post(
        f"/api/v1/invoices/{inv.id}/allocate/",
        {"source_type": "credit_note", "source_id": str(cn.id), "amount": "525"},
        format="json",
    )
    assert res.status_code == 200, res.content
    inv.refresh_from_db()
    assert inv.balance == Decimal("525.00")
    assert inv.status == InvoiceStatus.PARTIALLY_PAID


def test_over_allocating_source_rejected(entity, customer, sr_tax, revenue_account):
    inv = _invoice(entity, customer, sr_tax, revenue_account)
    cn = _credit_note(entity, customer, sr_tax, revenue_account)  # 525 available
    client = _superuser()
    client.post(
        f"/api/v1/invoices/{inv.id}/allocate/",
        {"source_type": "credit_note", "source_id": str(cn.id), "amount": "525"},
        format="json",
    )
    # The source is now exhausted — a second allocation is rejected even though the
    # invoice still has an outstanding balance.
    res = client.post(
        f"/api/v1/invoices/{inv.id}/allocate/",
        {"source_type": "credit_note", "source_id": str(cn.id), "amount": "100"},
        format="json",
    )
    assert res.status_code == 400


def test_allocate_bulk_settles_multiple_invoices(entity, customer, sr_tax, revenue_account):
    inv1 = _invoice(entity, customer, sr_tax, revenue_account)
    inv2 = _invoice(entity, customer, sr_tax, revenue_account)
    cn = CreditNote.objects.create(
        entity=entity, customer=customer, credit_note_date=date(2026, 6, 16)
    )
    CreditNoteLine.objects.create(
        credit_note=cn,
        line_no=1,
        revenue_account=revenue_account,
        line_amount=Decimal("2000"),  # covers both 1000-line invoices in one source
        tax_code=sr_tax,
    )
    cn = post_credit_note(cn)
    client = _superuser()

    res = client.post(
        "/api/v1/invoices/allocate-bulk/",
        {
            "customer": str(customer.id),
            "source_type": "credit_note",
            "source_id": str(cn.id),
            "lines": [
                {"invoice_id": str(inv1.id), "amount": str(inv1.total)},
                {"invoice_id": str(inv2.id), "amount": str(inv2.total)},
            ],
        },
        format="json",
    )
    assert res.status_code == 200, res.content
    inv1.refresh_from_db()
    inv2.refresh_from_db()
    assert inv1.balance == Decimal("0.00")
    assert inv1.status == InvoiceStatus.PAID
    assert inv2.balance == Decimal("0.00")
    assert inv2.status == InvoiceStatus.PAID


def test_allocate_bulk_rejects_total_exceeding_source(entity, customer, sr_tax, revenue_account):
    inv1 = _invoice(entity, customer, sr_tax, revenue_account)
    inv2 = _invoice(entity, customer, sr_tax, revenue_account)
    cn = _credit_note(entity, customer, sr_tax, revenue_account)  # 525 available
    client = _superuser()

    res = client.post(
        "/api/v1/invoices/allocate-bulk/",
        {
            "customer": str(customer.id),
            "source_type": "credit_note",
            "source_id": str(cn.id),
            "lines": [
                {"invoice_id": str(inv1.id), "amount": "300"},
                {"invoice_id": str(inv2.id), "amount": "300"},
            ],
        },
        format="json",
    )
    assert res.status_code == 400
    inv1.refresh_from_db()
    inv2.refresh_from_db()
    # Rejected as a whole — nothing from the batch is applied.
    assert inv1.balance == inv1.total
    assert inv2.balance == inv2.total


def test_unallocate_restores_balance_and_source(entity, customer, sr_tax, revenue_account):
    inv = _invoice(entity, customer, sr_tax, revenue_account)
    cn = _credit_note(entity, customer, sr_tax, revenue_account)  # 525 available
    client = _superuser()

    res = client.post(
        f"/api/v1/invoices/{inv.id}/allocate/",
        {"source_type": "credit_note", "source_id": str(cn.id), "amount": "525"},
        format="json",
    )
    assert res.status_code == 200, res.content

    res = client.get(f"/api/v1/invoices/{inv.id}/allocations/")
    assert res.status_code == 200
    allocation_id = res.data["allocations"][0]["id"]
    assert res.data["allocations"][0]["reversed"] is False

    res = client.post(
        f"/api/v1/invoices/{inv.id}/unallocate/",
        {"allocation_id": allocation_id},
        format="json",
    )
    assert res.status_code == 200, res.content
    inv.refresh_from_db()
    assert inv.balance == inv.total
    assert inv.status == InvoiceStatus.POSTED

    res = client.get(f"/api/v1/invoices/allocatable-sources/?customer={customer.id}")
    assert any(
        s["source_id"] == str(cn.id) and s["available"] == "525.00" for s in res.data["sources"]
    )

    # Reversing the same allocation twice is rejected.
    res = client.post(
        f"/api/v1/invoices/{inv.id}/unallocate/",
        {"allocation_id": allocation_id},
        format="json",
    )
    assert res.status_code == 400
