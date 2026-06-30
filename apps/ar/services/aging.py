"""Customer aging — derived from open invoices (no stored aging tables)."""

from datetime import date

from apps.ar.models import InvoiceStatus, SalesInvoice

BUCKETS = ["current", "d1_30", "d31_60", "d61_90", "d91_120", "d120_plus"]


def _bucket(days_overdue):
    if days_overdue <= 0:
        return "current"
    if days_overdue <= 30:
        return "d1_30"
    if days_overdue <= 60:
        return "d31_60"
    if days_overdue <= 90:
        return "d61_90"
    if days_overdue <= 120:
        return "d91_120"
    return "d120_plus"


def customer_aging(entity, as_of=None):
    """Return a list of per-customer aging rows for open invoices."""
    as_of = as_of or date.today()
    invoices = SalesInvoice.objects.filter(
        entity=entity,
        balance__gt=0,
        status__in=[InvoiceStatus.POSTED, InvoiceStatus.PARTIALLY_PAID],
    ).select_related("customer")
    rows = {}
    for inv in invoices:
        due = inv.due_date or inv.invoice_date
        bucket = _bucket((as_of - due).days)
        row = rows.setdefault(
            inv.customer_id,
            {"customer": inv.customer, "total": 0, **{b: 0 for b in BUCKETS}},
        )
        row[bucket] += inv.balance
        row["total"] += inv.balance
    return list(rows.values())
