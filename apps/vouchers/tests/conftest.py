"""Shared fixtures for voucher tests."""

from datetime import date

import pytest

from apps.accounts.models import Account
from apps.accounts.services.seed import seed_entity_coa
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
def acct(entity):
    def _get(code):
        return Account.objects.get(entity=entity, code=code)

    return _get
