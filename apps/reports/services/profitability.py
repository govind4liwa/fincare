"""Profitability by dimension (vehicle / driver / platform), derived from the GL.

Profit for a dimension = Σ revenue lines − Σ direct-cost lines carrying that dim
(doc 04). Computed from posted ``ledger_journal_line`` rows filtered by the dim id;
no separate profitability ledger.
"""

from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Sum

from apps.ledger.models import JournalLine

TWO_PLACES = Decimal("0.01")
ZERO = Decimal("0.00")
DIM_COLUMN = {"vehicle": "vehicle_id", "driver": "driver_id", "platform": "platform_id"}


def _q(amount):
    return Decimal(amount or 0).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def profit_by_dim(*, entity_ids, period, dim_type):
    """Revenue, direct cost and net profit per dimension id for the period."""
    col = DIM_COLUMN[dim_type]
    qs = JournalLine.objects.filter(
        entry__status="posted",
        entry__entity_id__in=list(entity_ids),
        entry__entry_date__gte=period.start_date,
        entry__entry_date__lte=period.end_date,
        **{f"{col}__isnull": False},
    )
    rows = {}
    agg = qs.values(col, "account__code").annotate(d=Sum("debit"), c=Sum("credit")).order_by(col)
    for r in agg:
        dim_id = r[col]
        main = r["account__code"][4:7]
        debit, credit = _q(r["d"]), _q(r["c"])
        bucket = rows.setdefault(dim_id, {"revenue": ZERO, "direct_cost": ZERO})
        if "400" <= main <= "499":
            bucket["revenue"] += credit - debit
        elif "500" <= main <= "599":
            bucket["direct_cost"] += debit - credit
    return [
        {
            "dim_type": dim_type,
            "dim_id": dim_id,
            "revenue": v["revenue"],
            "direct_cost": v["direct_cost"],
            "net_profit": v["revenue"] - v["direct_cost"],
        }
        for dim_id, v in rows.items()
    ]
