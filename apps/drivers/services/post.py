"""Post driver financial events (advance, settlement) through the ledger engine.

Advance:
    DR  Driver Advance (asset, driver dim)   = amount
    CR  Bank                                 = amount

Settlement (net = gross − Σ deductions):
    DR  gross account (driver/vehicle dim)   = gross
    CR  each deduction account               = deduction amount
    CR  bank                                 = net      (net > 0)
    DR  bank                                 = -net     (net < 0, driver pays in)
"""

from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction

from apps.audit.services import record as audit_record
from apps.core.services import sequences
from apps.drivers.models import Advance, DriverDocStatus, Settlement
from apps.ledger.models import JournalEntry, JournalLine
from apps.ledger.services.posting import PostingError, post_journal_entry

TWO_PLACES = Decimal("0.01")
ZERO = Decimal("0.00")


class DriverError(ValueError):
    """Raised when a driver document cannot be posted."""


def _q(amount):
    return Decimal(amount).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _post_rows(*, entity, date, source_type, source_id, currency, narration, rows, user):
    entry = JournalEntry.objects.create(
        entity=entity,
        entry_date=date,
        source_type=source_type,
        source_id=source_id,
        currency=currency,
        narration=narration,
    )
    for line_no, row in enumerate(rows, start=1):
        JournalLine.objects.create(
            entry=entry,
            line_no=line_no,
            account=row["account"],
            description=row.get("description", ""),
            debit=row.get("debit", ZERO),
            credit=row.get("credit", ZERO),
            driver_id=row.get("driver_id"),
            vehicle_id=row.get("vehicle_id"),
        )
    try:
        post_journal_entry(entry, user=user)
    except PostingError as exc:
        raise DriverError(str(exc)) from exc
    return entry


@transaction.atomic
def post_advance(advance: Advance, *, user=None):
    if advance.status != DriverDocStatus.DRAFT:
        raise DriverError(f"Cannot post an advance in status {advance.status!r}.")
    amount = _q(advance.amount)
    if amount <= ZERO:
        raise DriverError("Advance amount must be positive.")
    if advance.bank_account_id is None:
        raise DriverError("Advance requires a bank_account to pay from.")

    rows = [
        {
            "account": advance.advance_account,
            "debit": amount,
            "description": "Driver advance",
            "driver_id": advance.driver_id,
        },
        {
            "account": advance.bank_account.gl_account,
            "credit": amount,
            "description": "Advance paid",
        },
    ]
    entry = _post_rows(
        entity=advance.entity,
        date=advance.advance_date,
        source_type="driver_advance",
        source_id=advance.id,
        currency=advance.bank_account.currency or advance.entity.base_currency,
        narration=f"Advance to {advance.driver.code}",
        rows=rows,
        user=user,
    )

    advance.balance = amount
    advance.recovered_amount = ZERO
    advance.advance_no = sequences.allocate(
        entity_id=advance.entity_id,
        code="DRIVER_ADVANCE",
        period_key=str(advance.advance_date.year),
        prefix="ADV-",
        padding=6,
    ).formatted
    advance.journal_entry = entry
    advance.status = DriverDocStatus.POSTED
    advance.save()

    audit_record(
        action="post",
        instance=advance,
        actor=user,
        entity_id=advance.entity_id,
        message=f"Posted {advance.advance_no} amount={amount}",
    )
    return advance


@transaction.atomic
def post_settlement(settlement: Settlement, *, user=None):
    if settlement.status != DriverDocStatus.DRAFT:
        raise DriverError(f"Cannot post a settlement in status {settlement.status!r}.")
    gross = _q(settlement.gross_amount)
    if gross <= ZERO:
        raise DriverError("Gross amount must be positive.")

    deductions = list(settlement.deductions.select_related("account").all())
    total_ded = sum((_q(d.amount) for d in deductions), ZERO)
    if total_ded > gross:
        raise DriverError(f"Deductions {total_ded} exceed gross {gross}.")
    net = _q(gross - total_ded)

    rows = [
        {
            "account": settlement.gross_account,
            "debit": gross,
            "description": "Driver earnings",
            "driver_id": settlement.driver_id,
            "vehicle_id": settlement.vehicle_id,
        },
    ]
    for d in deductions:
        rows.append(
            {
                "account": d.account,
                "credit": _q(d.amount),
                "description": f"{d.get_kind_display()} recovery",
                "driver_id": settlement.driver_id,
            }
        )
    pay_gl = settlement.pay_account.gl_account
    if net > ZERO:
        rows.append({"account": pay_gl, "credit": net, "description": "Net payout"})
    elif net < ZERO:
        rows.append({"account": pay_gl, "debit": -net, "description": "Driver settlement receipt"})

    entry = _post_rows(
        entity=settlement.entity,
        date=settlement.settlement_date,
        source_type="drv_settlement",
        source_id=settlement.id,
        currency=settlement.pay_account.currency or settlement.entity.base_currency,
        narration=f"Settlement {settlement.driver.code} {settlement.period_start}..{settlement.period_end}",
        rows=rows,
        user=user,
    )

    # Recover advances linked to deduction lines.
    for d in deductions:
        if d.advance_id:
            adv = d.advance
            adv.recovered_amount = _q(adv.recovered_amount + _q(d.amount))
            adv.balance = _q(adv.amount - adv.recovered_amount)
            adv.save(update_fields=["recovered_amount", "balance", "updated_at"])

    settlement.total_deductions = total_ded
    settlement.net_amount = net
    settlement.settlement_no = sequences.allocate(
        entity_id=settlement.entity_id,
        code="DRIVER_SETTLEMENT",
        period_key=str(settlement.settlement_date.year),
        prefix="SETL-",
        padding=6,
    ).formatted
    settlement.journal_entry = entry
    settlement.status = DriverDocStatus.POSTED
    settlement.save()

    audit_record(
        action="post",
        instance=settlement,
        actor=user,
        entity_id=settlement.entity_id,
        message=f"Posted {settlement.settlement_no} gross={gross} ded={total_ded} net={net}",
    )
    return settlement
