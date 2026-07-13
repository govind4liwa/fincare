"""Shared fixtures for AR tests."""

from datetime import date
from decimal import Decimal

import pytest

from apps.accounts.models import Account, TaxCode
from apps.accounts.services.seed import seed_entity_coa
from apps.ar.models import Customer
from apps.core.models import Currency
from apps.ledger.models import AccountingPeriod
from apps.tenants.models import BusinessCategory, Entity


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


@pytest.fixture
def sr_tax(entity):
    return TaxCode.objects.create(
        entity=entity,
        code="SR",
        name="Standard Rated 5%",
        rate=Decimal("5.000"),
        treatment=TaxCode.Treatment.STANDARD,
        direction=TaxCode.Direction.OUTPUT,
    )


@pytest.fixture
def customer(entity):
    ar_control = Account.objects.get(entity=entity, code="101-100-120-001")
    return Customer.objects.create(
        entity=entity,
        code="C001",
        name="Acme Corp",
        customer_type="corporate",
        receivable_account=ar_control,
        currency=entity.base_currency,
        credit_days=30,
    )


@pytest.fixture
def revenue_account(entity):
    return Account.objects.get(entity=entity, code="101-400-410-001")
