"""DRF serializers for ledger resources (accounting periods)."""

from rest_framework import serializers

from apps.ledger.models import AccountingPeriod


class AccountingPeriodSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccountingPeriod
        fields = [
            "id",
            "entity",
            "fiscal_year",
            "period_no",
            "name",
            "start_date",
            "end_date",
            "status",
        ]
