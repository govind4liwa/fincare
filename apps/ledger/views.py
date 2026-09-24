"""Ledger API: accounting periods — entity-scoped read for everyone, create,
and close/reopen/lock actions, all gated by role (apps.ledger.services.periods)."""

import logging

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.views import scope_to_entities
from apps.ledger.models import AccountingPeriod
from apps.ledger.serializers import AccountingPeriodSerializer
from apps.ledger.services import periods
from apps.users.permissions import HasAnyRole

logger = logging.getLogger(__name__)


class AccountingPeriodViewSet(viewsets.ModelViewSet):
    """Read is open to any authenticated member; create/close/reopen need an
    accounting role, lock needs manager/admin. No update/delete — every
    change to an existing period goes through a named transition action, and
    the core fields (dates, fiscal_year, period_no) are immutable once set."""

    serializer_class = AccountingPeriodSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]
    filterset_fields = ["entity", "fiscal_year", "status"]
    ordering_fields = ["start_date", "period_no"]
    ordering = ["-start_date"]

    def get_queryset(self):
        return scope_to_entities(AccountingPeriod.objects.all(), self.request.user)

    def get_permissions(self):
        if self.action == "lock":
            self.required_roles = ("manager", "admin")
            return [IsAuthenticated(), HasAnyRole()]
        if self.action in ("create", "close", "reopen"):
            self.required_roles = ("accountant", "manager", "admin")
            return [IsAuthenticated(), HasAnyRole()]
        return [IsAuthenticated()]

    def _transition(self, request, fn, error_detail):
        period = self.get_object()
        try:
            fn(period, user=request.user)
        except periods.PeriodError:
            logger.exception("Period transition rejected for %s", period.pk)
            return Response({"detail": error_detail}, status=400)
        return Response(self.get_serializer(period).data)

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        return self._transition(request, periods.close_period, "Only an open period can be closed.")

    @action(detail=True, methods=["post"])
    def reopen(self, request, pk=None):
        return self._transition(
            request, periods.reopen_period, "Only a closed period can be reopened."
        )

    @action(detail=True, methods=["post"])
    def lock(self, request, pk=None):
        return self._transition(request, periods.lock_period, "Period is already locked.")
