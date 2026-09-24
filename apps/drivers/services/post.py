"""Post driver financial events through the ledger engine.

Advance:
    DR  Driver Advance (asset, driver dim)   = amount
    CR  Bank                                 = amount

Settlement (net = gross − Σ deductions):
    DR  gross account (driver/vehicle dim)   = gross
    CR  each deduction account               = deduction amount
    CR  bank                                 = net      (net > 0)
    DR  Driver Receivable (driver dim)       = -net     (net < 0, driver owes)

Clearing — settles what a negative-net settlement left outstanding:
    DR  bank (receipt) / bad debts (write-off) = amount
    CR  Driver Receivable (driver dim)         = amount
"""

from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction

from apps.audit.services import record as audit_record
from apps.core.services import sequences
from apps.drivers.models import Advance, DriverClearing, DriverDocStatus, Settlement
from apps.ledger.models import JournalEntry, JournalLine
from apps.ledger.services.posting import (
    PostingError,
    post_journal_entry,
    reverse_journal_entry,
)
from apps.settings.services.driver_accounting import (
    DriverAccountingConfigError,
    resolve_receivable_account,
    resolve_write_off_account,
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
    # A negative net is what the driver owes; seed the outstanding balance so a
    # clearing has something to apply against. Any other net owes nothing.
    settlement.cleared_amount = ZERO
    settlement.receivable_balance = -net if net < ZERO else ZERO
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


def _clearing_debit_account(clearing: DriverClearing):
    """The account a clearing debits.

    Resolved from the chosen bank or from configuration — never a free-text pick
    — so a receipt cannot debit somewhere the money did not land, and a write-off
    cannot be booked to an arbitrary expense.
    """
    bank = clearing.bank_account if clearing.bank_account_id else None
    if clearing.kind == DriverClearing.Kind.RECEIPT:
        if bank is None:
            raise DriverError("A receipt from a driver requires the bank account it was paid into.")
        return bank.gl_account
    # WRITE_OFF: no money moves, so naming a bank account would misstate the event.
    if bank is not None:
        raise DriverError("A write-off moves no money, so it cannot name a bank account.")
    try:
        return resolve_write_off_account(clearing.entity)
    except DriverAccountingConfigError as exc:
        raise DriverError(str(exc)) from exc


def _applied_by_settlement(clearing: DriverClearing):
    """Total applied per settlement, so split lines are validated as a whole."""
    totals: dict = {}
    for line in clearing.lines.all():
        totals[line.settlement_id] = totals.get(line.settlement_id, ZERO) + _q(line.amount)
    return totals


def _lock_settlements(settlement_ids):
    """Re-read the settlements FOR UPDATE in primary-key order.

    The lock is what makes the outstanding-balance check safe: two clearings
    applied to one settlement concurrently would otherwise both validate against
    the same stale balance and jointly over-clear it. Ordering by primary key
    means two posts touching the same settlements always acquire them in the same
    sequence, so they cannot deadlock each other.
    """
    return {
        s.id: s
        for s in Settlement.objects.select_for_update().filter(id__in=settlement_ids).order_by("id")
    }


@transaction.atomic
def post_clearing(clearing: DriverClearing, *, user=None):
    """Settle outstanding driver receivables, by receipt or by write-off.

        RECEIPT     DR bank       / CR driver receivable (driver dim)
        WRITE_OFF   DR bad debts  / CR driver receivable (driver dim)

    The credit is always the entity's configured receivable account — the same
    account the settlement debited — so a clearing cannot credit somewhere the
    receivable never sat.

    Allocation is explicit: a clearing names the settlements it settles, and those
    lines must total the document amount. Nothing is applied on account.
    """
    if clearing.status != DriverDocStatus.DRAFT:
        raise DriverError(f"Cannot post a clearing in status {clearing.status!r}.")
    amount = _q(clearing.amount)
    if amount <= ZERO:
        raise DriverError("Clearing amount must be positive.")

    lines = list(clearing.lines.all())
    if not lines:
        raise DriverError("A clearing must apply to at least one settlement.")
    if any(_q(line.amount) <= ZERO for line in lines):
        raise DriverError("Clearing line amounts must be positive.")

    applied = _applied_by_settlement(clearing)
    total_applied = sum(applied.values(), ZERO)
    if total_applied != amount:
        raise DriverError(f"Allocated {total_applied} does not equal the clearing amount {amount}.")

    try:
        receivable_account = resolve_receivable_account(clearing.entity)
    except DriverAccountingConfigError as exc:
        raise DriverError(str(exc)) from exc
    debit_account = _clearing_debit_account(clearing)

    settlement_ids = sorted(applied)
    locked = _lock_settlements(settlement_ids)
    if len(locked) != len(settlement_ids):
        raise DriverError("Clearing line references a missing settlement.")
    for settlement_id in settlement_ids:
        settlement = locked[settlement_id]
        if settlement.driver_id != clearing.driver_id or settlement.entity_id != clearing.entity_id:
            raise DriverError("Settlement belongs to a different driver or entity.")
        if settlement.status != DriverDocStatus.POSTED:
            raise DriverError("Only a posted settlement can be cleared.")
        outstanding = _q(settlement.receivable_balance)
        if outstanding <= ZERO:
            raise DriverError(
                f"Settlement {settlement.settlement_no or settlement_id} has nothing outstanding."
            )
        if applied[settlement_id] > outstanding:
            raise DriverError(
                f"Applying {applied[settlement_id]} exceeds the outstanding {outstanding} on "
                f"settlement {settlement.settlement_no or settlement_id}."
            )

    rows = [
        {
            "account": debit_account,
            "debit": amount,
            "description": clearing.get_kind_display(),
            "driver_id": clearing.driver_id,
        },
        {
            "account": receivable_account,
            "credit": amount,
            "description": f"Receivable cleared ({clearing.driver.code})",
            "driver_id": clearing.driver_id,
        },
    ]
    bank = clearing.bank_account if clearing.bank_account_id else None
    entry = _post_rows(
        entity=clearing.entity,
        date=clearing.clearing_date,
        source_type="drv_clearing",
        source_id=clearing.id,
        currency=(bank.currency if bank else None) or clearing.entity.base_currency,
        narration=clearing.narration or f"{clearing.get_kind_display()} {clearing.driver.code}",
        rows=rows,
        user=user,
    )

    # Apply to the locked rows, never the prefetched copies.
    for settlement_id, part in applied.items():
        settlement = locked[settlement_id]
        settlement.cleared_amount = _q(settlement.cleared_amount + part)
        settlement.receivable_balance = _q(settlement.receivable_balance - part)
        settlement.save(update_fields=["cleared_amount", "receivable_balance", "updated_at"])

    # Persist what was actually used, so later configuration changes never rewrite
    # the history of this posting.
    clearing.receivable_account = receivable_account
    if clearing.kind == DriverClearing.Kind.WRITE_OFF:
        clearing.write_off_account = debit_account
    clearing.clearing_no = sequences.allocate(
        entity_id=clearing.entity_id,
        code=f"DRIVER_{clearing.kind.upper()}",
        period_key=str(clearing.clearing_date.year),
        prefix="DWO-" if clearing.kind == DriverClearing.Kind.WRITE_OFF else "DRCP-",
        padding=6,
    ).formatted
    clearing.journal_entry = entry
    clearing.status = DriverDocStatus.POSTED
    clearing.save()

    audit_record(
        action="post",
        instance=clearing,
        actor=user,
        entity_id=clearing.entity_id,
        message=f"Posted {clearing.clearing_no} {clearing.kind} amount={amount}",
    )
    return clearing


@transaction.atomic
def reverse_clearing(clearing: DriverClearing, *, user=None, date=None):
    """Undo a posted clearing: reverse its entry and give back what it cleared.

    A correction, never an edit (CLAUDE.md section 4.5) — the original entry and
    its mirror both stay in the books. Balances are restored under the same row
    locks the forward path takes, so a reversal racing a fresh clearing cannot
    lose one of the two updates.
    """
    if clearing.status != DriverDocStatus.POSTED:
        raise DriverError(f"Cannot reverse a clearing in status {clearing.status!r}.")

    applied = _applied_by_settlement(clearing)
    locked = _lock_settlements(sorted(applied))

    try:
        reverse_journal_entry(clearing.journal_entry, user=user, date=date)
    except PostingError as exc:
        raise DriverError(str(exc)) from exc

    for settlement_id, part in applied.items():
        settlement = locked[settlement_id]
        settlement.cleared_amount = _q(settlement.cleared_amount - part)
        settlement.receivable_balance = _q(settlement.receivable_balance + part)
        settlement.save(update_fields=["cleared_amount", "receivable_balance", "updated_at"])

    clearing.status = DriverDocStatus.REVERSED
    clearing.save(update_fields=["status", "updated_at"])

    audit_record(
        action="reverse",
        instance=clearing,
        actor=user,
        entity_id=clearing.entity_id,
        message=f"Reversed {clearing.clearing_no} amount={_q(clearing.amount)}",
    )
    return clearing
