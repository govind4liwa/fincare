"""API tests for cashbook: cash accounts, petty-cash floats, replenishments,
and cash counts."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from rest_framework.test import APIClient

import pytest

from apps.cashbook.models import CashDocStatus
from apps.cashbook.tests.conftest import BANK_ENBD, PETTY_CASH, VARIANCE
from apps.tenants.models import UserEntityMembership

pytestmark = pytest.mark.django_db
User = get_user_model()


def _client(entity, role=None):
    user = User.objects.create_user(email=f"{role or 'member'}@example.com", password="pw")
    UserEntityMembership.objects.create(user=user, entity=entity)
    if role:
        user.groups.add(Group.objects.get_or_create(name=role)[0])
    client = APIClient()
    client.force_authenticate(user)
    return client


def test_member_without_role_can_read_but_not_write_cash_account(entity, cash_account):
    client = _client(entity, role=None)
    read = client.get("/api/v1/cash-accounts/")
    assert read.status_code == 200
    assert {a["code"] for a in read.data["results"]} == {"TILL1"}

    res = client.post(
        "/api/v1/cash-accounts/",
        {
            "entity": str(entity.id),
            "code": "TILL2",
            "name": "X",
            "gl_account": str(cash_account.gl_account_id),
        },
        format="json",
    )
    assert res.status_code == 403


def test_create_petty_cash_float(entity, cash_account):
    client = _client(entity, "accountant")
    res = client.post(
        "/api/v1/petty-cash-floats/",
        {
            "entity": str(entity.id),
            "cash_account": str(cash_account.id),
            "code": "PCF2",
            "float_amount": "500.00",
            "custodian": "Driver B",
        },
        format="json",
    )
    assert res.status_code == 201, res.content
    assert res.data["cash_account_code"] == "TILL1"


def test_create_and_post_replenishment(entity, bank_enbd, cash_account, petty_float, acct):
    client = _client(entity, "accountant")
    res = client.post(
        "/api/v1/replenishments/",
        {
            "entity": str(entity.id),
            "petty_cash_float": str(petty_float.id),
            "bank_account": str(bank_enbd.id),
            "replenish_date": "2026-06-15",
            "amount": "750.00",
        },
        format="json",
    )
    assert res.status_code == 201, res.content
    rep_id = res.data["id"]
    assert res.data["status"] == CashDocStatus.DRAFT

    res = client.post(f"/api/v1/replenishments/{rep_id}/post/")
    assert res.status_code == 200, res.content
    assert res.data["status"] == CashDocStatus.POSTED
    assert res.data["replenish_no"].startswith("REP-")

    je_id = res.data["journal_entry"]
    assert je_id is not None
    from apps.ledger.models import JournalEntry

    je = JournalEntry.objects.get(id=je_id)
    assert je.total_debit == je.total_credit == Decimal("750.00")
    lines = {ln.account.code: (ln.debit, ln.credit) for ln in je.lines.all()}
    assert lines[PETTY_CASH] == (Decimal("750.00"), Decimal("0.00"))
    assert lines[BANK_ENBD] == (Decimal("0.00"), Decimal("750.00"))


def test_replenishment_cannot_be_posted_twice(entity, bank_enbd, petty_float):
    client = _client(entity, "accountant")
    res = client.post(
        "/api/v1/replenishments/",
        {
            "entity": str(entity.id),
            "petty_cash_float": str(petty_float.id),
            "bank_account": str(bank_enbd.id),
            "replenish_date": "2026-06-15",
            "amount": "400.00",
        },
        format="json",
    )
    rep_id = res.data["id"]
    first = client.post(f"/api/v1/replenishments/{rep_id}/post/")
    assert first.status_code == 200, first.content
    second = client.post(f"/api/v1/replenishments/{rep_id}/post/")
    assert second.status_code == 400


def test_create_and_post_cash_count_with_shortage(entity, cash_account, acct):
    client = _client(entity, "accountant")
    res = client.post(
        "/api/v1/cash-counts/",
        {
            "entity": str(entity.id),
            "cash_account": str(cash_account.id),
            "count_date": "2026-06-15",
            "expected_amount": "1000.00",
            "variance_account": str(acct(VARIANCE).id),
            "denominations": [
                {"denomination_value": "500.00", "quantity": 1},
                {"denomination_value": "100.00", "quantity": 4},
            ],
        },
        format="json",
    )
    assert res.status_code == 201, res.content
    count_id = res.data["id"]
    assert len(res.data["denominations"]) == 2

    res = client.post(f"/api/v1/cash-counts/{count_id}/post/")
    assert res.status_code == 200, res.content
    assert res.data["counted_amount"] == "900.00"
    assert res.data["variance"] == "-100.00"
    assert res.data["status"] == CashDocStatus.POSTED

    je_id = res.data["journal_entry"]
    from apps.ledger.models import JournalEntry

    je = JournalEntry.objects.get(id=je_id)
    lines = {ln.account.code: (ln.debit, ln.credit) for ln in je.lines.all()}
    assert lines[VARIANCE] == (Decimal("100.00"), Decimal("0.00"))
    assert lines[PETTY_CASH] == (Decimal("0.00"), Decimal("100.00"))


def test_cash_count_with_no_variance_posts_without_journal_entry(entity, cash_account):
    client = _client(entity, "accountant")
    res = client.post(
        "/api/v1/cash-counts/",
        {
            "entity": str(entity.id),
            "cash_account": str(cash_account.id),
            "count_date": "2026-06-15",
            "expected_amount": "1000.00",
            "denominations": [{"denomination_value": "1000.00", "quantity": 1}],
        },
        format="json",
    )
    count_id = res.data["id"]

    res = client.post(f"/api/v1/cash-counts/{count_id}/post/")
    assert res.status_code == 200, res.content
    assert res.data["variance"] == "0.00"
    assert res.data["journal_entry"] is None


def test_cash_count_variance_without_account_rejected(entity, cash_account):
    client = _client(entity, "accountant")
    res = client.post(
        "/api/v1/cash-counts/",
        {
            "entity": str(entity.id),
            "cash_account": str(cash_account.id),
            "count_date": "2026-06-15",
            "expected_amount": "1000.00",
            "denominations": [{"denomination_value": "900.00", "quantity": 1}],
        },
        format="json",
    )
    count_id = res.data["id"]

    res = client.post(f"/api/v1/cash-counts/{count_id}/post/")
    assert res.status_code == 400


def test_cashbook_write_requires_role(entity, cash_account, petty_float):
    client = _client(entity, role=None)
    res = client.post(
        "/api/v1/replenishments/",
        {
            "entity": str(entity.id),
            "petty_cash_float": str(petty_float.id),
            "replenish_date": "2026-06-15",
            "amount": "100.00",
        },
        format="json",
    )
    assert res.status_code == 403
