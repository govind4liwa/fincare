"""Reporting tests: TB nets to zero, P&L/BS tie, consolidation elimination."""

from decimal import Decimal

import pytest

from apps.reports.services.balances import trial_balance
from apps.reports.services.catalog import trial_balance_table
from apps.reports.services.consolidation import consolidated_trial_balance
from apps.reports.services.statements import balance_sheet, profit_and_loss
from apps.reports.services.templates import seed_statement_templates
from apps.reports.tests.conftest import (
    BANK,
    CAPITAL,
    DUE_FROM,
    DUE_TO,
    EXPENSE,
    REVENUE,
    acct,
)
from apps.tenants.models import IntercompanyMap

pytestmark = pytest.mark.django_db


def _seed_books(entity, post_entry):
    post_entry(entity, [(BANK, "10000.00", "0.00"), (CAPITAL, "0.00", "10000.00")])  # capital
    post_entry(entity, [(BANK, "5000.00", "0.00"), (REVENUE, "0.00", "5000.00")])  # revenue
    post_entry(entity, [(EXPENSE, "2000.00", "0.00"), (BANK, "0.00", "2000.00")])  # expense


def test_trial_balance_nets_to_zero(entity, period, post_entry):
    _seed_books(entity, post_entry)
    tb = trial_balance(entity_ids=[entity.id], period=period)
    assert tb.total_debit == tb.total_credit == Decimal("15000.00")
    assert tb.is_balanced


def test_pnl_and_bs_tie(entity, period, post_entry):
    _seed_books(entity, post_entry)
    pnl = profit_and_loss(entity_ids=[entity.id], period=period)
    bs = balance_sheet(entity_ids=[entity.id], period=period)

    assert pnl.revenue == Decimal("5000.00")
    assert pnl.direct_cost == Decimal("2000.00")
    assert pnl.net_profit == Decimal("3000.00")

    assert bs.assets == Decimal("13000.00")  # bank 10000 + 5000 - 2000
    assert bs.equity == Decimal("10000.00")
    assert bs.liabilities == Decimal("0.00")
    # Assets = Liabilities + Equity + result for the period.
    assert bs.is_balanced
    assert bs.assets == bs.liabilities + bs.equity + bs.net_profit


def test_consolidation_eliminates_intercompany(entity, entity_b, period, post_entry):
    # A books a receivable from B; B books the matching payable to A.
    post_entry(entity, [(DUE_FROM, "1000.00", "0.00"), (REVENUE, "0.00", "1000.00")])
    post_entry(entity_b, [(EXPENSE, "1000.00", "0.00"), (DUE_TO, "0.00", "1000.00")])
    IntercompanyMap.objects.create(
        from_entity=entity,
        to_entity=entity_b,
        due_from_account=acct(entity, DUE_FROM),
        due_to_account=acct(entity_b, DUE_TO),
    )
    group = [entity.id, entity_b.id]

    gross = consolidated_trial_balance(entity_ids=group, period=period, eliminate=False)
    net = consolidated_trial_balance(entity_ids=group, period=period, eliminate=True)

    gross_codes = {b.account.code for b in gross.rows}
    net_codes = {b.account.code for b in net.rows}
    assert f"{entity.numeric_code}-{DUE_FROM}" in gross_codes
    assert f"{entity_b.numeric_code}-{DUE_TO}" in gross_codes
    # Intercompany accounts are eliminated on consolidation.
    assert f"{entity.numeric_code}-{DUE_FROM}" not in net_codes
    assert f"{entity_b.numeric_code}-{DUE_TO}" not in net_codes

    assert gross.total_debit == gross.total_credit == Decimal("2000.00")
    assert net.total_debit == net.total_credit == Decimal("1000.00")
    assert net.is_balanced


def test_trial_balance_table_export_to_xlsx(entity, period, post_entry):
    _seed_books(entity, post_entry)
    report = trial_balance_table(entity_ids=[entity.id], period=period)
    assert report["meta"]["balanced"] is True
    assert report["rows"][-1][1] == "TOTAL"

    from apps.exports.services.xlsx import report_to_xlsx_bytes

    data = report_to_xlsx_bytes(report)
    assert data[:2] == b"PK"  # xlsx is a zip archive
    assert len(data) > 0


def test_seed_statement_templates_idempotent(db):
    assert seed_statement_templates() == 4  # TB / PNL / BS / CF
    assert seed_statement_templates() == 0  # idempotent re-run
