"""FLAT_QUOTED_EFFECTIVE amortization (design doc 08 §4.3, Slice A).

The golden-file test validates every row of the generated schedule against the
reference workbook (``docs/supporting-source/Auto-Loan-Repayment-Schedule-
Updated.xlsx``) — due dates, EMI, principal/interest splits, and opening/closing
balances, not just the totals. The workbook's DAYS column is informational and
deliberately absent from both fixture assertions and the engine.
"""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from apps.fleet.models import AmortizationMethod, FleetDocStatus, VehicleLoan
from apps.fleet.services.post import post_emi
from apps.fleet.services.schedule import (
    ScheduleError,
    _implied_monthly_rate,
    approve_schedule,
    effective_annual_rate_percent,
    generate_schedule,
)

pytestmark = pytest.mark.django_db

D = Decimal
ZERO = D("0.00")
VEHICLE_LOAN = "101-200-220-001"
LOAN_INTEREST = "101-700-710-001"

FIXTURE = Path(__file__).parent / "fixtures" / "lexus_es300h_flat_quoted_effective.json"


@pytest.fixture(scope="module")
def golden():
    with FIXTURE.open() as fh:
        return json.load(fh)


def _flat_loan(entity, vehicle, acct, *, principal, term, flat_rate, first_payment):
    return VehicleLoan.objects.create(
        entity=entity,
        vehicle=vehicle,
        lender="Star Regency (self-financed reference deal)",
        loan_account=acct(VEHICLE_LOAN),
        interest_account=acct(LOAN_INTEREST),
        principal=D(principal),
        term_months=term,
        quoted_flat_rate=D(flat_rate),
        amortization_method=AmortizationMethod.FLAT_QUOTED_EFFECTIVE,
        first_payment_date=first_payment,
    )


# --- golden file ------------------------------------------------------------


def test_golden_workbook_all_36_rows(entity, vehicle, acct, golden):
    """Every cell of the reference schedule must be reproduced exactly."""
    inputs = golden["inputs"]
    loan = _flat_loan(
        entity,
        vehicle,
        acct,
        principal=inputs["principal"],
        term=inputs["term_months"],
        flat_rate=inputs["quoted_flat_rate_percent"],
        first_payment=date.fromisoformat(inputs["first_payment_date"]),
    )
    schedule = generate_schedule(loan)

    expected = golden["expected"]
    assert schedule.total_principal == D(inputs["principal"])
    assert schedule.total_interest == D(expected["total_interest"])
    assert schedule.total_payments == D(expected["total_payments"])
    assert schedule.annual_interest_rate == D(inputs["quoted_flat_rate_percent"])

    rows = list(schedule.installments.order_by("installment_no"))
    assert len(rows) == len(golden["rows"]) == 36
    for row, want in zip(rows, golden["rows"], strict=True):
        assert row.installment_no == want["no"]
        assert row.due_date == date.fromisoformat(want["due_date"])
        assert row.total_amount == D(want["total"])
        assert row.principal_component == D(want["principal"])
        assert row.interest_component == D(want["interest"])
        assert row.opening_balance == D(want["opening"])
        assert row.closing_balance == D(want["closing"])

    assert rows[0].total_amount == D(expected["emi"])
    assert rows[-1].due_date == date.fromisoformat(expected["final_due_date"])
    assert rows[-1].closing_balance == D(expected["closing_balance"]) == ZERO


def test_golden_derived_rates(entity, vehicle, acct, golden):
    inputs, expected = golden["inputs"], golden["expected"]
    r = _implied_monthly_rate(D(inputs["principal"]), D(expected["emi"]), inputs["term_months"])
    assert (r * 100).quantize(D("0.000001")) == D(expected["implied_monthly_rate_6dp_percent"])
    assert effective_annual_rate_percent(r) == D(expected["effective_annual_rate_percent"])

    loan = _flat_loan(
        entity,
        vehicle,
        acct,
        principal=inputs["principal"],
        term=inputs["term_months"],
        flat_rate=inputs["quoted_flat_rate_percent"],
        first_payment=date.fromisoformat(inputs["first_payment_date"]),
    )
    generate_schedule(loan)
    loan.refresh_from_db()
    # Both rates stored, quoted and derived (Decimal(9,6) precision). The deal
    # sheet displays "4.5%", but the contract rate is back-solved from the round
    # EMI (20,166 / 447,750 = 4.503853%) — 3 dp storage would drift the totals.
    assert loan.quoted_flat_rate == D("4.503853")
    assert loan.effective_annual_rate == D(expected["effective_annual_rate_percent"])


# --- determinism ------------------------------------------------------------


def test_generation_is_deterministic(entity, vehicle, acct, golden):
    inputs = golden["inputs"]
    loan = _flat_loan(
        entity,
        vehicle,
        acct,
        principal=inputs["principal"],
        term=inputs["term_months"],
        flat_rate=inputs["quoted_flat_rate_percent"],
        first_payment=date.fromisoformat(inputs["first_payment_date"]),
    )
    first = generate_schedule(loan)
    second = generate_schedule(loan)
    assert second.version_no == first.version_no + 1

    def snapshot(schedule):
        return [
            (
                r.installment_no,
                r.due_date,
                r.total_amount,
                r.principal_component,
                r.interest_component,
                r.opening_balance,
                r.closing_balance,
            )
            for r in schedule.installments.order_by("installment_no")
        ]

    assert snapshot(first) == snapshot(second)


# --- edges & validation -----------------------------------------------------


def test_zero_flat_rate_degrades_to_equal_principal(entity, vehicle, acct):
    loan = _flat_loan(
        entity,
        vehicle,
        acct,
        principal="90000",
        term=36,
        flat_rate="0",
        first_payment=date(2026, 6, 15),
    )
    schedule = generate_schedule(loan)
    rows = list(schedule.installments.order_by("installment_no"))
    assert schedule.total_interest == ZERO
    assert all(r.interest_component == ZERO for r in rows)
    assert sum((r.principal_component for r in rows), ZERO) == D("90000.00")
    assert rows[-1].closing_balance == ZERO


def test_rounding_residual_lands_only_on_final_instalment(entity, vehicle, acct):
    # 100,000 @ 5.75% flat / 7 months — deliberately non-round splits.
    loan = _flat_loan(
        entity,
        vehicle,
        acct,
        principal="100000",
        term=7,
        flat_rate="5.75",
        first_payment=date(2026, 6, 15),
    )
    schedule = generate_schedule(loan)
    rows = list(schedule.installments.order_by("installment_no"))
    # All instalments except the last carry the identical quantised EMI.
    emis = {r.total_amount for r in rows[:-1]}
    assert len(emis) == 1
    assert sum((r.total_amount for r in rows), ZERO) == schedule.total_payments
    assert sum((r.principal_component for r in rows), ZERO) == D("100000.00")
    assert sum((r.interest_component for r in rows), ZERO) == schedule.total_interest
    assert rows[-1].closing_balance == ZERO


def test_single_instalment_term(entity, vehicle, acct):
    loan = _flat_loan(
        entity,
        vehicle,
        acct,
        principal="12000",
        term=1,
        flat_rate="6",
        first_payment=date(2026, 6, 15),
    )
    schedule = generate_schedule(loan)
    row = schedule.installments.get()
    assert row.principal_component == D("12000.00")
    assert row.interest_component == D("60.00")  # 12000 × 6% × 1/12
    assert row.closing_balance == ZERO


def test_missing_quoted_flat_rate_fails_clearly(entity, vehicle, acct):
    loan = VehicleLoan.objects.create(
        entity=entity,
        vehicle=vehicle,
        loan_account=acct(VEHICLE_LOAN),
        interest_account=acct(LOAN_INTEREST),
        principal=D("10000"),
        term_months=6,
        quoted_flat_rate=None,
        amortization_method=AmortizationMethod.FLAT_QUOTED_EFFECTIVE,
        first_payment_date=date(2026, 6, 15),
    )
    with pytest.raises(ScheduleError, match="quoted flat rate"):
        generate_schedule(loan)


def test_negative_quoted_flat_rate_rejected(entity, vehicle, acct):
    loan = _flat_loan(
        entity,
        vehicle,
        acct,
        principal="10000",
        term=6,
        flat_rate="-1",
        first_payment=date(2026, 6, 15),
    )
    with pytest.raises(ScheduleError, match="cannot be negative"):
        generate_schedule(loan)


def test_solver_rejects_unamortisable_inputs():
    # 3 EMIs of 1.00 can never amortise 100.00 — no positive rate exists.
    with pytest.raises(ScheduleError, match="cannot amortise"):
        _implied_monthly_rate(D("100"), D("1"), 3)


# --- locking / immutability with the new method -----------------------------


def test_regeneration_never_rewrites_posted_instalment(entity, vehicle, acct, bank_enbd):
    loan = _flat_loan(
        entity,
        vehicle,
        acct,
        principal="60000",
        term=6,
        flat_rate="4.5",
        first_payment=date(2026, 6, 15),
    )
    v1 = generate_schedule(loan)
    approve_schedule(v1)
    first = v1.installments.order_by("installment_no").first()
    first.bank_account = bank_enbd
    first.save(update_fields=["bank_account"])
    post_emi(first)
    posted_snapshot = (
        first.principal_component,
        first.interest_component,
        first.journal_entry_id,
    )

    v2 = generate_schedule(loan)
    approve_schedule(v2)
    v1.refresh_from_db()
    first.refresh_from_db()
    assert v1.status == v1.Status.SUPERSEDED
    assert first.status == FleetDocStatus.POSTED
    assert (
        first.principal_component,
        first.interest_component,
        first.journal_entry_id,
    ) == posted_snapshot


def test_approved_schedule_cannot_be_reapproved_or_discarded(entity, vehicle, acct):
    from apps.fleet.services.schedule import discard_schedule

    loan = _flat_loan(
        entity,
        vehicle,
        acct,
        principal="60000",
        term=6,
        flat_rate="4.5",
        first_payment=date(2026, 6, 15),
    )
    schedule = generate_schedule(loan)
    approve_schedule(schedule)
    with pytest.raises(ScheduleError):
        approve_schedule(schedule)
    with pytest.raises(ScheduleError):
        discard_schedule(schedule)
