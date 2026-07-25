"""API tests for the banking slice: bank accounts, statements, auto-match reconciliation."""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from rest_framework.test import APIClient

import pytest

from apps.banking.models import Reconciliation
from apps.tenants.models import UserEntityMembership

pytestmark = pytest.mark.django_db
User = get_user_model()

D = Decimal
TXN_DATE = date(2026, 6, 15)
RECON_DATE = date(2026, 6, 30)
REVENUE = "101-400-410-001"


def _superuser():
    client = APIClient()
    client.force_authenticate(
        User.objects.create_superuser(email="root@example.com", password="pw")
    )
    return client


# --- bank account master: creation, GL validation, isolation, permissions ---


def test_create_bank_account(entity, acct):
    payload = {
        "entity": str(entity.id),
        "code": "ENBD2",
        "name": "ENBD Savings",
        "gl_account": str(acct("101-100-110-011").id),  # a bank-type GL account
    }
    res = _superuser().post("/api/v1/bank-accounts/", payload, format="json")
    assert res.status_code == 201, res.content
    assert res.data["gl_account_code"] == "101-100-110-011"


def test_bank_account_rejects_non_bank_gl(entity, acct):
    payload = {
        "entity": str(entity.id),
        "code": "BADGL",
        "name": "Wrong",
        "gl_account": str(acct(REVENUE).id),  # revenue account, not a bank account
    }
    res = _superuser().post("/api/v1/bank-accounts/", payload, format="json")
    assert res.status_code == 400
    assert "gl_account" in res.data


def test_bank_accounts_entity_scoped(entity, bank_enbd):
    # A user with the role but no membership sees no bank accounts (tenant isolation).
    user = User.objects.create_user(email="outsider@example.com", password="pw")
    user.groups.add(Group.objects.create(name="accountant"))
    client = APIClient()
    client.force_authenticate(user)
    res = client.get("/api/v1/bank-accounts/")
    assert res.status_code == 200
    assert res.data["results"] == []


def test_unauthenticated_rejected(bank_enbd):
    res = APIClient().get("/api/v1/bank-accounts/")
    assert res.status_code == 401


def test_member_without_role_can_read_but_not_write(entity, bank_enbd, acct):
    user = User.objects.create_user(email="viewer@example.com", password="pw")
    UserEntityMembership.objects.create(user=user, entity=entity)
    client = APIClient()
    client.force_authenticate(user)
    read = client.get("/api/v1/bank-accounts/")
    assert read.status_code == 200
    res = client.post(
        "/api/v1/bank-accounts/",
        {
            "entity": str(entity.id),
            "code": "X",
            "name": "X",
            "gl_account": str(bank_enbd.gl_account_id),
        },
        format="json",
    )
    assert res.status_code == 403


# --- statement entry + auto-match reconciliation ---


def _statement(client, entity, bank, *, lines, closing="3000"):
    payload = {
        "entity": str(entity.id),
        "bank_account": str(bank.id),
        "statement_date": TXN_DATE.isoformat(),
        "closing_balance": closing,
        "lines": lines,
    }
    res = client.post("/api/v1/bank-statements/", payload, format="json")
    assert res.status_code == 201, res.content
    return res.data["id"]


def _reconciliation(client, entity, bank, statement_id):
    res = client.post(
        "/api/v1/reconciliations/",
        {
            "entity": str(entity.id),
            "bank_account": str(bank.id),
            "statement": statement_id,
            "recon_date": RECON_DATE.isoformat(),
        },
        format="json",
    )
    assert res.status_code == 201, res.content
    return res.data["id"]


def test_deposit_matches_debit_and_stays_in_progress(entity, bank_enbd, acct, post_gl):
    # A deposit hits the bank GL (DR bank / CR revenue).
    post_gl(
        debit_account=bank_enbd.gl_account, credit_account=acct(REVENUE), amount="3000", on=TXN_DATE
    )
    client = _superuser()
    stmt = _statement(
        client,
        entity,
        bank_enbd,
        lines=[{"txn_date": TXN_DATE.isoformat(), "deposit": "3000", "reference": "REF1"}],
    )
    recon_id = _reconciliation(client, entity, bank_enbd, stmt)

    res = client.post(f"/api/v1/reconciliations/{recon_id}/auto-match/", {}, format="json")
    assert res.status_code == 200, res.content
    assert res.data["totals"]["matched_count"] == 1
    assert res.data["totals"]["gl_balance"] == "3000.00"
    assert res.data["totals"]["difference"] == "0.00"
    assert res.data["unmatched_lines"] == []
    assert res.data["gl_lines"][0]["is_matched"] is True
    # Boundary for this slice: never auto-complete.
    assert Reconciliation.objects.get(id=recon_id).status == Reconciliation.Status.IN_PROGRESS


def test_withdrawal_matches_credit(entity, bank_enbd, acct, post_gl):
    # Money out: CR bank / DR expense → a credit on the bank GL.
    post_gl(
        debit_account=acct(REVENUE), credit_account=bank_enbd.gl_account, amount="500", on=TXN_DATE
    )
    client = _superuser()
    stmt = _statement(
        client,
        entity,
        bank_enbd,
        lines=[{"txn_date": TXN_DATE.isoformat(), "withdrawal": "500"}],
        closing="-500",
    )
    recon_id = _reconciliation(client, entity, bank_enbd, stmt)
    res = client.post(f"/api/v1/reconciliations/{recon_id}/auto-match/", {}, format="json")
    assert res.data["totals"]["matched_count"] == 1
    assert res.data["totals"]["gl_balance"] == "-500.00"


def test_out_of_window_unmatched_leaves_difference(entity, bank_enbd, acct, post_gl):
    post_gl(
        debit_account=bank_enbd.gl_account,
        credit_account=acct(REVENUE),
        amount="3000",
        on=date(2026, 6, 1),
    )
    client = _superuser()
    stmt = _statement(
        client,
        entity,
        bank_enbd,
        lines=[{"txn_date": date(2026, 6, 20).isoformat(), "deposit": "3000"}],
    )
    recon_id = _reconciliation(client, entity, bank_enbd, stmt)
    res = client.post(
        f"/api/v1/reconciliations/{recon_id}/auto-match/", {"date_window_days": 3}, format="json"
    )
    assert res.data["totals"]["matched_count"] == 0
    assert res.data["totals"]["unmatched_count"] == 1
    # statement closing 3000 vs GL 3000 → difference 0, but the line is still unmatched.
    assert res.data["totals"]["difference"] == "0.00"


def test_amount_tolerance(entity, bank_enbd, acct, post_gl):
    post_gl(
        debit_account=bank_enbd.gl_account, credit_account=acct(REVENUE), amount="3000", on=TXN_DATE
    )
    client = _superuser()
    stmt = _statement(
        client,
        entity,
        bank_enbd,
        lines=[{"txn_date": TXN_DATE.isoformat(), "deposit": "3002"}],
    )
    recon_id = _reconciliation(client, entity, bank_enbd, stmt)
    # No tolerance → no match.
    res = client.post(f"/api/v1/reconciliations/{recon_id}/auto-match/", {}, format="json")
    assert res.data["totals"]["matched_count"] == 0
    # Tolerance 5 → matches.
    res = client.post(
        f"/api/v1/reconciliations/{recon_id}/auto-match/", {"amount_tolerance": "5"}, format="json"
    )
    assert res.data["totals"]["matched_count"] == 1


def test_auto_match_idempotent(entity, bank_enbd, acct, post_gl):
    post_gl(
        debit_account=bank_enbd.gl_account, credit_account=acct(REVENUE), amount="3000", on=TXN_DATE
    )
    client = _superuser()
    stmt = _statement(
        client, entity, bank_enbd, lines=[{"txn_date": TXN_DATE.isoformat(), "deposit": "3000"}]
    )
    recon_id = _reconciliation(client, entity, bank_enbd, stmt)
    first = client.post(f"/api/v1/reconciliations/{recon_id}/auto-match/", {}, format="json")
    assert first.data["totals"]["matched_count"] == 1
    # Re-running does not double-match.
    second = client.post(f"/api/v1/reconciliations/{recon_id}/auto-match/", {}, format="json")
    assert second.data["totals"]["matched_count"] == 1
