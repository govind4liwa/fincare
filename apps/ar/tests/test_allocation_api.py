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
