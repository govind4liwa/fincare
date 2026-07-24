"""Voucher posting service tests — debit/credit mapping per voucher type."""

import uuid
from datetime import date
from decimal import Decimal

import pytest

from apps.ledger.models import EntryStatus
from apps.vouchers.models import Voucher, VoucherLine, VoucherStatus
from apps.vouchers.services.post import VoucherError, post_voucher, reverse_voucher

pytestmark = pytest.mark.django_db

VDATE = date(2026, 6, 15)

# Codes from the seeded transport (entity 101) COA.
BANK = "101-100-110-010"
CASH = "101-100-110-001"
AR = "101-100-120-001"  # Trade Receivables (control, customer)
AP = "101-200-210-001"  # Trade Payables (control, supplier)
REVENUE = "101-400-410-001"
FUEL = "101-500-510-003"


def _voucher(entity, acct, vtype, lines, **header):
    v = Voucher.objects.create(
        entity=entity,
        voucher_type=vtype,
        voucher_date=VDATE,
        currency=entity.base_currency,
        **header,
    )
    for i, (code, debit, credit, extra) in enumerate(lines, start=1):
        VoucherLine.objects.create(
            voucher=v,
            line_no=i,
            account=acct(code),
            debit=Decimal(debit),
            credit=Decimal(credit),
            **extra,
        )
    return v


def test_receipt_maps_dr_bank_cr_customer(entity, acct):
    party = {"party_type": "customer", "party_id": uuid.uuid4()}
    v = _voucher(
        entity,
        acct,
        "receipt",
        [
            (BANK, "500", "0", {}),
            (AR, "0", "500", party),
        ],
    )
    post_voucher(v)
    v.refresh_from_db()
    assert v.status == VoucherStatus.POSTED
    assert v.voucher_no.startswith("RV-")
    je = v.journal_entry
    assert je.source_type == "voucher"
    assert je.status == EntryStatus.POSTED
    assert je.total_debit == je.total_credit == Decimal("500.00")
    assert je.lines.get(account__code=BANK).debit == Decimal("500")
    assert je.lines.get(account__code=AR).credit == Decimal("500")


def test_payment_maps_dr_supplier_cr_bank(entity, acct):
    party = {"party_type": "supplier", "party_id": uuid.uuid4()}
    v = _voucher(
        entity,
        acct,
        "payment",
        [
            (AP, "300", "0", party),
            (BANK, "0", "300", {}),
        ],
    )
    post_voucher(v)
    v.refresh_from_db()
    assert v.voucher_no.startswith("PV-")
    assert v.journal_entry.lines.get(account__code=AP).debit == Decimal("300")


def test_contra_bank_to_cash(entity, acct):
    v = _voucher(
        entity,
        acct,
        "contra",
        [
            (BANK, "1000", "0", {}),
            (CASH, "0", "1000", {}),
        ],
    )
    post_voucher(v)
    v.refresh_from_db()
    assert v.voucher_no.startswith("CV-")
    assert v.journal_entry.total_debit == Decimal("1000.00")


def test_expense_dr_expense_cr_bank(entity, acct):
    v = _voucher(
        entity,
        acct,
        "expense",
        [
            (FUEL, "250", "0", {}),
            (BANK, "0", "250", {}),
        ],
    )
    post_voucher(v)
    v.refresh_from_db()
    assert v.voucher_no.startswith("EV-")
    assert v.journal_entry.lines.get(account__code=FUEL).debit == Decimal("250")


def test_journal_voucher_generic(entity, acct):
    v = _voucher(
        entity,
        acct,
        "journal",
        [
            (CASH, "75", "0", {}),
            (REVENUE, "0", "75", {}),
        ],
    )
    post_voucher(v)
    v.refresh_from_db()
    assert v.voucher_no.startswith("JV-")
    assert v.journal_entry.total_credit == Decimal("75.00")


def test_unbalanced_voucher_rejected(entity, acct):
    v = _voucher(
        entity,
        acct,
        "journal",
        [
            (CASH, "75", "0", {}),
            (REVENUE, "0", "70", {}),
        ],
    )
    with pytest.raises(VoucherError):
        post_voucher(v)
    v.refresh_from_db()
    assert v.status == VoucherStatus.DRAFT  # rolled back


def test_reversing_voucher_reverses_entry(entity, acct):
    v = _voucher(
        entity,
        acct,
        "contra",
        [
            (BANK, "1000", "0", {}),
            (CASH, "0", "1000", {}),
        ],
    )
    post_voucher(v)
    original_entry = v.journal_entry

    mirror = reverse_voucher(v)
    v.refresh_from_db()
    original_entry.refresh_from_db()
    assert v.status == VoucherStatus.REVERSED
    assert original_entry.status == EntryStatus.REVERSED
    assert mirror.status == EntryStatus.POSTED
    assert mirror.total_debit == mirror.total_credit == Decimal("1000.00")
