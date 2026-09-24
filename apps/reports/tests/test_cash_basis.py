"""Cash-basis reporting (CLAUDE.md §1, AGENTS.md §1).

Cash basis recognises income and expense only when money moves, so a report on
that basis includes an entry only if it touches a bank or cash account. Until
this module, nothing tested it at all, although it is a headline feature.
These tests pin the behaviour, so a change to how the "touches cash" set is
computed can be shown to return identical results rather than asserted to.
"""

from decimal import Decimal

import pytest

from apps.reports.services.balances import trial_balance

from .conftest import BANK, DUE_FROM, EXPENSE, REVENUE, acct

pytestmark = pytest.mark.django_db


def _by_code(tb):
    return {b.account.code: (b.closing_debit, b.closing_credit) for b in tb.rows}


def test_cash_basis_counts_only_entries_that_touch_cash(entity, period, post_entry):
    post_entry(entity, [(BANK, "500.00", "0.00"), (REVENUE, "0.00", "500.00")])  # cash sale
    post_entry(entity, [(DUE_FROM, "800.00", "0.00"), (REVENUE, "0.00", "800.00")])  # on account

    cash = _by_code(trial_balance(entity_ids=[entity.id], period=period, basis="cash"))
    accrual = _by_code(trial_balance(entity_ids=[entity.id], period=period))

    revenue, bank, due = (acct(entity, s).code for s in (REVENUE, BANK, DUE_FROM))
    assert cash[revenue] == (Decimal("0"), Decimal("500.00"))
    assert cash[bank] == (Decimal("500.00"), Decimal("0"))
    assert due not in cash, "an entry with no bank or cash line must not appear on cash basis"

    assert accrual[revenue] == (Decimal("0"), Decimal("1300.00"))
    assert accrual[due] == (Decimal("800.00"), Decimal("0"))


def test_cash_basis_balances(entity, period, post_entry):
    post_entry(entity, [(BANK, "500.00", "0.00"), (REVENUE, "0.00", "500.00")])
    post_entry(entity, [(EXPENSE, "120.00", "0.00"), (BANK, "0.00", "120.00")])
    post_entry(entity, [(DUE_FROM, "800.00", "0.00"), (REVENUE, "0.00", "800.00")])

    tb = trial_balance(entity_ids=[entity.id], period=period, basis="cash")
    assert tb.is_balanced
    assert tb.total_debit == Decimal("500.00")  # bank 380 net + expense 120


def test_another_entitys_cash_does_not_leak_in(entity, entity_b, period, post_entry):
    """The 'touches cash' set must not draw on other entities' postings.

    Entity B's cash entries must neither appear in entity A's cash-basis report
    nor cause entity A's non-cash entry to be counted.
    """
    post_entry(entity, [(DUE_FROM, "800.00", "0.00"), (REVENUE, "0.00", "800.00")])  # A, no cash
    post_entry(entity_b, [(BANK, "999.00", "0.00"), (REVENUE, "0.00", "999.00")])  # B, cash

    tb = trial_balance(entity_ids=[entity.id], period=period, basis="cash")
    assert tb.rows == []
    assert tb.total_debit == tb.total_credit == Decimal("0")


def test_cash_basis_across_a_group(entity, entity_b, period, post_entry):
    post_entry(entity, [(BANK, "500.00", "0.00"), (REVENUE, "0.00", "500.00")])
    post_entry(entity_b, [(BANK, "300.00", "0.00"), (REVENUE, "0.00", "300.00")])
    post_entry(entity_b, [(DUE_FROM, "700.00", "0.00"), (REVENUE, "0.00", "700.00")])  # no cash

    tb = trial_balance(entity_ids=[entity.id, entity_b.id], period=period, basis="cash")
    assert tb.is_balanced
    assert tb.total_debit == Decimal("800.00")
