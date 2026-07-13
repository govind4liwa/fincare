"""Tests for purchase bill posting (normal + reverse-charge), allocation, aging."""

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.ap.models import BillStatus, PurchaseBill, PurchaseBillLine
from apps.ap.services.aging import supplier_aging
from apps.ap.services.post import APError, apply_payment_allocation, post_bill
from apps.ledger.models import EntryStatus

pytestmark = pytest.mark.django_db

BILL_DATE = date(2026, 6, 15)
AP_CONTROL = "101-200-210-001"
INPUT_VAT = "101-200-230-002"
OUTPUT_VAT = "101-200-230-001"
FUEL = "101-500-510-003"


def _bill(entity, supplier, currency, *, rcm=False, due=None):
    return PurchaseBill.objects.create(
        entity=entity,
        supplier=supplier,
        bill_date=BILL_DATE,
        due_date=due,
        currency=currency,
        is_reverse_charge=rcm,
    )


def _line(bill, account, unit_price, tax_code=None, recoverable=True):
    return PurchaseBillLine.objects.create(
        bill=bill,
        line_no=1,
        account=account,
        quantity=Decimal("1"),
        unit_price=Decimal(unit_price),
        tax_code=tax_code,
        recoverable=recoverable,
    )


def test_normal_bill_dr_expense_input_vat_cr_ap(entity, supplier, sr_tax, expense_account):
    bill = _bill(entity, supplier, entity.base_currency)
    _line(bill, expense_account, "1000", tax_code=sr_tax)

    post_bill(bill)
    bill.refresh_from_db()
    assert bill.status == BillStatus.POSTED
    assert bill.bill_no.startswith("BILL-")
    assert bill.subtotal == Decimal("1000.00")
    assert bill.tax_total == Decimal("50.00")
    assert bill.total == bill.balance == Decimal("1050.00")  # gross owed to supplier

    je = bill.journal_entry
    assert je.status == EntryStatus.POSTED
    assert je.total_debit == je.total_credit == Decimal("1050.00")
    assert je.lines.get(account__code=FUEL).debit == Decimal("1000.00")
    assert je.lines.get(account__code=INPUT_VAT).debit == Decimal("50.00")
    assert je.lines.get(account__code=AP_CONTROL).credit == Decimal("1050.00")
    assert je.lines.get(account__code=AP_CONTROL).party_type == "supplier"
    assert not je.lines.filter(account__code=OUTPUT_VAT).exists()


def test_reverse_charge_raises_both_input_and_output_vat(entity, supplier, sr_tax, expense_account):
    bill = _bill(entity, supplier, entity.base_currency, rcm=True)
    _line(bill, expense_account, "1000", tax_code=sr_tax)

    post_bill(bill)
    bill.refresh_from_db()
    je = bill.journal_entry
    # supplier billed net -> AP is the net amount, VAT self-assessed both sides
    assert bill.total == Decimal("1000.00")
    assert je.lines.get(account__code=FUEL).debit == Decimal("1000.00")
    assert je.lines.get(account__code=INPUT_VAT).debit == Decimal("50.00")
    assert je.lines.get(account__code=OUTPUT_VAT).credit == Decimal("50.00")
    assert je.lines.get(account__code=AP_CONTROL).credit == Decimal("1000.00")
    assert je.total_debit == je.total_credit == Decimal("1050.00")


def test_non_recoverable_vat_is_expensed(entity, supplier, sr_tax, expense_account):
    bill = _bill(entity, supplier, entity.base_currency)
    _line(bill, expense_account, "1000", tax_code=sr_tax, recoverable=False)

    post_bill(bill)
    bill.refresh_from_db()
    je = bill.journal_entry
    # no input VAT line; the 50 is folded into the expense debit
    assert not je.lines.filter(account__code=INPUT_VAT).exists()
    assert je.lines.get(account__code=FUEL).debit == Decimal("1050.00")
    assert je.lines.get(account__code=AP_CONTROL).credit == Decimal("1050.00")


def test_payment_allocation_reduces_balance(entity, supplier, sr_tax, expense_account):
    bill = _bill(entity, supplier, entity.base_currency)
    _line(bill, expense_account, "1000", tax_code=sr_tax)
    post_bill(bill)

    apply_payment_allocation(
        bill, amount=Decimal("1050"), source_type="payment_voucher", source_id=uuid.uuid4()
    )
    bill.refresh_from_db()
    assert bill.balance == Decimal("0.00")
    assert bill.status == BillStatus.PAID


def test_supplier_aging_buckets(entity, supplier, sr_tax, expense_account):
    bill = _bill(entity, supplier, entity.base_currency, due=date(2026, 6, 1))
    _line(bill, expense_account, "1000", tax_code=sr_tax)
    post_bill(bill)

    rows = supplier_aging(entity, as_of=date(2026, 6, 1) + timedelta(days=100))
    assert len(rows) == 1
    assert rows[0]["supplier"].id == supplier.id
    assert rows[0]["d91_120"] == Decimal("1050.00")


def test_unbalanced_protection_via_engine(entity, supplier, expense_account):
    # A bill with a zero-amount line cannot post (engine rejects zero total).
    bill = _bill(entity, supplier, entity.base_currency)
    _line(bill, expense_account, "0")
    with pytest.raises(APError):
        post_bill(bill)
    bill.refresh_from_db()
    assert bill.status == BillStatus.DRAFT
