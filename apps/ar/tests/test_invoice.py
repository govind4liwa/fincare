"""Tests for sales invoice posting, allocation, and aging."""

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.ar.models import InvoiceStatus, SalesInvoice, SalesInvoiceLine
from apps.ar.services.aging import customer_aging
from apps.ar.services.post import ARError, apply_allocation, post_invoice
from apps.ledger.models import EntryStatus

pytestmark = pytest.mark.django_db

INV_DATE = date(2026, 6, 15)
OUTPUT_VAT = "101-200-230-001"
AR_CONTROL = "101-100-120-001"
REVENUE = "101-400-410-001"


def _invoice(entity, customer, currency, due=None):
    return SalesInvoice.objects.create(
        entity=entity,
        customer=customer,
        invoice_date=INV_DATE,
        due_date=due,
        currency=currency,
        place_of_supply="Dubai",
    )


def test_invoice_posts_dr_ar_cr_revenue_cr_vat(entity, customer, sr_tax, revenue_account):
    inv = _invoice(entity, customer, entity.base_currency)
    SalesInvoiceLine.objects.create(
        invoice=inv,
        line_no=1,
        revenue_account=revenue_account,
        quantity=Decimal("1"),
        unit_price=Decimal("1000"),
        tax_code=sr_tax,
    )

    post_invoice(inv)
    inv.refresh_from_db()

    assert inv.status == InvoiceStatus.POSTED
    assert inv.invoice_no.startswith("INV-")
    assert inv.subtotal == Decimal("1000.00")
    assert inv.tax_total == Decimal("50.00")  # 5% from TaxCode, not hardcoded
    assert inv.total == inv.balance == Decimal("1050.00")

    je = inv.journal_entry
    assert je.status == EntryStatus.POSTED
    assert je.total_debit == je.total_credit == Decimal("1050.00")
    assert je.lines.get(account__code=AR_CONTROL).debit == Decimal("1050.00")
    assert je.lines.get(account__code=AR_CONTROL).party_type == "customer"
    assert je.lines.get(account__code=REVENUE).credit == Decimal("1000.00")
    assert je.lines.get(account__code=OUTPUT_VAT).credit == Decimal("50.00")


def test_zero_rated_invoice_has_no_vat_line(entity, customer, revenue_account):
    from apps.accounts.models import TaxCode

    zr = TaxCode.objects.create(
        entity=entity,
        code="ZR",
        name="Zero Rated",
        rate=Decimal("0"),
        treatment=TaxCode.Treatment.ZERO,
    )
    inv = _invoice(entity, customer, entity.base_currency)
    SalesInvoiceLine.objects.create(
        invoice=inv,
        line_no=1,
        revenue_account=revenue_account,
        quantity=Decimal("2"),
        unit_price=Decimal("500"),
        tax_code=zr,
    )
    post_invoice(inv)
    inv.refresh_from_db()
    assert inv.tax_total == Decimal("0.00")
    assert inv.total == Decimal("1000.00")
    assert not inv.journal_entry.lines.filter(account__code=OUTPUT_VAT).exists()


def test_allocation_reduces_balance(entity, customer, sr_tax, revenue_account):
    inv = _invoice(entity, customer, entity.base_currency)
    SalesInvoiceLine.objects.create(
        invoice=inv,
        line_no=1,
        revenue_account=revenue_account,
        quantity=Decimal("1"),
        unit_price=Decimal("1000"),
        tax_code=sr_tax,
    )
    post_invoice(inv)

    apply_allocation(
        inv, amount=Decimal("400"), source_type="receipt_voucher", source_id=uuid.uuid4()
    )
    inv.refresh_from_db()
    assert inv.amount_allocated == Decimal("400.00")
    assert inv.balance == Decimal("650.00")
    assert inv.status == InvoiceStatus.PARTIALLY_PAID

    apply_allocation(
        inv, amount=Decimal("650"), source_type="receipt_voucher", source_id=uuid.uuid4()
    )
    inv.refresh_from_db()
    assert inv.balance == Decimal("0.00")
    assert inv.status == InvoiceStatus.PAID


def test_overallocation_rejected(entity, customer, sr_tax, revenue_account):
    inv = _invoice(entity, customer, entity.base_currency)
    SalesInvoiceLine.objects.create(
        invoice=inv,
        line_no=1,
        revenue_account=revenue_account,
        quantity=Decimal("1"),
        unit_price=Decimal("100"),
        tax_code=sr_tax,
    )
    post_invoice(inv)
    with pytest.raises(ARError):
        apply_allocation(inv, amount=Decimal("9999"), source_type="advance", source_id=uuid.uuid4())


def test_aging_buckets_open_invoices(entity, customer, sr_tax, revenue_account):
    # due 45 days before as_of -> 31-60 bucket
    inv = _invoice(entity, customer, entity.base_currency, due=date(2026, 6, 1))
    SalesInvoiceLine.objects.create(
        invoice=inv,
        line_no=1,
        revenue_account=revenue_account,
        quantity=Decimal("1"),
        unit_price=Decimal("1000"),
        tax_code=sr_tax,
    )
    post_invoice(inv)

    rows = customer_aging(entity, as_of=date(2026, 6, 1) + timedelta(days=45))
    assert len(rows) == 1
    row = rows[0]
    assert row["customer"].id == customer.id
    assert row["d31_60"] == Decimal("1050.00")
    assert row["total"] == Decimal("1050.00")
