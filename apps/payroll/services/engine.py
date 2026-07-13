"""Shared payroll posting helpers — every payroll JE goes through the engine."""

from decimal import ROUND_HALF_UP, Decimal

from apps.ledger.models import JournalEntry, JournalLine
from apps.ledger.services.posting import PostingError, post_journal_entry

TWO_PLACES = Decimal("0.01")
ZERO = Decimal("0.00")


class PayrollError(ValueError):
    """Raised when a payroll document cannot be built or posted."""


def q(amount):
    return Decimal(amount).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def post_rows(*, entity, date, source_type, source_id, currency, narration, rows, user):
    """Create a JournalEntry from ``rows`` and post it via the ledger engine."""
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
        )
    try:
        post_journal_entry(entry, user=user)
    except PostingError as exc:
        raise PayrollError(str(exc)) from exc
    return entry
