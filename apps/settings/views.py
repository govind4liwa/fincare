"""Per-entity configuration API."""

from apps.accounts.views import EntityScopedMasterViewSet
from apps.settings.models import DriverAccountingConfig
from apps.settings.serializers import DriverAccountingConfigSerializer


class DriverAccountingConfigViewSet(EntityScopedMasterViewSet):
    """The entity's approved Driver Receivable account.

    Readable by any member so the settlement screen can show which account a
    shortfall will hit; writes need manager/admin rather than the usual
    accountant role — pointing this FK at an account *is* the authorisation to
    post driver receivables, so it is administration, not day-to-day entry.
    """

    queryset = DriverAccountingConfig.objects.select_related("entity", "default_receivable_account")
    serializer_class = DriverAccountingConfigSerializer
    required_roles = ("manager", "admin")
    filterset_fields = ["entity"]
    ordering_fields = ["entity"]
    ordering = ["entity"]
