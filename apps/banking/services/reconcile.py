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
    mark_complete=True,
    user=None,
):
    """Auto-match statement lines to GL lines. Returns the count of new matches.

    When ``mark_complete`` is False the reconciliation is left ``IN_PROGRESS``
    even if every line matched — formal completion/locking is a later concern.
    """
    statement = reconciliation.statement if reconciliation.statement_id else None
    if statement is None:
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
    for sl in statement.lines.filter(is_matched=False).order_by("line_no"):
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
    reconciliation.statement_balance = statement.closing_balance
    reconciliation.difference = reconciliation.statement_balance - reconciliation.gl_balance
    unmatched = statement.lines.filter(is_matched=False).exists()
    if mark_complete and not unmatched:
        reconciliation.status = Reconciliation.Status.COMPLETED
    else:
        reconciliation.status = Reconciliation.Status.IN_PROGRESS
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


def recompute_balances(reconciliation):
    """Refresh statement/GL balances + difference (no matching), persisted."""
    statement = reconciliation.statement if reconciliation.statement_id else None
    reconciliation.gl_balance = _gl_balance(
        reconciliation.bank_account.gl_account,
        reconciliation.entity_id,
        reconciliation.recon_date,
    )
    reconciliation.statement_balance = statement.closing_balance if statement else ZERO
    reconciliation.difference = reconciliation.statement_balance - reconciliation.gl_balance
    reconciliation.save(
        update_fields=["gl_balance", "statement_balance", "difference", "updated_at"]
    )
    return reconciliation


def reconciliation_detail(reconciliation):
    """Workspace view: matched pairs, unmatched statement lines, the bank GL lines
    (with a matched flag), and the balance/difference summary."""
    bank_gl = reconciliation.bank_account.gl_account
    items = list(
        reconciliation.items.select_related("statement_line", "journal_line", "journal_line__entry")
    )
    matched_jl_ids = {it.journal_line_id for it in items if it.journal_line_id}

    statement = reconciliation.statement if reconciliation.statement_id else None
    unmatched_lines = (
        list(statement.lines.filter(is_matched=False).order_by("line_no")) if statement else []
    )
    gl_lines = list(
        JournalLine.objects.filter(
            account=bank_gl,
            entry__status=EntryStatus.POSTED,
            entry__entity_id=reconciliation.entity_id,
            entry__entry_date__lte=reconciliation.recon_date,
        )
        .select_related("entry")
        .order_by("entry__entry_date", "line_no")
    )

    return {
        "items": items,
        "unmatched_lines": unmatched_lines,
        "gl_lines": gl_lines,
        "matched_jl_ids": matched_jl_ids,
        "totals": {
            "statement_balance": reconciliation.statement_balance,
            "gl_balance": reconciliation.gl_balance,
            "difference": reconciliation.difference,
            "matched_count": len(items),
            "matched_total": sum((it.amount for it in items), ZERO),
            "unmatched_count": len(unmatched_lines),
            "unmatched_deposits": sum((sl.deposit for sl in unmatched_lines), ZERO),
            "unmatched_withdrawals": sum((sl.withdrawal for sl in unmatched_lines), ZERO),
        },
    }
