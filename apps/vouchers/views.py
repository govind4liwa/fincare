"""Voucher API: CRUD on drafts + post/reverse actions (RBAC-gated)."""

import logging

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.views import scope_to_entities
from apps.users.permissions import HasAnyRole
from apps.vouchers.models import Voucher
from apps.vouchers.serializers import VoucherSerializer
from apps.vouchers.services.post import VoucherError, post_voucher, reverse_voucher

logger = logging.getLogger(__name__)


class VoucherViewSet(viewsets.ModelViewSet):
    queryset = Voucher.objects.all().prefetch_related("lines")
    serializer_class = VoucherSerializer
    permission_classes = [IsAuthenticated, HasAnyRole]
    required_roles = ("accountant", "manager", "admin")
    filterset_fields = ["entity", "voucher_type", "status"]
    ordering_fields = ["voucher_date", "voucher_no", "amount"]
    ordering = ["-voucher_date", "-created_at"]

    def get_queryset(self):
        # Scope to the requesting user's accessible entities (superuser sees all).
        return scope_to_entities(super().get_queryset(), self.request.user)

    @action(detail=True, methods=["post"], url_path="post")
    def post_voucher(self, request, pk=None):
        voucher = self.get_object()
        try:
            post_voucher(voucher, user=request.user)
        except VoucherError:
            logger.exception("Voucher posting failed for voucher %s", voucher.pk)
            return Response(
                {"detail": "Voucher could not be posted."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(self.get_serializer(voucher).data)

    @action(detail=True, methods=["post"], url_path="reverse")
    def reverse_voucher(self, request, pk=None):
        voucher = self.get_object()
        try:
            mirror = reverse_voucher(voucher, user=request.user)
        except VoucherError:
            logger.exception("Voucher reversal failed for voucher %s", voucher.pk)
            return Response(
                {"detail": "Voucher could not be reversed."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {"reversed": True, "reversal_entry_no": mirror.entry_no},
            status=status.HTTP_200_OK,
        )
