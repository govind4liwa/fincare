"""Platform settlement reconciliation + posting through the ledger engine.

Trip revenue (see ``bookings``) leaves a debit (receivable) in the platform's
clearing account: clearing balance = Σ(fare − commission) for the period. When the
platform pays the net to the bank, a settlement clears that balance and books the
difference to an adjustment account:

    DR  Bank                  = net_received
    CR  Platform Clearing     = gross_earnings − commission        (clears receivable)
    CR  Adjustment account    = net_received − clearing  (if > 0, surplus income)
    DR  Adjustment account    = clearing − net_received  (if > 0, shortfall cost)

``reconcile`` aggregates staged ``EarningImport`` rows into the settlement's
statement totals (gross/commission/net) and flags them matched, before posting.
"""

from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.db.models import Sum

from apps.audit.services import record as audit_record
from apps.core.services import sequences
from apps.ledger.models import JournalEntry, JournalLine
from apps.ledger.services.posting import PostingError, post_journal_entry
from apps.platforms.models import EarningImport, PlatformDocStatus, PlatformSettlement

TWO_PLACES = Decimal("0.01")
ZERO = Decimal("0.00")


class PlatformError(ValueError):
    """Raised when a platform settlement cannot be reconciled or posted."""


def _q(amount):
    return Decimal(amount).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


@transaction.atomic
def reconcile(settlement: PlatformSettlement, *, user=None):
    """Aggregate staged earning imports into the settlement totals; flag matched.

    ``net_received`` (the bank-confirmed amount) is left as entered — the variance
    is the gap between the statement's implied net and what the bank received.
    """
    if settlement.status not in {PlatformDocStatus.DRAFT, PlatformDocStatus.RECONCILED}:
        raise PlatformError(f"Cannot reconcile a settlement in status {settlement.status!r}.")

    imports = EarningImport.objects.filter(
        entity=settlement.entity,
        platform=settlement.platform,
        earning_date__gte=settlement.period_start,
        earning_date__lte=settlement.period_end,
    )
    agg = imports.aggregate(gross=Sum("gross"), commission=Sum("commission"), net=Sum("net"))
    settlement.gross_earnings = _q(agg["gross"] or ZERO)
    settlement.commission = _q(agg["commission"] or ZERO)
    statement_net = _q(agg["net"] or ZERO)
    # Variance = statement net vs. what the platform actually paid to the bank.
    settlement.variance = _q(settlement.net_received - statement_net)
    settlement.status = PlatformDocStatus.RECONCILED
    settlement.save(
        update_fields=[
            "gross_earnings",
            "commission",
            "variance",
            "status",
            "updated_at",
        ]
    )
    imports.update(settlement=settlement, matched=True)
    return settlement


@transaction.atomic
def post_settlement(settlement: PlatformSettlement, *, user=None):
    if settlement.status not in {PlatformDocStatus.DRAFT, PlatformDocStatus.RECONCILED}:
        raise PlatformError(f"Cannot post a settlement in status {settlement.status!r}.")
    if settlement.bank_account_id is None:
        raise PlatformError("Settlement requires a bank_account to receive the net.")

    gross = _q(settlement.gross_earnings)
    commission = _q(settlement.commission)
    net_received = _q(settlement.net_received)
    clearing = _q(gross - commission)  # receivable accrued from trips
    adjustment = _q(net_received - clearing)  # signed: + surplus income / - shortfall cost
    if adjustment != ZERO and settlement.adjustment_account_id is None:
        raise PlatformError("A non-zero variance requires an adjustment_account.")

    platform_id = settlement.platform_id
    rows = [
        {
            "account": settlement.bank_account.gl_account,
            "debit": net_received,
            "description": "Platform settlement received",
            "platform_id": platform_id,
        },
        {
            "account": settlement.platform.clearing_account,
            "credit": clearing,
            "description": "Clear platform receivable",
            "platform_id": platform_id,
        },
    ]
    if adjustment > ZERO:
        rows.append(
            {
                "account": settlement.adjustment_account,
                "credit": adjustment,
                "description": "Settlement surplus",
                "platform_id": platform_id,
            }
        )
    elif adjustment < ZERO:
        rows.append(
            {
                "account": settlement.adjustment_account,
                "debit": -adjustment,
                "description": "Settlement shortfall",
                "platform_id": platform_id,
            }
        )

    entry = JournalEntry.objects.create(
        entity=settlement.entity,
        entry_date=settlement.settlement_date,
        source_type="platform_setl",
        source_id=settlement.id,
        currency=settlement.bank_account.currency or settlement.entity.base_currency,
        narration=f"Platform settlement {settlement.platform.name}",
    )
    for line_no, row in enumerate(rows, start=1):
        JournalLine.objects.create(
            entry=entry,
            line_no=line_no,
            account=row["account"],
            description=row.get("description", ""),
            debit=row.get("debit", ZERO),
            credit=row.get("credit", ZERO),
            platform_id=row.get("platform_id"),
        )
    try:
        post_journal_entry(entry, user=user)
    except PostingError as exc:
        raise PlatformError(str(exc)) from exc

    settlement.variance = _q(adjustment - _q(settlement.adjustments))
    settlement.settlement_no = sequences.allocate(
        entity_id=settlement.entity_id,
        code="PLATFORM_SETTLEMENT",
        period_key=str(settlement.settlement_date.year),
        prefix="PSL-",
        padding=6,
    ).formatted
    settlement.journal_entry = entry
    settlement.status = PlatformDocStatus.POSTED
    settlement.save()

    audit_record(
        action="post",
        instance=settlement,
        actor=user,
        entity_id=settlement.entity_id,
        message=(
            f"Posted {settlement.settlement_no} gross={gross} comm={commission} "
            f"net={net_received} adj={adjustment}"
        ),
    )
    return settlement
