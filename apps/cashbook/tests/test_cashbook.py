"""Cashbook tests: replenishment contra, cash-count variance (short/over/none)."""

from datetime import date
from decimal import Decimal

import pytest

from apps.cashbook.models import CashCount, CashDocStatus, Denomination, Replenishment
from apps.cashbook.services.post import post_cash_count, post_replenishment
from apps.ledger.models import EntryStatus

pytestmark = pytest.mark.django_db

D = Decimal
ON = date(2026, 6, 15)
PETTY_CASH = "101-100-110-001"
BANK_ENBD = "101-100-110-010"
VARIANCE = "101-600-640-099"


def test_replenishment_dr_cash_cr_bank(entity, bank_enbd, cash_account, petty_float, acct):
    rep = Replenishment.objects.create(
        entity=entity,
        petty_cash_float=petty_float,
        bank_account=bank_enbd,
        replenish_date=ON,
        amount=D("750"),
    )
    post_replenishment(rep)
    rep.refresh_from_db()

    assert rep.status == CashDocStatus.POSTED
    assert rep.replenish_no.startswith("REP-")
    je = rep.journal_entry
    assert je.status == EntryStatus.POSTED
    assert je.lines.get(account=cash_account.gl_account).debit == D("750.00")
    assert je.lines.get(account=bank_enbd.gl_account).credit == D("750.00")
    assert je.total_debit == je.total_credit == D("750.00")


def test_cash_count_shortage_posts_variance(entity, cash_account, acct):
    count = CashCount.objects.create(
        entity=entity,
        cash_account=cash_account,
        count_date=ON,
        expected_amount=D("1000"),
        variance_account=acct(VARIANCE),
    )
    Denomination.objects.create(cash_count=count, denomination_value=D("500"), quantity=1)
    Denomination.objects.create(cash_count=count, denomination_value=D("100"), quantity=4)
    # counted = 500 + 400 = 900 -> shortage 100

    post_cash_count(count)
    count.refresh_from_db()

    assert count.counted_amount == D("900.00")
    assert count.variance == D("-100.00")
    je = count.journal_entry
    assert je.lines.get(account=acct(VARIANCE)).debit == D("100.00")
    assert je.lines.get(account=cash_account.gl_account).credit == D("100.00")


def test_cash_count_overage_posts_variance(entity, cash_account, acct):
    count = CashCount.objects.create(
        entity=entity,
        cash_account=cash_account,
        count_date=ON,
        expected_amount=D("1000"),
        variance_account=acct(VARIANCE),
    )
    Denomination.objects.create(cash_count=count, denomination_value=D("500"), quantity=2)
    Denomination.objects.create(cash_count=count, denomination_value=D("50"), quantity=1)
    # counted = 1000 + 50 = 1050 -> overage 50

    post_cash_count(count)
    count.refresh_from_db()

    assert count.counted_amount == D("1050.00")
    assert count.variance == D("50.00")
    je = count.journal_entry
    assert je.lines.get(account=cash_account.gl_account).debit == D("50.00")
    assert je.lines.get(account=acct(VARIANCE)).credit == D("50.00")


def test_cash_count_no_variance_no_journal(entity, cash_account, acct):
    count = CashCount.objects.create(
        entity=entity,
        cash_account=cash_account,
        count_date=ON,
        expected_amount=D("1000"),
        variance_account=acct(VARIANCE),
    )
    Denomination.objects.create(cash_count=count, denomination_value=D("1000"), quantity=1)

    post_cash_count(count)
    count.refresh_from_db()

    assert count.variance == D("0.00")
    assert count.journal_entry is None
    assert count.status == CashDocStatus.POSTED


def test_cash_count_variance_without_account_rejected(entity, cash_account):
    count = CashCount.objects.create(
        entity=entity, cash_account=cash_account, count_date=ON, expected_amount=D("1000")
    )
    Denomination.objects.create(cash_count=count, denomination_value=D("900"), quantity=1)

    from apps.cashbook.services.post import CashbookError

    with pytest.raises(CashbookError):
        post_cash_count(count)
