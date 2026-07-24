"""AP API: supplier master (read-only) + purchase bill CRUD with a post action."""

import logging

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.views import EntityScopedMasterViewSet, scope_to_entities
from apps.ap.models import DebitNote, PurchaseBill, Supplier
from apps.ap.serializers import DebitNoteSerializer, PurchaseBillSerializer, SupplierSerializer
from apps.ap.services.post import APError, post_bill, post_debit_note
from apps.users.permissions import HasAnyRole

logger = logging.getLogger(__name__)


class SupplierViewSet(EntityScopedMasterViewSet):
    queryset = Supplier.objects.select_related("payable_account")
    serializer_class = SupplierSerializer
    filterset_fields = ["entity", "is_active"]
    ordering_fields = ["code", "name"]
    ordering = ["code"]


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


class DebitNoteViewSet(viewsets.ModelViewSet):
    serializer_class = DebitNoteSerializer
    permission_classes = [IsAuthenticated, HasAnyRole]
    required_roles = ("accountant", "manager", "admin")
    filterset_fields = ["entity", "supplier", "status"]
    ordering_fields = ["debit_note_date", "debit_note_no", "total"]
    ordering = ["-debit_note_date", "-created_at"]

    def get_queryset(self):
        return scope_to_entities(
            DebitNote.objects.select_related("supplier").prefetch_related("lines"),
            self.request.user,
        )

    @action(detail=True, methods=["post"], url_path="post")
    def post_debit_note(self, request, pk=None):
        note = self.get_object()
        try:
            post_debit_note(note, user=request.user)
        except APError:
            logger.exception("Debit note posting failed for note %s", note.pk)
            return Response(
                {"detail": "Debit note could not be posted."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(self.get_serializer(note).data)
