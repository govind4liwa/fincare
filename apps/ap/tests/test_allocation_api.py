"""API tests for AP allocation — settle a debit note against a bill."""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model

from rest_framework.test import APIClient

import pytest

from apps.ap.models import BillStatus, DebitNote, DebitNoteLine, PurchaseBill, PurchaseBillLine
from apps.ap.services.post import post_bill, post_debit_note

pytestmark = pytest.mark.django_db
User = get_user_model()


def _superuser():
    client = APIClient()
    client.force_authenticate(
        User.objects.create_superuser(email="root@example.com", password="pw")
    )
    return client


def _bill(entity, supplier, sr_tax, expense_account):
    bill = PurchaseBill.objects.create(
        entity=entity, supplier=supplier, bill_date=date(2026, 6, 15), currency=entity.base_currency
    )
    PurchaseBillLine.objects.create(
        bill=bill,
        line_no=1,
        account=expense_account,
        quantity=Decimal("1"),
        unit_price=Decimal("1000"),
        tax_code=sr_tax,
        recoverable=True,
    )
    return post_bill(bill)


def _debit_note(entity, supplier, sr_tax, expense_account):
    dn = DebitNote.objects.create(
        entity=entity, supplier=supplier, debit_note_date=date(2026, 6, 16)
    )
    DebitNoteLine.objects.create(
        debit_note=dn,
        line_no=1,
        account=expense_account,
        line_amount=Decimal("500"),
        tax_code=sr_tax,
    )
    return post_debit_note(dn)


def test_allocate_debit_note_reduces_balance(entity, supplier, sr_tax, expense_account):
    bill = _bill(entity, supplier, sr_tax, expense_account)
    dn = _debit_note(entity, supplier, sr_tax, expense_account)
    client = _superuser()

    res = client.get(f"/api/v1/bills/allocatable-sources/?supplier={supplier.id}")
    assert res.status_code == 200
    assert any(
        s["source_id"] == str(dn.id) and s["available"] == "525.00" for s in res.data["sources"]
    )

    res = client.post(
        f"/api/v1/bills/{bill.id}/allocate/",
        {"source_type": "debit_note", "source_id": str(dn.id), "amount": "525"},
        format="json",
    )
    assert res.status_code == 200, res.content
    bill.refresh_from_db()
    assert bill.balance == Decimal("525.00")
    assert bill.status == BillStatus.PARTIALLY_PAID
