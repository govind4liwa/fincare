"""Accounting period lifecycle: open -> closed -> locked.

Closing blocks new postings into a period (``posting.post_journal_entry``
checks ``period.is_open``) but is routine and reversible — a manager can
reopen it for a correction. Locking is a further, one-way step (e.g. after a
year-end audit): a locked period never reopens, mirroring the same
immutability CLAUDE.md §4.5 applies to posted entries, applied here to the
period itself.
"""

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.audit.services import record as audit_record
from apps.ledger.models import AccountingPeriod

Status = AccountingPeriod.Status


class PeriodError(ValueError):
    """Raised when a period cannot transition to the requested status."""


@transaction.atomic
def create_period(entity, *, fiscal_year, period_no, name, start_date, end_date, user=None):
    """Open a new accounting period. Dates must not overlap an existing one
    for the entity — posting resolves an entry's period purely from its date,
    so two overlapping periods would make that resolution ambiguous."""
    if start_date > end_date:
        raise PeriodError("start_date must be on or before end_date.")
    overlap = AccountingPeriod.objects.filter(
        entity=entity, start_date__lte=end_date, end_date__gte=start_date
    ).exists()
    if overlap:
        raise PeriodError("This period overlaps an existing period for the entity.")

    try:
        period = AccountingPeriod.objects.create(
            entity=entity,
            fiscal_year=fiscal_year,
            period_no=period_no,
            name=name,
            start_date=start_date,
            end_date=end_date,
            status=Status.OPEN,
        )
    except IntegrityError as exc:
        raise PeriodError(f"Entity already has a period {fiscal_year}/{period_no}.") from exc
    audit_record(
        action="create",
        instance=period,
        actor=user,
        entity_id=period.entity_id,
        message=f"Opened period {period.name} ({start_date}..{end_date})",
    )
    return period


@transaction.atomic
def close_period(period, *, user=None):
    if period.status != Status.OPEN:
        raise PeriodError(f"Only an open period can be closed (currently {period.status}).")
    period.status = Status.CLOSED
    period.closed_at = timezone.now()
    period.closed_by = user
    period.save(update_fields=["status", "closed_at", "closed_by", "updated_at"])
    audit_record(
        action="close",
        instance=period,
        actor=user,
        entity_id=period.entity_id,
        message=f"Closed period {period.name}",
    )
    return period


@transaction.atomic
def reopen_period(period, *, user=None):
    if period.status != Status.CLOSED:
        raise PeriodError(f"Only a closed period can be reopened (currently {period.status}).")
    period.status = Status.OPEN
    period.closed_at = None
    period.closed_by = None
    period.save(update_fields=["status", "closed_at", "closed_by", "updated_at"])
    audit_record(
        action="reopen",
        instance=period,
        actor=user,
        entity_id=period.entity_id,
        message=f"Reopened period {period.name}",
    )
    return period


@transaction.atomic
def lock_period(period, *, user=None):
    if period.status == Status.LOCKED:
        raise PeriodError("Period is already locked.")
    period.status = Status.LOCKED
    period.closed_at = period.closed_at or timezone.now()
    period.closed_by = period.closed_by or user
    period.save(update_fields=["status", "closed_at", "closed_by", "updated_at"])
    audit_record(
        action="lock",
        instance=period,
        actor=user,
        entity_id=period.entity_id,
        message=f"Locked period {period.name}",
    )
    return period
