"""Voucher API tests: create a draft and post it via the /post/ action."""

import uuid
from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from rest_framework.test import APIClient

import pytest

from apps.tenants.models import UserEntityMembership
from apps.vouchers.models import Voucher, VoucherStatus

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


def test_vouchers_scoped_by_membership(entity):
    voucher = Voucher.objects.create(
        entity=entity, voucher_type="journal", voucher_date=date(2026, 6, 15)
    )
    acct_group, _ = Group.objects.get_or_create(name="accountant")

    member = User.objects.create_user(email="member@example.com", password="pw")
    member.groups.add(acct_group)
    UserEntityMembership.objects.create(user=member, entity=entity)
    client = APIClient()
    client.force_authenticate(member)
    res = client.get("/api/v1/vouchers/")
    assert res.status_code == 200
    assert {r["id"] for r in res.data["results"]} == {str(voucher.id)}

    outsider = User.objects.create_user(email="outsider@example.com", password="pw")
    outsider.groups.add(acct_group)
    other = APIClient()
    other.force_authenticate(outsider)
    assert other.get("/api/v1/vouchers/").data["results"] == []


def test_vouchers_entity_filter(api, entity):
    voucher = Voucher.objects.create(
        entity=entity, voucher_type="payment", voucher_date=date(2026, 6, 20)
    )
    res = api.get(f"/api/v1/vouchers/?entity={entity.id}")
    assert res.status_code == 200
    assert str(voucher.id) in {r["id"] for r in res.data["results"]}


def test_voucher_cannot_post_to_another_entitys_account(entity, acct):
    """The API path that proved the bug.

    An accountant for entity A only — no access at all to entity B — created
    and posted an entity-A voucher whose bank line pointed at entity B's bank
    account. It returned 201 then 200, and entity A's journal entry carried a
    500.00 debit on entity B's books.
    """
    from django.contrib.auth.models import Group

    from apps.accounts.models import Account
    from apps.accounts.services.seed import seed_entity_coa
    from apps.ledger.models import JournalLine
    from apps.tenants.models import Entity, UserEntityMembership

    other = Entity.objects.create(
        code="RGL",
        numeric_code="102",
        legal_name="Regency Limo LLC",
        category=entity.category,
        base_currency=entity.base_currency,
    )
    seed_entity_coa(other)
    foreign_bank = Account.objects.get(entity=other, code="102-100-110-010")

    user = User.objects.create_user(email="acct@a.example", password="pw")
    UserEntityMembership.objects.create(user=user, entity=entity)
    user.groups.add(Group.objects.get_or_create(name="accountant")[0])
    client = APIClient()
    client.force_authenticate(user)

    created = client.post(
        "/api/v1/vouchers/",
        {
            "entity": str(entity.id),
            "voucher_type": "receipt",
            "voucher_date": "2026-06-15",
            "currency": str(entity.base_currency_id),
            "lines": [
                {"account": str(foreign_bank.id), "debit": "500", "credit": "0"},
                {
                    "account": str(acct(AR).id),
                    "debit": "0",
                    "credit": "500",
                    "party_type": "customer",
                    "party_id": str(uuid.uuid4()),
                },
            ],
        },
        format="json",
    )
    posted = client.post(f"/api/v1/vouchers/{created.data['id']}/post/", {}, format="json")

    assert posted.status_code == 400, posted.data
    assert not JournalLine.objects.filter(account=foreign_bank).exists()
