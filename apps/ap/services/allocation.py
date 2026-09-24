"""AP allocation helpers — settle payments / debit notes against open bills.

Mirror of the AR allocation subledger: applying an allocation records a
``PaymentAllocation`` link and reduces the bill balance; the GL was already
posted by the payment voucher / bill, so no journal entry is written here.

Un-allocating restores both sides: it marks the ``PaymentAllocation`` row
reversed (never deleted, so the history stays auditable) and gives the amount
back to the bill's balance and the source's unallocated amount.
"""

from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.ap.models import BillStatus, DebitNote, PaymentAllocation, PurchaseBill
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
        PaymentAllocation.objects.filter(source_id=source_id, reversed_at__isnull=True).aggregate(
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


def _validate_source(entity, supplier, source_type, source_id):
    """Shared source lookup, used by both the single and bulk allocation paths."""
    if source_type not in {PAYMENT_VOUCHER, DEBIT_NOTE}:
        raise APError("Unsupported allocation source.")
    if source_type == PAYMENT_VOUCHER:
        v = Voucher.objects.filter(id=source_id, entity=entity, party_id=supplier.id).first()
        if v is None:
            raise APError("Payment not found for this supplier.")
    else:
        dn = DebitNote.objects.filter(id=source_id, entity=entity, supplier=supplier).first()
        if dn is None:
            raise APError("Debit note not found for this supplier.")


def allocate(bill, *, source_type, source_id, amount, user=None):
    _validate_source(bill.entity, bill.supplier, source_type, source_id)
    amount = Decimal(amount)
    if amount > available_amount(source_type, source_id):
        raise APError("Amount exceeds the source's unallocated balance.")

    return apply_payment_allocation(
        bill, amount=amount, source_type=source_type, source_id=source_id, user=user
    )


@transaction.atomic
def allocate_bulk(entity, supplier, *, source_type, source_id, lines, user=None):
    """Apply one source across several bills in a single atomic action.

    ``lines`` is ``[{"bill_id": ..., "amount": ...}, ...]``. The source's
    unallocated amount is checked once against the combined total, so a bulk
    submit can't spend more of the source than it actually has across its own
    lines. Bills are locked in primary-key order (mirroring the driver
    clearing pattern) so two concurrent bulk allocations touching an overlapping
    bill can't both apply against the same stale balance.
    """
    _validate_source(entity, supplier, source_type, source_id)
    if not lines:
        raise APError("At least one bill line is required.")

    parsed = [(str(line["bill_id"]), Decimal(line["amount"])) for line in lines]
    if len({bill_id for bill_id, _ in parsed}) != len(parsed):
        raise APError("Each bill can only appear once per bulk allocation.")
    if any(amount <= ZERO for _, amount in parsed):
        raise APError("Allocation amounts must be positive.")

    total = sum((amount for _, amount in parsed), ZERO)
    if total > available_amount(source_type, source_id):
        raise APError("Total exceeds the source's unallocated balance.")

    bill_ids = [bill_id for bill_id, _ in parsed]
    locked = {
        str(b.id): b
        for b in PurchaseBill.objects.select_for_update()
        .filter(id__in=bill_ids, entity=entity, supplier=supplier)
        .order_by("id")
    }
    if len(locked) != len(bill_ids):
        raise APError("One or more bills were not found for this supplier.")

    for bill_id, amount in parsed:
        apply_payment_allocation(
            locked[bill_id], amount=amount, source_type=source_type, source_id=source_id, user=user
        )
    return [locked[bill_id] for bill_id in bill_ids]


@transaction.atomic
def unallocate(bill, allocation_id, *, user=None):
    """Reverse a previously applied allocation, restoring the bill's balance
    and freeing the amount back up on the source it came from."""
    try:
        alloc = PaymentAllocation.objects.select_for_update().get(id=allocation_id, bill=bill)
    except PaymentAllocation.DoesNotExist as exc:
        raise APError("Allocation not found for this bill.") from exc
    if alloc.reversed_at is not None:
        raise APError("This allocation was already reversed.")

    locked_bill = PurchaseBill.objects.select_for_update().get(id=bill.id)
    amount = alloc.amount_allocated
    locked_bill.amount_allocated -= amount
    locked_bill.balance += amount
    locked_bill.status = (
        BillStatus.PARTIALLY_PAID if locked_bill.amount_allocated > ZERO else BillStatus.POSTED
    )
    locked_bill.save(update_fields=["amount_allocated", "balance", "status", "updated_at"])

    alloc.reversed_at = timezone.now()
    alloc.reversed_by = user
    alloc.save(update_fields=["reversed_at", "reversed_by", "updated_at"])
    return locked_bill
