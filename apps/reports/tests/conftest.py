"""Shared fixtures for reports tests — entities, periods, and a GL post helper."""

from datetime import date
from decimal import Decimal

import pytest

from apps.accounts.models import Account
from apps.accounts.services.seed import seed_entity_coa
from apps.core.models import Currency
from apps.ledger.models import AccountingPeriod, JournalEntry, JournalLine
from apps.ledger.services.posting import post_journal_entry
from apps.tenants.models import BusinessCategory, Entity

# Non-control accounts safe for direct manual posting.
BANK = "100-110-010"
REVENUE = "400-410-001"  # Uber Earnings
EXPENSE = "500-530-001"  # Driver Salary
CAPITAL = "300-310-001"  # Owner's / Share Capital
DUE_FROM = "100-120-002"  # Advances to Suppliers (asset) — used as intercompany due-from
DUE_TO = "200-240-001"  # Salaries Payable (liability) — used as intercompany due-to


@pytest.fixture
def aed(db):
    return Currency.objects.create(code="AED", name="UAE Dirham", symbol="AED", is_base=True)


@pytest.fixture
def category(db):
    return BusinessCategory.objects.create(
        key="transport", label="Transport", band="1", coa_template_key="transport"
    )


def _make_entity(aed, category, *, code, numeric_code, name):
    ent = Entity.objects.create(
        code=code,
        numeric_code=numeric_code,
        legal_name=name,
        category=category,
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


@pytest.fixture
def entity(aed, category):
    return _make_entity(aed, category, code="RGT", numeric_code="101", name="Regency Transport LLC")


@pytest.fixture
def entity_b(aed, category):
    return _make_entity(aed, category, code="RGL", numeric_code="102", name="Regency Limo LLC")


@pytest.fixture
def period(entity):
    return AccountingPeriod.objects.get(entity=entity, period_no=6)


def acct(entity, suffix):
    return Account.objects.get(entity=entity, code=f"{entity.numeric_code}-{suffix}")


@pytest.fixture
def post_entry():
    """Post a balanced entry: rows = [(account_suffix, debit, credit), ...]."""

    def _post(entity, rows, *, when=date(2026, 6, 15)):
        entry = JournalEntry.objects.create(
            entity=entity,
            entry_date=when,
            source_type="test",
            currency=entity.base_currency,
        )
        for line_no, (suffix, debit, credit) in enumerate(rows, start=1):
            JournalLine.objects.create(
                entry=entry,
                line_no=line_no,
                account=acct(entity, suffix),
                debit=Decimal(debit),
                credit=Decimal(credit),
            )
        return post_journal_entry(entry)

    return _post
