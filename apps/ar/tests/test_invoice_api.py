"""API tests for the sales-invoice endpoint: create a draft, then post it."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from rest_framework.test import APIClient

import pytest

from apps.ar.models import InvoiceStatus, SalesInvoice
from apps.ledger.models import EntryStatus

pytestmark = pytest.mark.django_db
User = get_user_model()


def _superuser():
    client = APIClient()
    client.force_authenticate(
        User.objects.create_superuser(email="root@example.com", password="pw")
    )
    return client


def _payload(entity, customer, revenue_account, sr_tax):
    return {
        "entity": str(entity.id),
        "customer": str(customer.id),
        "invoice_date": "2026-06-15",
        "place_of_supply": "Dubai",
        "currency": str(entity.base_currency_id),
        "narration": "June trips",
        "lines": [
            {
                "revenue_account": str(revenue_account.id),
                "description": "Trip charges",
                "quantity": "1",
                "unit_price": "1000",
                "tax_code": str(sr_tax.id),
            }
        ],
    }


def test_create_draft_then_post(entity, customer, sr_tax, revenue_account):
    client = _superuser()

    res = client.post(
        "/api/v1/invoices/",
        _payload(entity, customer, revenue_account, sr_tax),
        format="json",
    )
    assert res.status_code == 201, res.content
    assert res.data["status"] == InvoiceStatus.DRAFT
    assert res.data["invoice_no"] == ""  # numbered only at post
    invoice_id = res.data["id"]

    res = client.post(f"/api/v1/invoices/{invoice_id}/post/", {}, format="json")
    assert res.status_code == 200, res.content
    assert res.data["status"] == InvoiceStatus.POSTED
    assert res.data["invoice_no"].startswith("INV-")
    assert res.data["total"] == "1050.00"  # 1000 + 5% VAT from the TaxCode

    inv = SalesInvoice.objects.get(id=invoice_id)
    je = inv.journal_entry
    assert je is not None
    assert je.status == EntryStatus.POSTED
    assert je.total_debit == je.total_credit == Decimal("1050.00")


def test_post_twice_is_rejected(entity, customer, sr_tax, revenue_account):
    client = _superuser()
    invoice_id = client.post(
        "/api/v1/invoices/",
        _payload(entity, customer, revenue_account, sr_tax),
        format="json",
    ).data["id"]
    assert client.post(f"/api/v1/invoices/{invoice_id}/post/", {}, format="json").status_code == 200
    # A posted invoice is immutable — a second post is a 400, not a double entry.
    again = client.post(f"/api/v1/invoices/{invoice_id}/post/", {}, format="json")
    assert again.status_code == 400


def test_non_member_sees_no_invoices(entity, customer, sr_tax, revenue_account):
    # Seed one invoice as a superuser.
    _superuser().post(
        "/api/v1/invoices/",
        _payload(entity, customer, revenue_account, sr_tax),
        format="json",
    )
    # A user with the accountant role but NO membership passes the role gate yet
    # sees an empty list — entity-scoping filters out invoices they can't access.
    outsider = User.objects.create_user(email="out@example.com", password="pw")
    outsider.groups.add(Group.objects.create(name="accountant"))
    client = APIClient()
    client.force_authenticate(outsider)
    res = client.get("/api/v1/invoices/")
    assert res.status_code == 200
    assert res.data["results"] == []
