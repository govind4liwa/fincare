"""Ledger API: accounting periods (entity-scoped, read-only) for report filters."""

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.accounts.views import scope_to_entities
from apps.ledger.models import AccountingPeriod
from apps.ledger.serializers import AccountingPeriodSerializer


class AccountingPeriodViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AccountingPeriodSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["entity", "fiscal_year", "status"]
    ordering_fields = ["start_date", "period_no"]
    ordering = ["-start_date"]

    def get_queryset(self):
        return scope_to_entities(AccountingPeriod.objects.all(), self.request.user)
