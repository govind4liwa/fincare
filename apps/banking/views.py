"""Banking API: bank accounts (CRUD), statement entry, and auto-match reconciliation.

Scope of this slice: auto-match only. Manual match/unmatch, completion/locking,
and statement file import are explicitly out of scope — reconciliations never
reach ``completed`` here (see ``auto_match(..., mark_complete=False)``).
"""

import logging
from decimal import Decimal

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.views import EntityScopedMasterViewSet, scope_to_entities
from apps.banking.models import BankAccount, BankStatement, Reconciliation
from apps.banking.serializers import (
    BankAccountSerializer,
    BankStatementSerializer,
    ReconciliationItemSerializer,
    ReconciliationSerializer,
    StatementLineSerializer,
)
from apps.banking.services import reconcile
from apps.users.permissions import ReadAnyWriteRole

logger = logging.getLogger(__name__)
ROLES = ("accountant", "manager", "admin")


class BankAccountViewSet(EntityScopedMasterViewSet):
    """Bank account master — wraps a bank-type GL account. Reads open to members;
    create/update need an accounting role; no hard delete (deactivate via is_active)."""

    queryset = BankAccount.objects.select_related("gl_account")
    serializer_class = BankAccountSerializer
    filterset_fields = ["entity", "is_active"]
    ordering_fields = ["code", "name"]
    ordering = ["code"]


class BankStatementViewSet(viewsets.ModelViewSet):
    serializer_class = BankStatementSerializer
    permission_classes = [IsAuthenticated, ReadAnyWriteRole]
    required_roles = ROLES
    http_method_names = ["get", "post", "head", "options"]
    filterset_fields = ["entity", "bank_account", "status"]
    ordering_fields = ["statement_date"]
    ordering = ["-statement_date", "-created_at"]

    def get_queryset(self):
        return scope_to_entities(
            BankStatement.objects.select_related("bank_account").prefetch_related("lines"),
            self.request.user,
        )


class ReconciliationViewSet(viewsets.ModelViewSet):
    serializer_class = ReconciliationSerializer
    permission_classes = [IsAuthenticated, ReadAnyWriteRole]
    required_roles = ROLES
    http_method_names = ["get", "post", "head", "options"]
    filterset_fields = ["entity", "bank_account", "statement", "status"]
    ordering_fields = ["recon_date"]
    ordering = ["-recon_date", "-created_at"]

    def get_queryset(self):
        return scope_to_entities(
            Reconciliation.objects.select_related("bank_account", "statement"),
            self.request.user,
        )

    def perform_create(self, serializer):
        recon = serializer.save()
        reconcile.recompute_balances(recon)

    @action(detail=True, methods=["post"], url_path="auto-match")
    def auto_match(self, request, pk=None):
        recon = self.get_object()
        try:
            reconcile.auto_match(
                recon,
                amount_tolerance=Decimal(str(request.data.get("amount_tolerance", "0"))),
                date_window_days=int(request.data.get("date_window_days", 3)),
                match_reference=bool(request.data.get("match_reference", False)),
                mark_complete=False,  # completion/locking is a later slice
                user=request.user,
            )
        except (ValueError, ArithmeticError, TypeError):
            logger.exception("Auto-match failed for reconciliation %s", recon.pk)
            return Response(
                {"detail": "Auto-match could not run — the reconciliation needs a statement."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(self._workspace(recon))

    @action(detail=True, methods=["get"], url_path="workspace")
    def workspace(self, request, pk=None):
        return Response(self._workspace(self.get_object()))

    def _workspace(self, recon):
        detail = reconcile.reconciliation_detail(recon)
        gl_lines = [
            {
                "id": str(jl.id),
                "entry_no": jl.entry.entry_no,
                "entry_date": jl.entry.entry_date,
                "description": jl.description or jl.entry.narration,
                "debit": str(jl.debit),
                "credit": str(jl.credit),
                "is_matched": jl.id in detail["matched_jl_ids"],
            }
            for jl in detail["gl_lines"]
        ]
        totals = {
            key: (str(value) if isinstance(value, Decimal) else value)
            for key, value in detail["totals"].items()
        }
        return {
            "reconciliation": ReconciliationSerializer(recon).data,
            "matched": ReconciliationItemSerializer(detail["items"], many=True).data,
            "unmatched_lines": StatementLineSerializer(detail["unmatched_lines"], many=True).data,
            "gl_lines": gl_lines,
            "totals": totals,
        }
