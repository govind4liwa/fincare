"""Drivers API: driver master, cash advances, and period settlements.

Advances and settlements are documents: created as drafts, then posted through
the ledger engine (ADR-0007) by a dedicated action. Posted documents are
immutable — they are never edited or deleted here.
"""

import logging

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.views import EntityScopedMasterViewSet, scope_to_entities
from apps.drivers.models import Advance, Driver, DriverDocStatus, Settlement
from apps.drivers.serializers import AdvanceSerializer, DriverSerializer, SettlementSerializer
from apps.drivers.services.post import DriverError, post_advance, post_settlement
from apps.users.permissions import HasAnyRole

logger = logging.getLogger(__name__)
ROLES = ("accountant", "manager", "admin")


class DriverViewSet(EntityScopedMasterViewSet):
    queryset = Driver.objects.all()
    serializer_class = DriverSerializer
    filterset_fields = ["entity", "nationality", "is_active"]
    ordering_fields = ["code", "name"]
    ordering = ["code"]


class AdvanceViewSet(viewsets.ModelViewSet):
    """Driver cash advances. Posting books DR Driver Advance / CR Bank."""

    serializer_class = AdvanceSerializer
    permission_classes = [IsAuthenticated, HasAnyRole]
    required_roles = ROLES
    http_method_names = ["get", "post", "head", "options"]
    filterset_fields = ["entity", "driver", "status"]
    ordering_fields = ["advance_date", "advance_no", "amount"]
    ordering = ["-advance_date", "-created_at"]

    def get_queryset(self):
        return scope_to_entities(
            Advance.objects.select_related("driver", "bank_account"), self.request.user
        )

    @action(detail=True, methods=["post"], url_path="post")
    def post_advance(self, request, pk=None):
        advance = self.get_object()
        try:
            post_advance(advance, user=request.user)
        except DriverError:
            logger.exception("Advance posting failed for advance %s", advance.pk)
            return Response(
                {
                    "detail": "Could not post this advance — it must be a draft with a "
                    "positive amount and a bank account to pay from."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(self.get_serializer(advance).data)

    @action(detail=False, methods=["get"], url_path="outstanding")
    def outstanding(self, request):
        """Posted advances with a balance left — the recoverable pool for a driver."""
        driver_id = request.query_params.get("driver")
        if not driver_id:
            return Response({"detail": "driver is required."}, status=status.HTTP_400_BAD_REQUEST)
        rows = self.get_queryset().filter(
            driver_id=driver_id, status=DriverDocStatus.POSTED, balance__gt=0
        )
        return Response({"advances": self.get_serializer(rows, many=True).data})


class SettlementViewSet(viewsets.ModelViewSet):
    """Driver settlements: gross earnings less deductions, netting to a payout.

    Posting books DR gross / CR each deduction / CR bank (net payout) — or DR
    bank when the settlement explicitly allows a negative net (driver pays in).
    """

    serializer_class = SettlementSerializer
    permission_classes = [IsAuthenticated, HasAnyRole]
    required_roles = ROLES
    http_method_names = ["get", "post", "head", "options"]
    filterset_fields = ["entity", "driver", "vehicle", "status"]
    ordering_fields = ["settlement_date", "settlement_no", "net_amount"]
    ordering = ["-settlement_date", "-created_at"]

    def get_queryset(self):
        return scope_to_entities(
            Settlement.objects.select_related("driver", "vehicle", "pay_account").prefetch_related(
                "deductions"
            ),
            self.request.user,
        )

    @action(detail=True, methods=["post"], url_path="post")
    def post_settlement(self, request, pk=None):
        settlement = self.get_object()
        try:
            post_settlement(settlement, user=request.user)
        except DriverError:
            logger.exception("Settlement posting failed for settlement %s", settlement.pk)
            return Response(
                {
                    "detail": "Could not post this settlement — check that it is a draft, the "
                    "gross is positive, deductions are within gross (unless a negative net is "
                    "allowed), and any advance recovery is within the advance's balance."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(self.get_serializer(settlement).data)
