"""Tax API: VAT 201 returns (per VAT group or standalone entity), Corporate
Tax returns (per entity), and tax-code rate history.

A return is created as a draft naming its scope/period (+ CT's accounting
inputs), `compute` derives the GL-authoritative figures, `file` marks it
filed with the FTA. Both lifecycles share `TaxReturnStatus`.
"""

import logging

from django.db.models import Q

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.views import EntityScopedMasterViewSet
from apps.tax.models import CorporateTaxReturn, TaxCodeRateHistory, TaxReturn
from apps.tax.serializers import (
    CorporateTaxReturnSerializer,
    TaxCodeRateHistorySerializer,
    TaxReturnSerializer,
)
from apps.tax.services.corporate_tax import (
    CorporateTaxError,
    compute_corporate_tax,
    file_corporate_tax_return,
)
from apps.tax.services.vat import TaxError, compute_vat_return, file_vat_return
from apps.tenants.views import accessible_entity_ids
from apps.users.permissions import ReadAnyWriteRole

logger = logging.getLogger(__name__)
ROLES = ("accountant", "manager", "admin")


class TaxCodeRateHistoryViewSet(EntityScopedMasterViewSet):
    queryset = TaxCodeRateHistory.objects.select_related("tax_code")
    serializer_class = TaxCodeRateHistorySerializer
    entity_field = "tax_code__entity_id"
    filterset_fields = ["tax_code"]
    ordering_fields = ["effective_from"]
    ordering = ["-effective_from"]


class TaxReturnViewSet(viewsets.ModelViewSet):
    """VAT 201 returns. Scope is polymorphic (a VAT group's member entities,
    or one standalone entity), so entity access is checked directly rather
    than via EntityScopedMasterViewSet's single entity_field."""

    serializer_class = TaxReturnSerializer
    permission_classes = [IsAuthenticated, ReadAnyWriteRole]
    required_roles = ROLES
    filterset_fields = ["vat_group", "entity", "status"]
    ordering_fields = ["period_end"]
    ordering = ["-period_end"]

    def get_queryset(self):
        qs = TaxReturn.objects.select_related("vat_group", "entity", "filed_by").prefetch_related(
            "boxes"
        )
        ids = accessible_entity_ids(self.request.user)
        if ids is None:
            return qs
        return qs.filter(Q(entity_id__in=ids) | Q(vat_group__entities__id__in=ids)).distinct()

    @action(detail=True, methods=["post"], url_path="compute")
    def compute_action(self, request, pk=None):
        tax_return = self.get_object()
        try:
            compute_vat_return(tax_return, user=request.user)
        except TaxError:
            logger.exception("VAT return compute failed for %s", tax_return.pk)
            return Response(
                {"detail": "Could not compute — a filed return cannot be recomputed."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(self.get_serializer(tax_return).data)

    @action(detail=True, methods=["post"], url_path="file")
    def file_action(self, request, pk=None):
        tax_return = self.get_object()
        try:
            file_vat_return(
                tax_return, reference=request.data.get("reference", ""), user=request.user
            )
        except TaxError:
            logger.exception("VAT return filing failed for %s", tax_return.pk)
            return Response(
                {"detail": "Only a computed return can be filed."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(self.get_serializer(tax_return).data)


class CorporateTaxReturnViewSet(EntityScopedMasterViewSet):
    queryset = CorporateTaxReturn.objects.select_related("entity", "filed_by")
    serializer_class = CorporateTaxReturnSerializer
    filterset_fields = ["entity", "fiscal_year", "status"]
    ordering_fields = ["fiscal_year"]
    ordering = ["-fiscal_year"]

    @action(detail=True, methods=["post"], url_path="compute")
    def compute_action(self, request, pk=None):
        ct_return = self.get_object()
        try:
            compute_corporate_tax(ct_return, user=request.user)
        except CorporateTaxError:
            logger.exception("Corporate tax compute failed for %s", ct_return.pk)
            return Response(
                {"detail": "Could not compute — a filed return cannot be recomputed."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(self.get_serializer(ct_return).data)

    @action(detail=True, methods=["post"], url_path="file")
    def file_action(self, request, pk=None):
        ct_return = self.get_object()
        try:
            file_corporate_tax_return(
                ct_return, reference=request.data.get("reference", ""), user=request.user
            )
        except CorporateTaxError:
            logger.exception("Corporate tax filing failed for %s", ct_return.pk)
            return Response(
                {"detail": "Only a computed return can be filed."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(self.get_serializer(ct_return).data)
