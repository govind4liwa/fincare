"""AP allocation helpers — settle payments / debit notes against open bills.

Mirror of the AR allocation subledger: applying an allocation records a
``PaymentAllocation`` link and reduces the bill balance; the GL was already
posted by the payment voucher / bill, so no journal entry is written here.
"""

from decimal import Decimal

from django.db.models import Sum

from apps.ap.models import DebitNote, PaymentAllocation
from apps.ap.services.post import APError, apply_payment_allocation
from apps.vouchers.models import Voucher, VoucherStatus, VoucherType

ZERO = Decimal("0")
PAYMENT_VOUCHER = PaymentAllocation.Source.PAYMENT_VOUCHER
DEBIT_NOTE = PaymentAllocation.Source.DEBIT_NOTE


def _source_total(source_type, source_id):
    if source_type == PAYMENT_VOUCHER:
        v = Voucher.objects.filter(id=source_id).first()
        return Decimal(v.amount) if v else ZERO
    if source_type == DEBIT_NOTE:
        dn = DebitNote.objects.filter(id=source_id).first()
        return Decimal(dn.total) if dn else ZERO
    return ZERO


def available_amount(source_type, source_id):
    allocated = (
        PaymentAllocation.objects.filter(source_id=source_id).aggregate(
            total=Sum("amount_allocated")
        )["total"]
        or ZERO
    )
    return _source_total(source_type, source_id) - allocated


def supplier_sources(entity, supplier):
    """Posted payments (tagged to the supplier) + debit notes with money left to apply."""
    sources = []
    payments = Voucher.objects.filter(
        entity=entity,
        voucher_type=VoucherType.PAYMENT,
        status=VoucherStatus.POSTED,
        party_id=supplier.id,
    )
    for v in payments:
        avail = available_amount(PAYMENT_VOUCHER, v.id)
        if avail > ZERO:
            sources.append(
                {
                    "source_type": PAYMENT_VOUCHER,
                    "source_id": str(v.id),
                    "label": v.voucher_no or "Payment (draft)",
                    "date": v.voucher_date,
                    "total": str(v.amount),
                    "available": str(avail),
                }
            )
    for dn in DebitNote.objects.filter(entity=entity, supplier=supplier, status="posted"):
        avail = available_amount(DEBIT_NOTE, dn.id)
        if avail > ZERO:
            sources.append(
                {
                    "source_type": DEBIT_NOTE,
                    "source_id": str(dn.id),
                    "label": dn.debit_note_no or "Debit note (draft)",
                    "date": dn.debit_note_date,
                    "total": str(dn.total),
                    "available": str(avail),
                }
            )
    return sources


def allocate(bill, *, source_type, source_id, amount, user=None):
    if source_type not in {PAYMENT_VOUCHER, DEBIT_NOTE}:
        raise APError("Unsupported allocation source.")
    if source_type == PAYMENT_VOUCHER:
        v = Voucher.objects.filter(
            id=source_id, entity=bill.entity, party_id=bill.supplier_id
        ).first()
        if v is None:
            raise APError("Payment not found for this supplier.")
    else:
        dn = DebitNote.objects.filter(
            id=source_id, entity=bill.entity, supplier=bill.supplier
        ).first()
        if dn is None:
            raise APError("Debit note not found for this supplier.")

    amount = Decimal(amount)
    if amount > available_amount(source_type, source_id):
        raise APError("Amount exceeds the source's unallocated balance.")

    return apply_payment_allocation(
        bill, amount=amount, source_type=source_type, source_id=source_id, user=user
    )
