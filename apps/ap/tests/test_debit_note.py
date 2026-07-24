"""Debit note posting: DR Accounts Payable / CR Expense / CR Input VAT."""

from datetime import date
from decimal import Decimal

import pytest

from apps.accounts.models import Account
from apps.ap.models import BillStatus, DebitNote, DebitNoteLine
from apps.ap.services.post import APError, post_debit_note
from apps.ledger.models import EntryStatus

pytestmark = pytest.mark.django_db

DN_DATE = date(2026, 6, 20)


def test_debit_note_posts_dr_ap_cr_expense_cr_vat(entity, supplier, sr_tax, expense_account):
    dn = DebitNote.objects.create(
        entity=entity, supplier=supplier, debit_note_date=DN_DATE, reason="Returned goods"
    )
    DebitNoteLine.objects.create(
        debit_note=dn,
        line_no=1,
        account=expense_account,
        line_amount=Decimal("1000"),
        tax_code=sr_tax,
    )

    post_debit_note(dn)
    dn.refresh_from_db()

    assert dn.status == BillStatus.POSTED
    assert dn.debit_note_no.startswith("DN-")
    assert dn.subtotal == Decimal("1000.00")
    assert dn.tax_total == Decimal("50.00")  # 5% from TaxCode, not hardcoded
    assert dn.total == Decimal("1050.00")

    je = dn.journal_entry
    assert je.status == EntryStatus.POSTED
    assert je.total_debit == je.total_credit == Decimal("1050.00")

    input_vat = Account.objects.get(entity=entity, account_type=Account.AccountType.VAT_INPUT)
    assert je.lines.get(account=supplier.payable_account).debit == Decimal("1050.00")
    assert je.lines.get(account=supplier.payable_account).party_type == "supplier"
    assert je.lines.get(account=expense_account).credit == Decimal("1000.00")
    assert je.lines.get(account=input_vat).credit == Decimal("50.00")


def test_cannot_post_empty_debit_note(entity, supplier):
    dn = DebitNote.objects.create(entity=entity, supplier=supplier, debit_note_date=DN_DATE)
    with pytest.raises(APError):
        post_debit_note(dn)
