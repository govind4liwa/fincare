"""Balance engine — the primitive every statement builds on (design doc 05).

Balances are computed live from posted ``ledger_journal_line`` rows (the GL is the
single source of truth). Supports accrual (all lines) and cash (only entries that
touch a bank/cash account) basis, optional profitability-dimension filters, and
multiple entities at once for consolidation.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Sum

from apps.accounts.models import Account
from apps.ledger.models import JournalLine

TWO_PLACES = Decimal("0.01")
ZERO = Decimal("0.00")
DIM_FIELDS = {"vehicle", "driver", "platform"}  # UUID dims on the journal line


def _q(amount):
    return Decimal(amount or 0).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


@dataclass
class AccountBalance:
    account: Account
    opening_debit: Decimal
    opening_credit: Decimal
    period_debit: Decimal
    period_credit: Decimal

    @property
    def opening_net(self):
        return self.opening_debit - self.opening_credit

    @property
    def closing_net(self):
        return (self.opening_debit + self.period_debit) - (self.opening_credit + self.period_credit)

    @property
    def closing_debit(self):
        net = self.closing_net
        return _q(net) if net > ZERO else ZERO

    @property
    def closing_credit(self):
        net = self.closing_net
        return _q(-net) if net < ZERO else ZERO


@dataclass
class TrialBalance:
    rows: list
    total_debit: Decimal
    total_credit: Decimal

    @property
    def is_balanced(self):
        return self.total_debit == self.total_credit


def _base_qs(entity_ids, basis, dims):
    qs = JournalLine.objects.filter(entry__status="posted", entry__entity_id__in=list(entity_ids))
    if basis == "cash":
        cash_entries = JournalLine.objects.filter(
            account__account_type__in=[Account.AccountType.BANK, Account.AccountType.CASH]
        ).values("entry_id")
        qs = qs.filter(entry_id__in=cash_entries)
    for key, value in (dims or {}).items():
        if value is None:
            continue
        if key in DIM_FIELDS:
            qs = qs.filter(**{f"{key}_id": value})  # vehicle/driver/platform UUID dims
        elif key == "cost_center":
            qs = qs.filter(cost_center_id=value)
        elif key == "branch":
            qs = qs.filter(entry__branch_id=value)
    return qs


def account_balances(*, entity_ids, period, basis="accrual", dims=None, as_of=None):
    """Opening / period-movement balances per account, from posted lines."""
    qs = _base_qs(entity_ids, basis, dims)
    end = as_of or period.end_date

    opening = {
        r["account"]: r
        for r in qs.filter(entry__entry_date__lt=period.start_date)
        .values("account")
        .annotate(d=Sum("debit"), c=Sum("credit"))
    }
    movement = {
        r["account"]: r
        for r in qs.filter(entry__entry_date__gte=period.start_date, entry__entry_date__lte=end)
        .values("account")
        .annotate(d=Sum("debit"), c=Sum("credit"))
    }

    account_ids = set(opening) | set(movement)
    accounts = {a.id: a for a in Account.objects.filter(id__in=account_ids)}
    balances = []
    for aid in account_ids:
        op, mv = opening.get(aid, {}), movement.get(aid, {})
        balances.append(
            AccountBalance(
                account=accounts[aid],
                opening_debit=_q(op.get("d")),
                opening_credit=_q(op.get("c")),
                period_debit=_q(mv.get("d")),
                period_credit=_q(mv.get("c")),
            )
        )
    balances.sort(key=lambda b: b.account.code)
    return balances


def trial_balance(*, entity_ids, period, basis="accrual", exclude_account_ids=None):
    rows = account_balances(entity_ids=entity_ids, period=period, basis=basis)
    if exclude_account_ids:
        excl = set(exclude_account_ids)
        rows = [b for b in rows if b.account.id not in excl]
    total_debit = sum((b.closing_debit for b in rows), ZERO)
    total_credit = sum((b.closing_credit for b in rows), ZERO)
    return TrialBalance(rows=rows, total_debit=_q(total_debit), total_credit=_q(total_credit))


def ledger_detail(*, entity_id, account_id, date_from, date_to):
    """Posted line detail for one account over a date range (GL drill-down)."""
    return list(
        JournalLine.objects.filter(
            entry__status="posted",
            entry__entity_id=entity_id,
            account_id=account_id,
            entry__entry_date__gte=date_from,
            entry__entry_date__lte=date_to,
        )
        .select_related("entry", "account")
        .order_by("entry__entry_date", "entry__entry_no", "line_no")
    )
