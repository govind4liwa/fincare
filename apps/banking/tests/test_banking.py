"""Banking tests: transfer (contra + charges), POS settlement, reconciliation match."""

from datetime import date
from decimal import Decimal

import pytest

from apps.banking.models import (
    BankDocStatus,
    BankStatement,
    BankTransfer,
    PosSettlement,
    Reconciliation,
    StatementLine,
)
from apps.banking.services.post import BankingError, post_pos_settlement, post_transfer
from apps.banking.services.reconcile import auto_match
from apps.ledger.models import EntryStatus

pytestmark = pytest.mark.django_db

D = Decimal
TXN_DATE = date(2026, 6, 15)
POS_CLEARING = "101-100-110-020"
BANK_CHARGES = "101-600-640-004"
BANK_ENBD = "101-100-110-010"
REVENUE = "101-400-410-001"


def test_transfer_contra_with_charges(entity, bank_enbd, bank_adcb, acct):
    trf = BankTransfer.objects.create(
        entity=entity,
        transfer_date=TXN_DATE,
        from_account=bank_enbd,
        to_account=bank_adcb,
        amount=D("10000"),
        charges=D("25"),
        charge_account=acct(BANK_CHARGES),
    )
    post_transfer(trf)
    trf.refresh_from_db()

    assert trf.status == BankDocStatus.POSTED
    assert trf.transfer_no.startswith("TRF-")
    je = trf.journal_entry
    assert je.status == EntryStatus.POSTED
    assert je.total_debit == je.total_credit == D("10025.00")
    assert je.lines.get(account=bank_adcb.gl_account).debit == D("10000.00")
    assert je.lines.get(account=acct(BANK_CHARGES)).debit == D("25.00")
    assert je.lines.get(account=bank_enbd.gl_account).credit == D("10025.00")


def test_transfer_same_account_rejected(entity, bank_enbd):
    trf = BankTransfer.objects.create(
        entity=entity,
        transfer_date=TXN_DATE,
        from_account=bank_enbd,
        to_account=bank_enbd,
        amount=D("100"),
    )
    with pytest.raises(BankingError):
        post_transfer(trf)


def test_pos_settlement_dr_bank_fee_cr_clearing(entity, bank_enbd, acct):
    stl = PosSettlement.objects.create(
        entity=entity,
        settlement_date=TXN_DATE,
        bank_account=bank_enbd,
        gross_amount=D("5000"),
        fee_amount=D("125"),
        fee_account=acct(BANK_CHARGES),
        pos_clearing_account=acct(POS_CLEARING),
    )
    post_pos_settlement(stl)
    stl.refresh_from_db()

    assert stl.net_amount == D("4875.00")
    je = stl.journal_entry
    assert je.lines.get(account=bank_enbd.gl_account).debit == D("4875.00")
    assert je.lines.get(account=acct(BANK_CHARGES)).debit == D("125.00")
    assert je.lines.get(account=acct(POS_CLEARING)).credit == D("5000.00")
    assert je.total_debit == je.total_credit == D("5000.00")


def test_reconciliation_auto_match(entity, bank_enbd, acct, post_gl):
    # A deposit hits the bank GL (DR bank / CR revenue).
    post_gl(
        debit_account=bank_enbd.gl_account,
        credit_account=acct(REVENUE),
        amount="3000",
        on=TXN_DATE,
        description="Customer deposit REF777",
    )
    stmt = BankStatement.objects.create(
        entity=entity,
        bank_account=bank_enbd,
        statement_date=TXN_DATE,
        closing_balance=D("3000"),
    )
    StatementLine.objects.create(
        statement=stmt, line_no=1, txn_date=TXN_DATE, deposit=D("3000"), reference="REF777"
    )
    recon = Reconciliation.objects.create(
        entity=entity, bank_account=bank_enbd, statement=stmt, recon_date=date(2026, 6, 30)
    )

    matched = auto_match(recon)
    recon.refresh_from_db()

    assert matched == 1
    assert recon.status == Reconciliation.Status.COMPLETED
    assert recon.gl_balance == D("3000.00")
    assert recon.difference == D("0.00")
    assert stmt.lines.get(line_no=1).is_matched is True


def test_reconciliation_no_match_out_of_window(entity, bank_enbd, acct, post_gl):
    post_gl(
        debit_account=bank_enbd.gl_account,
        credit_account=acct(REVENUE),
        amount="3000",
        on=date(2026, 6, 1),
    )
    stmt = BankStatement.objects.create(
        entity=entity, bank_account=bank_enbd, statement_date=TXN_DATE, closing_balance=D("3000")
    )
    StatementLine.objects.create(
        statement=stmt, line_no=1, txn_date=date(2026, 6, 20), deposit=D("3000")
    )
    recon = Reconciliation.objects.create(
        entity=entity, bank_account=bank_enbd, statement=stmt, recon_date=date(2026, 6, 30)
    )

    matched = auto_match(recon, date_window_days=3)
    assert matched == 0
    recon.refresh_from_db()
    assert recon.status == Reconciliation.Status.IN_PROGRESS
