"""Cashbook API: cash-account and petty-cash-float masters, replenishments
(draft -> post), and cash counts (draft -> post, denomination-driven variance)."""

import logging

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.views import EntityScopedMasterViewSet, scope_to_entities
from apps.cashbook.models import CashAccount, CashCount, PettyCashFloat, Replenishment
from apps.cashbook.serializers import (
    CashAccountSerializer,
    CashCountSerializer,
    PettyCashFloatSerializer,
    ReplenishmentSerializer,
)
from apps.cashbook.services.post import CashbookError, post_cash_count, post_replenishment
from apps.users.permissions import ReadAnyWriteRole

logger = logging.getLogger(__name__)
ROLES = ("accountant", "manager", "admin")


class CashAccountViewSet(EntityScopedMasterViewSet):
    queryset = CashAccount.objects.select_related("gl_account")
    serializer_class = CashAccountSerializer
    filterset_fields = ["entity", "is_active"]
    ordering_fields = ["code", "name"]
    ordering = ["code"]


class PettyCashFloatViewSet(EntityScopedMasterViewSet):
    queryset = PettyCashFloat.objects.select_related("cash_account")
    serializer_class = PettyCashFloatSerializer
    filterset_fields = ["entity", "cash_account", "is_active"]
    ordering_fields = ["code"]
    ordering = ["code"]


class ReplenishmentViewSet(viewsets.ModelViewSet):
    serializer_class = ReplenishmentSerializer
    permission_classes = [IsAuthenticated, ReadAnyWriteRole]
    required_roles = ROLES
    http_method_names = ["get", "post", "head", "options"]
    filterset_fields = ["entity", "petty_cash_float", "status"]
    ordering_fields = ["replenish_date"]
    ordering = ["-replenish_date"]

    def get_queryset(self):
        return scope_to_entities(
            Replenishment.objects.select_related("petty_cash_float__cash_account", "bank_account"),
            self.request.user,
        )

    @action(detail=True, methods=["post"], url_path="post")
    def post_action(self, request, pk=None):
        rep = self.get_object()
        try:
            post_replenishment(rep, user=request.user)
        except CashbookError:
            logger.exception("Replenishment posting failed for %s", rep.pk)
            return Response(
                {
                    "detail": "Could not post — the replenishment must be a draft with a "
                    "positive amount."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(self.get_serializer(rep).data)


class CashCountViewSet(viewsets.ModelViewSet):
    serializer_class = CashCountSerializer
    permission_classes = [IsAuthenticated, ReadAnyWriteRole]
    required_roles = ROLES
    http_method_names = ["get", "post", "head", "options"]
    filterset_fields = ["entity", "cash_account", "status"]
    ordering_fields = ["count_date"]
    ordering = ["-count_date"]

    def get_queryset(self):
        return scope_to_entities(
            CashCount.objects.select_related("cash_account", "variance_account").prefetch_related(
                "denominations"
            ),
            self.request.user,
        )

    @action(detail=True, methods=["post"], url_path="post")
    def post_action(self, request, pk=None):
        count = self.get_object()
        try:
            post_cash_count(count, user=request.user)
        except CashbookError:
            logger.exception("Cash count posting failed for %s", count.pk)
            return Response(
                {
                    "detail": "Could not post — the count must be a draft, and a non-zero "
                    "variance needs a variance account."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(self.get_serializer(count).data)
