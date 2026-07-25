"""Shared fixtures for drivers tests."""

from datetime import date
from decimal import Decimal

import pytest

from apps.accounts.models import Account
from apps.accounts.services.seed import seed_entity_coa
from apps.banking.models import BankAccount
from apps.core.models import Currency
from apps.drivers.models import Driver
from apps.ledger.models import AccountingPeriod
from apps.settings.services.driver_accounting import provision_driver_accounting
from apps.tenants.models import BusinessCategory, Entity

BANK_ENBD = "101-100-110-010"
DRIVER_PAYOUT = "101-500-530-003"
DRIVER_COMMISSION = "101-500-530-002"
STAFF_ADVANCES = "101-100-120-003"
SALIK = "101-500-510-001"
FINES = "101-500-510-004"


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
    # Mirrors real provisioning (see the seed_coa command): a freshly seeded
    # entity comes with its Driver Receivable account already configured.
    provision_driver_accounting(ent)
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
def driver(entity):
    return Driver.objects.create(
        entity=entity,
        code="D001",
        name="Imran Khan",
        basic_salary=Decimal("2500"),
        commission_rate=Decimal("10.000"),
    )
