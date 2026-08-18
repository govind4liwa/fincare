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


def test_allocate_bulk_settles_multiple_bills(entity, supplier, sr_tax, expense_account):
    bill1 = _bill(entity, supplier, sr_tax, expense_account)
    bill2 = _bill(entity, supplier, sr_tax, expense_account)
    dn = DebitNote.objects.create(
        entity=entity, supplier=supplier, debit_note_date=date(2026, 6, 16)
    )
    DebitNoteLine.objects.create(
        debit_note=dn,
        line_no=1,
        account=expense_account,
        line_amount=Decimal("2000"),  # covers both 1000-line bills in one source
        tax_code=sr_tax,
    )
    dn = post_debit_note(dn)
    client = _superuser()

    res = client.post(
        "/api/v1/bills/allocate-bulk/",
        {
            "supplier": str(supplier.id),
            "source_type": "debit_note",
            "source_id": str(dn.id),
            "lines": [
                {"bill_id": str(bill1.id), "amount": str(bill1.total)},
                {"bill_id": str(bill2.id), "amount": str(bill2.total)},
            ],
        },
        format="json",
    )
    assert res.status_code == 200, res.content
    bill1.refresh_from_db()
    bill2.refresh_from_db()
    assert bill1.balance == Decimal("0.00")
    assert bill1.status == BillStatus.PAID
    assert bill2.balance == Decimal("0.00")
    assert bill2.status == BillStatus.PAID


def test_allocate_bulk_rejects_total_exceeding_source(entity, supplier, sr_tax, expense_account):
    bill1 = _bill(entity, supplier, sr_tax, expense_account)
    bill2 = _bill(entity, supplier, sr_tax, expense_account)
    dn = _debit_note(entity, supplier, sr_tax, expense_account)  # 525 available
    client = _superuser()

    res = client.post(
        "/api/v1/bills/allocate-bulk/",
        {
            "supplier": str(supplier.id),
            "source_type": "debit_note",
            "source_id": str(dn.id),
            "lines": [
                {"bill_id": str(bill1.id), "amount": "300"},
                {"bill_id": str(bill2.id), "amount": "300"},
            ],
        },
        format="json",
    )
    assert res.status_code == 400
    bill1.refresh_from_db()
    bill2.refresh_from_db()
    # Rejected as a whole — nothing from the batch is applied.
    assert bill1.balance == bill1.total
    assert bill2.balance == bill2.total


def test_unallocate_restores_balance_and_source(entity, supplier, sr_tax, expense_account):
    bill = _bill(entity, supplier, sr_tax, expense_account)
    dn = _debit_note(entity, supplier, sr_tax, expense_account)  # 525 available
    client = _superuser()

    res = client.post(
        f"/api/v1/bills/{bill.id}/allocate/",
        {"source_type": "debit_note", "source_id": str(dn.id), "amount": "525"},
        format="json",
    )
    assert res.status_code == 200, res.content

    res = client.get(f"/api/v1/bills/{bill.id}/allocations/")
    assert res.status_code == 200
    allocation_id = res.data["allocations"][0]["id"]
    assert res.data["allocations"][0]["reversed"] is False

    res = client.post(
        f"/api/v1/bills/{bill.id}/unallocate/",
        {"allocation_id": allocation_id},
        format="json",
    )
    assert res.status_code == 200, res.content
    bill.refresh_from_db()
    assert bill.balance == bill.total
    assert bill.status == BillStatus.POSTED

    res = client.get(f"/api/v1/bills/allocatable-sources/?supplier={supplier.id}")
    assert any(
        s["source_id"] == str(dn.id) and s["available"] == "525.00" for s in res.data["sources"]
    )

    # Reversing the same allocation twice is rejected.
    res = client.post(
        f"/api/v1/bills/{bill.id}/unallocate/",
        {"allocation_id": allocation_id},
        format="json",
    )
    assert res.status_code == 400
