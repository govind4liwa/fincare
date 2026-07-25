"""Banking API: bank accounts (CRUD), statement entry, and reconciliation.

Reconciliation supports auto-match plus manual match/unmatch, and completion —
allowed only when every statement line is matched and the statement/GL balances
agree — which locks the reconciliation and marks the statement reconciled. A
completed reconciliation can be reopened by a manager/admin. Statement file
import and multi-currency reconciliation remain out of scope.
"""

import logging
from decimal import Decimal

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.views import EntityScopedMasterViewSet, scope_to_entities
from apps.banking.models import (
    BankAccount,
    BankStatement,
    Reconciliation,
    ReconciliationItem,
    StatementLine,
)
from apps.banking.serializers import (
    BankAccountSerializer,
    BankStatementSerializer,
    ReconciliationItemSerializer,
    ReconciliationSerializer,
    StatementLineSerializer,
)
from apps.banking.services import reconcile
from apps.ledger.models import JournalLine
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

    @action(detail=True, methods=["post"], url_path="manual-match")
    def manual_match(self, request, pk=None):
        recon = self.get_object()
        sl = StatementLine.objects.filter(
            id=request.data.get("statement_line"), statement_id=recon.statement_id
        ).first()
        jl = (
            JournalLine.objects.filter(
                id=request.data.get("journal_line"),
                account=recon.bank_account.gl_account,
                entry__entity_id=recon.entity_id,
            )
            .select_related("entry")
            .first()
        )
        if sl is None or jl is None:
            return Response(
                {"detail": "Statement line or GL line not found."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            reconcile.manual_match(recon, statement_line=sl, journal_line=jl, user=request.user)
        except (ValueError, ArithmeticError, TypeError):
            logger.exception("Manual match failed for reconciliation %s", recon.pk)
            return Response(
                {
                    "detail": "Could not match — the amounts and sides must correspond "
                    "(a deposit matches a GL debit; a withdrawal matches a GL credit)."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(self._workspace(recon))

    @action(detail=True, methods=["post"], url_path="unmatch")
    def unmatch(self, request, pk=None):
        recon = self.get_object()
        item = ReconciliationItem.objects.filter(
            id=request.data.get("item"), reconciliation=recon
        ).first()
        if item is None:
            return Response({"detail": "Match not found."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            reconcile.unmatch(item, user=request.user)
        except (ValueError, ArithmeticError, TypeError):
            logger.exception("Unmatch failed for reconciliation %s", recon.pk)
            return Response({"detail": "Could not unmatch."}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self._workspace(recon))

    @action(detail=True, methods=["post"], url_path="complete")
    def complete(self, request, pk=None):
        recon = self.get_object()
        try:
            reconcile.complete(recon, user=request.user)
        except (ValueError, ArithmeticError, TypeError):
            logger.warning("Complete rejected for reconciliation %s", recon.pk)
            return Response(
                {
                    "detail": "Cannot complete — every statement line must be matched and the "
                    "statement and GL balances must agree."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(self._workspace(recon))

    @action(detail=True, methods=["post"], url_path="reopen")
    def reopen(self, request, pk=None):
        recon = self.get_object()
        user = request.user
        if not (user.is_superuser or user.groups.filter(name__in=("manager", "admin")).exists()):
            return Response(
                {"detail": "Reopening a reconciliation requires a manager or admin role."},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            reconcile.reopen(recon, user=user)
        except (ValueError, ArithmeticError, TypeError):
            logger.warning("Reopen rejected for reconciliation %s", recon.pk)
            return Response(
                {"detail": "Only a completed reconciliation can be reopened."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(self._workspace(recon))

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
