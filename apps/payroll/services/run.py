"""Build payroll runs (payslips from the effective salary structure) and post the
salary accrual JE. The WPS / bank payment is posted separately (see ``pay_run``).

Accrual (doc 07):
    DR  Salary Expense (per earning component account)   = Σ earnings
    CR  deduction accounts (incl. Staff Advance recovery) = Σ deductions
    CR  Salaries Payable / WPS Clearing (per employee)    = Σ net pay
Net = gross earnings − deductions; advance recovery is a deduction line crediting
the advance's Staff Advances account and reducing the linked ``Advance``.
"""

from collections import OrderedDict

from django.db import transaction
from django.db.models import Q

from apps.audit.services import record as audit_record
from apps.payroll.models import (
    Advance,
    ComponentType,
    EmployeeSalary,
    Payslip,
    PayslipLine,
    PayslipStatus,
    RunStatus,
    SalaryComponent,
)
from apps.payroll.services.engine import ZERO, PayrollError, post_rows, q

ADVANCE_COMPONENT_CODE = "ADV"


def _current_salary(employee, as_of):
    return list(
        EmployeeSalary.objects.filter(employee=employee, effective_from__lte=as_of)
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=as_of))
        .select_related("component")
    )


def _advance_component(entity):
    return (
        SalaryComponent.objects.filter(code=ADVANCE_COMPONENT_CODE)
        .filter(Q(entity=entity) | Q(entity__isnull=True))
        .first()
    )


@transaction.atomic
def build_run(run, *, employees=None, user=None):
    """(Re)build payslips for the run from the current salary structure."""
    if run.status != RunStatus.DRAFT:
        raise PayrollError(f"Cannot build a run in status {run.status!r}.")
    run.payslips.all().hard_delete()

    if employees is None:
        employees = run.entity.employees.filter(status="active")
    adv_component = _advance_component(run.entity)

    gross_total = ded_total = net_total = ZERO
    for emp in employees:
        rows = _current_salary(emp, run.run_date)
        if not rows:
            continue
        payslip = Payslip.objects.create(run=run, employee=emp)
        gross = ded = ZERO
        for sr in rows:
            amount = q(sr.amount)
            PayslipLine.objects.create(
                payslip=payslip,
                component=sr.component,
                component_type=sr.component.component_type,
                amount=amount,
            )
            if sr.component.component_type == ComponentType.EARNING:
                gross += amount
            else:
                ded += amount

        adv_rec = _recover_advances(emp, adv_component, payslip)
        ded += adv_rec
        net = q(gross - ded)

        payslip.gross_earnings = gross
        payslip.total_deductions = ded
        payslip.advance_recovery = adv_rec
        payslip.net_pay = net
        payslip.status = PayslipStatus.FINALISED
        payslip.save()

        gross_total += gross
        ded_total += ded
        net_total += net

    run.gross_total = gross_total
    run.deduction_total = ded_total
    run.net_total = net_total
    run.save(update_fields=["gross_total", "deduction_total", "net_total", "updated_at"])
    return run


def _recover_advances(employee, adv_component, payslip):
    """Recover open advances (one installment each, capped by balance) for the period."""
    open_advances = Advance.objects.filter(
        employee=employee, status__in=[Advance.Status.OPEN, Advance.Status.RECOVERING]
    ).order_by("advance_date")
    total = ZERO
    for adv in open_advances:
        if adv.balance <= ZERO:
            continue
        instal = q(adv.installment_amount) if adv.installment_amount else q(adv.balance)
        recover = min(instal, q(adv.balance))
        if recover <= ZERO:
            continue
        adv.recovered_amount = q(adv.recovered_amount + recover)
        adv.balance = q(adv.amount - adv.recovered_amount)
        adv.status = Advance.Status.CLEARED if adv.balance <= ZERO else Advance.Status.RECOVERING
        adv.save(update_fields=["recovered_amount", "balance", "status", "updated_at"])
        total += recover

    if total > ZERO:
        if adv_component is None:
            raise PayrollError(
                f"Advance recovery requires a salary component {ADVANCE_COMPONENT_CODE!r}."
            )
        PayslipLine.objects.create(
            payslip=payslip,
            component=adv_component,
            component_type=ComponentType.DEDUCTION,
            amount=total,
        )
    return total


@transaction.atomic
def post_run(run, *, user=None):
    """Post the salary accrual JE for a built run."""
    if run.status not in {RunStatus.DRAFT, RunStatus.APPROVED}:
        raise PayrollError(f"Cannot post a run in status {run.status!r}.")
    payslips = list(run.payslips.prefetch_related("lines__component").select_related("employee"))
    if not payslips:
        raise PayrollError("Run has no payslips; build it first.")

    earnings = OrderedDict()  # account -> Σ debit
    deductions = OrderedDict()  # account -> Σ credit
    payable = OrderedDict()  # account -> Σ credit (net)
    for ps in payslips:
        for ln in ps.lines.all():
            acct = ln.component.account
            if acct is None:
                raise PayrollError(f"Component {ln.component.code!r} has no GL account configured.")
            target = earnings if ln.component_type == ComponentType.EARNING else deductions
            target[acct] = target.get(acct, ZERO) + q(ln.amount)
        pa = ps.employee.payable_account
        payable[pa] = payable.get(pa, ZERO) + q(ps.net_pay)

    rows = []
    for acct, amt in earnings.items():
        rows.append({"account": acct, "debit": amt, "description": "Salary expense"})
    for acct, amt in deductions.items():
        if amt > ZERO:
            rows.append({"account": acct, "credit": amt, "description": "Payroll deduction"})
    for acct, amt in payable.items():
        if amt > ZERO:
            rows.append({"account": acct, "credit": amt, "description": "Net salary payable"})

    entry = post_rows(
        entity=run.entity,
        date=run.run_date,
        source_type="payroll_accr",
        source_id=run.id,
        currency=run.entity.base_currency,
        narration=f"Payroll accrual {run.salary_month}",
        rows=rows,
        user=user,
    )
    run.journal_entry = entry
    run.status = RunStatus.POSTED
    run.save(update_fields=["journal_entry", "status", "updated_at"])

    audit_record(
        action="post",
        instance=run,
        actor=user,
        entity_id=run.entity_id,
        message=f"Posted payroll accrual {run.salary_month} net={run.net_total}",
    )
    return run


@transaction.atomic
def pay_run(run, *, bank_account, user=None, date=None):
    """Post the salary payment JE: DR Salaries Payable / CR Bank (separate from accrual)."""
    if run.status != RunStatus.POSTED:
        raise PayrollError("Only a posted (accrued) run can be paid.")
    net = q(run.net_total)
    if net <= ZERO:
        raise PayrollError("Nothing to pay.")
    payable_accounts = OrderedDict()
    for ps in run.payslips.select_related("employee"):
        pa = ps.employee.payable_account
        payable_accounts[pa] = payable_accounts.get(pa, ZERO) + q(ps.net_pay)

    rows = [
        {"account": acct, "debit": amt, "description": "Clear salary payable"}
        for acct, amt in payable_accounts.items()
        if amt > ZERO
    ]
    rows.append({"account": bank_account.gl_account, "credit": net, "description": "Salary paid"})

    entry = post_rows(
        entity=run.entity,
        date=date or run.run_date,
        source_type="payroll_pay",
        source_id=run.id,
        currency=bank_account.currency or run.entity.base_currency,
        narration=f"Payroll payment {run.salary_month}",
        rows=rows,
        user=user,
    )
    run.payment_entry = entry
    run.status = RunStatus.PAID
    run.save(update_fields=["payment_entry", "status", "updated_at"])
    return run
