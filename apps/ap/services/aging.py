"""Supplier aging — derived from open bills (no stored aging tables)."""

from datetime import date

from apps.ap.models import BillStatus, PurchaseBill

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


def supplier_aging(entity, as_of=None):
    """Return a list of per-supplier aging rows for open bills."""
    as_of = as_of or date.today()
    bills = PurchaseBill.objects.filter(
        entity=entity,
        balance__gt=0,
        status__in=[BillStatus.POSTED, BillStatus.PARTIALLY_PAID],
    ).select_related("supplier")
    rows = {}
    for bill in bills:
        due = bill.due_date or bill.bill_date
        bucket = _bucket((as_of - due).days)
        row = rows.setdefault(
            bill.supplier_id,
            {"supplier": bill.supplier, "total": 0, **dict.fromkeys(BUCKETS, 0)},
        )
        row[bucket] += bill.balance
        row["total"] += bill.balance
    return list(rows.values())
