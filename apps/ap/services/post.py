"""Post AP documents through the ledger engine (ADR-0007).

Purchase bill posting (normal):
    DR  Expense / Asset (per line)         = line amounts (+ non-recoverable VAT)
    DR  Input VAT (recoverable, by type)   = recoverable tax
    CR  Accounts Payable (supplier, party) = gross (subtotal + tax)

Reverse charge (import / RCM): the supplier bills net, the buyer self-assesses VAT:
    DR  Expense / Asset                    = line amounts (net)
    DR  Input VAT                          = tax
    CR  Output VAT                         = tax        (self-charged)
    CR  Accounts Payable                   = subtotal (net)

VAT rate comes from ``accounts.TaxCode``; VAT GL accounts are resolved by
``account_type`` ('vat_input' / 'vat_output') — no hardcoded rates.
"""

from collections import OrderedDict
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction

from apps.accounts.models import Account
from apps.ap.models import BillStatus, PaymentAllocation
from apps.audit.services import record as audit_record
from apps.core.services import sequences
from apps.ledger.models import JournalEntry, JournalLine
from apps.ledger.services.posting import PostingError, post_journal_entry

TWO_PLACES = Decimal("0.01")
ZERO = Decimal("0")


class APError(ValueError):
    """Raised when an AP document cannot be posted or allocated."""


def _q(amount):
    return Decimal(amount).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _vat_account(entity, account_type, label):
    acct = Account.objects.filter(entity=entity, account_type=account_type, is_active=True).first()
    if acct is None:
        raise APError(
            f"No {label} account (account_type={account_type!r}) in the chart of accounts."
        )
    return acct


@transaction.atomic
def post_bill(bill, *, user=None):
    if bill.status != BillStatus.DRAFT:
        raise APError(f"Cannot post a bill in status {bill.status!r}.")
    lines = list(bill.lines.select_related("account", "tax_code").all())
    if not lines:
        raise APError("Bill has no lines.")

    subtotal, tax_total, recoverable_tax = ZERO, ZERO, ZERO
    expense = OrderedDict()  # account -> debit amount
    for ln in lines:
        ln.line_amount = _q(Decimal(ln.quantity) * Decimal(ln.unit_price))
        ln.tax_rate = ln.tax_code.rate if ln.tax_code_id else ZERO
        ln.tax_amount = _q(ln.line_amount * Decimal(ln.tax_rate) / Decimal(100))
        ln.save(update_fields=["line_amount", "tax_rate", "tax_amount", "updated_at"])

        subtotal += ln.line_amount
        tax_total += ln.tax_amount
        debit = ln.line_amount
        if bill.is_reverse_charge:
            recoverable_tax += ln.tax_amount  # self-assessed, recoverable
        elif ln.recoverable:
            recoverable_tax += ln.tax_amount
        else:
            debit += ln.tax_amount  # non-recoverable VAT is expensed
        expense[ln.account] = expense.get(ln.account, ZERO) + debit

    ap_amount = subtotal if bill.is_reverse_charge else subtotal + tax_total

    entry = JournalEntry.objects.create(
        entity=bill.entity,
        branch=bill.branch,
        entry_date=bill.bill_date,
        source_type="purchase_bill",
        source_id=bill.id,
        currency=bill.currency,
        narration=f"Purchase bill {bill.supplier.code}",
    )
    line_no = 1
    for account, amount in expense.items():
        JournalLine.objects.create(entry=entry, line_no=line_no, account=account, debit=amount)
        line_no += 1
    if recoverable_tax > ZERO:
        JournalLine.objects.create(
            entry=entry,
            line_no=line_no,
            account=_vat_account(bill.entity, Account.AccountType.VAT_INPUT, "Input VAT"),
            debit=recoverable_tax,
        )
        line_no += 1
    if bill.is_reverse_charge and tax_total > ZERO:
        JournalLine.objects.create(
            entry=entry,
            line_no=line_no,
            account=_vat_account(bill.entity, Account.AccountType.VAT_OUTPUT, "Output VAT"),
            credit=tax_total,
        )
        line_no += 1
    JournalLine.objects.create(
        entry=entry,
        line_no=line_no,
        account=bill.supplier.payable_account,
        credit=ap_amount,
        party_type="supplier",
        party_id=bill.supplier_id,
    )

    try:
        post_journal_entry(entry, user=user)
    except PostingError as exc:
        raise APError(str(exc)) from exc

    bill.bill_no = sequences.allocate(
        entity_id=bill.entity_id,
        code="PURCHASE_BILL",
        period_key=str(bill.bill_date.year),
        prefix="BILL-",
        padding=6,
    ).formatted
    bill.subtotal = subtotal
    bill.tax_total = tax_total
    bill.total = ap_amount
    bill.amount_allocated = ZERO
    bill.balance = ap_amount
    bill.status = BillStatus.POSTED
    bill.journal_entry = entry
    bill.save()

    audit_record(
        action="post",
        instance=bill,
        actor=user,
        entity_id=bill.entity_id,
        message=f"Posted {bill.bill_no} total={ap_amount} (RCM={bill.is_reverse_charge})",
    )
    return bill


@transaction.atomic
def post_debit_note(debit_note, *, user=None):
    """Post a debit note (supplier return/credit): DR Accounts Payable /
    CR Expense (per line) / CR Input VAT. The mirror of a purchase bill —
    it reduces what the entity owes the supplier."""
    if debit_note.status != BillStatus.DRAFT:
        raise APError(f"Cannot post a debit note in status {debit_note.status!r}.")
    lines = list(debit_note.lines.select_related("account", "tax_code").all())
    if not lines:
        raise APError("Debit note has no lines.")

    subtotal, tax_total = ZERO, ZERO
    expense = OrderedDict()  # account -> credit amount
    for ln in lines:
        ln.line_amount = _q(ln.line_amount)
        ln.tax_rate = ln.tax_code.rate if ln.tax_code_id else ZERO
        ln.tax_amount = _q(ln.line_amount * Decimal(ln.tax_rate) / Decimal(100))
        ln.save(update_fields=["line_amount", "tax_rate", "tax_amount", "updated_at"])
        subtotal += ln.line_amount
        tax_total += ln.tax_amount
        expense[ln.account] = expense.get(ln.account, ZERO) + ln.line_amount
    total = subtotal + tax_total

    entry = JournalEntry.objects.create(
        entity=debit_note.entity,
        entry_date=debit_note.debit_note_date,
        source_type="debit_note",
        source_id=debit_note.id,
        narration=debit_note.reason or "Debit note",
    )
    line_no = 1
    for account, amount in expense.items():
        JournalLine.objects.create(entry=entry, line_no=line_no, account=account, credit=amount)
        line_no += 1
    if tax_total > ZERO:
        JournalLine.objects.create(
            entry=entry,
            line_no=line_no,
            account=_vat_account(debit_note.entity, Account.AccountType.VAT_INPUT, "Input VAT"),
            credit=tax_total,
        )
        line_no += 1
    JournalLine.objects.create(
        entry=entry,
        line_no=line_no,
        account=debit_note.supplier.payable_account,
        debit=total,
        party_type="supplier",
        party_id=debit_note.supplier_id,
    )

    try:
        post_journal_entry(entry, user=user)
    except PostingError as exc:
        raise APError(str(exc)) from exc

    debit_note.debit_note_no = sequences.allocate(
        entity_id=debit_note.entity_id,
        code="DEBIT_NOTE",
        period_key=str(debit_note.debit_note_date.year),
        prefix="DN-",
        padding=6,
    ).formatted
    debit_note.subtotal = subtotal
    debit_note.tax_total = tax_total
    debit_note.total = total
    debit_note.status = BillStatus.POSTED
    debit_note.journal_entry = entry
    debit_note.save()

    audit_record(
        action="post",
        instance=debit_note,
        actor=user,
        entity_id=debit_note.entity_id,
        message=f"Posted {debit_note.debit_note_no} total={total}",
    )
    return debit_note


@transaction.atomic
def apply_payment_allocation(
    bill, *, amount, source_type, source_id, allocation_date=None, user=None
):
    """Apply a payment/debit-note/advance against a bill, reducing its balance."""
    if bill.status not in {BillStatus.POSTED, BillStatus.PARTIALLY_PAID}:
        raise APError(f"Cannot allocate against a bill in status {bill.status!r}.")
    amount = _q(amount)
    if amount <= ZERO:
        raise APError("Allocation amount must be positive.")
    if amount > bill.balance:
        raise APError(f"Allocation {amount} exceeds outstanding balance {bill.balance}.")

    PaymentAllocation.objects.create(
        entity=bill.entity,
        supplier=bill.supplier,
        source_type=source_type,
        source_id=source_id,
        bill=bill,
        amount_allocated=amount,
        allocation_date=allocation_date or date.today(),
    )
    bill.amount_allocated += amount
    bill.balance -= amount
    bill.status = BillStatus.PAID if bill.balance == ZERO else BillStatus.PARTIALLY_PAID
    bill.save(update_fields=["amount_allocated", "balance", "status", "updated_at"])
    return bill
