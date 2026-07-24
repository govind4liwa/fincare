"""Dashboard KPI summary.

Derives the four headline figures from the balance engine (posted GL lines):
- Revenue / Expenses: the period's movement on income / expense accounts.
- Cash & Bank: the closing balance across bank + cash accounts.
- VAT payable: net output VAT (credit) less recoverable input VAT (debit).
"""

from decimal import Decimal

from apps.accounts.models import Account
from apps.reports.services.balances import account_balances

ZERO = Decimal("0.00")


def dashboard_summary(*, entity_ids, period, basis="accrual"):
    """Return the four KPIs (as Decimals) for ``entity_ids`` over ``period``."""
    revenue = expenses = cash_bank = vat_payable = ZERO
    for bal in account_balances(entity_ids=entity_ids, period=period, basis=basis):
        acct_type = bal.account.account_type
        period_net = bal.period_debit - bal.period_credit  # debit-positive
        if acct_type == Account.AccountType.REVENUE:
            revenue += -period_net  # revenue accrues on the credit side
        elif acct_type == Account.AccountType.EXPENSE:
            expenses += period_net
        elif acct_type in (Account.AccountType.BANK, Account.AccountType.CASH):
            cash_bank += bal.closing_net
        elif acct_type in (Account.AccountType.VAT_OUTPUT, Account.AccountType.VAT_INPUT):
            # closing_net is debit-positive; output VAT (credit) - input VAT (debit)
            # payable = -(sum of closing_net).
            vat_payable += -bal.closing_net
    return {
        "revenue": revenue,
        "expenses": expenses,
        "cash_bank": cash_bank,
        "vat_payable": vat_payable,
    }
