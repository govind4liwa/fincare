"""Driver tests: advance posting, settlement net payout with advance recovery."""

from datetime import date
from decimal import Decimal

import pytest

from apps.drivers.models import Advance, DriverDocStatus, Settlement, SettlementDeduction
from apps.drivers.services.post import DriverError, post_advance, post_settlement
from apps.ledger.models import EntryStatus

pytestmark = pytest.mark.django_db

D = Decimal
ON = date(2026, 6, 15)
DRIVER_PAYOUT = "101-500-530-003"
DRIVER_COMMISSION = "101-500-530-002"
STAFF_ADVANCES = "101-100-120-003"
SALIK = "101-500-510-001"
FINES = "101-500-510-004"


def _advance(entity, driver, bank, acct, amount="1000"):
    adv = Advance.objects.create(
        entity=entity,
        driver=driver,
        advance_date=date(2026, 6, 1),
        amount=D(amount),
        advance_account=acct(STAFF_ADVANCES),
        bank_account=bank,
    )
    return post_advance(adv)


def test_advance_dr_advance_cr_bank(entity, driver, bank_enbd, acct):
    adv = _advance(entity, driver, bank_enbd, acct)
    adv.refresh_from_db()

    assert adv.status == DriverDocStatus.POSTED
    assert adv.balance == D("1000.00")
    je = adv.journal_entry
    adv_line = je.lines.get(account=acct(STAFF_ADVANCES))
    assert adv_line.debit == D("1000.00")
    assert adv_line.driver_id == driver.id
    assert je.lines.get(account=bank_enbd.gl_account).credit == D("1000.00")


def test_settlement_net_payout_with_deductions(entity, driver, bank_enbd, acct):
    adv = _advance(entity, driver, bank_enbd, acct, amount="1000")

    setl = Settlement.objects.create(
        entity=entity,
        driver=driver,
        period_start=date(2026, 6, 1),
        period_end=date(2026, 6, 30),
        settlement_date=ON,
        gross_amount=D("5000"),
        gross_account=acct(DRIVER_PAYOUT),
        pay_account=bank_enbd,
    )
    SettlementDeduction.objects.create(
        settlement=setl, kind="commission", account=acct(DRIVER_COMMISSION), amount=D("500")
    )
    SettlementDeduction.objects.create(
        settlement=setl, kind="advance", account=acct(STAFF_ADVANCES), amount=D("1000"), advance=adv
    )
    SettlementDeduction.objects.create(
        settlement=setl, kind="salik", account=acct(SALIK), amount=D("100")
    )
    SettlementDeduction.objects.create(
        settlement=setl, kind="fine", account=acct(FINES), amount=D("200")
    )

    post_settlement(setl)
    setl.refresh_from_db()

    # gross 5000 - (500 + 1000 + 100 + 200) = 3200 net
    assert setl.total_deductions == D("1800.00")
    assert setl.net_amount == D("3200.00")
    je = setl.journal_entry
    assert je.status == EntryStatus.POSTED
    assert je.total_debit == je.total_credit == D("5000.00")

    gross_line = je.lines.get(account=acct(DRIVER_PAYOUT))
    assert gross_line.debit == D("5000.00")
    assert gross_line.driver_id == driver.id
    assert je.lines.get(account=acct(DRIVER_COMMISSION)).credit == D("500.00")
    assert je.lines.get(account=acct(STAFF_ADVANCES)).credit == D("1000.00")
    assert je.lines.get(account=bank_enbd.gl_account).credit == D("3200.00")

    # Advance fully recovered by the settlement deduction.
    adv.refresh_from_db()
    assert adv.recovered_amount == D("1000.00")
    assert adv.balance == D("0.00")


def test_settlement_deductions_exceed_gross_rejected(entity, driver, bank_enbd, acct):
    setl = Settlement.objects.create(
        entity=entity,
        driver=driver,
        period_start=date(2026, 6, 1),
        period_end=date(2026, 6, 30),
        settlement_date=ON,
        gross_amount=D("500"),
        gross_account=acct(DRIVER_PAYOUT),
        pay_account=bank_enbd,
    )
    SettlementDeduction.objects.create(
        settlement=setl, kind="advance", account=acct(STAFF_ADVANCES), amount=D("900")
    )
    with pytest.raises(DriverError):
        post_settlement(setl)
