"""Bookings API: trip register (periodic aggregate revenue posting) and
corporate contracts (scheduled invoice generation, delegates to apps.ar)."""

import logging

from django.utils.dateparse import parse_date

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.views import EntityScopedMasterViewSet, scope_to_entities
from apps.bookings.models import Contract, Trip
from apps.bookings.serializers import ContractSerializer, TripSerializer
from apps.bookings.services.post import BookingError, generate_invoice, post_aggregate_revenue
from apps.platforms.models import Platform
from apps.users.permissions import ReadAnyWriteRole

logger = logging.getLogger(__name__)
ROLES = ("accountant", "manager", "admin")


class TripViewSet(viewsets.ModelViewSet):
    serializer_class = TripSerializer
    permission_classes = [IsAuthenticated, ReadAnyWriteRole]
    required_roles = ROLES
    filterset_fields = [
        "entity",
        "platform",
        "vehicle",
        "driver",
        "customer",
        "trip_type",
        "status",
    ]
    ordering_fields = ["trip_date"]
    ordering = ["-trip_date"]

    def get_queryset(self):
        return scope_to_entities(
            Trip.objects.select_related("vehicle", "driver", "platform", "customer"),
            self.request.user,
        )

    @action(detail=False, methods=["post"], url_path="post-revenue")
    def post_revenue(self, request):
        platform = scope_to_entities(
            Platform.objects.filter(id=request.data.get("platform")), request.user
        ).first()
        if platform is None:
            return Response({"detail": "Platform not found."}, status=status.HTTP_404_NOT_FOUND)
        entry_date = parse_date(request.data.get("date") or "")
        if entry_date is None:
            return Response(
                {"detail": "date is required (YYYY-MM-DD)."}, status=status.HTTP_400_BAD_REQUEST
            )
        trip_ids = request.data.get("trip_ids") or []
        trips = list(Trip.objects.filter(id__in=trip_ids, entity=platform.entity))
        try:
            entry = post_aggregate_revenue(platform, trips, date=entry_date, user=request.user)
        except (BookingError, TypeError, ValueError):
            logger.exception("Trip revenue posting failed for platform %s", platform.pk)
            return Response(
                {
                    "detail": "Could not post — trips must be recorded (not already posted) "
                    "and belong to the selected platform."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {
                "journal_entry": str(entry.id),
                "entry_no": entry.entry_no,
                "trips": TripSerializer(trips, many=True).data,
            }
        )


class ContractViewSet(EntityScopedMasterViewSet):
    queryset = Contract.objects.select_related(
        "customer", "vehicle", "driver", "revenue_account", "tax_code"
    )
    serializer_class = ContractSerializer
    filterset_fields = ["entity", "customer", "status"]
    ordering_fields = ["contract_no", "start_date"]
    ordering = ["contract_no"]

    @action(detail=True, methods=["post"], url_path="generate-invoice")
    def generate_invoice_action(self, request, pk=None):
        contract = self.get_object()
        invoice_date = parse_date(request.data.get("invoice_date") or "")
        if invoice_date is None:
            return Response(
                {"detail": "invoice_date is required (YYYY-MM-DD)."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            invoice = generate_invoice(
                contract,
                invoice_date=invoice_date,
                period_label=request.data.get("period_label", ""),
                user=request.user,
            )
        except (BookingError, TypeError, ValueError):
            logger.exception("Invoice generation failed for contract %s", contract.pk)
            return Response(
                {
                    "detail": "Could not generate the invoice — the contract must be active "
                    "with a positive monthly amount."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"invoice_id": str(invoice.id), "invoice_no": invoice.invoice_no})
