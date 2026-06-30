"""Platform settlement reconciliation + posting tests."""

from datetime import date
from decimal import Decimal

import pytest

from apps.platforms.models import EarningImport, PlatformDocStatus, PlatformSettlement
from apps.platforms.services.post import PlatformError, post_settlement, reconcile
from apps.platforms.tests.conftest import MISC_EXPENSE, PLATFORM_CLEARING

pytestmark = pytest.mark.django_db


def _settlement(entity, platform, **kw):
    defaults = dict(
        entity=entity,
        platform=platform,
        period_start=date(2026, 6, 1),
        period_end=date(2026, 6, 7),
        settlement_date=date(2026, 6, 8),
        gross_earnings=Decimal("1000.00"),
        commission=Decimal("200.00"),
        net_received=Decimal("800.00"),
    )
    defaults.update(kw)
    return PlatformSettlement.objects.create(**defaults)


def test_settlement_clears_receivable_zero_variance(entity, platform, bank_enbd, acct):
    setl = _settlement(entity, platform, bank_account=bank_enbd)
    post_settlement(setl)

    setl.refresh_from_db()
    assert setl.status == PlatformDocStatus.POSTED
    assert setl.settlement_no.startswith("PSL-")
    je = setl.journal_entry
    assert je.total_debit == je.total_credit == Decimal("800.00")
    # Two lines only (no adjustment): DR bank 800 / CR clearing 800.
    lines = {ln.account.code: (ln.debit, ln.credit) for ln in je.lines.all()}
    assert lines[bank_enbd.gl_account.code] == (Decimal("800.00"), Decimal("0.00"))
    assert lines[PLATFORM_CLEARING] == (Decimal("0.00"), Decimal("800.00"))
    assert all(ln.platform_id == platform.id for ln in je.lines.all())


def test_settlement_shortfall_books_adjustment(entity, platform, bank_enbd, acct):
    # Platform withheld 20 (clearing 800 vs received 780) -> DR adjustment 20.
    setl = _settlement(
        entity,
        platform,
        net_received=Decimal("780.00"),
        bank_account=bank_enbd,
        adjustment_account=acct(MISC_EXPENSE),
    )
    post_settlement(setl)

    setl.refresh_from_db()
    je = setl.journal_entry
    assert je.total_debit == je.total_credit == Decimal("800.00")
    lines = {ln.account.code: (ln.debit, ln.credit) for ln in je.lines.all()}
    assert lines[bank_enbd.gl_account.code] == (Decimal("780.00"), Decimal("0.00"))
    assert lines[PLATFORM_CLEARING] == (Decimal("0.00"), Decimal("800.00"))
    assert lines[MISC_EXPENSE] == (Decimal("20.00"), Decimal("0.00"))
    assert setl.variance == Decimal("-20.00")  # net_received − clearing − adjustments


def test_nonzero_variance_requires_adjustment_account(entity, platform, bank_enbd):
    setl = _settlement(entity, platform, net_received=Decimal("780.00"), bank_account=bank_enbd)
    with pytest.raises(PlatformError):
        post_settlement(setl)


def test_reconcile_aggregates_imports(entity, platform):
    for ref, gross, comm, net in [
        ("T1", "600.00", "120.00", "480.00"),
        ("T2", "400.00", "80.00", "320.00"),
    ]:
        EarningImport.objects.create(
            entity=entity,
            platform=platform,
            trip_ref=ref,
            earning_date=date(2026, 6, 3),
            gross=Decimal(gross),
            commission=Decimal(comm),
            net=Decimal(net),
        )
    setl = _settlement(
        entity,
        platform,
        gross_earnings=Decimal("0"),
        commission=Decimal("0"),
        net_received=Decimal("800.00"),
    )
    reconcile(setl)

    setl.refresh_from_db()
    assert setl.status == PlatformDocStatus.RECONCILED
    assert setl.gross_earnings == Decimal("1000.00")
    assert setl.commission == Decimal("200.00")
    assert setl.variance == Decimal("0.00")  # statement net 800 == received 800
    assert EarningImport.objects.filter(settlement=setl, matched=True).count() == 2
