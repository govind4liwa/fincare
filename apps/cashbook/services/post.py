"""Post cashbook documents (replenishment, cash-count variance) through the engine.

Replenishment:
    DR  Petty Cash (cash GL)         = amount
    CR  Bank (bank GL)               = amount

Cash count variance (counted vs expected):
    shortage (counted < expected):  DR Short/Over expense / CR Cash
    overage  (counted > expected):  DR Cash           / CR Short/Over income
"""

from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction

from apps.audit.services import record as audit_record
from apps.cashbook.models import CashCount, CashDocStatus, Replenishment
from apps.core.services import sequences
from apps.ledger.models import JournalEntry, JournalLine
from apps.ledger.services.posting import PostingError, post_journal_entry

TWO_PLACES = Decimal("0.01")
ZERO = Decimal("0.00")


class CashbookError(ValueError):
    """Raised when a cashbook document cannot be posted."""


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
        )
    try:
        post_journal_entry(entry, user=user)
    except PostingError as exc:
        raise CashbookError(str(exc)) from exc
    return entry


@transaction.atomic
def post_replenishment(rep: Replenishment, *, user=None):
    if rep.status != CashDocStatus.DRAFT:
        raise CashbookError(f"Cannot post a replenishment in status {rep.status!r}.")
    amount = _q(rep.amount)
    if amount <= ZERO:
        raise CashbookError("Replenishment amount must be positive.")

    rows = [
        {
            "account": rep.petty_cash_float.cash_account.gl_account,
            "debit": amount,
            "description": "Petty cash top-up",
        },
        {
            "account": rep.bank_account.gl_account,
            "credit": amount,
            "description": "Bank withdrawal",
        },
    ]
    entry = _post_rows(
        entity=rep.entity,
        date=rep.replenish_date,
        source_type="replenishment",
        source_id=rep.id,
        currency=rep.bank_account.currency or rep.entity.base_currency,
        narration="Petty cash replenishment",
        rows=rows,
        user=user,
    )

    rep.replenish_no = sequences.allocate(
        entity_id=rep.entity_id,
        code="REPLENISH",
        period_key=str(rep.replenish_date.year),
        prefix="REP-",
        padding=6,
    ).formatted
    rep.journal_entry = entry
    rep.status = CashDocStatus.POSTED
    rep.save()

    audit_record(
        action="post",
        instance=rep,
        actor=user,
        entity_id=rep.entity_id,
        message=f"Posted {rep.replenish_no} amount={amount}",
    )
    return rep


@transaction.atomic
def post_cash_count(count: CashCount, *, user=None):
    """Recompute counted/variance from denominations and post any variance."""
    if count.status != CashDocStatus.DRAFT:
        raise CashbookError(f"Cannot post a cash count in status {count.status!r}.")

    counted = sum(
        (_q(Decimal(d.denomination_value) * d.quantity) for d in count.denominations.all()),
        ZERO,
    )
    # Persist per-line amounts for the audit trail.
    for d in count.denominations.all():
        d.amount = _q(Decimal(d.denomination_value) * d.quantity)
        d.save(update_fields=["amount", "updated_at"])

    expected = _q(count.expected_amount)
    variance = _q(counted - expected)
    cash_gl = count.cash_account.gl_account

    entry = None
    if variance != ZERO:
        if count.variance_account_id is None:
            raise CashbookError("A non-zero variance requires a variance_account.")
        if variance < ZERO:  # shortage: cash is less than the books -> reduce cash
            rows = [
                {
                    "account": count.variance_account,
                    "debit": -variance,
                    "description": "Cash short",
                },
                {"account": cash_gl, "credit": -variance, "description": "Cash shortage"},
            ]
        else:  # overage: more cash than the books -> increase cash
            rows = [
                {"account": cash_gl, "debit": variance, "description": "Cash overage"},
                {"account": count.variance_account, "credit": variance, "description": "Cash over"},
            ]
        entry = _post_rows(
            entity=count.entity,
            date=count.count_date,
            source_type="cash_count",
            source_id=count.id,
            currency=count.entity.base_currency,
            narration="Cash count variance",
            rows=rows,
            user=user,
        )

    count.counted_amount = counted
    count.variance = variance
    count.count_no = sequences.allocate(
        entity_id=count.entity_id,
        code="CASH_COUNT",
        period_key=str(count.count_date.year),
        prefix="CNT-",
        padding=6,
    ).formatted
    count.journal_entry = entry
    count.status = CashDocStatus.POSTED
    count.save()

    audit_record(
        action="post",
        instance=count,
        actor=user,
        entity_id=count.entity_id,
        message=f"Posted {count.count_no} counted={counted} expected={expected} var={variance}",
    )
    return count
