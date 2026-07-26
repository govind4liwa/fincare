"""Concurrency safety for driver receivable clearing.

Two clearings applied to the same settlement must not jointly over-clear it.
``post_clearing`` re-reads the referenced settlements ``FOR UPDATE`` inside its
transaction, so the second post blocks until the first commits and then sees the
reduced outstanding balance.

``transaction=True`` (TransactionTestCase semantics) because real commits and
independent connections are the whole point — the data must be visible to other
threads, and row locks only mean something across real transactions.
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
from apps.drivers.models import (
    Driver,
    DriverClearing,
    DriverClearingLine,
    DriverDocStatus,
    Settlement,
    SettlementDeduction,
)
from apps.drivers.services.post import DriverError, post_clearing, post_settlement
from apps.ledger.models import AccountingPeriod, JournalEntry
from apps.settings.services.driver_accounting import provision_driver_accounting
from apps.tenants.models import BusinessCategory, Entity

D = Decimal
ON = date(2026, 6, 15)
BANK_ENBD = "101-100-110-010"
DRIVER_PAYOUT = "101-500-530-003"
SALIK = "101-500-510-001"


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
    provision_driver_accounting(entity)
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


def _owing_settlement(entity, driver, bank, acct, *, shortfall="1000"):
    """A posted settlement leaving ``shortfall`` outstanding from the driver."""
    gross = D("1000")
    settlement = Settlement.objects.create(
        entity=entity,
        driver=driver,
        period_start=date(2026, 6, 1),
        period_end=date(2026, 6, 30),
        settlement_date=ON,
        gross_amount=gross,
        gross_account=acct(DRIVER_PAYOUT),
        pay_account=bank,
        allows_negative_net=True,
    )
    SettlementDeduction.objects.create(
        settlement=settlement, kind="fine", account=acct(SALIK), amount=gross + D(shortfall)
    )
    post_settlement(settlement)
    settlement.refresh_from_db()
    return settlement


def _clearing(entity, driver, bank, settlement, *, amount):
    clearing = DriverClearing.objects.create(
        entity=entity,
        driver=driver,
        kind=DriverClearing.Kind.RECEIPT,
        clearing_date=ON,
        amount=D(amount),
        bank_account=bank,
    )
    DriverClearingLine.objects.create(clearing=clearing, settlement=settlement, amount=D(amount))
    return clearing


def _cleanup():
    for conn in connections.all():
        conn.close()


@pytest.mark.django_db(transaction=True)
def test_sequential_clearings_see_the_reduced_balance():
    """A second receipt is measured against what the first left outstanding."""
    entity, driver, bank, acct = _world()
    settlement = _owing_settlement(entity, driver, bank, acct, shortfall="1000")
    assert settlement.receivable_balance == D("1000.00")

    post_clearing(_clearing(entity, driver, bank, settlement, amount="600"))
    settlement.refresh_from_db()
    assert settlement.receivable_balance == D("400.00")

    # 400 left: this one fits exactly.
    post_clearing(_clearing(entity, driver, bank, settlement, amount="400"))
    settlement.refresh_from_db()
    assert settlement.cleared_amount == D("1000.00")
    assert settlement.receivable_balance == D("0.00")

    # Nothing remains, so a third is rejected.
    third = _clearing(entity, driver, bank, settlement, amount="1")
    with pytest.raises(DriverError):
        post_clearing(third)
    third.refresh_from_db()
    assert third.status == DriverDocStatus.DRAFT
    _cleanup()


@pytest.mark.django_db(transaction=True)
def test_concurrent_clearings_only_one_consumes_the_balance():
    """Two threads race to clear 700 each from a 1,000 receivable — one must lose.

    Without ``select_for_update`` both would read an outstanding 1,000, both would
    pass validation, and the settlement would be over-cleared to 1,400 — money the
    driver never paid, credited out of the receivable.
    """
    entity, driver, bank, acct = _world()
    settlement = _owing_settlement(entity, driver, bank, acct, shortfall="1000")
    a = _clearing(entity, driver, bank, settlement, amount="700")
    b = _clearing(entity, driver, bank, settlement, amount="700")

    results: dict = {}
    start = threading.Barrier(2, timeout=30)

    def attempt(key, clearing_id):
        try:
            start.wait()
            with transaction.atomic():
                post_clearing(DriverClearing.objects.get(id=clearing_id))
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
        assert sorted(results.values()) == ["posted", "rejected"], results

        settlement.refresh_from_db()
        assert settlement.cleared_amount == D("700.00")
        assert settlement.receivable_balance == D("300.00")  # never driven negative

        # The loser wrote nothing at all: still draft, no number, no journal entry.
        loser = next(c for c in (a, b) if DriverClearing.objects.get(id=c.id).status != "posted")
        loser.refresh_from_db()
        assert loser.status == DriverDocStatus.DRAFT
        assert loser.journal_entry_id is None
        assert loser.clearing_no == ""
        assert not JournalEntry.objects.filter(source_id=loser.id).exists()
    finally:
        _cleanup()


@pytest.mark.django_db(transaction=True)
def test_settlements_are_locked_in_primary_key_order():
    """Deterministic lock order keeps concurrent clearings deadlock-free."""
    entity, driver, bank, acct = _world()
    first = _owing_settlement(entity, driver, bank, acct, shortfall="500")
    second = _owing_settlement(entity, driver, bank, acct, shortfall="500")
    ordered = sorted([first.id, second.id])

    clearing = DriverClearing.objects.create(
        entity=entity,
        driver=driver,
        kind=DriverClearing.Kind.RECEIPT,
        clearing_date=ON,
        amount=D("200"),
        bank_account=bank,
    )
    # Deliberately add the lines in the reverse of PK order: the service must
    # still acquire the locks ascending by primary key.
    for settlement_id in reversed(ordered):
        DriverClearingLine.objects.create(
            clearing=clearing,
            settlement=Settlement.objects.get(id=settlement_id),
            amount=D("100"),
        )

    with CaptureQueriesContext(connection) as captured:
        post_clearing(clearing)

    locking = [q["sql"] for q in captured.captured_queries if "FOR UPDATE" in q["sql"].upper()]
    assert locking, "settlements should be re-read FOR UPDATE"
    assert any(
        "ORDER BY" in sql.upper() and "ID" in sql.upper() for sql in locking
    ), f"expected a deterministic ORDER BY id on the locking read, got: {locking}"

    for settlement_id in ordered:
        s = Settlement.objects.get(id=settlement_id)
        assert s.cleared_amount == D("100.00")
        assert s.receivable_balance == D("400.00")
    _cleanup()
