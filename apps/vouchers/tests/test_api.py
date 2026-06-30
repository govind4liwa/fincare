"""Voucher API tests: create a draft and post it via the /post/ action."""

import uuid

from django.contrib.auth import get_user_model

from rest_framework.test import APIClient

import pytest

from apps.vouchers.models import VoucherStatus

pytestmark = pytest.mark.django_db

User = get_user_model()
BANK = "101-100-110-010"
AR = "101-100-120-001"


@pytest.fixture
def api():
    client = APIClient()
    admin = User.objects.create_superuser(email="admin@example.com", password="pw")
    client.force_authenticate(user=admin)
    return client


def test_create_then_post_voucher(api, entity, acct):
    payload = {
        "entity": str(entity.id),
        "voucher_type": "receipt",
        "voucher_date": "2026-06-15",
        "currency": str(entity.base_currency_id),
        "lines": [
            {"account": str(acct(BANK).id), "debit": "500", "credit": "0"},
            {
                "account": str(acct(AR).id),
                "debit": "0",
                "credit": "500",
                "party_type": "customer",
                "party_id": str(uuid.uuid4()),
            },
        ],
    }
    create = api.post("/api/v1/vouchers/", payload, format="json")
    assert create.status_code == 201, create.data
    voucher_id = create.data["id"]
    assert create.data["status"] == VoucherStatus.DRAFT

    posted = api.post(f"/api/v1/vouchers/{voucher_id}/post/", {}, format="json")
    assert posted.status_code == 200, posted.data
    assert posted.data["status"] == VoucherStatus.POSTED
    assert posted.data["voucher_no"].startswith("RV-")
    assert posted.data["journal_entry"] is not None
