"""Payroll run accrual, WPS SIF reconciliation, and gratuity accrual tests."""

from datetime import date
from decimal import Decimal

import pytest

from apps.payroll.models import Advance, Gratuity, Run, RunStatus
from apps.payroll.services.engine import PayrollError
from apps.payroll.services.gratuity import accrue_gratuity
from apps.payroll.services.run import build_run, post_run
from apps.payroll.services.wps import export_sif, generate_wps
from apps.payroll.tests.conftest import (
    DRIVER_SALARY,
    GRATUITY_EXPENSE,
    GRATUITY_PROVISION,
    SALARIES_PAYABLE,
    STAFF_ADVANCES,
)

pytestmark = pytest.mark.django_db


def _run(entity):
    return Run.objects.create(entity=entity, salary_month="2026-06", run_date=date(2026, 6, 30))


def test_payroll_run_accrual_balanced(entity, employee):
    run = _run(entity)
    build_run(run)
    assert run.gross_total == Decimal("4000.00")
    assert run.net_total == Decimal("4000.00")

    post_run(run)
    run.refresh_from_db()
    assert run.status == RunStatus.POSTED
    je = run.journal_entry
    assert je.total_debit == je.total_credit == Decimal("4000.00")
    lines = {ln.account.code: (ln.debit, ln.credit) for ln in je.lines.all()}
    assert lines[DRIVER_SALARY] == (Decimal("4000.00"), Decimal("0.00"))  # BASIC + HRA
    assert lines[SALARIES_PAYABLE] == (Decimal("0.00"), Decimal("4000.00"))


def test_run_recovers_advance_and_stays_balanced(entity, employee, acct):
    adv = Advance.objects.create(
        entity=entity,
        employee=employee,
        advance_date=date(2026, 5, 1),
        amount=Decimal("1200.00"),
        installments=3,
        installment_amount=Decimal("400.00"),
        balance=Decimal("1200.00"),
        advance_account=acct(STAFF_ADVANCES),
        status=Advance.Status.OPEN,
    )
    run = _run(entity)
    build_run(run)

    payslip = run.payslips.get(employee=employee)
    assert payslip.advance_recovery == Decimal("400.00")
    assert payslip.net_pay == Decimal("3600.00")  # 4000 gross - 400 recovery
    adv.refresh_from_db()
    assert adv.balance == Decimal("800.00")
    assert adv.status == Advance.Status.RECOVERING

    post_run(run)
    je = run.journal_entry
    assert je.total_debit == je.total_credit == Decimal("4000.00")
    lines = {ln.account.code: (ln.debit, ln.credit) for ln in je.lines.all()}
    assert lines[DRIVER_SALARY] == (Decimal("4000.00"), Decimal("0.00"))
    assert lines[STAFF_ADVANCES] == (Decimal("0.00"), Decimal("400.00"))
    assert lines[SALARIES_PAYABLE] == (Decimal("0.00"), Decimal("3600.00"))


def test_sif_totals_reconcile(entity, make_employee):
    make_employee("E001", "3000.00", "1000.00")
    make_employee("E002", "5000.00", "2000.00")
    run = _run(entity)
    build_run(run)
    post_run(run)

    batch = generate_wps(run, employer_eid="EST-123", employer_bank_routing="CBUAEAD")
    assert batch.total_records == 2
    assert batch.fixed_total == Decimal("8000.00")  # BASIC 3000 + 5000
    assert batch.variable_total == Decimal("3000.00")  # HRA 1000 + 2000
    assert batch.total_salary == Decimal("11000.00")

    rec_sum = sum(r.fixed_amount + r.variable_amount for r in batch.records.all())
    assert rec_sum == batch.total_salary  # reconciles

    content = export_sif(batch)
    assert content.startswith("SCR,")
    assert content.count("\nEDR,") == 2
    assert batch.sif_file_ref.endswith(".csv")


def test_sif_export_rejects_unreconciled_batch(entity, make_employee):
    make_employee("E001", "3000.00", "1000.00")
    run = _run(entity)
    build_run(run)
    post_run(run)
    batch = generate_wps(run, employer_eid="EST-123", employer_bank_routing="CBUAEAD")
    batch.total_salary = Decimal("9999.00")  # tamper
    batch.save(update_fields=["total_salary"])
    with pytest.raises(PayrollError, match="SIF total"):
        export_sif(batch)


def test_gratuity_accrual(entity, employee, acct):
    # join 2022-06-30 -> 2026-06-30 = 1461 days / 365.25 = 4.0 service years.
    gratuity = accrue_gratuity(
        employee,
        as_of_date=date(2026, 6, 30),
        provision_account=acct(GRATUITY_PROVISION),
        expense_account=acct(GRATUITY_EXPENSE),
    )
    assert gratuity.service_years == Decimal("4.0000")
    assert gratuity.eligible_days == Decimal("84.00")  # 4 years * 21 days
    assert gratuity.basis_salary == Decimal("3000.00")  # BASIC (gratuity base)
    assert gratuity.amount == Decimal("8400.00")  # (3000/30) * 84
    assert gratuity.status == Gratuity.Status.POSTED

    je = gratuity.journal_entry
    assert je.total_debit == je.total_credit == Decimal("8400.00")
    lines = {ln.account.code: (ln.debit, ln.credit) for ln in je.lines.all()}
    assert lines[GRATUITY_EXPENSE] == (Decimal("8400.00"), Decimal("0.00"))
    assert lines[GRATUITY_PROVISION] == (Decimal("0.00"), Decimal("8400.00"))
