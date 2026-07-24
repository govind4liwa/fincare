"""Financial statements assembled from the balance engine + COA band ranges.

The COA is banded (ADR-0004): 1xx assets, 2xx liabilities, 3xx equity, 4xx income,
5xx direct cost, 6xx overheads, 7xx finance/tax. Statement mapping is therefore
range-based and stable across entities/categories. Income is credit-normal
(amount = credit − debit); expense/asset is debit-normal (amount = debit − credit).
"""

from dataclasses import dataclass
from decimal import Decimal

from apps.reports.services.balances import ZERO, account_balances

ASSET, LIABILITY, EQUITY = ("100", "199"), ("200", "299"), ("300", "399")
INCOME = ("400", "499")
DIRECT_COST, OVERHEAD, FINANCE = ("500", "599"), ("600", "699"), ("700", "799")


def _main(account):
    return account.code[4:7]


def _in(main, rng):
    return rng[0] <= main <= rng[1]


def _credit_sum(balances, rng):
    """Net credit (income/liability/equity normal) for accounts in a Main range."""
    return sum(
        (b.closing_credit - b.closing_debit for b in balances if _in(_main(b.account), rng)), ZERO
    )


def _debit_sum(balances, rng):
    """Net debit (asset/expense normal) for accounts in a Main range."""
    return sum(
        (b.closing_debit - b.closing_credit for b in balances if _in(_main(b.account), rng)), ZERO
    )


@dataclass
class ProfitAndLoss:
    revenue: Decimal
    direct_cost: Decimal
    overhead: Decimal
    finance: Decimal

    @property
    def gross_profit(self):
        return self.revenue - self.direct_cost

    @property
    def net_profit(self):
        return self.revenue - self.direct_cost - self.overhead - self.finance


@dataclass
class BalanceSheet:
    assets: Decimal
    liabilities: Decimal
    equity: Decimal
    net_profit: Decimal

    @property
    def is_balanced(self):
        # Current-year profit is not yet rolled into equity, so add it explicitly.
        return self.assets == self.liabilities + self.equity + self.net_profit


def profit_and_loss(*, entity_ids, period, basis="accrual"):
    b = account_balances(entity_ids=entity_ids, period=period, basis=basis)
    return ProfitAndLoss(
        revenue=_credit_sum(b, INCOME),
        direct_cost=_debit_sum(b, DIRECT_COST),
        overhead=_debit_sum(b, OVERHEAD),
        finance=_debit_sum(b, FINANCE),
    )


def balance_sheet(*, entity_ids, period, basis="accrual"):
    b = account_balances(entity_ids=entity_ids, period=period, basis=basis)
    pnl = profit_and_loss(entity_ids=entity_ids, period=period, basis=basis)
    return BalanceSheet(
        assets=_debit_sum(b, ASSET),
        liabilities=_credit_sum(b, LIABILITY),
        equity=_credit_sum(b, EQUITY),
        net_profit=pnl.net_profit,
    )


def cash_flow(*, entity_ids, period, basis="accrual"):
    """Indirect cash flow: net change in cash = movement on bank/cash accounts."""
    b = account_balances(entity_ids=entity_ids, period=period, basis=basis)
    cash_types = {"bank", "cash"}
    net_change = sum(
        (
            bal.period_debit - bal.period_credit
            for bal in b
            if bal.account.account_type in cash_types
        ),
        ZERO,
    )
    pnl = profit_and_loss(entity_ids=entity_ids, period=period, basis=basis)
    return {
        "net_profit": pnl.net_profit,
        "net_change_in_cash": net_change,
    }
