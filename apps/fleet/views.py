"""Fleet vehicle master API (entity-scoped, read-only)."""

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.accounts.views import scope_to_entities
from apps.fleet.models import Vehicle
from apps.fleet.serializers import VehicleSerializer


class VehicleViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = VehicleSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["entity", "ownership", "is_active"]
    ordering_fields = ["code", "make"]
    ordering = ["code"]

    def get_queryset(self):
        return scope_to_entities(Vehicle.objects.all(), self.request.user)
