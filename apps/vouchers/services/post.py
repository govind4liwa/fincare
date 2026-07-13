"""Post and reverse vouchers through the ledger engine (ADR-0007).

A voucher's lines are mapped 1:1 to a ``JournalEntry`` (``source_type="voucher"``)
and posted via ``ledger.services.posting`` — the voucher app never writes GL rows
directly. Control-account lines take their party from the line, else the header.
"""

from django.db import transaction

from apps.audit.services import record as audit_record
from apps.core.services import sequences
from apps.ledger.models import JournalEntry, JournalLine
from apps.ledger.services.posting import PostingError, post_journal_entry, reverse_journal_entry
from apps.vouchers.models import NUMBER_PREFIX, VoucherStatus


class VoucherError(ValueError):
    """Raised when a voucher cannot be posted or reversed."""


@transaction.atomic
def post_voucher(voucher, *, user=None):
    """Build a JournalEntry from the voucher's lines and post it."""
    if voucher.status != VoucherStatus.DRAFT:
        raise VoucherError(f"Cannot post a voucher in status {voucher.status!r}.")

    lines = list(voucher.lines.select_related("account").all())
    if not lines:
        raise VoucherError("Voucher has no lines.")

    entry = JournalEntry.objects.create(
        entity=voucher.entity,
        branch=voucher.branch,
        entry_date=voucher.voucher_date,
        source_type="voucher",
        source_id=voucher.id,
        currency=voucher.currency,
        narration=voucher.narration or f"{voucher.get_voucher_type_display()} voucher",
    )
    for vl in lines:
        JournalLine.objects.create(
            entry=entry,
            line_no=vl.line_no,
            account=vl.account,
            description=vl.description,
            debit=vl.debit,
            credit=vl.credit,
            cost_center=vl.cost_center,
            party_type=vl.party_type or voucher.party_type,
            party_id=vl.party_id or voucher.party_id,
            vehicle_id=vl.vehicle_id,
            driver_id=vl.driver_id,
            platform_id=vl.platform_id,
            tax_code=vl.tax_code,
        )

    try:
        post_journal_entry(entry, user=user)
    except PostingError as exc:
        # Surface posting failures as VoucherError; the atomic block rolls back.
        raise VoucherError(str(exc)) from exc

    voucher.journal_entry = entry
    voucher.amount = entry.total_debit
    voucher.voucher_no = sequences.allocate(
        entity_id=voucher.entity_id,
        code=f"VCH-{voucher.voucher_type}",
        period_key=str(voucher.voucher_date.year),
        prefix=NUMBER_PREFIX.get(voucher.voucher_type, "VCH-"),
        padding=6,
    ).formatted
    voucher.status = VoucherStatus.POSTED
    voucher.posted_at = entry.posted_at
    voucher.posted_by = user
    voucher.save()

    audit_record(
        action="post",
        instance=voucher,
        actor=user,
        entity_id=voucher.entity_id,
        message=f"Posted {voucher.voucher_no} -> {entry.entry_no}",
    )
    return voucher


@transaction.atomic
def reverse_voucher(voucher, *, user=None, date=None):
    """Reverse the voucher's posted journal entry and mark the voucher reversed."""
    if voucher.status != VoucherStatus.POSTED:
        raise VoucherError("Only a posted voucher can be reversed.")
    if voucher.journal_entry_id is None:
        raise VoucherError("Voucher has no posted journal entry.")

    mirror = reverse_journal_entry(voucher.journal_entry, user=user, date=date)
    voucher.status = VoucherStatus.REVERSED
    voucher.save(update_fields=["status", "updated_at"])

    audit_record(
        action="reverse",
        instance=voucher,
        actor=user,
        entity_id=voucher.entity_id,
        message=f"Reversed via {mirror.entry_no}",
    )
    return mirror
