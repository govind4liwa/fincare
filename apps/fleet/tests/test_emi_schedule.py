"""EMI schedule generation: both methods, reconciliation, versioning, locking."""

from datetime import date
from decimal import Decimal

import pytest

from apps.fleet.models import (
    AmortizationMethod,
    FleetDocStatus,
    LoanSchedule,
    VehicleLoan,
    VehicleLoanInstallment,
)
from apps.fleet.services.post import FleetError, post_emi
from apps.fleet.services.schedule import (
    ScheduleError,
    add_months,
    approve_schedule,
    discard_schedule,
    generate_schedule,
)

pytestmark = pytest.mark.django_db

D = Decimal
ZERO = D("0.00")
VEHICLE_LOAN = "101-200-220-001"
LOAN_INTEREST = "101-700-710-001"


def _loan(entity, vehicle, acct, *, method, principal, term, rate, first_payment=date(2026, 6, 15)):
    return VehicleLoan.objects.create(
        entity=entity,
        vehicle=vehicle,
        lender="ENBD Auto Finance",
        loan_account=acct(VEHICLE_LOAN),
        interest_account=acct(LOAN_INTEREST),
        principal=D(principal),
        term_months=term,
        annual_interest_rate=D(rate),
        amortization_method=method,
        first_payment_date=first_payment,
    )


def _assert_reconciles(schedule, opening):
    """Every schedule must tie back exactly — this is the core control."""
    rows = list(schedule.installments.order_by("installment_no"))
    assert len(rows) == schedule.term_months
    assert sum((r.principal_component for r in rows), ZERO) == opening
    assert sum((r.interest_component for r in rows), ZERO) == schedule.total_interest
    assert sum((r.total_amount for r in rows), ZERO) == schedule.total_payments
    assert schedule.total_payments == schedule.total_principal + schedule.total_interest
    # Row-level integrity + a balance that walks down to exactly zero.
    balance = opening
    for row in rows:
        assert row.total_amount == row.principal_component + row.interest_component
        assert row.opening_balance == balance
        assert row.closing_balance == balance - row.principal_component
        balance = row.closing_balance
    assert rows[-1].closing_balance == ZERO


# --- method behaviour -------------------------------------------------------


def test_reducing_balance_tapers_interest(entity, vehicle, acct):
    loan = _loan(
        entity,
        vehicle,
        acct,
        method=AmortizationMethod.REDUCING_BALANCE,
        principal="100000",
        term=12,
        rate="12",
    )
    schedule = generate_schedule(loan)

    rows = list(schedule.installments.order_by("installment_no"))
    # Interest accrues on the outstanding balance: 100000 * 12%/12 = 1000.00.
    assert rows[0].interest_component == D("1000.00")
    # ...and tapers as principal is repaid.
    assert rows[-1].interest_component < rows[0].interest_component
    assert rows[-1].principal_component > rows[0].principal_component
    assert schedule.status == LoanSchedule.Status.DRAFT
    _assert_reconciles(schedule, D("100000"))


def test_flat_rate_is_even(entity, vehicle, acct):
    loan = _loan(
        entity,
        vehicle,
        acct,
        method=AmortizationMethod.FLAT_RATE,
        principal="120000",
        term=24,
        rate="5",
    )
    schedule = generate_schedule(loan)

    # total interest = 120000 * 5% * 2 years = 12000
    assert schedule.total_interest == D("12000.00")
    rows = list(schedule.installments.order_by("installment_no"))
    assert all(r.principal_component == D("5000.00") for r in rows)
    assert all(r.interest_component == D("500.00") for r in rows)
    _assert_reconciles(schedule, D("120000"))


def test_zero_interest_loan(entity, vehicle, acct):
    loan = _loan(
        entity,
        vehicle,
        acct,
        method=AmortizationMethod.REDUCING_BALANCE,
        principal="12000",
        term=12,
        rate="0",
    )
    schedule = generate_schedule(loan)

    assert schedule.total_interest == ZERO
    rows = list(schedule.installments.order_by("installment_no"))
    assert all(r.interest_component == ZERO for r in rows)
    assert all(r.principal_component == D("1000.00") for r in rows)
    _assert_reconciles(schedule, D("12000"))


def test_rounding_lands_on_final_instalment(entity, vehicle, acct):
    # 10000/3 and 250/3 don't divide evenly — the last row absorbs the remainder.
    loan = _loan(
        entity,
        vehicle,
        acct,
        method=AmortizationMethod.FLAT_RATE,
        principal="10000",
        term=3,
        rate="10",
    )
    schedule = generate_schedule(loan)
    rows = list(schedule.installments.order_by("installment_no"))

    assert rows[0].principal_component == D("3333.33")
    assert rows[0].interest_component == D("83.33")
    assert rows[-1].principal_component == D("3333.34")
    assert rows[-1].interest_component == D("83.34")
    _assert_reconciles(schedule, D("10000"))


def test_reducing_balance_rounding_still_reconciles(entity, vehicle, acct):
    loan = _loan(
        entity,
        vehicle,
        acct,
        method=AmortizationMethod.REDUCING_BALANCE,
        principal="77777.77",
        term=7,
        rate="7.25",
    )
    schedule = generate_schedule(loan)
    _assert_reconciles(schedule, D("77777.77"))


# --- dates ------------------------------------------------------------------


def test_add_months_clamps_to_month_end():
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert add_months(date(2026, 1, 31), 2) == date(2026, 3, 31)
    assert add_months(date(2026, 12, 15), 1) == date(2027, 1, 15)


def test_non_month_end_emi_dates(entity, vehicle, acct):
    loan = _loan(
        entity,
        vehicle,
        acct,
        method=AmortizationMethod.FLAT_RATE,
        principal="9000",
        term=3,
        rate="0",
        first_payment=date(2026, 1, 31),
    )
    schedule = generate_schedule(loan)
    due = list(schedule.installments.order_by("installment_no").values_list("due_date", flat=True))
    assert due == [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31)]


def test_generation_requires_terms(entity, vehicle, acct):
    loan = _loan(
        entity,
        vehicle,
        acct,
        method=AmortizationMethod.REDUCING_BALANCE,
        principal="1000",
        term=12,
        rate="5",
        first_payment=None,
    )
    loan.start_date = None
    loan.save()
    with pytest.raises(ScheduleError):
        generate_schedule(loan)


# --- versioning, approval, locking -----------------------------------------


def test_duplicate_generation_creates_new_version(entity, vehicle, acct):
    loan = _loan(
        entity,
        vehicle,
        acct,
        method=AmortizationMethod.FLAT_RATE,
        principal="12000",
        term=12,
        rate="0",
    )
    first = generate_schedule(loan)
    second = generate_schedule(loan)

    assert (first.version_no, second.version_no) == (1, 2)
    # The first version is untouched — both remain auditable.
    first.refresh_from_db()
    assert first.status == LoanSchedule.Status.DRAFT
    assert first.installments.count() == 12
    assert second.installments.count() == 12


def test_approval_locks_and_supersedes(entity, vehicle, acct):
    loan = _loan(
        entity,
        vehicle,
        acct,
        method=AmortizationMethod.FLAT_RATE,
        principal="12000",
        term=12,
        rate="0",
    )
    v1 = approve_schedule(generate_schedule(loan))
    assert v1.status == LoanSchedule.Status.APPROVED
    assert v1.approved_at is not None

    # Approving a locked schedule again is rejected.
    with pytest.raises(ScheduleError):
        approve_schedule(v1)

    # A new version supersedes the previous approval.
    v2 = approve_schedule(generate_schedule(loan))
    v1.refresh_from_db()
    assert v1.status == LoanSchedule.Status.SUPERSEDED
    assert v2.status == LoanSchedule.Status.APPROVED


def test_cannot_discard_approved_schedule(entity, vehicle, acct):
    loan = _loan(
        entity,
        vehicle,
        acct,
        method=AmortizationMethod.FLAT_RATE,
        principal="12000",
        term=12,
        rate="0",
    )
    schedule = approve_schedule(generate_schedule(loan))
    with pytest.raises(ScheduleError):
        discard_schedule(schedule)


# --- posted instalments are protected --------------------------------------


def test_cannot_post_from_unapproved_schedule(entity, vehicle, acct, bank_enbd):
    loan = _loan(
        entity,
        vehicle,
        acct,
        method=AmortizationMethod.FLAT_RATE,
        principal="12000",
        term=12,
        rate="0",
    )
    schedule = generate_schedule(loan)  # still draft
    emi = schedule.installments.get(installment_no=1)
    emi.bank_account = bank_enbd
    emi.save()
    with pytest.raises(FleetError):
        post_emi(emi)


def test_posted_instalment_survives_regeneration(entity, vehicle, acct, bank_enbd):
    loan = _loan(
        entity,
        vehicle,
        acct,
        method=AmortizationMethod.FLAT_RATE,
        principal="12000",
        term=12,
        rate="0",
    )
    v1 = approve_schedule(generate_schedule(loan))
    emi = v1.installments.get(installment_no=1)
    emi.bank_account = bank_enbd
    emi.save()
    post_emi(emi)
    emi.refresh_from_db()
    journal_entry_id = emi.journal_entry_id
    assert emi.status == FleetDocStatus.POSTED

    # Amending the loan schedule creates v2; the posted EMI is untouched.
    generate_schedule(loan, note="rescheduled")
    emi.refresh_from_db()
    assert emi.status == FleetDocStatus.POSTED
    assert emi.journal_entry_id == journal_entry_id
    assert emi.schedule_id == v1.id

    # ...and the version carrying it cannot be discarded.
    v1.refresh_from_db()
    with pytest.raises(ScheduleError):
        discard_schedule(v1)


def test_discard_removes_draft_schedule(entity, vehicle, acct):
    loan = _loan(
        entity,
        vehicle,
        acct,
        method=AmortizationMethod.FLAT_RATE,
        principal="12000",
        term=12,
        rate="0",
    )
    schedule = generate_schedule(loan)
    schedule_id = schedule.id
    discard_schedule(schedule)
    assert not LoanSchedule.objects.filter(id=schedule_id).exists()
    assert not VehicleLoanInstallment.objects.filter(schedule_id=schedule_id).exists()


def test_discarded_version_number_is_never_reused(entity, vehicle, acct):
    """A retired version stays retired — schedules are soft-deleted for audit."""
    loan = _loan(
        entity,
        vehicle,
        acct,
        method=AmortizationMethod.FLAT_RATE,
        principal="12000",
        term=12,
        rate="0",
    )
    discard_schedule(generate_schedule(loan))
    assert generate_schedule(loan).version_no == 2
