"""Shared fixtures for tax tests.

Builds a VAT group of two transport entities so we can prove the return
aggregates VAT across member entities. VAT lands in the GL by posting real
AR / AP documents through the ledger engine (the return reads the VAT control
accounts, never the source docs, for its totals).
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.accounts.models import Account, TaxCode
from apps.accounts.services.seed import seed_entity_coa
from apps.ap.models import PurchaseBill, PurchaseBillLine, Supplier
from apps.ap.services.post import post_bill
from apps.ar.models import Customer, SalesInvoice, SalesInvoiceLine
from apps.ar.services.post import post_invoice
from apps.core.models import Currency
from apps.ledger.models import AccountingPeriod
from apps.tenants.models import BusinessCategory, Entity, VatGroup

PERIOD_START = date(2026, 6, 1)
PERIOD_END = date(2026, 6, 30)


@pytest.fixture
def aed(db):
    return Currency.objects.create(code="AED", name="UAE Dirham", symbol="AED", is_base=True)


@pytest.fixture
def category(db):
    return BusinessCategory.objects.create(
        key="transport", label="Transport", band="1", coa_template_key="transport"
    )


def _make_entity(numeric_code, legal_name, category, currency):
    ent = Entity.objects.create(
        code=f"E{numeric_code}",
        numeric_code=numeric_code,
        legal_name=legal_name,
        category=category,
        base_currency=currency,
    )
    seed_entity_coa(ent)
    AccountingPeriod.objects.create(
        entity=ent,
        fiscal_year=2026,
        period_no=6,
        name="Jun-2026",
        start_date=PERIOD_START,
        end_date=PERIOD_END,
        status=AccountingPeriod.Status.OPEN,
    )
    return ent


def _sr_tax(entity):
    return TaxCode.objects.create(
        entity=entity,
        code="SR",
        name="Standard Rated 5%",
        rate=Decimal("5.000"),
        treatment=TaxCode.Treatment.STANDARD,
        direction=TaxCode.Direction.BOTH,
    )


@pytest.fixture
def vat_group(aed, category):
    """Two transport entities (101, 102) sharing one TRN."""
    group = VatGroup.objects.create(code="VG1", name="Regency VAT Group", trn="100123456700003")
    ent_a = _make_entity("101", "Regency Transport LLC", category, aed)
    ent_b = _make_entity("102", "Regency Limo LLC", category, aed)
    ent_a.vat_group = group
    ent_b.vat_group = group
    ent_a.save(update_fields=["vat_group"])
    ent_b.save(update_fields=["vat_group"])
    group.entity_a = ent_a  # convenience handles for tests
    group.entity_b = ent_b
    return group


def _post_sale(entity, *, amount, place_of_supply):
    """Post a standard-rated sales invoice -> Output VAT in the GL."""
    ar_control = Account.objects.get(entity=entity, code=f"{entity.numeric_code}-100-120-001")
    revenue = Account.objects.get(entity=entity, code=f"{entity.numeric_code}-400-410-001")
    cust = Customer.objects.create(
        entity=entity,
        code="C001",
        name="Acme Corp",
        customer_type="corporate",
        receivable_account=ar_control,
        currency=entity.base_currency,
    )
    inv = SalesInvoice.objects.create(
        entity=entity,
        customer=cust,
        invoice_date=date(2026, 6, 15),
        place_of_supply=place_of_supply,
        currency=entity.base_currency,
    )
    SalesInvoiceLine.objects.create(
        invoice=inv,
        line_no=1,
        revenue_account=revenue,
        quantity=Decimal("1"),
        unit_price=Decimal(amount),
        tax_code=_sr_tax(entity),
    )
    return post_invoice(inv)


def _post_purchase(entity, *, amount):
    """Post a standard-rated purchase bill -> Input VAT in the GL."""
    ap_control = Account.objects.get(entity=entity, code=f"{entity.numeric_code}-200-210-001")
    expense = Account.objects.get(entity=entity, code=f"{entity.numeric_code}-500-510-003")
    supp = Supplier.objects.create(
        entity=entity,
        code="S001",
        name="Fuel Co",
        payable_account=ap_control,
        currency=entity.base_currency,
    )
    bill = PurchaseBill.objects.create(
        entity=entity,
        supplier=supp,
        bill_date=date(2026, 6, 20),
        currency=entity.base_currency,
    )
    PurchaseBillLine.objects.create(
        bill=bill,
        line_no=1,
        account=expense,
        quantity=Decimal("1"),
        unit_price=Decimal(amount),
        tax_code=_sr_tax(entity),
    )
    return post_bill(bill)


@pytest.fixture
def post_sale():
    return _post_sale


@pytest.fixture
def post_purchase():
    return _post_purchase
