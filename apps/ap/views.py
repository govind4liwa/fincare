"""AP supplier master API (entity-scoped, read-only)."""

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.accounts.views import scope_to_entities
from apps.ap.models import Supplier
from apps.ap.serializers import SupplierSerializer


class SupplierViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SupplierSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["entity", "is_active"]
    ordering_fields = ["code", "name"]
    ordering = ["code"]

    def get_queryset(self):
        return scope_to_entities(
            Supplier.objects.select_related("payable_account"), self.request.user
        )
