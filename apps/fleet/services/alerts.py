"""Vehicle document expiry alerts."""

from datetime import date, timedelta

from apps.fleet.models import VehicleDocument


def expiring_documents(entity, *, within_days=30, as_of=None):
    """Vehicle documents for ``entity`` expiring on/before ``as_of + within_days``.

    Includes already-expired documents (expiry_date <= cutoff). Ordered soonest
    first so a dashboard can surface the most urgent renewals.
    """
    as_of = as_of or date.today()
    cutoff = as_of + timedelta(days=within_days)
    return (
        VehicleDocument.objects.filter(
            vehicle__entity=entity,
            vehicle__is_active=True,
            expiry_date__isnull=False,
            expiry_date__lte=cutoff,
        )
        .select_related("vehicle")
        .order_by("expiry_date")
    )
