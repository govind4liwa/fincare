"""Recognise trip revenue (periodic aggregate) and bill contracts through AR.

Aggregate trip revenue (per platform, grouped by vehicle/driver) — one JE:
    DR  Platform Clearing      = Σ net_revenue (fare − commission)   [dims]
    DR  Platform Commission    = Σ commission                        [dims]
    CR  Platform Revenue       = Σ fare                              [dims]
Lines carry the vehicle_id / driver_id / platform_id profitability dimensions.

Contract billing delegates to ``ar.services.post.post_invoice`` — a contract
generates one ``ar.SalesInvoice`` per cycle (DR AR / CR Revenue / CR Output VAT).
"""

from collections import OrderedDict
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction

from apps.audit.services import record as audit_record
from apps.bookings.models import Contract, TripStatus
from apps.ledger.models import JournalEntry, JournalLine
from apps.ledger.services.posting import PostingError, post_journal_entry

TWO_PLACES = Decimal("0.01")
ZERO = Decimal("0.00")


class BookingError(ValueError):
    """Raised when trip revenue or a contract invoice cannot be posted."""


def _q(amount):
    return Decimal(amount).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


@transaction.atomic
def post_aggregate_revenue(platform, trips, *, date, user=None):
    """Recognise revenue for a batch of platform trips as one aggregate JE.

    ``trips`` are grouped by (vehicle, driver); each group contributes a
    clearing / commission / revenue line-set carrying its profitability dims.
    """
    trips = list(trips)
    if not trips:
        raise BookingError("No trips to post.")

    groups = OrderedDict()  # (vehicle_id, driver_id) -> [fare, commission, net]
    for t in trips:
        if t.platform_id != platform.id:
            raise BookingError(f"Trip {t.id} does not belong to platform {platform.id}.")
        if t.status != TripStatus.RECORDED:
            raise BookingError(f"Trip {t.id} is {t.status!r}, expected 'recorded'.")
        key = (t.vehicle_id, t.driver_id)
        fare, comm = _q(t.fare), _q(t.commission)
        bucket = groups.setdefault(key, [ZERO, ZERO, ZERO])
        bucket[0] += fare
        bucket[1] += comm
        bucket[2] += _q(fare - comm)

    rows = []
    for (vehicle_id, driver_id), (fare, comm, net) in groups.items():
        dims = {"vehicle_id": vehicle_id, "driver_id": driver_id, "platform_id": platform.id}
        rows.append(
            {
                "account": platform.clearing_account,
                "debit": net,
                "description": "Platform receivable",
                **dims,
            }
        )
        if comm > ZERO:
            rows.append(
                {
                    "account": platform.commission_account,
                    "debit": comm,
                    "description": "Platform commission",
                    **dims,
                }
            )
        rows.append(
            {
                "account": platform.revenue_account,
                "credit": fare,
                "description": "Platform earnings",
                **dims,
            }
        )

    entry = JournalEntry.objects.create(
        entity=platform.entity,
        entry_date=date,
        source_type="trip_revenue",
        source_id=platform.id,
        currency=platform.entity.base_currency,
        narration=f"Trip revenue {platform.name} ({len(trips)} trips)",
    )
    for line_no, row in enumerate(rows, start=1):
        JournalLine.objects.create(
            entry=entry,
            line_no=line_no,
            account=row["account"],
            description=row.get("description", ""),
            debit=row.get("debit", ZERO),
            credit=row.get("credit", ZERO),
            vehicle_id=row.get("vehicle_id"),
            driver_id=row.get("driver_id"),
            platform_id=row.get("platform_id"),
        )
    try:
        post_journal_entry(entry, user=user)
    except PostingError as exc:
        raise BookingError(str(exc)) from exc

    for t in trips:
        t.compute_net()
        t.revenue_journal_entry = entry
        t.status = TripStatus.INVOICED
        t.save(update_fields=["net_revenue", "revenue_journal_entry", "status", "updated_at"])

    audit_record(
        action="post",
        instance=trips[0],
        actor=user,
        entity_id=platform.entity_id,
        message=f"Aggregate trip revenue {platform.name}: {len(trips)} trips via {entry.entry_no}",
    )
    return entry


@transaction.atomic
def generate_invoice(contract: Contract, *, invoice_date, period_label="", user=None):
    """Generate and post one ``ar.SalesInvoice`` for a contract billing cycle."""
    from apps.ar.models import SalesInvoice, SalesInvoiceLine
    from apps.ar.services.post import post_invoice

    if contract.status != Contract.Status.ACTIVE:
        raise BookingError(f"Cannot bill a contract in status {contract.status!r}.")
    amount = _q(contract.monthly_amount)
    if amount <= ZERO:
        raise BookingError("Contract amount must be positive.")

    invoice = SalesInvoice.objects.create(
        entity=contract.entity,
        customer=contract.customer,
        invoice_date=invoice_date,
        place_of_supply=contract.customer.emirate,
        currency=contract.entity.base_currency,
        narration=f"Contract {contract.contract_no} {period_label}".strip(),
    )
    SalesInvoiceLine.objects.create(
        invoice=invoice,
        line_no=1,
        revenue_account=contract.revenue_account,
        description=f"Contract {contract.contract_no} {period_label}".strip(),
        quantity=1,
        unit_price=amount,
        tax_code=contract.tax_code,
        vehicle_id=contract.vehicle_id,
        driver_id=contract.driver_id,
    )
    return post_invoice(invoice, user=user)
