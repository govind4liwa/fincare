"""Driver master API (entity-scoped, read-only)."""

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.accounts.views import scope_to_entities
from apps.drivers.models import Driver
from apps.drivers.serializers import DriverSerializer


class DriverViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DriverSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["entity", "nationality", "is_active"]
    ordering_fields = ["code", "name"]
    ordering = ["code"]

    def get_queryset(self):
        return scope_to_entities(Driver.objects.all(), self.request.user)
