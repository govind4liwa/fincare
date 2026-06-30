"""Post banking documents (transfers, POS settlements) through the ledger engine.

Bank transfer:
    DR  destination bank GL          = amount
    DR  bank charges expense         = charges        (optional)
    CR  source bank GL               = amount + charges

POS settlement:
    DR  bank GL                      = net amount
    DR  card fee expense             = fee amount      (optional)
    CR  POS clearing account         = gross amount
"""

from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction

from apps.audit.services import record as audit_record
from apps.banking.models import BankDocStatus, BankTransfer, PosSettlement
from apps.core.services import sequences
from apps.ledger.models import JournalEntry, JournalLine
from apps.ledger.services.posting import PostingError, post_journal_entry, reverse_journal_entry

TWO_PLACES = Decimal("0.01")
ZERO = Decimal("0.00")


class BankingError(ValueError):
    """Raised when a banking document cannot be posted or reversed."""


def _q(amount):
    return Decimal(amount).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _post_rows(*, entity, date, source_type, source_id, currency, narration, rows, user):
    """Create a JournalEntry from ``rows`` and post it via the engine."""
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
        raise BankingError(str(exc)) from exc
    return entry


@transaction.atomic
def post_transfer(transfer: BankTransfer, *, user=None):
    if transfer.status != BankDocStatus.DRAFT:
        raise BankingError(f"Cannot post a transfer in status {transfer.status!r}.")
    amount = _q(transfer.amount)
    charges = _q(transfer.charges or ZERO)
    if amount <= ZERO:
        raise BankingError("Transfer amount must be positive.")
    if charges > ZERO and transfer.charge_account_id is None:
        raise BankingError("Charges require a charge_account.")
    if transfer.from_account_id == transfer.to_account_id:
        raise BankingError("Source and destination accounts must differ.")

    rows = [
        {"account": transfer.to_account.gl_account, "debit": amount, "description": "Transfer in"},
    ]
    if charges > ZERO:
        rows.append(
            {"account": transfer.charge_account, "debit": charges, "description": "Bank charges"}
        )
    rows.append(
        {
            "account": transfer.from_account.gl_account,
            "credit": amount + charges,
            "description": "Transfer out",
        }
    )

    entry = _post_rows(
        entity=transfer.entity,
        date=transfer.transfer_date,
        source_type="bank_transfer",
        source_id=transfer.id,
        currency=transfer.from_account.currency or transfer.entity.base_currency,
        narration=transfer.narration or "Bank transfer",
        rows=rows,
        user=user,
    )

    transfer.transfer_no = sequences.allocate(
        entity_id=transfer.entity_id,
        code="BANK_TRANSFER",
        period_key=str(transfer.transfer_date.year),
        prefix="TRF-",
        padding=6,
    ).formatted
    transfer.journal_entry = entry
    transfer.status = BankDocStatus.POSTED
    transfer.save()

    audit_record(
        action="post",
        instance=transfer,
        actor=user,
        entity_id=transfer.entity_id,
        message=f"Posted {transfer.transfer_no} amount={amount} charges={charges}",
    )
    return transfer


@transaction.atomic
def post_pos_settlement(settlement: PosSettlement, *, user=None):
    if settlement.status != BankDocStatus.DRAFT:
        raise BankingError(f"Cannot post a settlement in status {settlement.status!r}.")
    gross = _q(settlement.gross_amount)
    fee = _q(settlement.fee_amount or ZERO)
    net = _q(gross - fee)
    if gross <= ZERO:
        raise BankingError("Gross amount must be positive.")
    if fee > ZERO and settlement.fee_account_id is None:
        raise BankingError("Fee requires a fee_account.")

    rows = [
        {"account": settlement.bank_account.gl_account, "debit": net, "description": "POS net"},
    ]
    if fee > ZERO:
        rows.append({"account": settlement.fee_account, "debit": fee, "description": "Card fee"})
    rows.append(
        {"account": settlement.pos_clearing_account, "credit": gross, "description": "POS clearing"}
    )

    entry = _post_rows(
        entity=settlement.entity,
        date=settlement.settlement_date,
        source_type="pos_settlement",
        source_id=settlement.id,
        currency=settlement.bank_account.currency or settlement.entity.base_currency,
        narration="POS settlement",
        rows=rows,
        user=user,
    )

    settlement.net_amount = net
    settlement.settlement_no = sequences.allocate(
        entity_id=settlement.entity_id,
        code="POS_SETTLEMENT",
        period_key=str(settlement.settlement_date.year),
        prefix="POS-",
        padding=6,
    ).formatted
    settlement.journal_entry = entry
    settlement.status = BankDocStatus.POSTED
    settlement.save()

    audit_record(
        action="post",
        instance=settlement,
        actor=user,
        entity_id=settlement.entity_id,
        message=f"Posted {settlement.settlement_no} gross={gross} fee={fee} net={net}",
    )
    return settlement


@transaction.atomic
def reverse_transfer(transfer: BankTransfer, *, user=None, date=None):
    if transfer.status != BankDocStatus.POSTED or transfer.journal_entry_id is None:
        raise BankingError("Only a posted transfer can be reversed.")
    mirror = reverse_journal_entry(transfer.journal_entry, user=user, date=date)
    transfer.status = BankDocStatus.REVERSED
    transfer.save(update_fields=["status", "updated_at"])
    audit_record(
        action="reverse",
        instance=transfer,
        actor=user,
        entity_id=transfer.entity_id,
        message=f"Reversed via {mirror.entry_no}",
    )
    return mirror
