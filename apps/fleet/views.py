"""Fleet vehicle master API (entity-scoped CRUD; writes require an accounting role)."""

from apps.accounts.views import EntityScopedMasterViewSet
from apps.fleet.models import Vehicle
from apps.fleet.serializers import VehicleSerializer


class VehicleViewSet(EntityScopedMasterViewSet):
    queryset = Vehicle.objects.all()
    serializer_class = VehicleSerializer
    filterset_fields = ["entity", "ownership", "is_active"]
    ordering_fields = ["code", "make"]
    ordering = ["code"]
