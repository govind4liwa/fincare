"""Shared fixtures for cashbook tests."""

from datetime import date

import pytest

from apps.accounts.models import Account
from apps.accounts.services.seed import seed_entity_coa
from apps.banking.models import BankAccount
from apps.cashbook.models import CashAccount, PettyCashFloat
from apps.core.models import Currency
from apps.ledger.models import AccountingPeriod
from apps.tenants.models import BusinessCategory, Entity

PETTY_CASH = "101-100-110-001"
BANK_ENBD = "101-100-110-010"
VARIANCE = "101-600-640-099"  # Miscellaneous Expense → cash short/over


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
def cash_account(entity):
    return CashAccount.objects.create(
        entity=entity, code="TILL1", name="Main Till", gl_account=_acct(entity, PETTY_CASH)
    )


@pytest.fixture
def petty_float(entity, cash_account):
    return PettyCashFloat.objects.create(
        entity=entity,
        cash_account=cash_account,
        code="PCF1",
        float_amount=1000,
        custodian="Driver A",
    )
