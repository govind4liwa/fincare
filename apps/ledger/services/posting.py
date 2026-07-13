"""The double-entry posting engine — the only writer that posts to the GL (ADR-0007).

Guarantees on ``post_journal_entry``:
- atomic; total base debit == total base credit and non-zero;
- each line is one-sided (exactly one of debit/credit > 0), on a postable+active
  account; manual entries may not touch control accounts; control-account lines
  carry a party;
- the entry_date falls in an OPEN period; ``entry_no`` is allocated gap-safe;
- once posted the entry/lines are immutable — corrections go through
  ``reverse_journal_entry`` (a balanced mirror).
Optional rounding: a residual within ``tolerance`` is booked to ``rounding_account``.
"""

from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.utils import timezone

from apps.audit.services import record as audit_record
from apps.core.services import sequences
from apps.ledger.models import AccountingPeriod, EntryStatus, JournalEntry, JournalLine

TWO_PLACES = Decimal("0.01")
ZERO = Decimal("0")


class PostingError(ValueError):
    """Raised when a journal entry cannot be posted."""


def _q(amount):
    return Decimal(amount).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _resolve_period(entry):
    if entry.period_id:
        return entry.period
    period = AccountingPeriod.objects.filter(
        entity=entry.entity,
        start_date__lte=entry.entry_date,
        end_date__gte=entry.entry_date,
    ).first()
    if period is None:
        raise PostingError(
            f"No accounting period covers {entry.entry_date} for entity {entry.entity_id}."
        )
    return period


def _validate_lines(entry, lines):
    if not lines:
        raise PostingError("Journal entry has no lines.")
    for ln in lines:
        debit, credit = Decimal(ln.debit or 0), Decimal(ln.credit or 0)
        if debit < 0 or credit < 0:
            raise PostingError(f"Line {ln.line_no}: amounts must be non-negative.")
        if (debit > 0) == (credit > 0):
            raise PostingError(f"Line {ln.line_no}: exactly one of debit/credit must be non-zero.")
        account = ln.account
        if not (account.is_postable and account.is_active):
            raise PostingError(f"Account {account.code} is not postable/active.")
        if entry.source_type == "manual" and not account.allow_manual_posting:
            raise PostingError(f"Manual posting is not allowed to control account {account.code}.")
        if account.is_control_account and not (ln.party_type and ln.party_id):
            raise PostingError(f"Control account {account.code} requires party_type and party_id.")


def _compute_base(line):
    rate = Decimal(line.fx_rate or 1)
    line.base_debit = _q(Decimal(line.debit or 0) * rate)
    line.base_credit = _q(Decimal(line.credit or 0) * rate)


def _book_rounding(entry, lines, *, rounding_account, tolerance):
    debit = sum((ln.base_debit for ln in lines), ZERO)
    credit = sum((ln.base_credit for ln in lines), ZERO)
    residual = _q(debit - credit)
    if residual == 0 or rounding_account is None or abs(residual) > tolerance:
        return
    line = JournalLine(
        entry=entry,
        line_no=max((ln.line_no for ln in lines), default=0) + 1,
        account=rounding_account,
        description="Rounding",
        fx_rate=Decimal("1"),
    )
    if residual > 0:  # debits exceed credits -> add a credit
        line.credit = residual
        line.base_credit = residual
    else:
        line.debit = -residual
        line.base_debit = -residual
    line._system_update = True
    line.save()
    lines.append(line)


@transaction.atomic
def post_journal_entry(entry, *, user=None, rounding_account=None, tolerance=ZERO):
    """Validate and post ``entry``. Returns the posted entry. Raises PostingError."""
    if entry.status not in {EntryStatus.DRAFT, EntryStatus.VALIDATED}:
        raise PostingError(f"Cannot post an entry in status {entry.status!r}.")

    lines = list(entry.lines.select_related("account").all())
    _validate_lines(entry, lines)

    for ln in lines:
        _compute_base(ln)
        ln._system_update = True
        ln.save(update_fields=["base_debit", "base_credit", "updated_at"])

    _book_rounding(entry, lines, rounding_account=rounding_account, tolerance=tolerance)

    total_debit = sum((ln.base_debit for ln in lines), ZERO)
    total_credit = sum((ln.base_credit for ln in lines), ZERO)
    if total_debit != total_credit:
        raise PostingError(f"Unbalanced entry: debit {total_debit} != credit {total_credit}.")
    if total_debit == ZERO:
        raise PostingError("Journal entry total is zero.")

    period = _resolve_period(entry)
    if not period.is_open:
        raise PostingError(f"Period {period.name} is {period.status}; posting blocked.")

    entry.period = period
    entry.entry_no = sequences.allocate(
        entity_id=entry.entity_id,
        code="JE",
        period_key=str(period.fiscal_year),
        prefix="JE-",
        padding=6,
    ).formatted
    entry.total_debit = total_debit
    entry.total_credit = total_credit
    entry.status = EntryStatus.POSTED
    entry.posted_at = timezone.now()
    entry.posted_by = user
    entry._system_update = True
    entry.save()

    audit_record(
        action="post",
        instance=entry,
        actor=user,
        entity_id=entry.entity_id,
        message=f"Posted {entry.entry_no}: debit={total_debit} credit={total_credit}",
    )
    return entry


@transaction.atomic
def reverse_journal_entry(entry, *, user=None, date=None):
    """Post a balanced mirror of ``entry`` and mark the original reversed."""
    if entry.status != EntryStatus.POSTED:
        raise PostingError("Only a posted entry can be reversed.")

    mirror = JournalEntry.objects.create(
        entity=entry.entity,
        branch=entry.branch,
        entry_date=date or entry.entry_date,
        basis=entry.basis,
        source_type="reversal",
        source_id=entry.id,
        currency=entry.currency,
        narration=f"Reversal of {entry.entry_no}",
        reversal_of=entry,
        status=EntryStatus.DRAFT,
    )
    for ln in entry.lines.all():
        JournalLine.objects.create(
            entry=mirror,
            line_no=ln.line_no,
            account=ln.account,
            description=ln.description,
            debit=ln.credit,  # swap
            credit=ln.debit,
            fx_rate=ln.fx_rate,
            cost_center=ln.cost_center,
            party_type=ln.party_type,
            party_id=ln.party_id,
            vehicle_id=ln.vehicle_id,
            driver_id=ln.driver_id,
            platform_id=ln.platform_id,
            tax_code=ln.tax_code,
        )

    post_journal_entry(mirror, user=user)

    entry.reversed_by = mirror
    entry.status = EntryStatus.REVERSED
    entry._system_update = True
    entry.save(update_fields=["reversed_by", "status", "updated_at"])

    audit_record(
        action="reverse",
        instance=entry,
        actor=user,
        entity_id=entry.entity_id,
        message=f"Reversed by {mirror.entry_no}",
    )
    return mirror
