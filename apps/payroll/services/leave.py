"""Leave-salary accrual (doc 07 §leave).

Monthly accrual: DR Leave Salary Expense / CR Leave Provision. Payment on leave is a
separate entry (DR Leave Provision / CR Bank).
"""

from django.db import transaction

from apps.payroll.models import Leave
from apps.payroll.services.engine import ZERO, PayrollError, post_rows, q


@transaction.atomic
def accrue_leave(
    employee,
    *,
    leave_type,
    accrued_amount,
    provision_account,
    expense_account,
    as_of_date,
    entitled_days=0,
    taken_days=0,
    user=None,
):
    amount = q(accrued_amount)
    if amount <= ZERO:
        raise PayrollError("Leave accrual amount must be positive.")
    entity = employee.entity
    balance = q(entitled_days) - q(taken_days)

    leave = Leave.objects.create(
        entity=entity,
        employee=employee,
        leave_type=leave_type,
        entitled_days=q(entitled_days),
        taken_days=q(taken_days),
        balance_days=balance,
        accrued_amount=amount,
        provision_account=provision_account,
        expense_account=expense_account,
        as_of_date=as_of_date,
    )
    entry = post_rows(
        entity=entity,
        date=as_of_date,
        source_type="leave_accr",
        source_id=leave.id,
        currency=entity.base_currency,
        narration=f"Leave salary accrual {employee.code}",
        rows=[
            {"account": expense_account, "debit": amount, "description": "Leave salary expense"},
            {"account": provision_account, "credit": amount, "description": "Leave provision"},
        ],
        user=user,
    )
    leave.journal_entry = entry
    leave.save(update_fields=["journal_entry", "updated_at"])
    return leave
