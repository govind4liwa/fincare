"""Platforms API: platform master, staged earnings, and settlement lifecycle.

A settlement is created as a draft (platform/period/net_received), `reconcile`
aggregates staged EarningImport rows into its gross/commission/variance, and
`post` books DR Bank / CR Platform Clearing / CR-or-DR Adjustment through the
ledger engine.
"""

import logging

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.views import EntityScopedMasterViewSet, scope_to_entities
from apps.platforms.models import EarningImport, Platform, PlatformSettlement
from apps.platforms.serializers import (
    EarningImportSerializer,
    PlatformSerializer,
    PlatformSettlementSerializer,
)
from apps.platforms.services.post import PlatformError, post_settlement, reconcile
from apps.users.permissions import ReadAnyWriteRole

logger = logging.getLogger(__name__)
ROLES = ("accountant", "manager", "admin")


class PlatformViewSet(EntityScopedMasterViewSet):
    queryset = Platform.objects.select_related(
        "revenue_account", "commission_account", "clearing_account"
    )
    serializer_class = PlatformSerializer
    filterset_fields = ["entity", "is_active"]
    ordering_fields = ["name"]
    ordering = ["name"]


class EarningImportViewSet(EntityScopedMasterViewSet):
    """Staged platform earning rows, matched to a settlement by `reconcile`."""

    queryset = EarningImport.objects.select_related("platform", "settlement")
    serializer_class = EarningImportSerializer
    filterset_fields = ["entity", "platform", "settlement", "matched"]
    ordering_fields = ["earning_date"]
    ordering = ["-earning_date"]


class PlatformSettlementViewSet(viewsets.ModelViewSet):
    serializer_class = PlatformSettlementSerializer
    permission_classes = [IsAuthenticated, ReadAnyWriteRole]
    required_roles = ROLES
    filterset_fields = ["entity", "platform", "status"]
    ordering_fields = ["settlement_date"]
    ordering = ["-settlement_date"]

    def get_queryset(self):
        return scope_to_entities(
            PlatformSettlement.objects.select_related(
                "platform", "bank_account", "adjustment_account"
            ),
            self.request.user,
        )

    @action(detail=True, methods=["post"], url_path="reconcile")
    def reconcile_action(self, request, pk=None):
        settlement = self.get_object()
        try:
            reconcile(settlement, user=request.user)
        except PlatformError:
            logger.exception("Reconcile failed for settlement %s", settlement.pk)
            return Response(
                {"detail": "Could not reconcile — check the settlement isn't already posted."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(self.get_serializer(settlement).data)

    @action(detail=True, methods=["post"], url_path="post")
    def post_action(self, request, pk=None):
        settlement = self.get_object()
        try:
            post_settlement(settlement, user=request.user)
        except PlatformError:
            logger.exception("Posting failed for settlement %s", settlement.pk)
            return Response(
                {
                    "detail": "Could not post — a bank account is required, and a non-zero "
                    "variance needs an adjustment account."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(self.get_serializer(settlement).data)
