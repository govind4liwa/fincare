"""Report catalog — turns statements into tabular payloads (columns + rows) that
the API serialises to JSON and the exports app renders to Excel / PDF.

A tabular report is ``{"code", "title", "columns": [...], "rows": [[...]],
"meta": {...}}`` so every output format shares one shape.
"""

from apps.reports.services.balances import trial_balance
from apps.reports.services.consolidation import consolidated_trial_balance
from apps.reports.services.profitability import profit_by_dim
from apps.reports.services.statements import balance_sheet, cash_flow, profit_and_loss


def _money(value):
    return f"{value:.2f}"


def trial_balance_table(*, entity_ids, period, basis="accrual", consolidate=False):
    tb = (
        consolidated_trial_balance(entity_ids=entity_ids, period=period, basis=basis)
        if consolidate
        else trial_balance(entity_ids=entity_ids, period=period, basis=basis)
    )
    rows = [
        [b.account.code, b.account.name, _money(b.closing_debit), _money(b.closing_credit)]
        for b in tb.rows
    ]
    rows.append(["", "TOTAL", _money(tb.total_debit), _money(tb.total_credit)])
    return {
        "code": "TB",
        "title": "Trial Balance",
        "columns": ["Account", "Name", "Debit", "Credit"],
        "rows": rows,
        "meta": {"balanced": tb.is_balanced, "basis": basis},
    }


def profit_and_loss_table(*, entity_ids, period, basis="accrual"):
    p = profit_and_loss(entity_ids=entity_ids, period=period, basis=basis)
    rows = [
        ["Revenue", _money(p.revenue)],
        ["Direct Operating Cost", _money(p.direct_cost)],
        ["Gross Profit", _money(p.gross_profit)],
        ["Overheads", _money(p.overhead)],
        ["Finance & Tax", _money(p.finance)],
        ["Net Profit", _money(p.net_profit)],
    ]
    return {
        "code": "PNL",
        "title": "Profit & Loss",
        "columns": ["Line", "Amount"],
        "rows": rows,
        "meta": {"net_profit": _money(p.net_profit), "basis": basis},
    }


def balance_sheet_table(*, entity_ids, period, basis="accrual"):
    bs = balance_sheet(entity_ids=entity_ids, period=period, basis=basis)
    rows = [
        ["Assets", _money(bs.assets)],
        ["Liabilities", _money(bs.liabilities)],
        ["Equity", _money(bs.equity)],
        ["Result for the period", _money(bs.net_profit)],
    ]
    return {
        "code": "BS",
        "title": "Balance Sheet",
        "columns": ["Line", "Amount"],
        "rows": rows,
        "meta": {"balanced": bs.is_balanced, "basis": basis},
    }


def cash_flow_table(*, entity_ids, period, basis="accrual"):
    cf = cash_flow(entity_ids=entity_ids, period=period, basis=basis)
    return {
        "code": "CF",
        "title": "Cash Flow (Indirect)",
        "columns": ["Line", "Amount"],
        "rows": [
            ["Net Profit", _money(cf["net_profit"])],
            ["Net Change in Cash", _money(cf["net_change_in_cash"])],
        ],
        "meta": {},
    }


def profitability_table(*, entity_ids, period, dim_type):
    data = profit_by_dim(entity_ids=entity_ids, period=period, dim_type=dim_type)
    rows = [
        [str(r["dim_id"]), _money(r["revenue"]), _money(r["direct_cost"]), _money(r["net_profit"])]
        for r in data
    ]
    return {
        "code": f"PROF_{dim_type.upper()}",
        "title": f"Profitability by {dim_type}",
        "columns": [dim_type, "Revenue", "Direct Cost", "Net Profit"],
        "rows": rows,
        "meta": {},
    }


BUILDERS = {
    "TB": trial_balance_table,
    "PNL": profit_and_loss_table,
    "BS": balance_sheet_table,
    "CF": cash_flow_table,
}


def build_report(report_code, **params):
    """Dispatch a report_code to its tabular builder."""
    try:
        builder = BUILDERS[report_code]
    except KeyError as exc:
        raise ValueError(f"Unknown report code {report_code!r}.") from exc
    return builder(**params)
