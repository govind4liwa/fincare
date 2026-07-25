"""API tests for the reconciliation follow-up: manual match/unmatch, complete, reopen."""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from rest_framework.test import APIClient

import pytest

from apps.banking.models import BankStatement, Reconciliation, StatementLine
from apps.tenants.models import UserEntityMembership

pytestmark = pytest.mark.django_db
User = get_user_model()

D = Decimal
REVENUE = "101-400-410-001"
RECON_DATE = date(2026, 6, 30)


def _superuser():
    client = APIClient()
    client.force_authenticate(
        User.objects.create_superuser(email="root@example.com", password="pw")
    )
    return client


def _setup(
    entity, bank, post_gl, acct, *, gl_date, line_date, deposit=True, amount="3000", closing="3000"
):
    if deposit:
        je = post_gl(
            debit_account=bank.gl_account, credit_account=acct(REVENUE), amount=amount, on=gl_date
        )
        line = {"deposit": D(amount)}
    else:
        je = post_gl(
            debit_account=acct(REVENUE), credit_account=bank.gl_account, amount=amount, on=gl_date
        )
        line = {"withdrawal": D(amount)}
    stmt = BankStatement.objects.create(
        entity=entity, bank_account=bank, statement_date=line_date, closing_balance=D(closing)
    )
    sl = StatementLine.objects.create(statement=stmt, line_no=1, txn_date=line_date, **line)
    recon = Reconciliation.objects.create(
        entity=entity, bank_account=bank, statement=stmt, recon_date=RECON_DATE
    )
    jl = je.lines.get(account=bank.gl_account)
    return stmt, sl, recon, jl


def _match(client, recon, sl, jl):
    return client.post(
        f"/api/v1/reconciliations/{recon.id}/manual-match/",
        {"statement_line": str(sl.id), "journal_line": str(jl.id)},
        format="json",
    )


def test_manual_match_out_of_window(entity, bank_enbd, acct, post_gl):
    _stmt, sl, recon, jl = _setup(
        entity, bank_enbd, post_gl, acct, gl_date=date(2026, 6, 1), line_date=date(2026, 6, 20)
    )
    client = _superuser()
    auto = client.post(
        f"/api/v1/reconciliations/{recon.id}/auto-match/", {"date_window_days": 3}, format="json"
    )
    assert auto.data["totals"]["matched_count"] == 0  # too far apart for auto

    res = _match(client, recon, sl, jl)
    assert res.status_code == 200, res.content
    assert res.data["totals"]["matched_count"] == 1
    assert res.data["matched"][0]["match_type"] == "manual"
    assert res.data["unmatched_lines"] == []


def test_manual_match_wrong_side_rejected(entity, bank_enbd, acct, post_gl):
    # A GL credit line (money out) cannot satisfy a statement deposit.
    _stmt, sl, recon, _jl = _setup(
        entity,
        bank_enbd,
        post_gl,
        acct,
        gl_date=date(2026, 6, 15),
        line_date=date(2026, 6, 15),
        deposit=True,
    )
    # Replace the candidate with a credit line by re-posting the opposite way.
    credit_je = post_gl(
        debit_account=acct(REVENUE),
        credit_account=bank_enbd.gl_account,
        amount="3000",
        on=date(2026, 6, 15),
    )
    credit_jl = credit_je.lines.get(account=bank_enbd.gl_account)
    res = _match(_superuser(), recon, sl, credit_jl)
    assert res.status_code == 400


def test_manual_match_amount_mismatch_rejected(entity, bank_enbd, acct, post_gl):
    je = post_gl(
        debit_account=bank_enbd.gl_account,
        credit_account=acct(REVENUE),
        amount="2000",
        on=date(2026, 6, 15),
    )
    stmt = BankStatement.objects.create(
        entity=entity,
        bank_account=bank_enbd,
        statement_date=date(2026, 6, 15),
        closing_balance=D("3000"),
    )
    sl = StatementLine.objects.create(
        statement=stmt, line_no=1, txn_date=date(2026, 6, 15), deposit=D("3000")
    )
    recon = Reconciliation.objects.create(
        entity=entity, bank_account=bank_enbd, statement=stmt, recon_date=RECON_DATE
    )
    jl = je.lines.get(account=bank_enbd.gl_account)  # debit 2000, line deposit 3000
    res = _match(_superuser(), recon, sl, jl)
    assert res.status_code == 400


def test_unmatch_frees_line(entity, bank_enbd, acct, post_gl):
    _stmt, sl, recon, jl = _setup(
        entity, bank_enbd, post_gl, acct, gl_date=date(2026, 6, 1), line_date=date(2026, 6, 20)
    )
    client = _superuser()
    matched = _match(client, recon, sl, jl)
    item_id = matched.data["matched"][0]["id"]

    res = client.post(
        f"/api/v1/reconciliations/{recon.id}/unmatch/", {"item": item_id}, format="json"
    )
    assert res.status_code == 200, res.content
    assert res.data["totals"]["matched_count"] == 0
    assert res.data["totals"]["unmatched_count"] == 1


def test_complete_requires_full_match_and_zero_difference(entity, bank_enbd, acct, post_gl):
    stmt, _sl, recon, _jl = _setup(
        entity, bank_enbd, post_gl, acct, gl_date=date(2026, 6, 15), line_date=date(2026, 6, 15)
    )
    client = _superuser()
    # Unmatched line → cannot complete.
    early = client.post(f"/api/v1/reconciliations/{recon.id}/complete/", {}, format="json")
    assert early.status_code == 400

    client.post(f"/api/v1/reconciliations/{recon.id}/auto-match/", {}, format="json")
    res = client.post(f"/api/v1/reconciliations/{recon.id}/complete/", {}, format="json")
    assert res.status_code == 200, res.content
    assert res.data["reconciliation"]["status"] == Reconciliation.Status.COMPLETED
    stmt.refresh_from_db()
    assert stmt.status == BankStatement.Status.RECONCILED


def test_completed_is_locked(entity, bank_enbd, acct, post_gl):
    _stmt, _sl, recon, _jl = _setup(
        entity, bank_enbd, post_gl, acct, gl_date=date(2026, 6, 15), line_date=date(2026, 6, 15)
    )
    client = _superuser()
    client.post(f"/api/v1/reconciliations/{recon.id}/auto-match/", {}, format="json")
    client.post(f"/api/v1/reconciliations/{recon.id}/complete/", {}, format="json")
    # Locked: further auto-match is rejected.
    locked = client.post(f"/api/v1/reconciliations/{recon.id}/auto-match/", {}, format="json")
    assert locked.status_code == 400


def test_reopen_requires_manager(entity, bank_enbd, acct, post_gl):
    _stmt, _sl, recon, _jl = _setup(
        entity, bank_enbd, post_gl, acct, gl_date=date(2026, 6, 15), line_date=date(2026, 6, 15)
    )
    su = _superuser()
    su.post(f"/api/v1/reconciliations/{recon.id}/auto-match/", {}, format="json")
    su.post(f"/api/v1/reconciliations/{recon.id}/complete/", {}, format="json")

    # An accountant (member) may act in the workspace but cannot reopen.
    accountant = User.objects.create_user(email="acc@example.com", password="pw")
    accountant.groups.add(Group.objects.create(name="accountant"))
    UserEntityMembership.objects.create(user=accountant, entity=entity)
    acc_client = APIClient()
    acc_client.force_authenticate(accountant)
    denied = acc_client.post(f"/api/v1/reconciliations/{recon.id}/reopen/", {}, format="json")
    assert denied.status_code == 403

    # Superuser can reopen.
    res = su.post(f"/api/v1/reconciliations/{recon.id}/reopen/", {}, format="json")
    assert res.status_code == 200
    assert res.data["reconciliation"]["status"] == Reconciliation.Status.IN_PROGRESS
