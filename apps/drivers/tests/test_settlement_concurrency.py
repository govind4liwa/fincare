"""Concurrency safety for advance recovery.

Two settlements recovering the same advance must not jointly over-recover it.
``post_settlement`` re-reads referenced advances ``FOR UPDATE`` inside its
transaction, so the second post blocks until the first commits and then sees the
reduced balance.

These use ``transaction=True`` (TransactionTestCase semantics) because real
commits and independent connections are the whole point — the data must be
visible to other threads, and row locks only mean something across real
transactions.
"""

import threading
from datetime import date
from decimal import Decimal

from django.db import connection, connections, transaction
from django.test.utils import CaptureQueriesContext

import pytest

from apps.accounts.models import Account
from apps.accounts.services.seed import seed_entity_coa
from apps.banking.models import BankAccount
from apps.core.models import Currency
from apps.drivers.models import Advance, Driver, DriverDocStatus, Settlement, SettlementDeduction
from apps.drivers.services.post import DriverError, post_advance, post_settlement
from apps.ledger.models import AccountingPeriod, JournalEntry
from apps.tenants.models import BusinessCategory, Entity

D = Decimal
ON = date(2026, 6, 15)
BANK_ENBD = "101-100-110-010"
DRIVER_PAYOUT = "101-500-530-003"
STAFF_ADVANCES = "101-100-120-003"


def _world():
    """Build a committed tenant: transactional tests start from an empty DB."""
    aed, _ = Currency.objects.get_or_create(
        code="AED", defaults={"name": "UAE Dirham", "symbol": "AED", "is_base": True}
    )
    cat, _ = BusinessCategory.objects.get_or_create(
        key="transport",
        defaults={"label": "Transport", "band": "1", "coa_template_key": "transport"},
    )
    entity, created = Entity.objects.get_or_create(
        numeric_code="101",
        defaults={
            "code": "RGT",
            "legal_name": "Regency Transport LLC",
            "category": cat,
            "base_currency": aed,
        },
    )
    if created:
        seed_entity_coa(entity)
    AccountingPeriod.objects.get_or_create(
        entity=entity,
        fiscal_year=2026,
        period_no=6,
        defaults={
            "name": "Jun-2026",
            "start_date": date(2026, 6, 1),
            "end_date": date(2026, 6, 30),
            "status": AccountingPeriod.Status.OPEN,
        },
    )
    acct = lambda code: Account.objects.get(entity=entity, code=code)  # noqa: E731
    bank, _ = BankAccount.objects.get_or_create(
        entity=entity,
        code="ENBD",
        defaults={"name": "ENBD Current", "gl_account": acct(BANK_ENBD), "currency": aed},
    )
    driver, _ = Driver.objects.get_or_create(
        entity=entity, code="D001", defaults={"name": "Imran Khan"}
    )
    return entity, driver, bank, acct


def _posted_advance(entity, driver, bank, acct, amount="1000"):
    advance = Advance.objects.create(
        entity=entity,
        driver=driver,
        advance_date=ON,
        amount=D(amount),
        advance_account=acct(STAFF_ADVANCES),
        bank_account=bank,
    )
    return post_advance(advance)


def _settlement(entity, driver, bank, acct, advance, *, recover, gross="9000"):
    settlement = Settlement.objects.create(
        entity=entity,
        driver=driver,
        period_start=date(2026, 6, 1),
        period_end=date(2026, 6, 30),
        settlement_date=ON,
        gross_amount=D(gross),
        gross_account=acct(DRIVER_PAYOUT),
        pay_account=bank,
    )
    SettlementDeduction.objects.create(
        settlement=settlement,
        kind="advance",
        account=acct(STAFF_ADVANCES),
        amount=D(recover),
        advance=advance,
    )
    return settlement


def _cleanup():
    for conn in connections.all():
        conn.close()


@pytest.mark.django_db(transaction=True)
def test_sequential_recoveries_see_the_reduced_balance():
    """A second recovery is measured against what the first left behind."""
    entity, driver, bank, acct = _world()
    advance = _posted_advance(entity, driver, bank, acct, amount="1000")

    first = _settlement(entity, driver, bank, acct, advance, recover="600")
    post_settlement(first)
    advance.refresh_from_db()
    assert advance.balance == D("400.00")

    # 400 left: this one fits.
    second = _settlement(entity, driver, bank, acct, advance, recover="400")
    post_settlement(second)
    advance.refresh_from_db()
    assert advance.recovered_amount == D("1000.00")
    assert advance.balance == D("0.00")

    # Nothing remains, so a third is rejected.
    third = _settlement(entity, driver, bank, acct, advance, recover="1")
    with pytest.raises(DriverError):
        post_settlement(third)
    third.refresh_from_db()
    assert third.status == DriverDocStatus.DRAFT


@pytest.mark.django_db(transaction=True)
def test_concurrent_posts_only_one_consumes_the_balance():
    """Two threads race to recover 700 each from a 1,000 advance — one must lose.

    Without ``select_for_update`` both would read balance=1000, both would pass
    validation, and the advance would end up over-recovered at 1,400.
    """
    entity, driver, bank, acct = _world()
    advance = _posted_advance(entity, driver, bank, acct, amount="1000")
    a = _settlement(entity, driver, bank, acct, advance, recover="700")
    b = _settlement(entity, driver, bank, acct, advance, recover="700")

    results: dict = {}
    start = threading.Barrier(2, timeout=30)

    def attempt(key, settlement_id):
        try:
            start.wait()
            with transaction.atomic():
                post_settlement(Settlement.objects.get(id=settlement_id))
            results[key] = "posted"
        except DriverError:
            results[key] = "rejected"
        except Exception as exc:  # pragma: no cover - surfaced in the assertion
            results[key] = f"error: {exc!r}"
        finally:
            connection.close()

    threads = [
        threading.Thread(target=attempt, args=("a", a.id)),
        threading.Thread(target=attempt, args=("b", b.id)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)

    try:
        outcomes = sorted(results.values())
        assert outcomes == ["posted", "rejected"], results

        advance.refresh_from_db()
        assert advance.recovered_amount == D("700.00")
        assert advance.balance == D("300.00")  # never driven negative

        # The loser wrote nothing at all: still draft, no journal entry.
        posted = [s for s in (a, b) if Settlement.objects.get(id=s.id).status == "posted"]
        loser = next(s for s in (a, b) if s.id not in {p.id for p in posted})
        loser.refresh_from_db()
        assert loser.status == DriverDocStatus.DRAFT
        assert loser.journal_entry_id is None
        assert loser.settlement_no == ""
        assert loser.total_deductions == D("0.00")
        assert not JournalEntry.objects.filter(source_id=loser.id).exists()
    finally:
        _cleanup()


@pytest.mark.django_db(transaction=True)
def test_multiple_advances_are_locked_in_primary_key_order():
    """Deterministic lock order across advances keeps concurrent posts deadlock-free."""
    entity, driver, bank, acct = _world()
    first = _posted_advance(entity, driver, bank, acct, amount="500")
    second = _posted_advance(entity, driver, bank, acct, amount="500")
    ordered = sorted([first.id, second.id])

    settlement = Settlement.objects.create(
        entity=entity,
        driver=driver,
        period_start=date(2026, 6, 1),
        period_end=date(2026, 6, 30),
        settlement_date=ON,
        gross_amount=D("9000"),
        gross_account=acct(DRIVER_PAYOUT),
        pay_account=bank,
    )
    # Deliberately add the lines in the reverse of PK order: the service must
    # still acquire the locks ascending by primary key.
    for advance_id in reversed(ordered):
        SettlementDeduction.objects.create(
            settlement=settlement,
            kind="advance",
            account=acct(STAFF_ADVANCES),
            amount=D("100"),
            advance=Advance.objects.get(id=advance_id),
        )

    with CaptureQueriesContext(connection) as captured:
        post_settlement(settlement)

    locking = [q["sql"] for q in captured.captured_queries if "FOR UPDATE" in q["sql"].upper()]
    assert locking, "advances should be re-read FOR UPDATE"
    # The lock query must be ordered by primary key, so concurrent posts touching
    # the same advances always take them in the same sequence.
    assert any(
        "ORDER BY" in sql.upper() and "ID" in sql.upper() for sql in locking
    ), f"expected a deterministic ORDER BY id on the locking read, got: {locking}"

    for advance_id in ordered:
        adv = Advance.objects.get(id=advance_id)
        assert adv.recovered_amount == D("100.00")
        assert adv.balance == D("400.00")
    _cleanup()
