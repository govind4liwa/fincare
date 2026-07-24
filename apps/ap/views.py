"""AP API: supplier master (read-only) + purchase bill CRUD with a post action."""

import logging

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.views import scope_to_entities
from apps.ap.models import PurchaseBill, Supplier
from apps.ap.serializers import PurchaseBillSerializer, SupplierSerializer
from apps.ap.services.post import APError, post_bill
from apps.users.permissions import HasAnyRole

logger = logging.getLogger(__name__)


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


class PurchaseBillViewSet(viewsets.ModelViewSet):
    serializer_class = PurchaseBillSerializer
    permission_classes = [IsAuthenticated, HasAnyRole]
    required_roles = ("accountant", "manager", "admin")
    filterset_fields = ["entity", "supplier", "status"]
    ordering_fields = ["bill_date", "bill_no", "total"]
    ordering = ["-bill_date", "-created_at"]

    def get_queryset(self):
        return scope_to_entities(
            PurchaseBill.objects.select_related("supplier").prefetch_related("lines"),
            self.request.user,
        )

    @action(detail=True, methods=["post"], url_path="post")
    def post_bill(self, request, pk=None):
        bill = self.get_object()
        try:
            post_bill(bill, user=request.user)
        except APError:
            logger.exception("Purchase bill posting failed for bill %s", bill.pk)
            return Response(
                {"detail": "Bill could not be posted."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(self.get_serializer(bill).data)
