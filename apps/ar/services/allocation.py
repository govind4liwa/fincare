"""AR allocation helpers — settle receipts / credit notes against open invoices.

Allocation is a **subledger** operation: the GL was already posted when the
receipt voucher and the invoice were posted, so applying an allocation only
records a ``ReceiptAllocation`` link and reduces the invoice balance — it never
writes a journal entry. A source can be spread across several invoices, capped
by its own unallocated amount.

Un-allocating restores both sides: it marks the ``ReceiptAllocation`` row
reversed (never deleted, so the history stays auditable) and gives the amount
back to the invoice's balance and the source's unallocated amount.
"""

from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.ar.models import CreditNote, InvoiceStatus, ReceiptAllocation, SalesInvoice
from apps.ar.services.post import ARError, apply_allocation
from apps.vouchers.models import Voucher, VoucherStatus, VoucherType

ZERO = Decimal("0")
RECEIPT_VOUCHER = ReceiptAllocation.Source.RECEIPT_VOUCHER
CREDIT_NOTE = ReceiptAllocation.Source.CREDIT_NOTE


def _source_total(source_type, source_id):
    """The document total behind an allocation source (0 if not found/eligible)."""
    if source_type == RECEIPT_VOUCHER:
        v = Voucher.objects.filter(id=source_id).first()
        return Decimal(v.amount) if v else ZERO
    if source_type == CREDIT_NOTE:
        cn = CreditNote.objects.filter(id=source_id).first()
        return Decimal(cn.total) if cn else ZERO
    return ZERO


def available_amount(source_type, source_id):
    """Unallocated amount of a source = its total minus everything still applied."""
    allocated = (
        ReceiptAllocation.objects.filter(source_id=source_id, reversed_at__isnull=True).aggregate(
            total=Sum("amount_allocated")
        )["total"]
        or ZERO
    )
    return _source_total(source_type, source_id) - allocated


def customer_sources(entity, customer):
    """Posted receipts (tagged to the customer) + credit notes with money left to apply."""
    sources = []
    receipts = Voucher.objects.filter(
        entity=entity,
        voucher_type=VoucherType.RECEIPT,
        status=VoucherStatus.POSTED,
        party_id=customer.id,
    )
    for v in receipts:
        avail = available_amount(RECEIPT_VOUCHER, v.id)
        if avail > ZERO:
            sources.append(
                {
                    "source_type": RECEIPT_VOUCHER,
                    "source_id": str(v.id),
                    "label": v.voucher_no or "Receipt (draft)",
                    "date": v.voucher_date,
                    "total": str(v.amount),
                    "available": str(avail),
                }
            )
    for cn in CreditNote.objects.filter(entity=entity, customer=customer, status="posted"):
        avail = available_amount(CREDIT_NOTE, cn.id)
        if avail > ZERO:
            sources.append(
                {
                    "source_type": CREDIT_NOTE,
                    "source_id": str(cn.id),
                    "label": cn.credit_note_no or "Credit note (draft)",
                    "date": cn.credit_note_date,
                    "total": str(cn.total),
                    "available": str(avail),
                }
            )
    return sources


def _validate_source(entity, customer, source_type, source_id):
    """Shared source lookup, used by both the single and bulk allocation paths."""
    if source_type not in {RECEIPT_VOUCHER, CREDIT_NOTE}:
        raise ARError("Unsupported allocation source.")
    if source_type == RECEIPT_VOUCHER:
        v = Voucher.objects.filter(id=source_id, entity=entity, party_id=customer.id).first()
        if v is None:
            raise ARError("Receipt not found for this customer.")
    else:
        cn = CreditNote.objects.filter(id=source_id, entity=entity, customer=customer).first()
        if cn is None:
            raise ARError("Credit note not found for this customer.")


def allocate(invoice, *, source_type, source_id, amount, user=None):
    """Validate the source, then apply it against ``invoice`` (subledger only)."""
    _validate_source(invoice.entity, invoice.customer, source_type, source_id)
    amount = Decimal(amount)
    if amount > available_amount(source_type, source_id):
        raise ARError("Amount exceeds the source's unallocated balance.")

    return apply_allocation(
        invoice, amount=amount, source_type=source_type, source_id=source_id, user=user
    )


@transaction.atomic
def allocate_bulk(entity, customer, *, source_type, source_id, lines, user=None):
    """Apply one source across several invoices in a single atomic action.

    ``lines`` is ``[{"invoice_id": ..., "amount": ...}, ...]``. The source's
    unallocated amount is checked once against the combined total, so a bulk
    submit can't spend more of the source than it actually has across its own
    lines. Invoices are locked in primary-key order (mirroring the driver
    clearing pattern) so two concurrent bulk allocations touching an overlapping
    invoice can't both apply against the same stale balance.
    """
    _validate_source(entity, customer, source_type, source_id)
    if not lines:
        raise ARError("At least one invoice line is required.")

    parsed = [(str(line["invoice_id"]), Decimal(line["amount"])) for line in lines]
    if len({invoice_id for invoice_id, _ in parsed}) != len(parsed):
        raise ARError("Each invoice can only appear once per bulk allocation.")
    if any(amount <= ZERO for _, amount in parsed):
        raise ARError("Allocation amounts must be positive.")

    total = sum((amount for _, amount in parsed), ZERO)
    if total > available_amount(source_type, source_id):
        raise ARError("Total exceeds the source's unallocated balance.")

    invoice_ids = [invoice_id for invoice_id, _ in parsed]
    locked = {
        str(inv.id): inv
        for inv in SalesInvoice.objects.select_for_update()
        .filter(id__in=invoice_ids, entity=entity, customer=customer)
        .order_by("id")
    }
    if len(locked) != len(invoice_ids):
        raise ARError("One or more invoices were not found for this customer.")

    for invoice_id, amount in parsed:
        apply_allocation(
            locked[invoice_id],
            amount=amount,
            source_type=source_type,
            source_id=source_id,
            user=user,
        )
    return [locked[invoice_id] for invoice_id in invoice_ids]


@transaction.atomic
def unallocate(invoice, allocation_id, *, user=None):
    """Reverse a previously applied allocation, restoring the invoice's balance
    and freeing the amount back up on the source it came from."""
    try:
        alloc = ReceiptAllocation.objects.select_for_update().get(id=allocation_id, invoice=invoice)
    except ReceiptAllocation.DoesNotExist as exc:
        raise ARError("Allocation not found for this invoice.") from exc
    if alloc.reversed_at is not None:
        raise ARError("This allocation was already reversed.")

    locked_invoice = SalesInvoice.objects.select_for_update().get(id=invoice.id)
    amount = alloc.amount_allocated
    locked_invoice.amount_allocated -= amount
    locked_invoice.balance += amount
    locked_invoice.status = (
        InvoiceStatus.PARTIALLY_PAID
        if locked_invoice.amount_allocated > ZERO
        else InvoiceStatus.POSTED
    )
    locked_invoice.save(update_fields=["amount_allocated", "balance", "status", "updated_at"])

    alloc.reversed_at = timezone.now()
    alloc.reversed_by = user
    alloc.save(update_fields=["reversed_at", "reversed_by", "updated_at"])
    return locked_invoice
