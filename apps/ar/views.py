"""AR API: customer master (read-only) + sales invoice CRUD with a post action."""

import logging

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.views import EntityScopedMasterViewSet, scope_to_entities
from apps.ar.models import CreditNote, Customer, SalesInvoice
from apps.ar.serializers import CreditNoteSerializer, CustomerSerializer, SalesInvoiceSerializer
from apps.ar.services.post import ARError, post_credit_note, post_invoice
from apps.users.permissions import HasAnyRole

logger = logging.getLogger(__name__)


class CustomerViewSet(EntityScopedMasterViewSet):
    queryset = Customer.objects.select_related("receivable_account")
    serializer_class = CustomerSerializer
    filterset_fields = ["entity", "customer_type", "is_active"]
    ordering_fields = ["code", "name"]
    ordering = ["code"]


class SalesInvoiceViewSet(viewsets.ModelViewSet):
    serializer_class = SalesInvoiceSerializer
    permission_classes = [IsAuthenticated, HasAnyRole]
    required_roles = ("accountant", "manager", "admin")
    filterset_fields = ["entity", "customer", "status"]
    ordering_fields = ["invoice_date", "invoice_no", "total"]
    ordering = ["-invoice_date", "-created_at"]

    def get_queryset(self):
        return scope_to_entities(
            SalesInvoice.objects.select_related("customer").prefetch_related("lines"),
            self.request.user,
        )

    @action(detail=True, methods=["post"], url_path="post")
    def post_invoice(self, request, pk=None):
        invoice = self.get_object()
        try:
            post_invoice(invoice, user=request.user)
        except ARError:
            logger.exception("Sales invoice posting failed for invoice %s", invoice.pk)
            return Response(
                {"detail": "Invoice could not be posted."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(self.get_serializer(invoice).data)


class CreditNoteViewSet(viewsets.ModelViewSet):
    serializer_class = CreditNoteSerializer
    permission_classes = [IsAuthenticated, HasAnyRole]
    required_roles = ("accountant", "manager", "admin")
    filterset_fields = ["entity", "customer", "status"]
    ordering_fields = ["credit_note_date", "credit_note_no", "total"]
    ordering = ["-credit_note_date", "-created_at"]

    def get_queryset(self):
        return scope_to_entities(
            CreditNote.objects.select_related("customer").prefetch_related("lines"),
            self.request.user,
        )

    @action(detail=True, methods=["post"], url_path="post")
    def post_credit_note(self, request, pk=None):
        note = self.get_object()
        try:
            post_credit_note(note, user=request.user)
        except ARError:
            logger.exception("Credit note posting failed for note %s", note.pk)
            return Response(
                {"detail": "Credit note could not be posted."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(self.get_serializer(note).data)
