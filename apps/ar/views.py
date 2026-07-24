"""AR customer master API (entity-scoped, read-only)."""

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.accounts.views import scope_to_entities
from apps.ar.models import Customer
from apps.ar.serializers import CustomerSerializer


class CustomerViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CustomerSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["entity", "customer_type", "is_active"]
    ordering_fields = ["code", "name"]
    ordering = ["code"]

    def get_queryset(self):
        return scope_to_entities(
            Customer.objects.select_related("receivable_account"), self.request.user
        )
