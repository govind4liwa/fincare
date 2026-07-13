"""Salary advance payment (doc 07 §advances).

Payment: DR Staff Advances / CR Bank. Recovery happens later through payslips
(see ``run.build_run``), reducing the advance balance.
"""

from django.db import transaction

from apps.payroll.models import Advance
from apps.payroll.services.engine import ZERO, PayrollError, post_rows, q


@transaction.atomic
def pay_advance(advance: Advance, *, user=None):
    if advance.status != Advance.Status.OPEN or advance.journal_entry_id is not None:
        raise PayrollError("Only an unpaid (open) advance can be paid.")
    bank_account = advance.bank_account if advance.bank_account_id else None
    if bank_account is None:
        raise PayrollError("Advance requires a bank_account to pay from.")
    amount = q(advance.amount)
    if amount <= ZERO:
        raise PayrollError("Advance amount must be positive.")

    if not advance.installment_amount or advance.installment_amount <= ZERO:
        advance.installment_amount = q(amount / max(advance.installments, 1))
    advance.recovered_amount = ZERO
    advance.balance = amount

    entry = post_rows(
        entity=advance.entity,
        date=advance.advance_date,
        source_type="staff_advance",
        source_id=advance.id,
        currency=bank_account.currency or advance.entity.base_currency,
        narration=f"Salary advance {advance.employee.code}",
        rows=[
            {"account": advance.advance_account, "debit": amount, "description": "Staff advance"},
            {
                "account": bank_account.gl_account,
                "credit": amount,
                "description": "Advance paid",
            },
        ],
        user=user,
    )
    advance.journal_entry = entry
    advance.save(
        update_fields=[
            "installment_amount",
            "recovered_amount",
            "balance",
            "journal_entry",
            "updated_at",
        ]
    )
    return advance
