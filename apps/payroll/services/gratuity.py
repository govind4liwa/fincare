"""End-of-service gratuity (EOSB) — monthly accrual and final settlement.

Day-rate and caps are config (``settings``), defaulting to UAE Labour Law:
~21 days of basic per year for the first 5 years, ~30 days/year thereafter, capped
at 2 years' wage. Postings (doc 07):
    Accrual:     DR Gratuity Expense   / CR Gratuity Provision
    Settlement:  DR Gratuity Provision / DR Gratuity Expense (shortfall) / CR Bank
"""

from decimal import Decimal

from django.db import transaction
from django.db.models import Q, Sum

from apps.audit.services import record as audit_record
from apps.payroll.models import EmployeeSalary, Gratuity
from apps.payroll.services.config import gratuity_eligible_days, gratuity_rule
from apps.payroll.services.engine import ZERO, PayrollError, post_rows, q

DAYS_PER_YEAR = Decimal("365.25")


def _service_years(join_date, as_of_date):
    if as_of_date < join_date:
        raise PayrollError("as_of_date precedes the employee join date.")
    days = Decimal((as_of_date - join_date).days)
    return (days / DAYS_PER_YEAR).quantize(Decimal("0.0001"))


def _gratuity_basis(employee, as_of_date):
    rows = EmployeeSalary.objects.filter(
        Q(effective_to__isnull=True) | Q(effective_to__gte=as_of_date),
        employee=employee,
        component__is_gratuity_base=True,
        effective_from__lte=as_of_date,
    )
    return q(rows.aggregate(total=Sum("amount"))["total"] or ZERO)


@transaction.atomic
def accrue_gratuity(
    employee,
    *,
    as_of_date,
    provision_account,
    expense_account,
    basis_salary=None,
    user=None,
):
    entity = employee.entity
    rule = gratuity_rule(entity)
    service_years = _service_years(employee.join_date, as_of_date)
    basis = q(basis_salary) if basis_salary is not None else _gratuity_basis(employee, as_of_date)
    if basis <= ZERO:
        raise PayrollError("No gratuity-base salary configured for the employee.")

    eligible_days = q(gratuity_eligible_days(service_years, rule))
    day_rate = basis / Decimal(rule["month_days"])
    amount = q(day_rate * eligible_days)
    cap = q(Decimal(rule["cap_years"]) * Decimal(12) * basis)
    if amount > cap:
        amount = cap

    gratuity = Gratuity.objects.create(
        entity=entity,
        employee=employee,
        as_of_date=as_of_date,
        service_years=service_years,
        basis_salary=basis,
        eligible_days=eligible_days,
        amount=amount,
        type=Gratuity.Type.ACCRUAL,
        provision_account=provision_account,
        expense_account=expense_account,
    )
    entry = post_rows(
        entity=entity,
        date=as_of_date,
        source_type="gratuity_acc",
        source_id=gratuity.id,
        currency=entity.base_currency,
        narration=f"Gratuity accrual {employee.code}",
        rows=[
            {"account": expense_account, "debit": amount, "description": "Gratuity expense"},
            {"account": provision_account, "credit": amount, "description": "Gratuity provision"},
        ],
        user=user,
    )
    gratuity.journal_entry = entry
    gratuity.status = Gratuity.Status.POSTED
    gratuity.save(update_fields=["journal_entry", "status", "updated_at"])

    audit_record(
        action="post",
        instance=gratuity,
        actor=user,
        entity_id=entity.id,
        message=f"Accrued gratuity {employee.code} {amount} ({eligible_days} days)",
    )
    return gratuity


@transaction.atomic
def settle_gratuity(
    employee,
    *,
    as_of_date,
    amount,
    provision_account,
    expense_account,
    bank_account,
    user=None,
):
    """Final settlement: clear the accrued provision, expense any shortfall, pay bank."""
    entity = employee.entity
    payable = q(amount)
    if payable <= ZERO:
        raise PayrollError("Settlement amount must be positive.")

    accrued = Gratuity.objects.filter(
        employee=employee, type=Gratuity.Type.ACCRUAL, status=Gratuity.Status.POSTED
    ).aggregate(total=Sum("amount"))["total"]
    provisioned = q(accrued or ZERO)
    from_provision = min(provisioned, payable)
    shortfall = q(payable - from_provision)

    rows = []
    if from_provision > ZERO:
        rows.append(
            {"account": provision_account, "debit": from_provision, "description": "Use provision"}
        )
    if shortfall > ZERO:
        rows.append(
            {"account": expense_account, "debit": shortfall, "description": "Gratuity shortfall"}
        )
    rows.append(
        {"account": bank_account.gl_account, "credit": payable, "description": "Gratuity paid"}
    )

    gratuity = Gratuity.objects.create(
        entity=entity,
        employee=employee,
        as_of_date=as_of_date,
        service_years=_service_years(employee.join_date, as_of_date),
        basis_salary=ZERO,
        eligible_days=ZERO,
        amount=payable,
        type=Gratuity.Type.SETTLEMENT,
        provision_account=provision_account,
        expense_account=expense_account,
        bank_account=bank_account,
    )
    entry = post_rows(
        entity=entity,
        date=as_of_date,
        source_type="gratuity_set",
        source_id=gratuity.id,
        currency=bank_account.currency or entity.base_currency,
        narration=f"Gratuity settlement {employee.code}",
        rows=rows,
        user=user,
    )
    gratuity.journal_entry = entry
    gratuity.status = Gratuity.Status.SETTLED
    gratuity.save(update_fields=["journal_entry", "status", "updated_at"])
    return gratuity
