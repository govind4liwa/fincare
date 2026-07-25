"""Vehicle-loan EMI schedule generation, versioning, and approval.

The lender's approved repayment schedule is the authoritative source; this module
models it. A schedule is generated as ``DRAFT``, must reconcile **exactly**
(instalments sum back to the opening principal and the balance closes at zero),
and is locked once ``APPROVED``. Regenerating never edits an existing version —
it creates a new one and supersedes the previous approval, so posted EMIs are
never rewritten.

Two methods are supported (per loan):

* ``REDUCING_BALANCE`` — annuity. Interest accrues on the outstanding balance, so
  it is high early and tapers. ``EMI = P·i / (1 − (1+i)^−n)``; with a zero rate
  this degrades to ``P / n``.
* ``FLAT_RATE`` — the common UAE auto-finance quoting convention. Total interest
  is ``P · rate · years`` spread evenly, as is principal.

Rounding differences from 2-dp quantisation are absorbed by the **final**
instalment, which is what makes the exact reconciliation possible.
"""

from calendar import monthrange
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.utils import timezone

from apps.audit.services import record as audit_record
from apps.fleet.models import (
    AmortizationMethod,
    FleetDocStatus,
    LoanSchedule,
    VehicleLoanInstallment,
)

TWO_PLACES = Decimal("0.01")
ZERO = Decimal("0.00")
MONTHS_PER_YEAR = Decimal("12")


class ScheduleError(ValueError):
    """Raised when a schedule cannot be generated, approved, or amended."""


def _q(amount):
    return Decimal(amount).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def add_months(start: date, months: int) -> date:
    """``start`` shifted by ``months``, keeping the day-of-month where possible.

    A 31st EMI date lands on the 30th/28th in shorter months (and stays on the
    31st thereafter) — the day is clamped, never rolled into the next month.
    """
    total = start.month - 1 + months
    year = start.year + total // 12
    month = total % 12 + 1
    return date(year, month, min(start.day, monthrange(year, month)[1]))


def _reducing_balance_rows(principal: Decimal, monthly_rate: Decimal, term: int):
    """(principal, interest) per instalment for the annuity method."""
    if monthly_rate == 0:
        emi = _q(principal / term)
    else:
        factor = (Decimal(1) + monthly_rate) ** -term
        emi = _q(principal * monthly_rate / (Decimal(1) - factor))

    rows = []
    balance = principal
    for _ in range(term - 1):
        interest = _q(balance * monthly_rate)
        principal_part = _q(emi - interest)
        # Never amortise more than what is outstanding.
        principal_part = min(principal_part, balance)
        balance -= principal_part
        rows.append((principal_part, interest))
    # The final instalment clears the balance exactly (absorbs rounding drift).
    rows.append((balance, _q(balance * monthly_rate)))
    return rows


def _flat_rate_rows(principal: Decimal, annual_rate: Decimal, term: int):
    """(principal, interest) per instalment for the flat-rate method."""
    years = Decimal(term) / MONTHS_PER_YEAR
    total_interest = _q(principal * annual_rate / Decimal(100) * years)
    per_principal = _q(principal / term)
    per_interest = _q(total_interest / term)

    rows = [(per_principal, per_interest) for _ in range(term - 1)]
    # The final instalment absorbs the rounding on both components.
    rows.append(
        (
            principal - per_principal * (term - 1),
            total_interest - per_interest * (term - 1),
        )
    )
    return rows


def _validate_reconciles(rows, opening_principal, schedule_totals):
    """The schedule must tie back exactly — otherwise the books would drift."""
    total_principal = sum((r[0] for r in rows), ZERO)
    total_interest = sum((r[1] for r in rows), ZERO)
    if total_principal != opening_principal:
        raise ScheduleError(
            f"Schedule does not reconcile: principal {total_principal} != opening "
            f"{opening_principal}."
        )
    if total_interest != schedule_totals["interest"]:
        raise ScheduleError("Schedule does not reconcile: interest total mismatch.")
    if any(p < ZERO or i < ZERO for p, i in rows):
        raise ScheduleError("Schedule produced a negative component.")


@transaction.atomic
def generate_schedule(loan, *, first_payment_date=None, note="", user=None):
    """Create a new DRAFT schedule version for ``loan`` from its own terms.

    Always a new version: existing versions (and any EMIs posted from them) are
    left untouched.
    """
    term = loan.term_months or 0
    principal = _q(loan.principal or 0)
    if term <= 0:
        raise ScheduleError("Loan needs a term in months before a schedule can be generated.")
    if principal <= ZERO:
        raise ScheduleError("Loan needs a positive principal.")

    start = first_payment_date or loan.first_payment_date or loan.start_date
    if start is None:
        raise ScheduleError("Loan needs a first-payment date.")

    method = loan.amortization_method
    annual_rate = Decimal(loan.annual_interest_rate or 0)
    if method == AmortizationMethod.FLAT_RATE:
        rows = _flat_rate_rows(principal, annual_rate, term)
    elif method == AmortizationMethod.REDUCING_BALANCE:
        monthly_rate = annual_rate / Decimal(100) / MONTHS_PER_YEAR
        rows = _reducing_balance_rows(principal, monthly_rate, term)
    else:  # pragma: no cover - guarded by model choices; future LENDER_PROVIDED
        raise ScheduleError(f"Unsupported amortization method {method!r}.")

    total_interest = sum((r[1] for r in rows), ZERO)
    _validate_reconciles(rows, principal, {"interest": total_interest})

    # Version numbers are monotonic and never reused — `all_objects` includes
    # soft-deleted (discarded) versions, so a retired number stays retired and the
    # audit trail can't be muddled by a recycled version.
    version_no = (
        LoanSchedule.all_objects.filter(loan=loan)
        .order_by("-version_no")
        .values_list("version_no", flat=True)
        .first()
        or 0
    ) + 1

    schedule = LoanSchedule.objects.create(
        loan=loan,
        version_no=version_no,
        method=method,
        opening_principal=principal,
        annual_interest_rate=annual_rate,
        term_months=term,
        first_payment_date=start,
        total_principal=principal,
        total_interest=total_interest,
        total_payments=principal + total_interest,
        status=LoanSchedule.Status.DRAFT,
        note=note,
    )

    balance = principal
    for index, (principal_part, interest_part) in enumerate(rows):
        closing = balance - principal_part
        VehicleLoanInstallment.objects.create(
            loan=loan,
            schedule=schedule,
            installment_no=index + 1,
            due_date=add_months(start, index),
            principal_component=principal_part,
            interest_component=interest_part,
            total_amount=principal_part + interest_part,
            opening_balance=balance,
            closing_balance=closing,
            status=FleetDocStatus.DRAFT,
        )
        balance = closing

    if balance != ZERO:
        raise ScheduleError(f"Schedule does not close to zero (residual {balance}).")

    audit_record(
        action="create",
        instance=schedule,
        actor=user,
        entity_id=loan.entity_id,
        message=(
            f"Generated schedule v{version_no} ({method}) — {term} instalments, "
            f"principal {principal}, interest {total_interest}"
        ),
    )
    return schedule


@transaction.atomic
def approve_schedule(schedule, *, user=None):
    """Approve and lock a draft schedule, superseding the loan's previous approval."""
    if schedule.status != LoanSchedule.Status.DRAFT:
        raise ScheduleError(f"Only a draft schedule can be approved (this is {schedule.status}).")

    superseded = (
        LoanSchedule.objects.filter(loan=schedule.loan, status=LoanSchedule.Status.APPROVED)
        .exclude(pk=schedule.pk)
        .update(status=LoanSchedule.Status.SUPERSEDED)
    )
    schedule.status = LoanSchedule.Status.APPROVED
    schedule.approved_at = timezone.now()
    schedule.approved_by = user
    schedule.save(update_fields=["status", "approved_at", "approved_by", "updated_at"])

    audit_record(
        action="update",
        instance=schedule,
        actor=user,
        entity_id=schedule.loan.entity_id,
        message=f"Approved schedule v{schedule.version_no}; superseded {superseded} prior version(s)",
    )
    return schedule


def posted_installment_count(schedule):
    return schedule.installments.filter(status=FleetDocStatus.POSTED).count()


@transaction.atomic
def discard_schedule(schedule, *, user=None):
    """Archive a draft schedule (soft delete). Refuses if anything on it was posted.

    The version number is *not* released — see ``generate_schedule``.
    """
    if schedule.status != LoanSchedule.Status.DRAFT:
        raise ScheduleError("Only a draft schedule can be discarded.")
    if posted_installment_count(schedule):
        raise ScheduleError("Schedule has posted instalments and cannot be discarded.")
    for installment in schedule.installments.all():
        installment.delete()
    schedule.delete()
    return None
