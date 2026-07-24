"""Shared fixtures for integrations tests — entity, bank account, platform, profiles."""

from decimal import Decimal

import pytest

from apps.accounts.models import Account
from apps.accounts.services.seed import seed_entity_coa
from apps.banking.models import BankAccount
from apps.core.models import Currency
from apps.integrations.models import ImportKind, ImportProfile
from apps.platforms.models import Platform
from apps.tenants.models import BusinessCategory, Entity

BANK_ENBD = "101-100-110-010"
PLATFORM_CLEARING = "101-100-110-021"
UBER_REVENUE = "101-400-410-001"
UBER_COMMISSION = "101-500-520-001"


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
    return ent


def _acct(entity, code):
    return Account.objects.get(entity=entity, code=code)


@pytest.fixture
def bank_account(entity):
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
        revenue_account=_acct(entity, UBER_REVENUE),
        commission_account=_acct(entity, UBER_COMMISSION),
        clearing_account=_acct(entity, PLATFORM_CLEARING),
    )


@pytest.fixture
def bank_profile(entity):
    return ImportProfile.objects.create(
        entity=entity,
        kind=ImportKind.BANK_STATEMENT,
        name="ENBD CSV",
        source_key="ENBD",
        column_map={
            "txn_date": "Date",
            "description": "Narrative",
            "reference": "Ref",
            "deposit": "Credit",
            "withdrawal": "Debit",
            "running_balance": "Balance",
        },
        date_format="%d/%m/%Y",
    )


@pytest.fixture
def platform_profile(entity):
    return ImportProfile.objects.create(
        entity=entity,
        kind=ImportKind.PLATFORM_EARNING,
        name="Uber XLSX",
        source_key="Uber",
        column_map={
            "earning_date": "Date",
            "trip_ref": "Trip",
            "driver_ref": "Driver",
            "gross": "Gross",
            "commission": "Commission",
            "net": "Net",
        },
        date_format="%Y-%m-%d",
    )
