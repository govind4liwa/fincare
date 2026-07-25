"""Vehicle-loan EMI schedule generation, versioning, and approval.

The lender's approved repayment schedule is the authoritative source; this module
models it. A schedule is generated as ``DRAFT``, must reconcile **exactly**
(instalments sum back to the opening principal and the balance closes at zero),
and is locked once ``APPROVED``. Regenerating never edits an existing version —
it creates a new one and supersedes the previous approval, so posted EMIs are
never rewritten.

Three methods are supported (per loan):

* ``REDUCING_BALANCE`` — annuity. Interest accrues on the outstanding balance, so
  it is high early and tapers. ``EMI = P·i / (1 − (1+i)^−n)``; with a zero rate
  this degrades to ``P / n``.
* ``FLAT_RATE`` — flat quoting with a flat split. Total interest is
  ``P · rate · years`` spread evenly, as is principal.
* ``FLAT_QUOTED_EFFECTIVE`` — flat quoting with an effective split (design doc
  08 §4.3, verified against the reference workbook). The contract totals come
  from the flat quote (``interest = P · flat · n/12``, ``EMI = (P + interest)/n``)
  but each EMI is split principal/interest at the **implied monthly effective
  rate** — the IRR ``r`` solving ``P = EMI · (1 − (1+r)^−n) / r`` — so interest
  tapers like a reducing-balance loan while the contract stays flat-quoted.
  ``r`` is derived deterministically from ``(P, EMI, n)`` alone.

Rounding differences from 2-dp quantisation are absorbed by the **final**
instalment, which is what makes the exact reconciliation possible.
"""

from calendar import monthrange
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, localcontext

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


#: Working precision for the IRR solve — far beyond the 2-dp money grid, so the
#: quantised splits are stable regardless of magnitude.
_IRR_PRECISION = 50
_IRR_TOLERANCE = Decimal("1e-30")
_IRR_MAX_NEWTON = 80
_IRR_MAX_BISECT = 200
_RATE_PLACES = Decimal("0.000001")


def _implied_monthly_rate(principal: Decimal, emi: Decimal, term: int) -> Decimal:
    """The monthly effective rate implied by ``term`` EMIs amortising ``principal``.

    Solves ``f(r) = EMI · (1 − (1+r)^−n) / r − P = 0`` on Decimal only (no binary
    floats): Newton with the analytic derivative, falling back to bisection.
    Deterministic — fixed precision, fixed iteration rule, inputs only.
    """
    with localcontext() as ctx:
        ctx.prec = _IRR_PRECISION
        p, emi_ = Decimal(principal), Decimal(emi)
        n = Decimal(term)
        total = emi_ * n
        if total == p:
            return ZERO  # zero-interest contract
        if total < p:
            raise ScheduleError(
                f"Instalments ({total}) cannot amortise the principal ({p}) — "
                "no positive effective rate exists."
            )

        def f(r: Decimal) -> Decimal:
            v = (Decimal(1) + r) ** -term
            return emi_ * (Decimal(1) - v) / r - p

        def f_prime(r: Decimal) -> Decimal:
            one_plus = Decimal(1) + r
            v = one_plus**-term
            return emi_ * (n * v / one_plus * r - (Decimal(1) - v)) / (r * r)

        # Standard closed-form first guess for an annuity rate.
        r = Decimal(2) * (total - p) / (p * (n + 1))
        for _ in range(_IRR_MAX_NEWTON):
            derivative = f_prime(r)
            if derivative == 0:
                break
            step = f(r) / derivative
            r -= step
            if r <= 0 or r > 1:
                break  # left the plausible domain — bisection will take over
            if abs(step) < _IRR_TOLERANCE:
                return +r
        # Bisection fallback: f is positive near 0 and decreasing in r.
        low, high = Decimal("1e-12"), Decimal("1")
        for _ in range(20):
            if f(high) < 0:
                break
            high *= 2
        else:
            raise ScheduleError("Implied-rate solve did not converge (no sign change found).")
        for _ in range(_IRR_MAX_BISECT):
            mid = (low + high) / 2
            if f(mid) > 0:
                low = mid
            else:
                high = mid
            if high - low < _IRR_TOLERANCE:
                return +((low + high) / 2)
        raise ScheduleError("Implied-rate solve did not converge.")


def effective_annual_rate_percent(monthly_rate: Decimal) -> Decimal:
    """``(1+r)^12 − 1`` as a percentage, 6 dp (e.g. 8.753846)."""
    with localcontext() as ctx:
        ctx.prec = _IRR_PRECISION
        ear = ((Decimal(1) + monthly_rate) ** 12 - Decimal(1)) * Decimal(100)
    return ear.quantize(_RATE_PLACES, rounding=ROUND_HALF_UP)


def _flat_quoted_effective_rows(principal: Decimal, flat_rate: Decimal, term: int):
    """Rows + (emi, total_interest, monthly_rate) for the flat-quoted method.

    Contract totals come from the flat quote; the split walks the balance down at
    the implied monthly rate. The final instalment absorbs *all* rounding: its
    total is the contract remainder after ``n−1`` equal EMIs, its principal
    clears the balance exactly, and its interest is the difference — so the
    schedule reconciles exactly by construction.
    """
    years = Decimal(term) / MONTHS_PER_YEAR
    total_interest = _q(principal * flat_rate / Decimal(100) * years)
    contract_total = principal + total_interest
    emi = _q(contract_total / term)
    monthly_rate = _implied_monthly_rate(principal, emi, term)

    rows = []
    balance = principal
    for _ in range(term - 1):
        interest = _q(balance * monthly_rate)
        principal_part = min(_q(emi - interest), balance)
        balance -= principal_part
        rows.append((principal_part, interest))
    final_total = contract_total - emi * (term - 1)
    rows.append((balance, final_total - balance))
    return rows, emi, total_interest, monthly_rate


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
    derived_ear = None
    if method == AmortizationMethod.FLAT_RATE:
        if annual_rate < 0:
            raise ScheduleError("Interest rate cannot be negative.")
        rows = _flat_rate_rows(principal, annual_rate, term)
    elif method == AmortizationMethod.REDUCING_BALANCE:
        if annual_rate < 0:
            raise ScheduleError("Interest rate cannot be negative.")
        monthly_rate = annual_rate / Decimal(100) / MONTHS_PER_YEAR
        rows = _reducing_balance_rows(principal, monthly_rate, term)
    elif method == AmortizationMethod.FLAT_QUOTED_EFFECTIVE:
        if loan.quoted_flat_rate is None:
            raise ScheduleError("FLAT_QUOTED_EFFECTIVE needs the loan's quoted flat rate (%/year).")
        flat_rate = Decimal(loan.quoted_flat_rate)
        if flat_rate < 0:
            raise ScheduleError("Quoted flat rate cannot be negative.")
        rows, _emi, _flat_interest, monthly_rate = _flat_quoted_effective_rows(
            principal, flat_rate, term
        )
        derived_ear = effective_annual_rate_percent(monthly_rate)
        # The snapshot rate for this method is the *quoted flat* rate — the
        # effective rate is reproducible from (principal, term, that rate).
        annual_rate = flat_rate
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

    if derived_ear is not None:
        # Snapshot the derived effective annual rate on the loan (design doc 08
        # §4.3): quoted and effective rates are both stored, never recomputed
        # from each other after approval.
        loan.effective_annual_rate = derived_ear
        loan.save(update_fields=["effective_annual_rate", "updated_at"])

    audit_record(
        action="create",
        instance=schedule,
        actor=user,
        entity_id=loan.entity_id,
        message=(
            f"Generated schedule v{version_no} ({method}) — {term} instalments, "
            f"principal {principal}, interest {total_interest}"
            + (f", effective annual rate {derived_ear}%" if derived_ear is not None else "")
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
