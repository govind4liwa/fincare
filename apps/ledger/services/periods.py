"""Accounting period lifecycle: open -> closed -> locked.

Closing blocks new postings into a period (``posting.post_journal_entry``
checks ``period.is_open``) but is routine and reversible — a manager can
reopen it for a correction. Locking is a further, one-way step (e.g. after a
year-end audit): a locked period never reopens, mirroring the same
immutability CLAUDE.md §4.5 applies to posted entries, applied here to the
period itself.
"""

from django.db import transaction
from django.utils import timezone

from apps.audit.services import record as audit_record
from apps.ledger.models import AccountingPeriod

Status = AccountingPeriod.Status


class PeriodError(ValueError):
    """Raised when a period cannot transition to the requested status."""


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
