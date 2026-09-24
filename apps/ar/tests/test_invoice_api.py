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


def test_posted_invoice_cannot_be_deleted(entity, customer, sr_tax, revenue_account):
    """A posted invoice must not be deletable — its journal entry is in the GL.

    Before the delete guard this returned 204 and soft-deleted the invoice,
    leaving the revenue and output VAT posted with no source document: the AR
    subledger and the GL disagreed, silently.
    """
    client = _superuser()
    invoice_id = client.post(
        "/api/v1/invoices/",
        _payload(entity, customer, revenue_account, sr_tax),
        format="json",
    ).data["id"]
    assert client.post(f"/api/v1/invoices/{invoice_id}/post/", {}, format="json").status_code == 200

    res = client.delete(f"/api/v1/invoices/{invoice_id}/")
    assert res.status_code == 409, res.content
    assert SalesInvoice.objects.filter(id=invoice_id).exists()


def test_draft_invoice_can_still_be_deleted(entity, customer, sr_tax, revenue_account):
    """The guard must not overreach — an unposted draft is still disposable."""
    client = _superuser()
    invoice_id = client.post(
        "/api/v1/invoices/",
        _payload(entity, customer, revenue_account, sr_tax),
        format="json",
    ).data["id"]

    res = client.delete(f"/api/v1/invoices/{invoice_id}/")
    assert res.status_code == 204, res.content
    assert not SalesInvoice.objects.filter(id=invoice_id).exists()


def _other_entity_zero_rated(entity):
    from apps.accounts.models import TaxCode
    from apps.accounts.services.seed import seed_entity_coa
    from apps.tenants.models import Entity

    other = Entity.objects.create(
        code="RGL",
        numeric_code="102",
        legal_name="Regency Limo LLC",
        category=entity.category,
        base_currency=entity.base_currency,
    )
    seed_entity_coa(other)
    return TaxCode.objects.create(
        entity=other,
        code="ZR",
        name="Zero rated",
        rate=Decimal("0.000"),
        treatment=TaxCode.Treatment.ZERO,
        direction=TaxCode.Direction.OUTPUT,
    )


def test_invoice_cannot_use_another_entitys_tax_code(entity, customer, sr_tax, revenue_account):
    """The case that proved the bug.

    An accountant for entity A only posted an entity-A sale on entity B's
    zero-rated code: it posted at 0%, totalling 1000.00 where a standard-rated
    sale should be 1050.00, under-declaring AED 50 of output VAT. The posting
    engine's account check did not catch it, because the VAT still posts to
    entity A's own VAT account — only the *rate* came from entity B.
    """
    foreign_zero = _other_entity_zero_rated(entity)
    client = _superuser()
    payload = _payload(entity, customer, revenue_account, sr_tax)
    payload["lines"][0]["tax_code"] = str(foreign_zero.id)
    invoice_id = client.post("/api/v1/invoices/", payload, format="json").data["id"]

    res = client.post(f"/api/v1/invoices/{invoice_id}/post/", {}, format="json")

    assert res.status_code == 400, res.content
    invoice = SalesInvoice.objects.get(id=invoice_id)
    assert invoice.status == InvoiceStatus.DRAFT
    assert invoice.journal_entry is None
