"""Shared fixtures for bookings tests."""

from datetime import date
from decimal import Decimal

import pytest

from apps.accounts.models import Account, TaxCode
from apps.accounts.services.seed import seed_entity_coa, seed_tax_codes
from apps.ar.models import Customer
from apps.bookings.models import Contract
from apps.core.models import Currency
from apps.drivers.models import Driver
from apps.fleet.models import Vehicle
from apps.ledger.models import AccountingPeriod
from apps.platforms.models import Platform
from apps.tenants.models import BusinessCategory, Entity

AR_CONTROL = "101-100-120-001"
PLATFORM_CLEARING = "101-100-110-021"
UBER_REVENUE = "101-400-410-001"
UBER_COMMISSION = "101-500-520-001"
CONTRACT_REVENUE = "101-400-410-007"


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
    seed_tax_codes(ent)
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
def vehicle(entity):
    return Vehicle.objects.create(entity=entity, code="V001", plate_no="A12345")


@pytest.fixture
def driver(entity):
    return Driver.objects.create(entity=entity, code="D001", name="Imran Khan")


@pytest.fixture
def customer(entity):
    return Customer.objects.create(
        entity=entity,
        code="C001",
        name="ADNOC Distribution",
        customer_type="corporate",
        receivable_account=_acct(entity, AR_CONTROL),
        emirate="Abu Dhabi",
    )


@pytest.fixture
def contract(entity, customer, vehicle, driver):
    return Contract.objects.create(
        entity=entity,
        customer=customer,
        vehicle=vehicle,
        driver=driver,
        contract_no="CTR-001",
        start_date=date(2026, 6, 1),
        billing_cycle=Contract.Cycle.MONTHLY,
        monthly_amount=Decimal("5000.00"),
        revenue_account=_acct(entity, CONTRACT_REVENUE),
        tax_code=TaxCode.objects.get(entity=entity, code="SR"),
    )
