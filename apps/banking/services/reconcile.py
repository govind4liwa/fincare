"""Rule-based bank reconciliation.

Matches imported statement lines to posted journal lines on the bank's GL
account. A pair matches when: the amounts are equal (within tolerance) on the
correct side (deposit ↔ GL debit, withdrawal ↔ GL credit), the dates fall within
``date_window_days``, and — if requested — the statement reference appears in the
journal line description. Each match is recorded as a ``ReconciliationItem``.
"""

from decimal import Decimal

from django.db import transaction

from apps.audit.services import record as audit_record
from apps.banking.models import Reconciliation, ReconciliationItem
from apps.ledger.models import EntryStatus, JournalLine

ZERO = Decimal("0.00")


def _gl_balance(bank_gl, entity_id, as_of):
    """Net posted movement (debit - credit) on the bank GL up to ``as_of``."""
    debit = credit = ZERO
    qs = JournalLine.objects.filter(
        account=bank_gl,
        entry__status=EntryStatus.POSTED,
        entry__entity_id=entity_id,
        entry__entry_date__lte=as_of,
    ).values_list("debit", "credit")
    for d, c in qs:
        debit += d
        credit += c
    return debit - credit


@transaction.atomic
def auto_match(
    reconciliation: Reconciliation,
    *,
    amount_tolerance=ZERO,
    date_window_days=3,
    match_reference=False,
    user=None,
):
    """Auto-match statement lines to GL lines. Returns the count of new matches."""
    if reconciliation.statement_id is None:
        raise ValueError("Reconciliation has no statement to match against.")

    bank_gl = reconciliation.bank_account.gl_account
    tol = Decimal(amount_tolerance)

    already = set(
        ReconciliationItem.objects.filter(journal_line__isnull=False).values_list(
            "journal_line_id", flat=True
        )
    )
    candidates = list(
        JournalLine.objects.filter(
            account=bank_gl,
            entry__status=EntryStatus.POSTED,
            entry__entity_id=reconciliation.entity_id,
        )
        .exclude(id__in=already)
        .select_related("entry")
    )

    used = set()
    matched = 0
    for sl in reconciliation.statement.lines.filter(is_matched=False).order_by("line_no"):
        for jl in candidates:
            if jl.id in used:
                continue
            if sl.deposit > ZERO:
                amount_ok = abs(jl.debit - sl.deposit) <= tol and jl.debit > ZERO
                amount = sl.deposit
            elif sl.withdrawal > ZERO:
                amount_ok = abs(jl.credit - sl.withdrawal) <= tol and jl.credit > ZERO
                amount = sl.withdrawal
            else:
                continue
            date_ok = abs((sl.txn_date - jl.entry.entry_date).days) <= date_window_days
            ref_ok = (not match_reference) or (
                bool(sl.reference) and sl.reference in (jl.description or "")
            )
            if amount_ok and date_ok and ref_ok:
                ReconciliationItem.objects.create(
                    reconciliation=reconciliation,
                    statement_line=sl,
                    journal_line=jl,
                    match_type=ReconciliationItem.MatchType.AUTO,
                    amount=amount,
                )
                sl.is_matched = True
                sl.save(update_fields=["is_matched", "updated_at"])
                used.add(jl.id)
                matched += 1
                break

    # Refresh reconciliation totals.
    reconciliation.gl_balance = _gl_balance(
        bank_gl, reconciliation.entity_id, reconciliation.recon_date
    )
    reconciliation.statement_balance = (
        reconciliation.statement.closing_balance if reconciliation.statement_id else ZERO
    )
    reconciliation.difference = reconciliation.statement_balance - reconciliation.gl_balance
    unmatched = reconciliation.statement.lines.filter(is_matched=False).exists()
    reconciliation.status = (
        Reconciliation.Status.IN_PROGRESS if unmatched else Reconciliation.Status.COMPLETED
    )
    reconciliation.performed_by = user or reconciliation.performed_by
    reconciliation.save(
        update_fields=[
            "gl_balance",
            "statement_balance",
            "difference",
            "status",
            "performed_by",
            "updated_at",
        ]
    )

    audit_record(
        action="reconcile",
        instance=reconciliation,
        actor=user,
        entity_id=reconciliation.entity_id,
        message=f"Auto-matched {matched} line(s); difference={reconciliation.difference}",
    )
    return matched
