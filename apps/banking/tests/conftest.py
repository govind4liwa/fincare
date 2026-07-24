"""Shared fixtures for banking tests."""

from datetime import date
from decimal import Decimal

import pytest

from apps.accounts.models import Account
from apps.accounts.services.seed import seed_entity_coa
from apps.banking.models import BankAccount
from apps.core.models import Currency
from apps.ledger.models import AccountingPeriod
from apps.tenants.models import BusinessCategory, Entity

# Seeded transport (entity 101) accounts used across banking tests.
BANK_ENBD = "101-100-110-010"
BANK_ADCB = "101-100-110-011"
POS_CLEARING = "101-100-110-020"
BANK_CHARGES = "101-600-640-004"
REVENUE = "101-400-410-001"


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
def bank_enbd(entity):
    return BankAccount.objects.create(
        entity=entity,
        code="ENBD",
        name="ENBD Current",
        gl_account=_acct(entity, BANK_ENBD),
        currency=entity.base_currency,
    )


@pytest.fixture
def bank_adcb(entity):
    return BankAccount.objects.create(
        entity=entity,
        code="ADCB",
        name="ADCB Current",
        gl_account=_acct(entity, BANK_ADCB),
        currency=entity.base_currency,
    )


@pytest.fixture
def acct(entity):
    """Helper to fetch a seeded GL account by code."""
    return lambda code: _acct(entity, code)


@pytest.fixture
def post_gl(entity):
    """Post an arbitrary balanced 2-line JE (helper for reconciliation tests)."""
    from apps.ledger.models import JournalEntry, JournalLine
    from apps.ledger.services.posting import post_journal_entry

    def _post(*, debit_account, credit_account, amount, on, description=""):
        entry = JournalEntry.objects.create(
            entity=entity, entry_date=on, source_type="manual", narration=description
        )
        JournalLine.objects.create(
            entry=entry,
            line_no=1,
            account=debit_account,
            debit=Decimal(amount),
            description=description,
        )
        JournalLine.objects.create(
            entry=entry, line_no=2, account=credit_account, credit=Decimal(amount)
        )
        return post_journal_entry(entry)

    return _post
