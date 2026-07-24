"""API tests for the debit-note endpoint: create a draft, then post it."""

from decimal import Decimal

from django.contrib.auth import get_user_model

from rest_framework.test import APIClient

import pytest

from apps.ap.models import BillStatus, DebitNote
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
        "debit_note_date": "2026-06-20",
        "reason": "Returned goods",
        "lines": [
            {
                "account": str(expense_account.id),
                "description": "Return",
                "line_amount": "1000",
                "tax_code": str(sr_tax.id),
            }
        ],
    }


def test_create_draft_then_post(entity, supplier, sr_tax, expense_account):
    client = _superuser()
    res = client.post(
        "/api/v1/debit-notes/", _payload(entity, supplier, expense_account, sr_tax), format="json"
    )
    assert res.status_code == 201, res.content
    assert res.data["status"] == BillStatus.DRAFT
    note_id = res.data["id"]

    res = client.post(f"/api/v1/debit-notes/{note_id}/post/", {}, format="json")
    assert res.status_code == 200, res.content
    assert res.data["status"] == BillStatus.POSTED
    assert res.data["debit_note_no"].startswith("DN-")
    assert res.data["total"] == "1050.00"

    je = DebitNote.objects.get(id=note_id).journal_entry
    assert je.status == EntryStatus.POSTED
    assert je.total_debit == je.total_credit == Decimal("1050.00")
