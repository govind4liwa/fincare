"""Shared fixtures for platforms tests."""

from datetime import date
from decimal import Decimal

import pytest

from apps.accounts.models import Account
from apps.accounts.services.seed import seed_entity_coa
from apps.banking.models import BankAccount
from apps.core.models import Currency
from apps.ledger.models import AccountingPeriod
from apps.platforms.models import Platform
from apps.tenants.models import BusinessCategory, Entity

BANK_ENBD = "101-100-110-010"
PLATFORM_CLEARING = "101-100-110-021"
UBER_REVENUE = "101-400-410-001"
UBER_COMMISSION = "101-500-520-001"
MISC_EXPENSE = "101-600-640-099"


@pytest.fixture
def entity(db):
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


def _acct(entity, code):
    return Account.objects.get(entity=entity, code=code)


@pytest.fixture
def acct(entity):
    return lambda code: _acct(entity, code)


@pytest.fixture
def bank_enbd(entity):
    return BankAccount.objects.create(
        entity=entity,
        code="ENBD",
        name="ENBD Current",
        gl_account=_acct(entity, BANK_ENBD),
        currency=entity.base_currency,
    )


@pytest.fixture
def platform(entity):
    return Platform.objects.create(
        entity=entity,
        name="Uber",
        commission_pct=Decimal("20.000"),
        settlement_cycle=Platform.Cycle.WEEKLY,
        revenue_account=_acct(entity, UBER_REVENUE),
        commission_account=_acct(entity, UBER_COMMISSION),
        clearing_account=_acct(entity, PLATFORM_CLEARING),
    )
