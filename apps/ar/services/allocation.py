"""AR allocation helpers — settle receipts / credit notes against open invoices.

Allocation is a **subledger** operation: the GL was already posted when the
receipt voucher and the invoice were posted, so applying an allocation only
records a ``ReceiptAllocation`` link and reduces the invoice balance — it never
writes a journal entry. A source can be spread across several invoices, capped
by its own unallocated amount.
"""

from decimal import Decimal

from django.db.models import Sum

from apps.ar.models import CreditNote, ReceiptAllocation
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
    """Unallocated amount of a source = its total minus everything already applied."""
    allocated = (
        ReceiptAllocation.objects.filter(source_id=source_id).aggregate(
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


def allocate(invoice, *, source_type, source_id, amount, user=None):
    """Validate the source, then apply it against ``invoice`` (subledger only)."""
    if source_type not in {RECEIPT_VOUCHER, CREDIT_NOTE}:
        raise ARError("Unsupported allocation source.")
    if source_type == RECEIPT_VOUCHER:
        v = Voucher.objects.filter(
            id=source_id, entity=invoice.entity, party_id=invoice.customer_id
        ).first()
        if v is None:
            raise ARError("Receipt not found for this customer.")
    else:
        cn = CreditNote.objects.filter(
            id=source_id, entity=invoice.entity, customer=invoice.customer
        ).first()
        if cn is None:
            raise ARError("Credit note not found for this customer.")

    amount = Decimal(amount)
    if amount > available_amount(source_type, source_id):
        raise ARError("Amount exceeds the source's unallocated balance.")

    return apply_allocation(
        invoice, amount=amount, source_type=source_type, source_id=source_id, user=user
    )
