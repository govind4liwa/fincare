"""Shared fixtures for fleet tests."""

from datetime import date
from decimal import Decimal

import pytest

from apps.accounts.models import Account
from apps.accounts.services.seed import seed_entity_coa
from apps.banking.models import BankAccount
from apps.core.models import Currency
from apps.fleet.models import Vehicle, VehicleLoan
from apps.ledger.models import AccountingPeriod
from apps.tenants.models import BusinessCategory, Entity

VEHICLE_COST = "101-100-150-001"
VEHICLE_ACCUM_DEP = "101-100-150-002"
VEHICLE_LOAN = "101-200-220-001"
LOAN_INTEREST = "101-700-710-001"
VEHICLE_DEP_EXPENSE = "101-600-630-003"
BANK_ENBD = "101-100-110-010"


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
def vehicle(entity):
    return Vehicle.objects.create(
        entity=entity,
        code="V001",
        plate_no="A12345",
        ownership=Vehicle.Ownership.FINANCED,
        acquisition_cost=Decimal("120000"),
        residual_value=Decimal("0"),
        useful_life_months=60,  # -> 2000/month
        asset_account=_acct(entity, VEHICLE_COST),
        depreciation_expense_account=_acct(entity, VEHICLE_DEP_EXPENSE),
        accumulated_depreciation_account=_acct(entity, VEHICLE_ACCUM_DEP),
    )


@pytest.fixture
def loan(entity, vehicle):
    return VehicleLoan.objects.create(
        entity=entity,
        vehicle=vehicle,
        lender="ENBD Auto Finance",
        loan_account=_acct(entity, VEHICLE_LOAN),
        interest_account=_acct(entity, LOAN_INTEREST),
        principal=Decimal("100000"),
        term_months=48,
        emi_amount=Decimal("1000"),
    )
