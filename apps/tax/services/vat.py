"""VAT 201 return computation — by VAT control accounts (ADR-0007 alignment).

The authoritative output/input VAT figures come straight from the general
ledger: we sum movements on accounts of type ``vat_output`` / ``vat_input``
across the VAT group's member entities, for *posted* journal entries dated in
the filing period. Because every source document (sales invoice, purchase bill,
voucher) posts through the ledger engine, the return always ties exactly to the
GL and balances by construction.

The emirate split of standard-rated supplies (VAT 201 Box 1a–1g) is supplementary
detail sourced from the sales subledger (``ar.SalesInvoice.place_of_supply``).
"""

from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from apps.accounts.models import Account, TaxCode
from apps.ar.models import InvoiceStatus, SalesInvoice
from apps.audit.services import record as audit_record
from apps.ledger.models import EntryStatus, JournalLine
from apps.tax.models import EMIRATES, TaxReturn, TaxReturnBox, TaxReturnStatus

ZERO = Decimal("0.00")


class TaxError(ValueError):
    """Raised when a tax return cannot be computed."""


def _net_movement(entity_ids, start, end, account_type, *, credit_positive):
    """Net GL movement on a VAT control account type over a period.

    ``credit_positive=True`` returns ``credits - debits`` (output VAT liability);
    ``False`` returns ``debits - credits`` (input VAT recoverable).
    """
    agg = JournalLine.objects.filter(
        entry__status=EntryStatus.POSTED,
        entry__entity_id__in=entity_ids,
        entry__entry_date__gte=start,
        entry__entry_date__lte=end,
        account__account_type=account_type,
    ).aggregate(d=Sum("debit"), c=Sum("credit"))
    debit = agg["d"] or ZERO
    credit = agg["c"] or ZERO
    return (credit - debit) if credit_positive else (debit - credit)


def _emirate_split(entity_ids, start, end):
    """Standard-rated taxable + output VAT by emirate, from posted sales invoices."""
    buckets = {name: {"amount": ZERO, "vat": ZERO} for _, name in EMIRATES}
    invoices = (
        SalesInvoice.objects.filter(
            entity_id__in=entity_ids,
            status__in=[InvoiceStatus.POSTED, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.PAID],
            invoice_date__gte=start,
            invoice_date__lte=end,
        )
        .prefetch_related("lines__tax_code")
        .only("id", "place_of_supply")
    )
    for inv in invoices:
        emirate = _match_emirate(inv.place_of_supply)
        if emirate is None:
            continue
        for ln in inv.lines.all():
            if ln.tax_code_id and ln.tax_code.treatment == TaxCode.Treatment.STANDARD:
                buckets[emirate]["amount"] += ln.line_amount
                buckets[emirate]["vat"] += ln.tax_amount
    return buckets


def _match_emirate(place_of_supply):
    if not place_of_supply:
        return None
    needle = place_of_supply.strip().lower()
    for _, name in EMIRATES:
        if name.lower() == needle:
            return name
    return None


@transaction.atomic
def compute_vat_return(tax_return: TaxReturn, *, user=None) -> TaxReturn:
    """Populate a VAT 201 return's totals and boxes from the GL. Idempotent."""
    if tax_return.status == TaxReturnStatus.FILED:
        raise TaxError("Cannot recompute a filed VAT return.")
    entity_ids = tax_return.member_entity_ids
    if not entity_ids:
        raise TaxError("VAT return scope has no member entities.")
    start, end = tax_return.period_start, tax_return.period_end
    if start > end:
        raise TaxError("period_start must be on or before period_end.")

    # Authoritative figures from the VAT control accounts.
    output_vat = _net_movement(
        entity_ids, start, end, Account.AccountType.VAT_OUTPUT, credit_positive=True
    )
    input_vat = _net_movement(
        entity_ids, start, end, Account.AccountType.VAT_INPUT, credit_positive=False
    )
    net = output_vat - input_vat

    # Rebuild boxes from scratch each compute. Boxes are pure derived output, so
    # hard-delete (not soft) to keep the unique (return, box_code) slot free.
    tax_return.boxes.all().hard_delete()
    boxes = []
    order = 0
    split = _emirate_split(entity_ids, start, end)
    for box_code, name in EMIRATES:
        b = split[name]
        boxes.append(
            TaxReturnBox(
                tax_return=tax_return,
                box_code=box_code,
                label=f"Standard rated supplies — {name}",
                emirate=name,
                amount=b["amount"],
                vat_amount=b["vat"],
                sort_order=order,
            )
        )
        order += 1
    boxes.append(
        TaxReturnBox(
            tax_return=tax_return,
            box_code="12",
            label="Totals — output tax due",
            vat_amount=output_vat,
            sort_order=90,
        )
    )
    boxes.append(
        TaxReturnBox(
            tax_return=tax_return,
            box_code="13",
            label="Totals — input tax recoverable",
            vat_amount=input_vat,
            sort_order=91,
        )
    )
    boxes.append(
        TaxReturnBox(
            tax_return=tax_return,
            box_code="14",
            label="Net VAT payable / (reclaimable)",
            vat_amount=net,
            sort_order=92,
        )
    )
    TaxReturnBox.objects.bulk_create(boxes)

    if tax_return.vat_group_id and tax_return.vat_group.trn:
        tax_return.trn = tax_return.vat_group.trn
    elif tax_return.entity_id:
        tax_return.trn = tax_return.entity.effective_trn or ""

    tax_return.total_output_vat = output_vat
    tax_return.total_input_vat = input_vat
    tax_return.net_vat_payable = net
    tax_return.status = TaxReturnStatus.COMPUTED
    tax_return.computed_at = timezone.now()
    tax_return.save(
        update_fields=[
            "trn",
            "total_output_vat",
            "total_input_vat",
            "net_vat_payable",
            "status",
            "computed_at",
            "updated_at",
        ]
    )

    audit_record(
        action="compute",
        instance=tax_return,
        actor=user,
        entity_id=(tax_return.entity_id or entity_ids[0]),
        message=(
            f"Computed VAT201 {start}..{end}: output={output_vat} "
            f"input={input_vat} net={net} ({len(entity_ids)} entities)"
        ),
    )
    return tax_return


@transaction.atomic
def file_vat_return(tax_return: TaxReturn, *, reference="", user=None) -> TaxReturn:
    """Mark a computed VAT return as filed with the FTA."""
    if tax_return.status != TaxReturnStatus.COMPUTED:
        raise TaxError(f"Only a computed return can be filed (status={tax_return.status!r}).")
    tax_return.status = TaxReturnStatus.FILED
    tax_return.filed_at = timezone.now()
    tax_return.filed_by = user
    tax_return.filing_reference = reference
    tax_return.save(
        update_fields=["status", "filed_at", "filed_by", "filing_reference", "updated_at"]
    )
    audit_record(
        action="file",
        instance=tax_return,
        actor=user,
        entity_id=(tax_return.entity_id or tax_return.member_entity_ids[0]),
        message=f"Filed VAT201 ref={reference}",
    )
    return tax_return


def rate_on(tax_code, on: date | None = None) -> Decimal:
    """The effective rate for a tax code on a date (falls back to the live rate)."""
    on = on or date.today()
    hist = (
        tax_code.rate_history.filter(effective_from__lte=on)
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=on))
        .order_by("-effective_from")
        .first()
    )
    return hist.rate if hist else tax_code.rate
