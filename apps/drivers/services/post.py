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
from apps.settings.services.driver_accounting import (
    DriverAccountingConfigError,
    resolve_receivable_account,
)

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
    bank_account = advance.bank_account if advance.bank_account_id else None
    if bank_account is None:
        raise DriverError("Advance requires a bank_account to pay from.")

    rows = [
        {
            "account": advance.advance_account,
            "debit": amount,
            "description": "Driver advance",
            "driver_id": advance.driver_id,
        },
        {
            "account": bank_account.gl_account,
            "credit": amount,
            "description": "Advance paid",
        },
    ]
    entry = _post_rows(
        entity=advance.entity,
        date=advance.advance_date,
        source_type="driver_advance",
        source_id=advance.id,
        currency=bank_account.currency or advance.entity.base_currency,
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


def _resolve_receivable_account(settlement: Settlement):
    """The entity's configured Driver Receivable account for a negative net.

    The account is never chosen per-settlement: each entity configures exactly
    one (``settings.DriverAccountingConfig``), and configuring it *is* the
    approval. A settlement may carry the account for historical audit, but it
    must equal the configured one — any other account, however plausible, is
    rejected. It is never defaulted from ``pay_account``, which is a bank
    account: booking a shortfall there would assert a receipt that never
    happened.
    """
    try:
        configured = resolve_receivable_account(settlement.entity)
    except DriverAccountingConfigError as exc:
        raise DriverError(str(exc)) from exc

    supplied = settlement.driver_receivable_account
    if supplied is not None and supplied.id != configured.id:
        raise DriverError(
            "Driver receivable account does not match the entity's configured "
            f"account ({configured.code})."
        )
    if supplied is None:
        # Persist what was actually used, so later configuration changes never
        # rewrite the history of this posting.
        settlement.driver_receivable_account = configured
    return configured


@transaction.atomic
def post_settlement(settlement: Settlement, *, user=None):
    if settlement.status != DriverDocStatus.DRAFT:
        raise DriverError(f"Cannot post a settlement in status {settlement.status!r}.")
    gross = _q(settlement.gross_amount)
    if gross <= ZERO:
        raise DriverError("Gross amount must be positive.")

    deductions = list(settlement.deductions.select_related("account").all())
    if any(_q(d.amount) <= ZERO for d in deductions):
        raise DriverError("Deduction amounts must be positive.")
    total_ded = sum((_q(d.amount) for d in deductions), ZERO)
    if total_ded > gross and not settlement.allows_negative_net:
        raise DriverError(f"Deductions {total_ded} exceed gross {gross}.")
    net = _q(gross - total_ded)

    # --- advance recovery: locked, aggregated, validated before any write ------
    #
    # Aggregate first so several lines against one advance are checked as a whole,
    # then re-read those advances FOR UPDATE. The lock is what makes the balance
    # check safe: two settlements recovering the same advance concurrently would
    # otherwise both validate against the same stale balance and jointly
    # over-recover it. Rows are locked in primary-key order so two posts touching
    # the same set of advances always acquire them in the same sequence, which
    # avoids deadlocking each other.
    #
    # The `deductions` rows are deliberately NOT select_related("advance") — a
    # prefetched copy would be a pre-lock snapshot, exactly the stale read this
    # guards against.
    recovery_by_advance: dict = {}
    for d in deductions:
        if d.advance_id:
            recovery_by_advance[d.advance_id] = recovery_by_advance.get(d.advance_id, ZERO) + _q(
                d.amount
            )

    locked_advances: dict = {}
    if recovery_by_advance:
        advance_ids = sorted(recovery_by_advance)
        locked_advances = {
            adv.id: adv
            for adv in Advance.objects.select_for_update().filter(id__in=advance_ids).order_by("id")
        }
        if len(locked_advances) != len(advance_ids):
            raise DriverError("Settlement deduction references a missing advance.")
        for advance_id in advance_ids:
            adv = locked_advances[advance_id]
            if adv.driver_id != settlement.driver_id or adv.entity_id != settlement.entity_id:
                raise DriverError("Advance belongs to a different driver or entity.")
            if adv.status != DriverDocStatus.POSTED:
                raise DriverError("Only a posted advance can be recovered.")
            if recovery_by_advance[advance_id] > _q(adv.balance):
                raise DriverError(
                    f"Recovery {recovery_by_advance[advance_id]} exceeds the outstanding "
                    f"balance {_q(adv.balance)} on advance {adv.advance_no or advance_id}."
                )

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
    if net >= ZERO and settlement.driver_receivable_account_id is not None:
        # Nothing is owed, so a receivable account is meaningless here. Rejecting
        # beats ignoring: silently dropping it would let an operator believe a
        # receivable had been configured on this settlement.
        raise DriverError(
            "A driver receivable account may only be set when deductions exceed gross."
        )
    if net > ZERO:
        # Money leaves the bank to the driver.
        rows.append(
            {
                "account": settlement.pay_account.gl_account,
                "credit": net,
                "description": "Net payout",
            }
        )
    elif net < ZERO:
        # Deductions swallowed the earnings: the driver OWES the difference. That
        # is a receivable, not a receipt — nothing has been paid, so bank and cash
        # stay untouched. A separate receipt clears it later
        # (DR Bank / CR Driver Receivable).
        rows.append(
            {
                "account": _resolve_receivable_account(settlement),
                "debit": -net,
                "description": f"Amount due from driver ({settlement.driver.code})",
                "driver_id": settlement.driver_id,
                "vehicle_id": settlement.vehicle_id,
            }
        )
    # net == ZERO: earnings fully absorbed — neither a bank nor a receivable line.

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

    # Apply the recovery to the rows locked above (never the prefetched copies),
    # using the per-advance aggregate so split lines are written once.
    for advance_id, recovered in recovery_by_advance.items():
        adv = locked_advances[advance_id]
        adv.recovered_amount = _q(adv.recovered_amount + recovered)
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
