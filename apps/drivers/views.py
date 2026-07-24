"""Driver master API (entity-scoped CRUD; writes require an accounting role)."""

from apps.accounts.views import EntityScopedMasterViewSet
from apps.drivers.models import Driver
from apps.drivers.serializers import DriverSerializer


class DriverViewSet(EntityScopedMasterViewSet):
    queryset = Driver.objects.all()
    serializer_class = DriverSerializer
    filterset_fields = ["entity", "nationality", "is_active"]
    ordering_fields = ["code", "name"]
    ordering = ["code"]
