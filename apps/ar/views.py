"""AR API: customer master (read-only) + sales invoice CRUD with a post action."""

import logging

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.views import EntityScopedMasterViewSet, scope_to_entities
from apps.ar.models import CreditNote, Customer, SalesInvoice
from apps.ar.serializers import CreditNoteSerializer, CustomerSerializer, SalesInvoiceSerializer
from apps.ar.services import allocation
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

    @action(detail=True, methods=["post"], url_path="allocate")
    def allocate(self, request, pk=None):
        invoice = self.get_object()
        try:
            allocation.allocate(
                invoice,
                source_type=request.data.get("source_type"),
                source_id=request.data.get("source_id"),
                amount=request.data.get("amount"),
                user=request.user,
            )
        except (ValueError, ArithmeticError, TypeError):
            logger.exception("Allocation failed for invoice %s", invoice.pk)
            return Response(
                {
                    "detail": "Allocation could not be applied — check the amount against the "
                    "invoice and source balances."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(self.get_serializer(invoice).data)

    @action(detail=False, methods=["get"], url_path="allocatable-sources")
    def allocatable_sources(self, request):
        customer_id = request.query_params.get("customer")
        if not customer_id:
            return Response({"detail": "customer is required."}, status=status.HTTP_400_BAD_REQUEST)
        customer = scope_to_entities(Customer.objects.filter(id=customer_id), request.user).first()
        if customer is None:
            return Response({"sources": []})
        return Response({"sources": allocation.customer_sources(customer.entity, customer)})

    @action(detail=True, methods=["get"], url_path="allocations")
    def allocations(self, request, pk=None):
        invoice = self.get_object()
        rows = [
            {
                "source_type": a.source_type,
                "amount": str(a.amount_allocated),
                "date": a.allocation_date,
            }
            for a in invoice.allocations.all()
        ]
        return Response({"allocations": rows})


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
