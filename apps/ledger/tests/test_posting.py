"""Posting-engine tests — the accounting core (ADR-0007)."""

import uuid
from datetime import date
from decimal import Decimal

import pytest

from apps.accounts.models import Account
from apps.accounts.services.seed import seed_entity_coa
from apps.core.models import Currency
from apps.ledger.models import AccountingPeriod, EntryStatus, JournalEntry, JournalLine
from apps.ledger.services.posting import PostingError, post_journal_entry, reverse_journal_entry
from apps.tenants.models import BusinessCategory, Entity

pytestmark = pytest.mark.django_db

ENTRY_DATE = date(2026, 6, 15)


@pytest.fixture
def entity():
    aed = Currency.objects.create(code="AED", name="UAE Dirham", symbol="AED", is_base=True)
    cat = BusinessCategory.objects.create(
        key="transport", label="Transport", band="1", coa_template_key="transport"
    )
    ent = Entity.objects.create(
        code="RGT",
        numeric_code="101",
        legal_name="Regency Transport LLC",
        category=cat,
        base_currency=aed,
    )
    seed_entity_coa(ent)
    AccountingPeriod.objects.create(
        entity=ent,
        fiscal_year=2026,
        period_no=6,
        name="Jun-2026",
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 30),
        status=AccountingPeriod.Status.OPEN,
    )
    return ent


def acct(entity, code):
    return Account.objects.get(entity=entity, code=code)


def _entry(entity, source_type="manual"):
    return JournalEntry.objects.create(
        entity=entity,
        entry_date=ENTRY_DATE,
        currency=entity.base_currency,
        source_type=source_type,
        narration="test",
    )


def test_balanced_post_succeeds(entity):
    je = _entry(entity)
    JournalLine.objects.create(
        entry=je, line_no=1, account=acct(entity, "101-100-110-001"), debit=Decimal("100")
    )
    JournalLine.objects.create(
        entry=je, line_no=2, account=acct(entity, "101-400-410-001"), credit=Decimal("100")
    )

    post_journal_entry(je)
    je.refresh_from_db()
    assert je.status == EntryStatus.POSTED
    assert je.entry_no.startswith("JE-")
    assert je.total_debit == je.total_credit == Decimal("100.00")
    assert je.period is not None


def test_unbalanced_raises(entity):
    je = _entry(entity)
    JournalLine.objects.create(
        entry=je, line_no=1, account=acct(entity, "101-100-110-001"), debit=Decimal("100")
    )
    JournalLine.objects.create(
        entry=je, line_no=2, account=acct(entity, "101-400-410-001"), credit=Decimal("90")
    )
    with pytest.raises(PostingError):
        post_journal_entry(je)


def test_one_sided_line_rule(entity):
    je = _entry(entity)
    JournalLine.objects.create(
        entry=je,
        line_no=1,
        account=acct(entity, "101-100-110-001"),
        debit=Decimal("50"),
        credit=Decimal("50"),
    )
    with pytest.raises(PostingError):
        post_journal_entry(je)


def test_closed_period_blocks_posting(entity):
    AccountingPeriod.objects.filter(entity=entity).update(status=AccountingPeriod.Status.CLOSED)
    je = _entry(entity)
    JournalLine.objects.create(
        entry=je, line_no=1, account=acct(entity, "101-100-110-001"), debit=Decimal("100")
    )
    JournalLine.objects.create(
        entry=je, line_no=2, account=acct(entity, "101-400-410-001"), credit=Decimal("100")
    )
    with pytest.raises(PostingError):
        post_journal_entry(je)


def test_no_period_raises(entity):
    je = JournalEntry.objects.create(
        entity=entity,
        entry_date=date(2025, 1, 1),
        currency=entity.base_currency,
        source_type="manual",
    )
    JournalLine.objects.create(
        entry=je, line_no=1, account=acct(entity, "101-100-110-001"), debit=Decimal("100")
    )
    JournalLine.objects.create(
        entry=je, line_no=2, account=acct(entity, "101-400-410-001"), credit=Decimal("100")
    )
    with pytest.raises(PostingError):
        post_journal_entry(je)


def test_manual_posting_to_control_account_blocked(entity):
    je = _entry(entity, source_type="manual")
    JournalLine.objects.create(
        entry=je, line_no=1, account=acct(entity, "101-100-120-001"), debit=Decimal("100")
    )
    JournalLine.objects.create(
        entry=je, line_no=2, account=acct(entity, "101-400-410-001"), credit=Decimal("100")
    )
    with pytest.raises(PostingError):
        post_journal_entry(je)


def test_control_account_requires_party(entity):
    je = _entry(entity, source_type="voucher")  # non-manual bypasses manual block
    JournalLine.objects.create(
        entry=je, line_no=1, account=acct(entity, "101-100-120-001"), debit=Decimal("100")
    )
    JournalLine.objects.create(
        entry=je, line_no=2, account=acct(entity, "101-400-410-001"), credit=Decimal("100")
    )
    with pytest.raises(PostingError):
        post_journal_entry(je)
    # with a party it posts
    je.lines.filter(line_no=1).update(party_type="customer", party_id=uuid.uuid4())
    post_journal_entry(je)
    je.refresh_from_db()
    assert je.status == EntryStatus.POSTED


def test_posted_entry_is_immutable(entity):
    je = _entry(entity)
    JournalLine.objects.create(
        entry=je, line_no=1, account=acct(entity, "101-100-110-001"), debit=Decimal("100")
    )
    JournalLine.objects.create(
        entry=je, line_no=2, account=acct(entity, "101-400-410-001"), credit=Decimal("100")
    )
    post_journal_entry(je)
    je.refresh_from_db()

    je.narration = "tampered"
    with pytest.raises(ValueError):
        je.save()
    with pytest.raises(ValueError):
        je.delete()
    line = je.lines.first()
    line.debit = Decimal("999")
    with pytest.raises(ValueError):
        line.save()


def test_idempotent_repost_rejected(entity):
    je = _entry(entity)
    JournalLine.objects.create(
        entry=je, line_no=1, account=acct(entity, "101-100-110-001"), debit=Decimal("100")
    )
    JournalLine.objects.create(
        entry=je, line_no=2, account=acct(entity, "101-400-410-001"), credit=Decimal("100")
    )
    post_journal_entry(je)
    with pytest.raises(PostingError):
        post_journal_entry(je)


def test_reversal_creates_balanced_mirror(entity):
    je = _entry(entity)
    JournalLine.objects.create(
        entry=je, line_no=1, account=acct(entity, "101-100-110-001"), debit=Decimal("100")
    )
    JournalLine.objects.create(
        entry=je, line_no=2, account=acct(entity, "101-400-410-001"), credit=Decimal("100")
    )
    post_journal_entry(je)

    mirror = reverse_journal_entry(je)
    je.refresh_from_db()
    assert je.status == EntryStatus.REVERSED
    assert je.reversed_by_id == mirror.id
    assert mirror.status == EntryStatus.POSTED
    assert mirror.total_debit == mirror.total_credit == Decimal("100.00")
    # debit/credit are swapped on the mirror
    orig_cash = je.lines.get(line_no=1)
    mirror_cash = mirror.lines.get(line_no=1)
    assert orig_cash.debit == mirror_cash.credit == Decimal("100")


def test_rounding_residual_booked(entity):
    je = _entry(entity)
    JournalLine.objects.create(
        entry=je, line_no=1, account=acct(entity, "101-100-110-001"), debit=Decimal("100.00")
    )
    JournalLine.objects.create(
        entry=je, line_no=2, account=acct(entity, "101-400-410-001"), credit=Decimal("99.99")
    )
    rounding = acct(entity, "101-600-640-099")  # Miscellaneous Expense

    post_journal_entry(je, rounding_account=rounding, tolerance=Decimal("0.05"))
    je.refresh_from_db()
    assert je.status == EntryStatus.POSTED
    assert je.lines.count() == 3
    assert je.total_debit == je.total_credit == Decimal("100.00")
