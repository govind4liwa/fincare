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
from apps.drivers.models import (
    Advance,
    Driver,
    DriverClearing,
    DriverDocStatus,
    Settlement,
)
from apps.drivers.serializers import (
    AdvanceSerializer,
    DriverClearingSerializer,
    DriverSerializer,
    SettlementSerializer,
)
from apps.drivers.services.post import (
    DriverError,
    post_advance,
    post_clearing,
    post_settlement,
    reverse_clearing,
)
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

    @action(detail=False, methods=["get"], url_path="outstanding")
    def outstanding(self, request):
        """Posted settlements a driver still owes on — what a clearing can apply to."""
        driver_id = request.query_params.get("driver")
        if not driver_id:
            return Response({"detail": "driver is required."}, status=status.HTTP_400_BAD_REQUEST)
        rows = self.get_queryset().filter(
            driver_id=driver_id,
            status=DriverDocStatus.POSTED,
            receivable_balance__gt=0,
        )
        return Response({"settlements": self.get_serializer(rows, many=True).data})

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


class DriverClearingViewSet(viewsets.ModelViewSet):
    """Settles what a driver owes: a receipt, or a write-off.

    Posting books DR bank (receipt) or DR bad debts (write-off) against CR the
    entity's configured Driver Receivable account, and applies the amount to the
    settlements the clearing names. A posted clearing is never edited — it is
    reversed (CLAUDE.md section 4.5).
    """

    serializer_class = DriverClearingSerializer
    permission_classes = [IsAuthenticated, HasAnyRole]
    required_roles = ROLES
    http_method_names = ["get", "post", "head", "options"]
    filterset_fields = ["entity", "driver", "kind", "status"]
    ordering_fields = ["clearing_date", "clearing_no", "amount"]
    ordering = ["-clearing_date", "-created_at"]

    def get_queryset(self):
        return scope_to_entities(
            DriverClearing.objects.select_related("driver", "bank_account").prefetch_related(
                "lines__settlement"
            ),
            self.request.user,
        )

    @action(detail=True, methods=["post"], url_path="post")
    def post_clearing(self, request, pk=None):
        clearing = self.get_object()
        try:
            post_clearing(clearing, user=request.user)
        except DriverError:
            logger.exception("Clearing posting failed for clearing %s", clearing.pk)
            return Response(
                {
                    "detail": "Could not post this clearing — check that it is a draft, the "
                    "amount is positive and equals what it applies, each settlement still has "
                    "that much outstanding, and the entity has the required account configured."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(self.get_serializer(clearing).data)

    @action(detail=True, methods=["post"], url_path="reverse")
    def reverse_clearing(self, request, pk=None):
        """Reverse a posted clearing and give back what it cleared.

        Restricted to manager/admin: it puts a receivable back on the books.
        """
        if (
            not request.user.is_superuser
            and not request.user.groups.filter(name__in=("manager", "admin")).exists()
        ):
            return Response(
                {"detail": "Reversing a clearing requires a manager or admin role."},
                status=status.HTTP_403_FORBIDDEN,
            )
        clearing = self.get_object()
        try:
            reverse_clearing(clearing, user=request.user)
        except DriverError:
            logger.exception("Clearing reversal failed for clearing %s", clearing.pk)
            return Response(
                {
                    "detail": "Could not reverse this clearing — only a posted clearing can be reversed."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(self.get_serializer(clearing).data)
