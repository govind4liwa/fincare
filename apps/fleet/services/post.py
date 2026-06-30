"""Post fleet financial events (EMI, depreciation) through the ledger engine.

Vehicle loan EMI:
    DR  Vehicle Loan Payable   = principal component
    DR  Loan Interest Expense  = interest component
    CR  Bank                   = total (principal + interest)

Depreciation run (per vehicle, carrying the vehicle_id dimension):
    DR  Depreciation Expense        = monthly depreciation
    CR  Accumulated Depreciation    = monthly depreciation
"""

from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction

from apps.audit.services import record as audit_record
from apps.core.services import sequences
from apps.fleet.models import (
    DepreciationLine,
    DepreciationRun,
    FleetDocStatus,
    VehicleLoanInstallment,
)
from apps.ledger.models import JournalEntry, JournalLine
from apps.ledger.services.posting import PostingError, post_journal_entry

TWO_PLACES = Decimal("0.01")
ZERO = Decimal("0.00")


class FleetError(ValueError):
    """Raised when a fleet document cannot be posted."""


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
            vehicle_id=row.get("vehicle_id"),
            driver_id=row.get("driver_id"),
        )
    try:
        post_journal_entry(entry, user=user)
    except PostingError as exc:
        raise FleetError(str(exc)) from exc
    return entry


@transaction.atomic
def post_emi(installment: VehicleLoanInstallment, *, user=None):
    if installment.status != FleetDocStatus.DRAFT:
        raise FleetError(f"Cannot post an installment in status {installment.status!r}.")
    principal = _q(installment.principal_component)
    interest = _q(installment.interest_component)
    total = _q(principal + interest)
    if total <= ZERO:
        raise FleetError("EMI total must be positive.")
    installment.total_amount = total

    loan = installment.loan
    vehicle_id = loan.vehicle_id
    rows = [
        {
            "account": loan.loan_account,
            "debit": principal,
            "description": "EMI principal",
            "vehicle_id": vehicle_id,
        },
    ]
    if interest > ZERO:
        rows.append(
            {
                "account": loan.interest_account,
                "debit": interest,
                "description": "EMI interest",
                "vehicle_id": vehicle_id,
            }
        )
    rows.append(
        {
            "account": installment.bank_account.gl_account,
            "credit": total,
            "description": "EMI payment",
        }
    )

    entry = _post_rows(
        entity=loan.entity,
        date=installment.due_date,
        source_type="vehicle_emi",
        source_id=installment.id,
        currency=installment.bank_account.currency or loan.entity.base_currency,
        narration=f"Vehicle EMI {loan.vehicle_id} #{installment.installment_no}",
        rows=rows,
        user=user,
    )

    installment.journal_entry = entry
    installment.status = FleetDocStatus.POSTED
    installment.save(update_fields=["total_amount", "journal_entry", "status", "updated_at"])

    audit_record(
        action="post",
        instance=installment,
        actor=user,
        entity_id=loan.entity_id,
        message=f"Posted EMI #{installment.installment_no} P={principal} I={interest}",
    )
    return installment


@transaction.atomic
def post_depreciation_run(run: DepreciationRun, *, user=None, vehicles=None):
    """Build depreciation lines for active vehicles and post one balanced JE."""
    if run.status != FleetDocStatus.DRAFT:
        raise FleetError(f"Cannot post a run in status {run.status!r}.")

    qs = vehicles if vehicles is not None else run.entity.vehicles.filter(is_active=True)
    rows = []
    total = ZERO
    run.lines.all().hard_delete()
    for v in qs:
        amount = _q(v.monthly_depreciation)
        if amount <= ZERO:
            continue
        if not (v.depreciation_expense_account_id and v.accumulated_depreciation_account_id):
            raise FleetError(f"Vehicle {v.code} has no depreciation accounts configured.")
        DepreciationLine.objects.create(run=run, vehicle=v, amount=amount)
        rows.append(
            {
                "account": v.depreciation_expense_account,
                "debit": amount,
                "description": f"Depreciation {v.code}",
                "vehicle_id": v.id,
            }
        )
        rows.append(
            {
                "account": v.accumulated_depreciation_account,
                "credit": amount,
                "description": f"Accum dep {v.code}",
                "vehicle_id": v.id,
            }
        )
        total += amount

    if not rows:
        raise FleetError("No vehicles with depreciation to post.")

    entry = _post_rows(
        entity=run.entity,
        date=run.run_date,
        source_type="depreciation",
        source_id=run.id,
        currency=run.entity.base_currency,
        narration=f"Depreciation run {run.period_label or run.run_date}",
        rows=rows,
        user=user,
    )

    run.total_amount = total
    run.run_no = sequences.allocate(
        entity_id=run.entity_id,
        code="DEP_RUN",
        period_key=str(run.run_date.year),
        prefix="DEP-",
        padding=6,
    ).formatted
    run.journal_entry = entry
    run.status = FleetDocStatus.POSTED
    run.save(update_fields=["total_amount", "run_no", "journal_entry", "status", "updated_at"])

    audit_record(
        action="post",
        instance=run,
        actor=user,
        entity_id=run.entity_id,
        message=f"Posted {run.run_no} total={total} ({len(rows)//2} vehicles)",
    )
    return run
