"""Post AR documents through the ledger engine (ADR-0007).

Sales invoice posting:
    DR  Accounts Receivable (customer control, party=customer)  = total
    CR  Sales Revenue (per revenue account)                     = line amounts
    CR  Output VAT (resolved by account_type, rate from TaxCode) = tax

VAT rate comes from ``accounts.TaxCode`` (never hardcoded); the Output VAT GL
account is resolved from the COA by ``account_type='vat_output'``.
"""

from collections import OrderedDict
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction

from apps.accounts.models import Account
from apps.ar.models import InvoiceStatus, ReceiptAllocation
from apps.audit.services import record as audit_record
from apps.core.services import sequences
from apps.ledger.models import JournalEntry, JournalLine
from apps.ledger.services.posting import PostingError, post_journal_entry

TWO_PLACES = Decimal("0.01")
ZERO = Decimal("0")


class ARError(ValueError):
    """Raised when an AR document cannot be posted or allocated."""


def _q(amount):
    return Decimal(amount).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _output_vat_account(entity):
    acct = Account.objects.filter(
        entity=entity, account_type=Account.AccountType.VAT_OUTPUT, is_active=True
    ).first()
    if acct is None:
        raise ARError("No Output VAT account (account_type='vat_output') in the chart of accounts.")
    return acct


def _compute_line(line):
    line.line_amount = _q(Decimal(line.quantity) * Decimal(line.unit_price))
    line.tax_rate = line.tax_code.rate if line.tax_code_id else ZERO
    line.tax_amount = _q(line.line_amount * Decimal(line.tax_rate) / Decimal(100))


@transaction.atomic
def post_invoice(invoice, *, user=None):
    if invoice.status != InvoiceStatus.DRAFT:
        raise ARError(f"Cannot post an invoice in status {invoice.status!r}.")
    lines = list(invoice.lines.select_related("revenue_account", "tax_code").all())
    if not lines:
        raise ARError("Invoice has no lines.")

    subtotal, tax_total = ZERO, ZERO
    revenue = OrderedDict()  # account -> amount
    for ln in lines:
        _compute_line(ln)
        ln.save(update_fields=["line_amount", "tax_rate", "tax_amount", "updated_at"])
        subtotal += ln.line_amount
        tax_total += ln.tax_amount
        revenue[ln.revenue_account] = revenue.get(ln.revenue_account, ZERO) + ln.line_amount
    total = subtotal + tax_total

    entry = JournalEntry.objects.create(
        entity=invoice.entity,
        branch=invoice.branch,
        entry_date=invoice.invoice_date,
        source_type="sales_invoice",
        source_id=invoice.id,
        currency=invoice.currency,
        narration=invoice.narration or f"Sales invoice {invoice.customer.code}",
    )
    JournalLine.objects.create(
        entry=entry,
        line_no=1,
        account=invoice.customer.receivable_account,
        debit=total,
        party_type="customer",
        party_id=invoice.customer_id,
    )
    line_no = 2
    for account, amount in revenue.items():
        JournalLine.objects.create(entry=entry, line_no=line_no, account=account, credit=amount)
        line_no += 1
    if tax_total > ZERO:
        JournalLine.objects.create(
            entry=entry,
            line_no=line_no,
            account=_output_vat_account(invoice.entity),
            credit=tax_total,
        )

    try:
        post_journal_entry(entry, user=user)
    except PostingError as exc:
        raise ARError(str(exc)) from exc

    invoice.invoice_no = sequences.allocate(
        entity_id=invoice.entity_id,
        code="SALES_INV",
        period_key=str(invoice.invoice_date.year),
        prefix="INV-",
        padding=6,
    ).formatted
    invoice.subtotal = subtotal
    invoice.tax_total = tax_total
    invoice.total = total
    invoice.amount_allocated = ZERO
    invoice.balance = total
    invoice.status = InvoiceStatus.POSTED
    invoice.journal_entry = entry
    invoice.save()

    audit_record(
        action="post",
        instance=invoice,
        actor=user,
        entity_id=invoice.entity_id,
        message=f"Posted {invoice.invoice_no} total={total}",
    )
    return invoice


@transaction.atomic
def apply_allocation(invoice, *, amount, source_type, source_id, allocation_date=None, user=None):
    """Apply a receipt/credit/advance against an invoice, reducing its balance."""
    if invoice.status not in {InvoiceStatus.POSTED, InvoiceStatus.PARTIALLY_PAID}:
        raise ARError(f"Cannot allocate against an invoice in status {invoice.status!r}.")
    amount = _q(amount)
    if amount <= ZERO:
        raise ARError("Allocation amount must be positive.")
    if amount > invoice.balance:
        raise ARError(f"Allocation {amount} exceeds outstanding balance {invoice.balance}.")

    ReceiptAllocation.objects.create(
        entity=invoice.entity,
        customer=invoice.customer,
        source_type=source_type,
        source_id=source_id,
        invoice=invoice,
        amount_allocated=amount,
        allocation_date=allocation_date or date.today(),
    )
    invoice.amount_allocated += amount
    invoice.balance -= amount
    invoice.status = InvoiceStatus.PAID if invoice.balance == ZERO else InvoiceStatus.PARTIALLY_PAID
    invoice.save(update_fields=["amount_allocated", "balance", "status", "updated_at"])
    return invoice


@transaction.atomic
def post_credit_note(credit_note, *, user=None):
    """Post a credit note: DR Revenue / DR Output VAT / CR Accounts Receivable."""
    if credit_note.status != InvoiceStatus.DRAFT:
        raise ARError(f"Cannot post a credit note in status {credit_note.status!r}.")
    lines = list(credit_note.lines.select_related("revenue_account", "tax_code").all())
    if not lines:
        raise ARError("Credit note has no lines.")

    subtotal, tax_total = ZERO, ZERO
    revenue = OrderedDict()
    for ln in lines:
        ln.line_amount = _q(ln.line_amount)
        ln.tax_rate = ln.tax_code.rate if ln.tax_code_id else ZERO
        ln.tax_amount = _q(ln.line_amount * Decimal(ln.tax_rate) / Decimal(100))
        ln.save(update_fields=["line_amount", "tax_rate", "tax_amount", "updated_at"])
        subtotal += ln.line_amount
        tax_total += ln.tax_amount
        revenue[ln.revenue_account] = revenue.get(ln.revenue_account, ZERO) + ln.line_amount
    total = subtotal + tax_total

    entry = JournalEntry.objects.create(
        entity=credit_note.entity,
        entry_date=credit_note.credit_note_date,
        source_type="credit_note",
        source_id=credit_note.id,
        narration=credit_note.reason or "Credit note",
    )
    line_no = 1
    for account, amount in revenue.items():
        JournalLine.objects.create(entry=entry, line_no=line_no, account=account, debit=amount)
        line_no += 1
    if tax_total > ZERO:
        JournalLine.objects.create(
            entry=entry,
            line_no=line_no,
            account=_output_vat_account(credit_note.entity),
            debit=tax_total,
        )
        line_no += 1
    JournalLine.objects.create(
        entry=entry,
        line_no=line_no,
        account=credit_note.customer.receivable_account,
        credit=total,
        party_type="customer",
        party_id=credit_note.customer_id,
    )

    try:
        post_journal_entry(entry, user=user)
    except PostingError as exc:
        raise ARError(str(exc)) from exc

    credit_note.credit_note_no = sequences.allocate(
        entity_id=credit_note.entity_id,
        code="CREDIT_NOTE",
        period_key=str(credit_note.credit_note_date.year),
        prefix="CN-",
        padding=6,
    ).formatted
    credit_note.subtotal = subtotal
    credit_note.tax_total = tax_total
    credit_note.total = total
    credit_note.status = InvoiceStatus.POSTED
    credit_note.journal_entry = entry
    credit_note.save()

    audit_record(
        action="post",
        instance=credit_note,
        actor=user,
        entity_id=credit_note.entity_id,
        message=f"Posted {credit_note.credit_note_no} total={total}",
    )
    return credit_note
