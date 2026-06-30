"""Shared fixtures for AP tests."""

from datetime import date
from decimal import Decimal

import pytest

from apps.accounts.models import Account, TaxCode
from apps.accounts.services.seed import seed_entity_coa
from apps.ap.models import Supplier
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
        direction=TaxCode.Direction.BOTH,
    )


@pytest.fixture
def supplier(entity):
    ap_control = Account.objects.get(entity=entity, code="101-200-210-001")
    return Supplier.objects.create(
        entity=entity,
        code="S001",
        name="Fuel Co",
        payable_account=ap_control,
        currency=entity.base_currency,
        credit_days=30,
    )


@pytest.fixture
def expense_account(entity):
    return Account.objects.get(entity=entity, code="101-500-510-003")  # Fuel
