"""API tests for the purchase-bill endpoint: create a draft, then post it."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from rest_framework.test import APIClient

import pytest

from apps.ap.models import BillStatus, PurchaseBill
from apps.ledger.models import EntryStatus

pytestmark = pytest.mark.django_db
User = get_user_model()


def _superuser():
    client = APIClient()
    client.force_authenticate(
        User.objects.create_superuser(email="root@example.com", password="pw")
    )
    return client


def _payload(entity, supplier, expense_account, sr_tax):
    return {
        "entity": str(entity.id),
        "supplier": str(supplier.id),
        "bill_date": "2026-06-15",
        "supplier_invoice_no": "SUP-123",
        "currency": str(entity.base_currency_id),
        "is_reverse_charge": False,
        "lines": [
            {
                "account": str(expense_account.id),
                "description": "Diesel",
                "quantity": "1",
                "unit_price": "1000",
                "tax_code": str(sr_tax.id),
                "recoverable": True,
            }
        ],
    }


def test_create_draft_then_post(entity, supplier, sr_tax, expense_account):
    client = _superuser()

    res = client.post(
        "/api/v1/bills/",
        _payload(entity, supplier, expense_account, sr_tax),
        format="json",
    )
    assert res.status_code == 201, res.content
    assert res.data["status"] == BillStatus.DRAFT
    assert res.data["bill_no"] == ""  # numbered only at post
    bill_id = res.data["id"]

    res = client.post(f"/api/v1/bills/{bill_id}/post/", {}, format="json")
    assert res.status_code == 200, res.content
    assert res.data["status"] == BillStatus.POSTED
    assert res.data["bill_no"].startswith("BILL-")
    assert res.data["total"] == "1050.00"  # 1000 + 5% recoverable input VAT

    bill = PurchaseBill.objects.get(id=bill_id)
    je = bill.journal_entry
    assert je is not None
    assert je.status == EntryStatus.POSTED
    assert je.total_debit == je.total_credit == Decimal("1050.00")


def test_non_member_sees_no_bills(entity, supplier, sr_tax, expense_account):
    _superuser().post(
        "/api/v1/bills/",
        _payload(entity, supplier, expense_account, sr_tax),
        format="json",
    )
    # Role granted, no membership → entity-scoping yields an empty list.
    outsider = User.objects.create_user(email="out@example.com", password="pw")
    outsider.groups.add(Group.objects.create(name="accountant"))
    client = APIClient()
    client.force_authenticate(outsider)
    res = client.get("/api/v1/bills/")
    assert res.status_code == 200
    assert res.data["results"] == []
